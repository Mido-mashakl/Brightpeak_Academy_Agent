"""
Adaptive Assessment — Human-in-the-Loop node type.

Condition for firing (defined here, in writing, per the Final Project
requirement): flag_for_review triggers when the session's final_score
lands within +/-5% of mastery_threshold. That is exactly the zone where
the agent's own pass/fail call is least trustworthy -- a hair on either
side of the line changes the student's outcome, so a human decides instead
of the graph. (See graph.py: finalize() sets state.flagged using this
rule before routing here.)

Same separation as academic_integrity/hitl.py: this is an EXPECTED pause
(the graph is not allowed to decide alone in the borderline zone), not a
ticket (which is for unplanned failures -- see tickets.py).
"""

from __future__ import annotations

from datetime import datetime

import sys as _sys
from pathlib import Path as _Path
MCP_SERVER_DIR = _Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(MCP_SERVER_DIR) not in _sys.path:
    _sys.path.insert(0, str(MCP_SERVER_DIR))

from mcp_server import database as db
from .state import AdaptiveAssessmentState


def flag_for_review_hitl(state: AdaptiveAssessmentState) -> dict:
    """True no-op, same as Week 5's `await_manager` example. graph.py uses
    interrupt_before=["flag_for_review"], which means this node's own code
    NEVER runs before the pause -- so any DB write meant to "open the task"
    has to happen in the node right before it instead (see finalize() in
    graph.py, which sets AssessmentSessions.status = 'flagged_for_review'
    when it decides flagged=True). Fixed after review: this function used
    to do that UPDATE itself, which meant it silently never ran until AFTER
    an admin had already resolved the review -- the platform would never
    have seen the pending task in time."""
    return {}


# --- Called by the platform's admin surface when an admin actually decides ---

def submit_review_decision(
    session_id: int,
    reviewed_by: str,
    decision: str,  # "approve" | "adjust_score" | "retake"
    notes: str | None = None,
    adjusted_score: float | None = None,
):
    """Platform calls this from the admin's 'resolve HITL task' button.
    The decision (and its rationale) is preserved by the checkpointer as
    part of the resumed state -- no separate log table exists yet for
    review decisions the way IntegrityDecisions does for the other graph;
    worth adding if the platform needs a queryable history of reviews."""
    from .graph import resume_session  # local import avoids circular import

    update = {
        "reviewed_by": reviewed_by,
        "review_decision": decision,
        "review_notes": notes,
        "adjusted_score": adjusted_score,
    }
    return resume_session(session_id, update=update)