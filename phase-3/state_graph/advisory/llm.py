"""
llm.py
======
FIXED (see chat): graph.py already did `from . import data, llm` and called
llm.decompose_policy_into_requirements / llm.evaluate_requirement /
llm.generate_recommendation, but this module never existed anywhere in the
repo (checked every branch, including advisory_problem and fix_advisory_1) —
that's the ImportError that made the whole graph unimportable. This file
supplies exactly those three functions.

Uses the same GeminiClient wrapper `mcp_server/tools.py` already uses for
academic_integrity's and adaptive_assessment's LLM-call additions (agent/client.py),
kept local to this graph the same way data.py is, instead of adding
advisory-only prompts into the shared mcp_server/tools.py file.

Two LLM-call additions for this graph (per the Phase-3 README table):
  1. Task Decomposition -> decompose_policy_into_requirements()
     Breaks the RAG-retrieved policy text into a checklist of atomic,
     independently-checkable eligibility requirements.
  2. (evaluate_requirement / generate_recommendation are the plain LLM calls
     the decomposed checklist and final write-up need; RAG itself is done in
     data.py/graph.py's retrieve_policy node via rag/rag_tool.py.)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from client import GeminiClient, load_gemini_config  # noqa: E402

_gemini: GeminiClient | None = None


def _client() -> GeminiClient:
    # Lazy singleton (not created at import time): lets this module be
    # imported -- and the graph built -- even in environments/tests that
    # never actually call an LLM function, without requiring GEMINI_API_KEY
    # just to import graph.py.
    global _gemini
    if _gemini is None:
        _gemini = GeminiClient(load_gemini_config())
    return _gemini


def _parse_kv_lines(text: str) -> dict[str, str]:
    return {
        line.split(":", 1)[0].strip().upper(): line.split(":", 1)[1].strip()
        for line in text.splitlines()
        if ":" in line
    }


# ---------------------------------------------------------------------------
# 1) Task Decomposition -- decompose the retrieved policy text into a
#    checklist of atomic, independently-checkable requirements.
# ---------------------------------------------------------------------------

def decompose_policy_into_requirements(policy_text: str, request_type: str) -> list[str]:
    if not policy_text or not policy_text.strip():
        # No policy text retrieved (e.g. RAG turned up nothing) -- fall back
        # to a minimal generic checklist rather than crashing the graph.
        return [f"Student meets the general {request_type} eligibility criteria."]

    prompt = (
        f"You are decomposing a {request_type} eligibility policy into a "
        f"checklist an advisor can evaluate one item at a time.\n\n"
        f"Policy text:\n{policy_text}\n\n"
        f"Break this into the distinct, atomic requirements a student must "
        f"satisfy (e.g. minimum grade, attendance percentage, enrollment "
        f"status, no outstanding integrity cases, etc.) -- each requirement "
        f"should be checkable independently of the others. "
        f"Number them 1 to N, one requirement per line, as a short, "
        f"self-contained sentence."
    )
    text = _client().generate(prompt)
    requirements = [
        line.split(".", 1)[-1].strip()
        for line in text.splitlines()
        if line.strip() and line.strip()[0].isdigit()
    ]
    return requirements or [text.strip()]


# ---------------------------------------------------------------------------
# 2) Evaluate a single requirement against the student's profile (and, on a
#    loop back through evaluate_eligibility, their latest free-text reply).
# ---------------------------------------------------------------------------

def evaluate_requirement(
    requirement: str,
    student_profile: dict[str, Any],
    student_response: str | None = None,
) -> dict[str, Any]:
    profile_summary = (
        f"Student: {student_profile.get('student')}\n"
        f"Overall average: {student_profile.get('overall_average')}\n"
        f"Enrollments: {student_profile.get('enrollments')}\n"
        f"Grades: {student_profile.get('grades')}\n"
        f"Attendance: {student_profile.get('attendance')}"
    )
    prompt = (
        f"Requirement to check: {requirement}\n\n"
        f"Student profile (from the database):\n{profile_summary}\n\n"
        + (
            f"Additional information the student just supplied:\n{student_response}\n\n"
            if student_response
            else ""
        )
        + "Decide whether the profile (and any additional information above) "
        "shows this requirement is satisfied.\n"
        "Reply in exactly this format:\n"
        "SATISFIED: <yes|no|unknown>\n"
        "EVIDENCE: <what in the profile/response supports this, one sentence>\n"
        "NOTE: <if unknown, what specific information is missing; otherwise a short note>"
    )
    text = _client().generate(prompt)
    fields = _parse_kv_lines(text)
    satisfied_raw = fields.get("SATISFIED", "unknown").strip().lower()
    if satisfied_raw.startswith("y"):
        satisfied: bool | None = True
    elif satisfied_raw.startswith("n"):
        satisfied = False
    else:
        satisfied = None  # unknown -> feeds missing_info in evaluate_eligibility

    return {
        "satisfied": satisfied,
        "evidence": fields.get("EVIDENCE"),
        "note": fields.get("NOTE"),
    }


# ---------------------------------------------------------------------------
# 3) Final write-up handed to the student/admin once eligibility is decided.
# ---------------------------------------------------------------------------

def generate_recommendation(summary: dict[str, Any]) -> str:
    checks_text = "\n".join(
        f"- {c['requirement']}: "
        f"{'satisfied' if c['satisfied'] else 'NOT satisfied' if c['satisfied'] is False else 'unresolved'}"
        + (f" ({c['note']})" if c.get("note") else "")
        for c in summary.get("requirement_checks", [])
    )
    prompt = (
        f"Write a short, clear recommendation for a {summary.get('request_type')} "
        f"request.\n"
        f"Overall eligibility status: {summary.get('eligibility_status')}\n"
        f"Confidence: {summary.get('confidence')}\n"
        f"Requirement checks:\n{checks_text}\n\n"
        f"Write 2-4 sentences a student and an admin could both read: state "
        f"the outcome plainly, then briefly explain why, referencing any "
        f"requirement that was not satisfied."
    )
    return _client().generate(prompt).strip()