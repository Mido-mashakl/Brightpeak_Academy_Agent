"""
Academic Integrity Investigation & Appeal — graph definition.

Locatable concerns (per Final Project requirements):
- Graph/cycle definitions: build_academic_integrity_graph() below.
- Checkpointing: checkpointing.py (get_checkpointer, thread_id helper).
- HITL node type: hitl.py (used by needs_committee_review, committee_final_decision).
- Ticket/failure path: tickets.py (used by the error-handling wrapper below).

This graph is NOT a straight line: needs_committee_review and
committee_final_decision are real interrupt points (see hitl.py), and
await_appeal can pause for days waiting on the student. A crash between any
two nodes resumes from the last checkpoint via the same thread_id
(f"academic-integrity-{case_id}"), not from the top.

FIXED (see chat): this version replaces four calls to functions that never
existed in mcp_server/tools.py or rag/rag_tool.py:
  1. rag.rag_tool.query_academic_integrity_policy -> real function is
     search_policies(), which returns a dict; we now pull the string
     context out of it (result["context"]) before handing it to
     classify_severity_with_policy().
  2. mcp_tools.get_similarity_report -> there is no such tool, and there's
     nowhere in the schema for it to compute a similarity score from
     (Assignments/Grades don't store submission text). IntegrityCases
     already HAS a similarity_score column, which means the instructor is
     expected to supply it when they report the case (through the
     platform). gather_evidence now reads it straight from state instead
     of calling a tool that doesn't exist.
  3. mcp_tools.send_notification -> no such tool exists. Removed; the
     platform's user surface is expected to read IntegrityCases.status to
     show the student what's happening, same pattern hitl.py already uses
     for admin-side visibility.
  4. mcp_tools.write_case_closure -> no such tool exists. Replaced with a
     direct db.execute() UPDATE, matching the pattern hitl.py already uses
     for status writes.
"""

from __future__ import annotations

from datetime import datetime

from langgraph.graph import StateGraph, END

from .state import AcademicIntegrityState, EvidenceItem, DecisionRecord
from .checkpointing import get_checkpointer, thread_id_for_case
from .tickets import with_ticket_on_failure
from .hitl import committee_review_hitl, final_decision_hitl, _open_hitl_task

import sys as _sys
from pathlib import Path as _Path
MCP_SERVER_DIR = _Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(MCP_SERVER_DIR) not in _sys.path:
    _sys.path.insert(0, str(MCP_SERVER_DIR))

PHASE3_DIR = _Path(__file__).resolve().parent.parent.parent
if str(PHASE3_DIR) not in _sys.path:
    _sys.path.insert(0, str(PHASE3_DIR))


# Real, existing modules only.
import database as db
import tools as mcp_tools
from rag.rag_tool import search_policies


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@with_ticket_on_failure(source_graph="academic_integrity", failure_type="evidence_gather_failed")
def gather_evidence(state: AcademicIntegrityState) -> dict:
    """Turns the report the instructor already filed (similarity_score +
    description, supplied via the platform when the case was opened) into
    IntegrityEvidence rows. No MCP tool call needed here — there is no
    similarity-checking tool in mcp_server, and the schema already expects
    similarity_score to arrive with the case, not be computed by the agent.
    """
    new_evidence = [
        EvidenceItem(evidence_type="similarity_report", content=str(state.similarity_score)),
        EvidenceItem(evidence_type="instructor_note", content=state.description),
    ]
    for item in new_evidence:
        db.execute(
            "INSERT INTO IntegrityEvidence (case_id, evidence_type, content) VALUES (?, ?, ?)",
            (state.case_id, item.evidence_type, item.content),
        )
    return {
        "evidence": new_evidence,
        "status": "under_review",
    }


@with_ticket_on_failure(source_graph="academic_integrity", failure_type="rag_severity_failed")
def analyze_severity(state: AcademicIntegrityState) -> dict:
    """RAG addition #1: grounds the severity call in documents/academic_integrity.md
    via the real search_policies() retrieval + Self-RAG verification pipeline."""
    result = search_policies(
        query=f"similarity_score={state.similarity_score}; {state.description}",
        category="Academic Integrity",
    )
    policy_context = result.get("context") or "\n".join(
        h.get("document", "") for h in result.get("hits", [])
    )
    severity, rationale = mcp_tools.classify_severity_with_policy(
        similarity_score=state.similarity_score,
        description=state.description,
        policy_context=policy_context,
    )
    # BUG FIX (found via real end-to-end testing, phase-4/backend/e2e_test_integrity.py):
    # `severity` was only ever kept in the LangGraph checkpoint state and
    # returned here — nothing wrote it back to IntegrityCases.severity.
    # Every other node in this graph that changes something the platform's
    # DB-facing API reads (gather_evidence's status, minor_warning's status,
    # notify_student's status, log_and_close's status) persists via
    # db.execute() the same way; severity was the one exception, which meant
    # IntegrityCases.severity stayed NULL forever and every case showed up
    # as "pending" in the instructor UI (integrity.js, hitl.js, case-details.js,
    # hitl-review.js) no matter what the AI actually classified.
    db.execute(
        "UPDATE IntegrityCases SET severity = ?, updated_at = ? WHERE case_id = ?",
        (severity, datetime.utcnow().isoformat(), state.case_id),
    )
    if severity != "minor":
        _open_hitl_task(state.case_id, "committee_review", {"status": "under_review"})
    return {"severity": severity, "severity_rationale": rationale}


