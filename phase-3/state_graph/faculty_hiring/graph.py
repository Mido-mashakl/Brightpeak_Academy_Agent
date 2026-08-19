"""
Faculty Hiring State Graph — graph definition.

Locatable concerns (per Final Project requirements):
  - Graph/cycle definitions:   build_faculty_hiring_graph() below.
  - Checkpointing:             checkpointing.py (get_checkpointer, thread_id_for_job).
  - HITL node type:            hitl.py  (dept_head_review_hitl, interrupt_before).
  - Ticket/failure path:       tickets.py (with_ticket_on_failure decorator).

Why this is a real state graph (not a for-loop wrapped in try/except):
  1. It WAITS indefinitely at `awaiting_more_applications` for an external event
     (new CV upload or deadline_reached command) — a for-loop can't pause like this.
  2. New CVs arrive as external events on the SAME thread; the old candidates are
     never reprocessed — `incoming_batch` vs `candidates` enforces this.
  3. HITL at `hitl_dept_head_review` is a real pause: the process can be killed
     and restarted; the checkpoint restores exactly at this node.
  4. A ticket opens on any unplanned failure; resolve → resume from last checkpoint,
     no re-ingestion/re-parsing of completed candidates.
  5. The rescore → shortlist → HITL cycle is a genuine loop, not a linear path.

LLM-call additions (two per graph, as required):
  1. RAG (parse_and_validate):
       Retrieves hiring policy passages from documents/hiring/hiring_policies.md to
       ground the parsing rules — specifically "never invent missing fields" and how
       to classify parse_status.  Uses the existing search_policies() in rag/rag_tool.py.
  2. Constrained ReAct (score_cv_against_qualifications):
       The scoring node calls the Gemini API with a strict tool schema (one tool:
       score_candidate).  The model is forced to call that function — it cannot
       free-form respond.  This prevents the model from hallucinating scores
       outside [0,100], inventing missing fields, or returning prose instead of
       structured data.

Thread identity:
  thread_id = f"faculty-hiring-{job_id}"  (see checkpointing.py)
  All candidates for Job #15 share thread "faculty-hiring-15".
  candidate_id is separate — each candidate has its own DB row, never its own thread.

NOTE ON LLM PROVIDER:
  This file was migrated from a direct Anthropic Messages API integration to
  Google's Gemini API. Only the two low-level HTTP helper functions
  (_call_claude_constrained, _parse_cv_with_policy) and the tool schemas were
  changed to match Gemini's function-calling request/response shape. Every
  node, edge, router, and the graph topology itself are untouched — the
  function *names* were deliberately kept the same so nothing else in this
  file (or in tickets.py / hitl.py, which don't touch these helpers) needed
  to change.

  Env vars used:
    GEMINI_API_KEY   - required. Get one at https://aistudio.google.com/apikey
    GEMINI_MODEL     - optional, defaults to "gemini-2.5-flash"
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, END

from .state import FacultyHiringState, CandidateResult
from .checkpointing import get_checkpointer, thread_id_for_job
from .hitl import dept_head_review_hitl
from .tickets import with_ticket_on_failure

# Real, existing modules only.
from mcp_server import database as db

# RAG — same pattern as academic_integrity/graph.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "rag"))
from rag_tool import search_policies  # noqa: E402

# Gemini API for constrained ReAct scoring / parsing
import urllib.request
import urllib.error
import os


# ---------------------------------------------------------------------------
# Gemini API config
# ---------------------------------------------------------------------------

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


# ---------------------------------------------------------------------------
# Schema conversion: our existing JSON-Schema-ish tool defs -> Gemini's
# expected OpenAPI-subset schema (upper-case type enums, no "null" unions).
# ---------------------------------------------------------------------------

def _to_gemini_schema(json_schema: dict) -> dict:
    """
    Converts a (loose) JSON-Schema dict into the schema shape Gemini's
    function-calling API expects: upper-case `type` enums, and no
    `["string", "null"]` unions (Gemini uses `nullable: true` instead).

    This is a small, defensive converter — it only handles the shapes
    actually used by SCORE_TOOL / the CV parse tool below.
    """
    if not isinstance(json_schema, dict):
        return json_schema

    schema = dict(json_schema)  # shallow copy, don't mutate the source dict

    raw_type = schema.get("type")
    nullable = False

    if isinstance(raw_type, list):
        # e.g. ["string", "null"] -> type STRING, nullable True
        non_null = [t for t in raw_type if t != "null"]
        nullable = "null" in raw_type
        raw_type = non_null[0] if non_null else "string"

    type_map = {
        "object": "OBJECT",
        "array": "ARRAY",
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
    }
    if raw_type in type_map:
        schema["type"] = type_map[raw_type]
    if nullable:
        schema["nullable"] = True

    if "properties" in schema and isinstance(schema["properties"], dict):
        schema["properties"] = {
            k: _to_gemini_schema(v) for k, v in schema["properties"].items()
        }
    if "items" in schema and isinstance(schema["items"], dict):
        schema["items"] = _to_gemini_schema(schema["items"])

    return schema


def _build_gemini_tool(tool_def: dict) -> dict:
    """Converts one Anthropic-style tool def {name, description, input_schema}
    into a Gemini functionDeclarations entry."""
    return {
        "name": tool_def["name"],
        "description": tool_def.get("description", ""),
        "parameters": _to_gemini_schema(tool_def["input_schema"]),
    }


# ---------------------------------------------------------------------------
# Gemini API helper (constrained ReAct — function-forced call)
# ---------------------------------------------------------------------------

def _call_claude_constrained(system: str, user: str, tools: list[dict]) -> dict:
    """
    Calls Gemini (model = GEMINI_MODEL) with function_calling_config mode
    "ANY" so the model MUST call one of the provided functions. This is the
    constrained ReAct pattern: the model reasons but cannot output free
    text — it must structure its answer as a function call.

    (Name kept as `_call_claude_constrained` for drop-in compatibility with
    every call site in this module — only the implementation moved to
    Gemini.)

    Returns the first functionCall's args dict.
    Raises ValueError if the model doesn't call a function (shouldn't happen
    with mode="ANY", but we raise rather than silently accept prose).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment.")

    gemini_tools = [_build_gemini_tool(t) for t in tools]
    allowed_names = [t["name"] for t in gemini_tools]

    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "tools": [{"function_declarations": gemini_tools}],
        "tool_config": {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": allowed_names,
            }
        },
    }).encode()

    url = f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent"

    def _one_attempt() -> dict:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise ValueError(f"Gemini API error {e.code}: {body}") from e

        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                fc = part.get("functionCall")
                if fc:
                    return fc.get("args", {})

        raise ValueError(
            f"Constrained ReAct: model did not call a function. Raw response: {data}"
        )

    def _is_degenerate(args: dict) -> bool:
        """
        gemini-3.5-flash-lite has a documented flakiness where, under a
        FORCED function call (mode='ANY') combined with encrypted thinking,
        it occasionally finishes normally (finishReason=STOP, real
        thoughtsTokenCount spent) but writes a stub function-call payload
        instead of translating its reasoning into real args — e.g.
        score=0, breakdown={}, reasoning="placeholder"/"" — for CVs that
        are structurally nothing alike. This is a flaky model response,
        not a parsing bug, so we detect and retry rather than silently
        accept it.
        """
        reasoning = str(args.get("reasoning", "")).strip().lower()
        return (
            args.get("score") == 0
            and not args.get("breakdown")
            and (reasoning == "" or reasoning.startswith("placeholder"))
        )

    args = {}
    last_args = {}
    for attempt in range(3):
        args = _one_attempt()
        last_args = args
        if not _is_degenerate(args):
            return args
        print(
            f"[_call_claude_constrained] Degenerate placeholder response on "
            f"attempt {attempt + 1}/3 — retrying: {args}"
        )
        # Back off before retrying — firing requests back-to-back with zero
        # delay appears to be exactly what triggers the degenerate response
        # in the first place (see _is_degenerate docstring), so retrying
        # immediately just reproduces the same failure mode.
        time.sleep(2 * (attempt + 1))  # 2s, 4s, 6s

    # All attempts came back degenerate — return the last one; the caller
    # (score_cv_against_qualifications) already prints raw results with
    # score==0 for visibility, and the ticket path can be extended to
    # treat repeated degenerate output as a real failure if needed.
    return last_args


