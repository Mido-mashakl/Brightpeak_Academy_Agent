"""
tracks_router.py
=================
API boundary over phase-3's Track Recommendation & Prerequisite Assessment
graph, using the start_/resume_ wrappers added to core/graph_loader.py
(this graph had none before — see graph_loader's module docstring).

IMPORTANT — thread_id, not recommendation_id, is the resume key:
TrackRecommendations (db/schema.sql) has no thread_id column, and
recommendation_id itself is only assigned INSIDE the graph
(collect_student_data -> db.create_recommendation), so it doesn't exist
yet when start() is called. This router returns thread_id to the caller
on start, and every resume endpoint takes it back as a path param. A
DB-level "map thread_id -> recommendation_id" convenience table would
remove the need for the frontend to hold onto thread_id itself; noted as
a follow-up in the final report rather than added here, since the
checkpointer already makes the graph fully resumable from thread_id
alone with no data loss.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, verify_user_query, CurrentUser
from core.graph_loader import (
    start_track_recommendation,
    resume_track_recommendation,
    get_track_recommendation_state,
)
from core.notifications import event_stream, publish
from core import student_notifications as sn

# Per-student channel — same naming convention as advisor_router so both
# graphs (advisory + track_recommendation) can push to the same student
# SSE stream if they ever share one endpoint. advisor_router.py already
# owns GET /advisor/notifications/student-stream; this router reuses the
# identical channel key so a single SSE subscription covers both.
def _student_channel(student_id: int) -> str:
    return f"student:{student_id}"

router = APIRouter(prefix="/tracks", tags=["tracks"])


class DiagnosticCompleteRequest(BaseModel):
    completed: bool = True


class TicketFixedRequest(BaseModel):
    fixed: bool = True


class AdvisorDecisionRequest(BaseModel):
    action: str  # "approve" | "choose_other" | "request_assessment"
    advisor_name: str
    track: str | None = None      # required for "choose_other"
    subject: str | None = None    # required for "request_assessment"


def _safe_state(result) -> dict:
    out = dict(result)
    interrupt = out.pop("__interrupt__", None)
    if interrupt:
        out["_interrupt"] = [getattr(i, "value", i) for i in interrupt]
    return out


@router.post("/recommend")
def recommend(user: CurrentUser = Depends(require_role("student"))):
    """Student clicks 'Get Track Recommendation' (student/tracks)."""
    try:
        result = start_track_recommendation(student_id=user.user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to start: {e}")
    result = _safe_state(result)
    return {
        "status": "ok",
        "thread_id": result.get("thread_id"),
        "recommendation_id": result.get("recommendation_id"),
        "result": result,
    }


@router.get("/recommendations")
def list_recommendations(
    student_id: int | None = None,
    status: str | None = None,
    user: CurrentUser = Depends(require_role("student", "advisor")),
):
    """Student's own history, or (with status='awaiting_advisor') the
    advisor's Track Recommendation review queue — the counterpart to
    advisor_router's GET /advisor/requests for certificate/scholarship."""
    if user.role == "student":
        student_id = user.user_id
    sql = "SELECT * FROM TrackRecommendations WHERE 1=1"
    params: list = []
    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    return db.query_all(sql, tuple(params))


@router.get("/thread/{thread_id}")
def get_thread_state(thread_id: str, user: CurrentUser = Depends(require_role("student", "advisor"))):
    state = get_track_recommendation_state(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No graph state for that thread_id.")
    return state


@router.post("/thread/{thread_id}/diagnostic-complete")
def diagnostic_complete(thread_id: str, body: DiagnosticCompleteRequest, user: CurrentUser = Depends(require_role("student"))):
    """Resumes after the student finishes a real Adaptive Assessment for a
    missing prerequisite course (await_diagnostic_response)."""
    try:
        result = resume_track_recommendation(thread_id, {"completed": body.completed})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}


@router.post("/thread/{thread_id}/ticket-resolved")
def ticket_resolved(thread_id: str, body: TicketFixedRequest, user: CurrentUser = Depends(require_role("advisor"))):
    """Admin 'fixes' a RAG-failure ticket and resumes (await_ticket_resolution)."""
    try:
        result = resume_track_recommendation(thread_id, {"fixed": body.fixed})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}


@router.post("/thread/{thread_id}/advisor-decision")
def advisor_decision(thread_id: str, body: AdvisorDecisionRequest, user: CurrentUser = Depends(require_role("advisor"))):
    """Advisor resolves hitl_node: approve the top track, override with the
    alternative, or request a targeted assessment on a specific subject."""
    payload = {"action": body.action, "advisor_name": body.advisor_name}
    if body.track:
        payload["track"] = body.track
    if body.subject:
        payload["subject"] = body.subject
    try:
        result = resume_track_recommendation(thread_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    safe = _safe_state(result)
    # If the advisor chose "request_assessment", the graph routes to
    # await_targeted_assessment_response — notify the student in real time.
    # The awaiting_student interrupt payload includes the subject and
    # assessment_id; student_id comes from the graph state values.
    for iv in safe.get("_interrupt") or []:
        if isinstance(iv, dict) and iv.get("type") == "awaiting_student":
            student_id = safe.get("student_id")
            if student_id:
                payload = {
                    "thread_id": thread_id,
                    "subject": iv.get("subject"),
                    "assessment_id": iv.get("assessment_id"),
                    "adaptive_thread_id": iv.get("adaptive_thread_id"),
                    "message": iv.get("message", "Your advisor requested a targeted assessment."),
                }
                # 1) Durable — survives page close/reopen
                notification_id = sn.write_notification(student_id, "assessment_requested", payload)
                # 2) Real-time — instant if the student's tracks page is open.
                # Include the DB id so the frontend can mark it read the
                # moment it's shown live, same as the poll path does —
                # otherwise a student who sees this via SSE would see the
                # same card reappear as "unread" next time they reload.
                publish(
                    _student_channel(student_id),
                    "assessment_requested",
                    {**payload, "_notification_id": notification_id},
                )
            break
    return {"status": "ok", "result": safe}


@router.post("/thread/{thread_id}/targeted-assessment-complete")
def targeted_assessment_complete(thread_id: str, body: DiagnosticCompleteRequest, user: CurrentUser = Depends(require_role("student"))):
    """Resumes after the student finishes an advisor-requested targeted
    assessment (await_targeted_assessment_response)."""
    try:
        result = resume_track_recommendation(thread_id, {"completed": body.completed})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}