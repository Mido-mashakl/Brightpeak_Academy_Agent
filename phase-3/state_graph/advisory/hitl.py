"""
hitl.py
=======
The two *expected*-pause points in this graph (kept separate from tickets.py's
unexpected-failure path):

  wait_for_student  — the agent has a genuine reason it cannot proceed: the
                       eligibility check is missing information only the
                       student can supply (e.g. an appeal letter, a missing
                       document reference). Not a retry-able tool error.

  human_review       — the agent is not allowed to decide alone: confidence is
                       below threshold, evidence conflicts, or the policy is
                       ambiguous. An admin must approve/reject/request more
                       info through the platform before the request can close.

Both use LangGraph's `interrupt()`, which checkpoints the graph and suspends
execution until the platform calls `graph.invoke(Command(resume=...), config)`
with the same thread_id — this can be minutes or days later, across process
restarts, because the pause itself is a persisted checkpoint, not an
in-memory wait.
"""

from __future__ import annotations

from langgraph.types import interrupt

from . import data
from .state import DecisionRecord, StudentAdvisorState


def wait_for_student_node(state: StudentAdvisorState) -> dict:
    """Pause until the platform resumes with the student's reply."""
    payload = interrupt(
        {
            "type": "student_info_request",
            "request_id": state.request_id,
            "student_id": state.student_id,
            "missing_info": state.missing_info,
        }
    )
    # `payload` is whatever the platform passes to Command(resume=...) — the
    # student's free-text reply.
    return {
        "student_response": payload,
        "awaiting_student": False,
        "status": "in_progress",
    }


def human_review_node(state: StudentAdvisorState) -> dict:
    """Pause for an admin decision: approve / reject / request_more_info."""
    # Persisted BEFORE interrupt() — same reason track_recommendation's
    # hitl_node writes status="awaiting_advisor" before its own interrupt():
    # once interrupt() suspends the graph, nothing in this process runs
    # again until Command(resume=...) is called, so this is the only chance
    # to record "an advisor decision is now needed here" durably.
    data.mark_needs_review(state.request_type, state.request_id)
    decision_payload = interrupt(
        {
            "type": "admin_review",
            "request_id": state.request_id,
            "student_id": state.student_id,
            "request_type": state.request_type,
            "requirement_checks": [c.model_dump() for c in state.requirement_checks],
            "confidence": state.confidence,
            "recommendation": state.recommendation,
        }
    )
    # Expected shape from the platform:
    # {"decided_by": "<admin id>", "decision": "approve"|"reject"|"request_more_info",
    #  "notes": "..."}
    decision = DecisionRecord(**decision_payload)

    updates: dict = {
        "decisions": [decision],
        "status": "in_progress",
        "review_required": False,
    }
    if decision.decision == "approve":
        updates["eligibility_status"] = "eligible"
    elif decision.decision == "reject":
        updates["eligibility_status"] = "ineligible"
    else:  # request_more_info
        updates["eligibility_status"] = "needs_review"
        updates["missing_info"] = [decision.notes or "Admin requested more information."]
        updates["awaiting_student"] = True

    return updates