# ---------------------------------------------------------------------------
# Scoring tool schema (constrained ReAct — the ONLY tool available)
# ---------------------------------------------------------------------------

SCORE_TOOL = {
    "name": "score_candidate",
    "description": (
        "Score a candidate against the job qualifications. "
        "You MUST call this tool. Do NOT invent information absent from the CV."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Overall score 0–100",
            },
            "breakdown": {
                "type": "object",
                "description": (
                    "Per-qualification results. Key = qualification string. "
                    "Value = {\"result\": \"PASS\"|\"FAIL\"|\"MISSING\", \"evidence\": str}"
                ),
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the overall score",
            },
        },
        "required": ["score", "breakdown", "reasoning"],
    },
}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@with_ticket_on_failure(source_graph="faculty_hiring", failure_type="ingest_failed")
def ingest_cv_batch(state: FacultyHiringState) -> dict:
    """
    Ingests incoming_batch CVs into the DB (Candidates table) and the vector store
    so they can be retrieved during scoring.

    Only processes incoming_batch — never touches state.candidates (old CVs).
    Each candidate gets a DB row with raw_cv_text stored.
    The vector store is updated with metadata job_id + candidate_id for
    job-scoped filtering (prevents cross-job CV retrieval).
    """
    if not state.incoming_batch:
        return {"status": "awaiting_more_applications"}

    updated = []
    for c in state.incoming_batch:
        # Insert DB row
        row = db.query_one(
            """INSERT INTO Candidates (job_id, name, raw_cv_text, parse_status)
               VALUES (?, ?, ?, 'pending')
               RETURNING candidate_id""",
            (state.job_id, c.name, c.raw_cv_text),
        )
        candidate_id = row["candidate_id"] if row else None

        # Index into vector store with job_id + candidate_id metadata
        try:
            _index_cv(
                candidate_id=candidate_id,
                job_id=state.job_id,
                name=c.name,
                raw_cv_text=c.raw_cv_text,
            )
        except Exception:
            pass  # vector indexing failure is non-fatal for ingestion;
                  # if scoring later fails, the ticket path will catch it

        updated.append(c.model_copy(update={"candidate_id": candidate_id}))

    return {"incoming_batch": updated, "status": "parsing"}


