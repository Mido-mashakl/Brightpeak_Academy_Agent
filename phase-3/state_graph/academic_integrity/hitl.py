"""
Academic Integrity — Human-in-the-Loop node type.

These nodes themselves do almost nothing: the actual pause happens because
graph.py compiles the graph with interrupt_before=["needs_committee_review",
"committee_final_decision", ...]. LangGraph stops BEFORE running the node,
persists the checkpoint, and returns control to the caller. This module's
job is:
  1. When the graph reaches this point, write a row the platform can show
     an admin (a "pending HITL task").
  2. Provide the function the platform calls when the admin acts, which
     writes the decision into IntegrityDecisions and resumes the graph.

This is intentionally separate from tickets.py: a HITL pause is EXPECTED
(the graph is not allowed to decide alone here) vs. a ticket, which is an
UNPLANNED failure.
"""

from __future__ import annotations

from datetime import datetime


import sys as _sys
from pathlib import Path as _Path
MCP_SERVER_DIR = _Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(MCP_SERVER_DIR) not in _sys.path:
    _sys.path.insert(0, str(MCP_SERVER_DIR))

    
from mcp_server import database as db
from .state import AcademicIntegrityState, DecisionRecord
from .checkpointing import thread_id_for_case


def _open_hitl_task(case_id: int, stage: str, context: dict) -> None:
    """Surfaced on the admin side of the platform as a pending task tied to
    this case_id + stage. The platform reads this via a simple query against
    IntegrityCases/IntegrityEvidence joined on case_id — no separate HITL
    table needed since `status` on IntegrityCases already tracks it
    ('under_review' / 'appeal_under_review' mean "a HITL task is pending").
    """
    db.execute(
        "UPDATE IntegrityCases SET status = ?, updated_at = ? WHERE case_id = ?",
        (context["status"], datetime.utcnow().isoformat(), case_id),
    )


# --- Node functions (run once, right when the graph arrives, before the interrupt) ---

def committee_review_hitl(state: AcademicIntegrityState) -> dict:
    return {}  # true no-op; the "open task" call moved to analyze_severity (see graph.py)


def final_decision_hitl(state: AcademicIntegrityState) -> dict:
    return {}  # true no-op; the "open task" call moved to evaluate_appeal (see graph.py)


# --- Called by the platform's admin surface when an admin actually decides ---

def submit_committee_decision(
    case_id: int, decided_by: str, decision: str, notes: str | None = None
):
    """Platform calls this from the admin's 'resolve HITL task' button.
    Writes IntegrityDecisions, then resumes the graph past needs_committee_review."""
    from .graph import resume_case  # local import avoids a circular import with graph.py

    db.execute(
        """INSERT INTO IntegrityDecisions (case_id, decision_stage, decided_by, decision, notes)
           VALUES (?, 'committee_review', ?, ?, ?)""",
        (case_id, decided_by, decision, notes),
    )
    record = DecisionRecord(
        decision_stage="committee_review", decided_by=decided_by, decision=decision, notes=notes
    )
    return resume_case(case_id, update={"decisions": [record]})


def submit_final_decision(
    case_id: int, decided_by: str, decision: str, notes: str | None = None
):
    """Platform calls this from the admin's 'resolve HITL task' button for the
    second gate (after Tree-of-Thoughts appeal evaluation)."""
    from .graph import resume_case

    db.execute(
        """INSERT INTO IntegrityDecisions (case_id, decision_stage, decided_by, decision, notes)
           VALUES (?, 'final_decision', ?, ?, ?)""",
        (case_id, decided_by, decision, notes),
    )
    record = DecisionRecord(
        decision_stage="final_decision", decided_by=decided_by, decision=decision, notes=notes
    )
    return resume_case(case_id, update={"decisions": [record]})