def route_after_committee_review(state: AcademicIntegrityState) -> str:
    """Real cycle: reads the admin's committee_review decision. 'dismiss'
    closes the case immediately, 'request_more_evidence' loops back to
    gather_evidence instead of forcing every case through the appeal flow."""
    last = state.decisions[-1] if state.decisions else None
    if last is None:
        return "notify_student"
    if last.decision == "dismiss":
        return "log_and_close"
    if last.decision == "request_more_evidence":
        return "gather_evidence"
    return "notify_student"

def route_by_severity(state: AcademicIntegrityState) -> str:
    """Pure routing function — reads state, returns next node name, no side effects."""
    return "minor_warning" if state.severity == "minor" else "needs_committee_review"


def minor_warning(state: AcademicIntegrityState) -> dict:
    db.execute(
        "UPDATE IntegrityCases SET status = 'closed', updated_at = ? WHERE case_id = ?",
        (datetime.utcnow().isoformat(), state.case_id),
    )
    return {"status": "closed"}


def notify_student(state: AcademicIntegrityState) -> dict:
    """No separate notification tool exists (and none is needed): the
    platform's user surface reads IntegrityCases.status to show the student
    where their case stands, same as the admin side already does."""
    db.execute(
        "UPDATE IntegrityCases SET status = 'awaiting_appeal', updated_at = ? WHERE case_id = ?",
        (datetime.utcnow().isoformat(), state.case_id),
    )
    return {"status": "awaiting_appeal"}


def await_appeal(state: AcademicIntegrityState) -> dict:
    """Runs once, on resume: the platform calls update_state() with the
    student's appeal_argument before invoking past the interrupt, so by the
    time this node actually executes it has the real argument to persist
    into IntegrityAppeals (the interrupt only delayed execution, it didn't
    skip it)."""
    db.execute(
        "INSERT INTO IntegrityAppeals (case_id, student_argument) VALUES (?, ?)",
        (state.case_id, state.appeal_argument),
    )
    return {}


@with_ticket_on_failure(source_graph="academic_integrity", failure_type="tot_appeal_eval_failed")
def evaluate_appeal(state: AcademicIntegrityState) -> dict:
    """Tree of Thoughts addition #2: generates candidate rulings, scores each
    against the policy + evidence, keeps the best-supported one."""
    candidates = mcp_tools.generate_appeal_rulings(
        argument=state.appeal_argument,
        evidence=[e.content for e in state.evidence],
        n=3,
    )
    scored = [
        (c, mcp_tools.score_ruling_against_policy(c, state.severity_rationale))
        for c in candidates
    ]
    best = max(scored, key=lambda pair: pair[1])[0]
    _open_hitl_task(state.case_id, "final_decision", {"status": "appeal_under_review"})
    db.execute(
        """UPDATE IntegrityAppeals SET evaluation = ?, status = 'evaluated'
           WHERE appeal_id = (SELECT appeal_id FROM IntegrityAppeals
                               WHERE case_id = ? ORDER BY appeal_id DESC LIMIT 1)""",
        (best, state.case_id),
    )
    return {
        "appeal_options_considered": [c for c, _ in scored],
        "appeal_evaluation": best,
        "status": "appeal_under_review",
    }


def log_and_close(state: AcademicIntegrityState) -> dict:
    db.execute(
        "UPDATE IntegrityCases SET status = 'closed', updated_at = ? WHERE case_id = ?",
        (datetime.utcnow().isoformat(), state.case_id),
    )
    return {"status": "closed"}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_academic_integrity_graph():
    builder = StateGraph(AcademicIntegrityState)

    builder.add_node("gather_evidence", gather_evidence)
    builder.add_node("analyze_severity", analyze_severity)
    builder.add_node("minor_warning", minor_warning)
    builder.add_node("needs_committee_review", committee_review_hitl)  # HITL #1
    builder.add_node("notify_student", notify_student)
    builder.add_node("await_appeal", await_appeal)
    builder.add_node("evaluate_appeal", evaluate_appeal)
    builder.add_node("committee_final_decision", final_decision_hitl)  # HITL #2
    builder.add_node("log_and_close", log_and_close)

    builder.set_entry_point("gather_evidence")
    builder.add_edge("gather_evidence", "analyze_severity")
    builder.add_conditional_edges(
        "analyze_severity",
        route_by_severity,
        {"minor_warning": "minor_warning", "needs_committee_review": "needs_committee_review"},
    )
    builder.add_edge("minor_warning", END)
    builder.add_conditional_edges(
        "needs_committee_review",
        route_after_committee_review,
        {
        "gather_evidence": "gather_evidence",
        "log_and_close": "log_and_close",
        "notify_student": "notify_student",
    },
)
    builder.add_edge("notify_student", "await_appeal")
    builder.add_edge("await_appeal", "evaluate_appeal")
    builder.add_edge("evaluate_appeal", "committee_final_decision")
    builder.add_edge("committee_final_decision", "log_and_close")
    builder.add_edge("log_and_close", END)

    return builder.compile(
        checkpointer=get_checkpointer(),
        interrupt_before=["needs_committee_review", "await_appeal", "committee_final_decision"],
    )


def start_case(case_input: dict):
    """Entry point the platform calls when an instructor reports a case."""
    graph = build_academic_integrity_graph()
    config = {"configurable": {"thread_id": thread_id_for_case(case_input["case_id"])}}
    return graph.invoke(case_input, config=config)


def resume_case(case_id: int, update: dict | None = None):
    """Entry point the platform calls after an admin acts (HITL) or a student
    submits an appeal (await_appeal), or after a ticket is resolved."""
    graph = build_academic_integrity_graph()
    config = {"configurable": {"thread_id": thread_id_for_case(case_id)}}
    if update:
        graph.update_state(config, update)
    return graph.invoke(None, config=config)