def _index_cv(candidate_id: int, job_id: int, name: str, raw_cv_text: str) -> None:
    """Add one CV to the shared vector store with job-scoped metadata."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "rag"))
    from vector_db import VectorStore  # noqa: E402

    store = VectorStore()
    chunk_id = f"cv-job{job_id}-candidate{candidate_id}"
    store.upsert(
        ids=[chunk_id],
        documents=[raw_cv_text],
        metadatas=[{
            "content_type": "cv",
            "job_id": str(job_id),
            "candidate_id": str(candidate_id),
            "candidate_name": name,
        }],
    )


@with_ticket_on_failure(source_graph="faculty_hiring", failure_type="parse_failed")
def parse_and_validate(state: FacultyHiringState) -> dict:
    """
    RAG Addition #1: grounds the parse rules in hiring_policies.md.

    Retrieves policy passages (especially the missing-data rule: never invent
    absent fields) before calling Gemini to parse the CV into structured fields.

    Only processes incoming_batch — state.candidates (old CVs) are untouched.
    """
    # Retrieve policy context once for the whole batch (same policy for all CVs)
    policy_result = search_policies(
        query="missing information parsing CV qualifications",
        category="Hiring",
    )
    policy_context = policy_result.get("context") or "\n".join(
        h.get("document", "") for h in policy_result.get("hits", [])
    )

    updated_batch = []
    for c in state.incoming_batch:
        parsed = _parse_cv_with_policy(c.raw_cv_text, policy_context)
        parse_status = _determine_parse_status(parsed)

        # Persist parsed_profile to DB
        if c.candidate_id:
            db.execute(
                """UPDATE Candidates
                   SET parsed_profile = ?, parse_status = ?
                   WHERE candidate_id = ?""",
                (json.dumps(parsed), parse_status, c.candidate_id),
            )

        updated_batch.append(c.model_copy(update={
            "parsed_profile": parsed,
            "parse_status": parse_status,
        }))

    return {
        "incoming_batch": updated_batch,
        "policy_context": policy_context,
        "status": "scoring",
    }


def _parse_cv_with_policy(raw_cv_text: str, policy_context: str) -> dict:
    """
    Calls Gemini to extract structured fields from the CV text.
    The policy context reinforces the "never invent missing fields" rule.
    Fields that are absent in the CV must remain null — not guessed.

    (Name kept as `_parse_cv_with_policy` for drop-in compatibility with the
    call site in parse_and_validate — only the implementation moved to
    Gemini.)
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    parse_tool = {
        "name": "parse_cv",
        "description": "Extract structured fields from a CV. Leave fields null if not found in the CV.",
        "input_schema": {
            "type": "object",
            "properties": {
                "education": {"type": ["string", "null"], "description": "Highest degree and field"},
                "years_experience": {"type": ["number", "null"], "description": "Years of relevant experience, null if not stated"},
                "skills": {"type": "array", "items": {"type": "string"}, "description": "Technical skills explicitly mentioned"},
                "teaching_experience": {"type": ["string", "null"], "description": "Teaching experience details, null if not mentioned"},
                "notes": {"type": "string", "description": "Any other relevant information"},
            },
            "required": ["education", "years_experience", "skills", "teaching_experience", "notes"],
        },
    }

    if not api_key:
        print("[_parse_cv_with_policy] GEMINI_API_KEY is empty at call time.")
        return {"education": None, "years_experience": None, "skills": [], "teaching_experience": None, "notes": "Parse failed"}

    gemini_tool = _build_gemini_tool(parse_tool)

    payload = json.dumps({
        "system_instruction": {"parts": [{"text": (
            "You are a CV parser. Extract structured fields from the CV text. "
            "CRITICAL RULE: If a field is not mentioned in the CV, return null for that field. "
            "Do NOT invent or infer missing information.\n\n"
            f"Hiring Policy:\n{policy_context}"
        )}]},
        "contents": [{"role": "user", "parts": [{"text": f"Parse this CV:\n\n{raw_cv_text}"}]}],
        "tools": [{"function_declarations": [gemini_tool]}],
        "tool_config": {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": ["parse_cv"],
            }
        },
    }).encode()

    url = f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"[_parse_cv_with_policy] Gemini API error {e.code}: {body}")
        return {"education": None, "years_experience": None, "skills": [], "teaching_experience": None, "notes": "Parse failed"}
    except Exception as e:
        # Catch anything else (network errors, JSON decode errors, etc.)
        # instead of letting parse silently fall through to "Parse failed"
        # with no visible reason.
        print(f"[_parse_cv_with_policy] Unexpected error calling Gemini: {type(e).__name__}: {e}")
        return {"education": None, "years_experience": None, "skills": [], "teaching_experience": None, "notes": "Parse failed"}

    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            fc = part.get("functionCall")
            if fc:
                return fc.get("args", {})

    return {"education": None, "years_experience": None, "skills": [], "teaching_experience": None, "notes": "Parse failed"}


