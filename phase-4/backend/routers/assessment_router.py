"""
assessment_router.py
=====================
API boundary over phase-3's Adaptive Assessment & Mastery Evaluation
graph. start_session() assumes the AssessmentSessions row already exists
(see graph.py's start_assessment: "Assumes the AssessmentSessions row was
already created by the platform when the student started, same pattern as
academic_integrity") — so this router creates that row first, then calls
start_session() with the resulting session_id (its INSERT OR IGNORE is a
no-op on the row we just made, and a real safety net if this endpoint is
ever retried).

Two distinct resume paths, matching graph.py's two interrupt_before nodes:
  - await_answer:      student answers a question -> update_state() with
                        pending_question.student_answer filled in, then
                        resume_session(session_id) with no update dict
                        needed beyond that (handled inside resume_session
                        itself via the `update` kwarg).
  - flag_for_review:    admin resolves a borderline mastery call ->
                        submit_review_decision() (hitl.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser
from core.graph_loader import (
    start_assessment_session,
    resume_assessment_session,
    submit_assessment_review_decision,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])


class StartSessionRequest(BaseModel):
    course_id: int
    topic: str
    max_questions: int = 8
    mastery_threshold: float = 0.75


class AnswerRequest(BaseModel):
    student_answer: str


class ReviewDecisionRequest(BaseModel):
    decision: str  # "approve" | "adjust_score" | "retake"
    notes: str | None = None
    adjusted_score: float | None = None


def _safe_state(result) -> dict:
    out = dict(result)
    interrupt = out.pop("__interrupt__", None)
    if interrupt:
        out["_interrupt"] = [getattr(i, "value", i) for i in interrupt]
    return out


def _session_row(session_id: int) -> dict:
    row = db.query_one("SELECT * FROM AssessmentSessions WHERE session_id = ?", (session_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Assessment session not found.")
    return row


@router.post("/start")
def start(body: StartSessionRequest, user: CurrentUser = Depends(require_role("student"))):
    row = db.query_one(
        """INSERT INTO AssessmentSessions (student_id, course_id, topic, status)
           VALUES (?, ?, ?, 'in_progress') RETURNING session_id""",
        (user.user_id, body.course_id, body.topic),
    )
    session_id = row["session_id"]

    session_input = {
        "session_id": session_id,
        "student_id": user.user_id,
        "course_id": body.course_id,
        "topic": body.topic,
        "max_questions": body.max_questions,
        "mastery_threshold": body.mastery_threshold,
    }
    try:
        result = start_assessment_session(session_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to start: {e}")
    return {"status": "ok", "session_id": session_id, "result": _safe_state(result)}


@router.get("/{session_id}")
def get_session(session_id: int, user: CurrentUser = Depends(require_role("student", "instructor"))):
    row = _session_row(session_id)
    if user.role == "student" and row["student_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session.")
    answers = db.query_all("SELECT * FROM AssessmentAnswers WHERE session_id = ?", (session_id,))
    return {"session": row, "answers": answers}


@router.get("")
def list_sessions(
    student_id: int | None = None,
    course_id: int | None = None,
    user: CurrentUser = Depends(require_role("student", "instructor")),
):
    if user.role == "student":
        student_id = user.user_id
    sql = "SELECT * FROM AssessmentSessions WHERE 1=1"
    params: list = []
    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)
    if course_id is not None:
        sql += " AND course_id = ?"
        params.append(course_id)
    sql += " ORDER BY started_at DESC"
    return db.query_all(sql, tuple(params))


@router.post("/{session_id}/answer")
def answer_question(session_id: int, body: AnswerRequest, user: CurrentUser = Depends(require_role("student"))):
    """Resumes past the await_answer interrupt. The graph's own
    await_answer node is a no-op — resuming means filling in
    pending_question.student_answer via the `update` dict resume_session
    already threads through to graph.update_state()."""
    row = _session_row(session_id)
    if row["student_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Not your session.")
    if row["status"] != "in_progress":
        raise HTTPException(status_code=409, detail=f"Session is '{row['status']}', not accepting answers.")

    from core.graph_loader import get_assessment_session_state
    state = get_assessment_session_state(session_id)
    if not state or not state["values"] or not state["values"].get("pending_question"):
        raise HTTPException(status_code=409, detail="No pending question to answer.")

    pending = state["values"]["pending_question"]
    pending = pending.model_dump() if hasattr(pending, "model_dump") else dict(pending)
    pending["student_answer"] = body.student_answer

    try:
        result = resume_assessment_session(session_id, update={"pending_question": pending})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}


@router.post("/{session_id}/review-decision")
def review_decision(session_id: int, body: ReviewDecisionRequest, user: CurrentUser = Depends(require_role("instructor"))):
    """Admin resolves the flag_for_review HITL gate (borderline mastery)."""
    _session_row(session_id)
    try:
        result = submit_assessment_review_decision(
            session_id,
            reviewed_by=f"instructor:{user.user_id}",
            decision=body.decision,
            notes=body.notes,
            adjusted_score=body.adjusted_score,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}