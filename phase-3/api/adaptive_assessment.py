"""
Adaptive Assessment -- platform API surface.

Same pattern as api/academic_integrity.py: wraps the exact functions
demo_interactive.py calls (start_session, submit_review_decision,
resolve_ticket) as real HTTP endpoints for the platform to call.

Endpoints:
  POST /adaptive-assessment/sessions                      -> start a session
  GET  /adaptive-assessment/sessions/{session_id}          -> current state (pending question, or paused-for-review)
  POST /adaptive-assessment/sessions/{session_id}/answer    -> student submits an answer, advances the cycle
  POST /adaptive-assessment/sessions/{session_id}/review-decision -> HITL resolve (borderline mastery score)
  GET  /adaptive-assessment/tickets                        -> open tickets for this graph
  POST /adaptive-assessment/tickets/{ticket_id}/resolve     -> resolve + resume from checkpoint
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PHASE3_DIR = Path(__file__).resolve().parent.parent
if str(PHASE3_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE3_DIR))
MCP_SERVER_DIR = PHASE3_DIR / "mcp_server"
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

import mcp_server.database as db  # noqa: E402
import state_graph.adaptive_assessment.graph as g  # noqa: E402
from state_graph.adaptive_assessment.hitl import submit_review_decision  # noqa: E402
from state_graph.adaptive_assessment.tickets import resolve_ticket  # noqa: E402


router = APIRouter(prefix="/adaptive-assessment", tags=["Adaptive Assessment"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    session_id: int
    student_id: int
    course_id: int
    topic: str


class AnswerRequest(BaseModel):
    answer_text: str


class ReviewDecisionRequest(BaseModel):
    reviewed_by: str
    decision: str  # "approve" | "adjust_score" | "retake"
    notes: Optional[str] = None
    adjusted_score: Optional[float] = None


class TicketResolveRequest(BaseModel):
    resolution_notes: str


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

@router.post("/sessions")
async def start_session(request: StartSessionRequest):
    """Starts a session: runs start_assessment -> select_next_question and
    pauses at await_answer with the first question ready."""
    try:
        g.start_session(request.model_dump())
        return await get_session(request.session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {exc}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: int):
    """Current state of the graph for this session: either a pending
    question (await_answer), a pending admin review (flag_for_review), or a
    finished session."""
    graph = g.build_adaptive_assessment_graph()
    config = {"configurable": {"thread_id": g.thread_id_for_session(session_id)}}
    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail=f"No session found for session_id {session_id}")

    pending_question = state.values.get("pending_question")
    return {
        "session_id": session_id,
        "status": state.values.get("status"),
        "pending_node": state.next,  # non-empty tuple means the graph is paused here
        "pending_question": pending_question.model_dump() if pending_question else None,
        "running_score": state.values.get("running_score"),
        "flag_reason": state.values.get("flag_reason"),
        "final_score": state.values.get("final_score"),
        "mastery_level": state.values.get("mastery_level"),
    }


@router.post("/sessions/{session_id}/answer")
async def submit_answer(session_id: int, request: AnswerRequest):
    """Student answers the current pending_question through the platform's
    user surface. Sets the student_answer on the pending question, then
    resumes the graph into evaluate_answer -> check_mastery_or_continue
    (real cycle back to select_next_question, or on to finalize)."""
    graph = g.build_adaptive_assessment_graph()
    config = {"configurable": {"thread_id": g.thread_id_for_session(session_id)}}
    state = graph.get_state(config)
    pending = state.values.get("pending_question")
    if pending is None:
        raise HTTPException(status_code=400, detail="No pending question for this session")
    try:
        updated = pending.model_copy(update={"student_answer": request.answer_text})
        graph.update_state(config, {"pending_question": updated})
        graph.invoke(None, config=config)
        return await get_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions/{session_id}/review-decision")
async def review_decision(session_id: int, request: ReviewDecisionRequest):
    """Admin resolves the HITL pause (flag_for_review) -- fires when the
    final score lands within the borderline zone around mastery_threshold."""
    try:
        return submit_review_decision(
            session_id, reviewed_by=request.reviewed_by, decision=request.decision,
            notes=request.notes, adjusted_score=request.adjusted_score,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Tickets (unplanned failures -- separate path from HITL)
# ---------------------------------------------------------------------------

@router.get("/tickets")
async def list_open_tickets():
    rows = db.query_all(
        "SELECT * FROM Tickets WHERE source_graph = 'adaptive_assessment' AND status != 'resolved' "
        "ORDER BY created_at DESC",
    )
    return rows


@router.post("/tickets/{ticket_id}/resolve")
async def resolve_session_ticket(ticket_id: int, request: TicketResolveRequest):
    try:
        return resolve_ticket(ticket_id, resolution_notes=request.resolution_notes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))