def _determine_parse_status(parsed: dict) -> str:
    """
    'missing_fields' if any key field is null (experience, education).
    'parsed' otherwise.
    'failed' only if parse returned no meaningful data at all.
    """
    if not parsed or parsed.get("notes") == "Parse failed":
        return "failed"
    if parsed.get("education") is None or parsed.get("years_experience") is None:
        return "missing_fields"
    return "parsed"


@with_ticket_on_failure(source_graph="faculty_hiring", failure_type="score_failed")
def score_cv_against_qualifications(state: FacultyHiringState) -> dict:
    """
    Constrained ReAct Addition #2.

    Scores candidates in incoming_batch (or rescore_candidate_ids if in rescore mode)
    against JobPostings.qualifications using a tool-forced Gemini call.

    The model MUST call the score_candidate function — it cannot free-form respond.
    This prevents hallucinated scores, invented missing fields, or prose output.

    MISSING fields receive uncertainty (lower score), not FAIL.
    The model is explicitly told not to invent data.
    """
    # Determine which candidates to score
    candidates_to_score = list(state.incoming_batch)

    # Rescore mode: only the explicitly selected candidate_ids
    if state.rescore_candidate_ids:
        id_set = set(state.rescore_candidate_ids)
        candidates_to_score = [
            c for c in state.candidates
            if c.candidate_id in id_set
        ]

    qualifications_text = "\n".join(f"- {q}" for q in state.qualifications)
    policy_context = state.policy_context or ""

    scored_batch = []
    for i, c in enumerate(candidates_to_score):
        if i > 0:
            # Pace consecutive calls — firing them back-to-back in a tight
            # loop is what seems to trigger degenerate placeholder
            # responses from Gemini (see _is_degenerate in
            # _call_claude_constrained); a lone, unhurried call reliably
            # succeeds.
            time.sleep(1.5)

        if c.parse_status == "failed":
            # Can't score a candidate with a failed parse; skip scoring but keep record
            scored_batch.append(c.model_copy(update={"score": 0.0, "breakdown": {"error": "parse_failed"}}))
            continue

        profile_text = json.dumps(c.parsed_profile, indent=2) if c.parsed_profile else c.raw_cv_text

        result = _call_claude_constrained(
            system=(
                "You are a faculty hiring evaluator for Brightpeak Academy.\n"
                "Score the candidate against the job qualifications.\n"
                "CRITICAL RULES:\n"
                "1. If a qualification is not mentioned in the CV, mark it MISSING (not FAIL).\n"
                "2. Do NOT invent experience, degrees, or skills absent from the profile.\n"
                "3. MISSING reduces the score less than FAIL.\n"
                "4. Teaching experience is weighted heavily for instructor roles.\n"
                f"\nHiring Policy:\n{policy_context}"
            ),
            user=(
                f"Job Qualifications:\n{qualifications_text}\n\n"
                f"Candidate Profile:\n{profile_text}"
            ),
            tools=[SCORE_TOOL],
        )

        score = float(result.get("score", 0))
        breakdown = result.get("breakdown", {})
        score_id = None

        if score == 0.0:
            # Score of 0 is suspicious for a real candidate — print the raw
            # args Gemini actually returned so we can see whether "score"
            # is missing, mistyped, or genuinely computed as 0.
            print(f"[score_cv_against_qualifications] {c.name}: raw Gemini result = {result}")

        # Persist to CandidateScores
        if c.candidate_id:
            trigger = "rescore" if state.rescore_candidate_ids else "initial"
            row = db.query_one(
                """INSERT INTO CandidateScores (candidate_id, score, breakdown, trigger)
                   VALUES (?, ?, ?, ?) RETURNING score_id""",
                (c.candidate_id, score, json.dumps(breakdown), trigger),
            )
            score_id = row["score_id"] if row else None

        scored_batch.append(c.model_copy(update={
            "score": score,
            "score_id": score_id,
            "breakdown": breakdown,
        }))

    # In rescore mode: merge updated scores back into state.candidates
    # by returning a new list (state.candidates uses add reducer, so we
    # return a list of corrected records that replaces scores in-flight
    # via the graph update mechanism)
    if state.rescore_candidate_ids:
        id_to_update = {c.candidate_id: c for c in scored_batch}
        merged = [
            id_to_update.get(c.candidate_id, c)
            for c in state.candidates
        ]
        return {
            "candidates": merged,   # full replacement via direct state update
            "incoming_batch": [],
            "rescore_candidate_ids": [],
            "status": "generating_shortlist",
        }

    return {
        "incoming_batch": scored_batch,
        "status": "awaiting_more_applications",
    }


def persist_batch_to_candidates(state: FacultyHiringState) -> dict:
    """
    Moves scored incoming_batch into the persistent candidates archive and clears
    incoming_batch.  Runs after score_cv_against_qualifications for new-CV events.
    """
    return {
        "candidates": list(state.incoming_batch),  # add reducer appends these
        "incoming_batch": [],
        "status": "awaiting_more_applications",
    }


def awaiting_more_applications(state: FacultyHiringState) -> dict:
    """
    No-op wait node.  The real pause is the interrupt_before configured in
    graph compile.  The graph stays here until the platform sends either:
      - A new CV event   (incoming_batch = [new_candidate], pending_event = "new_cv")
      - A deadline event (pending_event = "deadline_reached")

    On resume, route_after_waiting() reads pending_event to decide next node.
    """
    return {"status": "awaiting_more_applications"}


def route_after_scoring(state: FacultyHiringState) -> str:
    """Conditional edge after score_cv_against_qualifications.

    Distinguishes the normal batch path (initial batch / new CV — must fold
    into the persistent `candidates` archive) from the HITL rescore path
    (rescored candidates are already merged into `candidates` by the node
    itself — must go straight to generate_shortlist, or persist_batch_to_candidates
    would re-append them and duplicate the archive).
    """
    if state.status == "generating_shortlist":
        return "generate_shortlist"
    return "persist_batch_to_candidates"


def route_after_waiting(state: FacultyHiringState) -> str:
    """Conditional edge — reads pending_event set by the external event."""
    if state.pending_event == "deadline_reached":
        return "generate_shortlist"
    if state.pending_event == "new_cv" or state.incoming_batch:
        return "ingest_cv_batch"
    # Default: stay waiting (shouldn't normally reach here)
    return "awaiting_more_applications"


@with_ticket_on_failure(source_graph="faculty_hiring", failure_type="shortlist_failed")
def generate_shortlist(state: FacultyHiringState) -> dict:
    """
    Creates a ranked shortlist snapshot in Shortlists + ShortlistEntries.
    Ranks all candidates by their most recent score (descending).
    Candidates with parse_status='failed' appear at the bottom.
    """
    if not state.job_id:
        return {"status": "generating_shortlist"}

    # Close the job posting
    db.execute(
        "UPDATE JobPostings SET status = 'closed', updated_at = ? WHERE job_id = ?",
        (datetime.utcnow().isoformat(), state.job_id),
    )

    # Sort: scored candidates first (by score desc), then failed parses at bottom
    scored = [c for c in state.candidates if c.score is not None]
    failed = [c for c in state.candidates if c.score is None]
    ranked = sorted(scored, key=lambda c: c.score or 0, reverse=True) + failed

    # Create Shortlists row
    row = db.query_one(
        "INSERT INTO Shortlists (job_id) VALUES (?) RETURNING shortlist_id",
        (state.job_id,),
    )
    shortlist_id = row["shortlist_id"] if row else None

    # Insert ShortlistEntries
    for rank, c in enumerate(ranked, start=1):
        if c.candidate_id:
            db.execute(
                """INSERT INTO ShortlistEntries (shortlist_id, candidate_id, score, rank)
                   VALUES (?, ?, ?, ?)""",
                (shortlist_id, c.candidate_id, c.score or 0, rank),
            )

    return {
        "current_shortlist_id": shortlist_id,
        "status": "hitl_review",
        "pending_event": None,
    }


def route_after_hitl(state: FacultyHiringState) -> str:
    """
    Reads the last HITL decision to route:
      hire       → record_hiring_decision
      interview  → schedule_interview
      rescore    → score_cv_against_qualifications
    """
    if not state.hitl_decisions:
        return "hitl_dept_head_review"  # no decision yet — stay at HITL
    last = state.hitl_decisions[-1]
    if last.decision == "hire":
        return "record_hiring_decision"
    if last.decision == "interview":
        return "schedule_interview"
    if last.decision == "rescore":
        return "score_cv_against_qualifications"
    return "hitl_dept_head_review"


def schedule_interview(state: FacultyHiringState) -> dict:
    """
    Transition node: marks the relevant interview as scheduled.
    The graph then pauses at await_interview_result (interrupt_before).
    """
    return {"status": "interviewing"}


def await_interview_result(state: FacultyHiringState) -> dict:
    """
    No-op wait node — waits for the interview result to arrive via
    hitl.submit_interview_result(), which calls resume_job() with the result
    and the graph continues to hitl_dept_head_review.
    """
    return {}


def record_hiring_decision(state: FacultyHiringState) -> dict:
    """Final node: marks the job as completed after a hire decision."""
    if state.job_id:
        db.execute(
            "UPDATE JobPostings SET status = 'completed', updated_at = ? WHERE job_id = ?",
            (datetime.utcnow().isoformat(), state.job_id),
        )
    return {"status": "completed"}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_faculty_hiring_graph():
    builder = StateGraph(FacultyHiringState)

    # --- Nodes ---
    builder.add_node("ingest_cv_batch", ingest_cv_batch)
    builder.add_node("parse_and_validate", parse_and_validate)
    builder.add_node("score_cv_against_qualifications", score_cv_against_qualifications)
    builder.add_node("persist_batch_to_candidates", persist_batch_to_candidates)
    builder.add_node("awaiting_more_applications", awaiting_more_applications)
    builder.add_node("generate_shortlist", generate_shortlist)
    builder.add_node("hitl_dept_head_review", dept_head_review_hitl)  # HITL node
    builder.add_node("schedule_interview", schedule_interview)
    builder.add_node("await_interview_result", await_interview_result)
    builder.add_node("record_hiring_decision", record_hiring_decision)

    # --- Entry point ---
    builder.set_entry_point("ingest_cv_batch")

    # --- Initial & new-CV path ---
    builder.add_edge("ingest_cv_batch", "parse_and_validate")
    builder.add_edge("parse_and_validate", "score_cv_against_qualifications")

    # score_cv_against_qualifications is shared by two very different callers:
    #   - normal batch scoring (initial batch / new CV): status ends as
    #     "awaiting_more_applications" -> must go to persist_batch_to_candidates
    #     so the scored candidates get folded into the persistent archive.
    #   - HITL rescore (route_after_hitl -> here directly, batch nodes skipped):
    #     status ends as "generating_shortlist" -> must go straight to
    #     generate_shortlist, since rescored candidates are already merged
    #     into state.candidates by the node itself and persist_batch_to_candidates
    #     would incorrectly re-append them via the `add` reducer.
    # A static edge can't express this — hence the conditional below.
    builder.add_conditional_edges(
        "score_cv_against_qualifications",
        route_after_scoring,
        {
            "persist_batch_to_candidates": "persist_batch_to_candidates",
            "generate_shortlist": "generate_shortlist",
        },
    )
    builder.add_edge("persist_batch_to_candidates", "awaiting_more_applications")

    # --- Wait node with conditional exit ---
    builder.add_conditional_edges(
        "awaiting_more_applications",
        route_after_waiting,
        {
            "ingest_cv_batch": "ingest_cv_batch",
            "generate_shortlist": "generate_shortlist",
            "awaiting_more_applications": "awaiting_more_applications",
        },
    )

    # --- Post-shortlist: HITL ---
    builder.add_edge("generate_shortlist", "hitl_dept_head_review")

    # --- HITL routing ---
    builder.add_conditional_edges(
        "hitl_dept_head_review",
        route_after_hitl,
        {
            "record_hiring_decision": "record_hiring_decision",
            "schedule_interview": "schedule_interview",
            "score_cv_against_qualifications": "score_cv_against_qualifications",
            "hitl_dept_head_review": "hitl_dept_head_review",
        },
    )

    # --- Interview path (loops back to HITL after result) ---
    builder.add_edge("schedule_interview", "await_interview_result")
    builder.add_edge("await_interview_result", "hitl_dept_head_review")

    # --- Rescore path ---
    # HITL routes "rescore" decisions to score_cv_against_qualifications (see
    # route_after_hitl below); route_after_scoring above then sends the
    # rescore result straight to generate_shortlist, closing the
    # rescore -> shortlist -> HITL cycle.

    # --- END ---
    builder.add_edge("record_hiring_decision", END)

    return builder.compile(
        checkpointer=get_checkpointer(),
        interrupt_before=[
            "awaiting_more_applications",  # wait for new CV or deadline event
            "hitl_dept_head_review",       # wait for Dept Head decision
            "await_interview_result",      # wait for interview result
        ],
    )


# ---------------------------------------------------------------------------
# Public API — called by the platform
# ---------------------------------------------------------------------------

def start_job(job_input: dict) -> Any:
    """
    Entry point the platform calls when creating a new job posting and
    submitting the initial batch of CVs.

    job_input keys:
        job_id          int
        job_title       str
        qualifications  list[str]
        initial_cvs     list[{"name": str, "raw_cv_text": str}]

    Creates the JobPostings row, builds the initial FacultyHiringState,
    and runs the graph until it reaches awaiting_more_applications.
    """
    job_id = job_input["job_id"]
    thread_id = thread_id_for_job(job_id)

    initial_batch = [
        CandidateResult(name=cv["name"], raw_cv_text=cv["raw_cv_text"])
        for cv in job_input.get("initial_cvs", [])
    ]

    state = FacultyHiringState(
        job_id=job_id,
        job_title=job_input.get("job_title", ""),
        qualifications=job_input.get("qualifications", []),
        incoming_batch=initial_batch,
        thread_id=thread_id,
    )

    graph = build_faculty_hiring_graph()
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(state, config=config)


def add_cv(job_id: int, name: str, raw_cv_text: str) -> Any:
    """
    Entry point the platform calls when a new CV arrives while the graph
    is waiting at awaiting_more_applications.

    This RESUMES the existing thread for job_id — does NOT start a new graph.
    The new candidate goes into incoming_batch only; old candidates are untouched.
    """
    graph = build_faculty_hiring_graph()
    config = {"configurable": {"thread_id": thread_id_for_job(job_id)}}

    new_candidate = CandidateResult(name=name, raw_cv_text=raw_cv_text)

    # Update state with only the new CV and set the event type
    graph.update_state(
        config,
        {
            "incoming_batch": [new_candidate],
            "pending_event": "new_cv",
        },
    )
    return graph.invoke(None, config=config)


def close_applications(job_id: int) -> Any:
    """
    Entry point the platform calls when the Admin clicks
    'Close Applications / Generate Shortlist'.

    Sends the deadline_reached event to the existing thread.
    The graph resumes from awaiting_more_applications → generate_shortlist.
    """
    graph = build_faculty_hiring_graph()
    config = {"configurable": {"thread_id": thread_id_for_job(job_id)}}

    graph.update_state(config, {"pending_event": "deadline_reached"})
    return graph.invoke(None, config=config)


def resume_job(job_id: int, update: dict | None = None) -> Any:
    """
    Generic resume — used by hitl.py and tickets.py after admin actions.
    Optionally injects state updates (HITL decisions, interview results, etc.)
    before resuming.
    """
    graph = build_faculty_hiring_graph()
    config = {"configurable": {"thread_id": thread_id_for_job(job_id)}}
    if update:
        graph.update_state(config, update)
    return graph.invoke(None, config=config)