"""
academic_integrity_router.py
=============================
API boundary over phase-3's Academic Integrity Investigation & Appeal
graph. Every function this router calls (start_case, resume_case,
submit_committee_decision, submit_final_decision) already exists in
phase-3/state_graph/academic_integrity/ — no new graph logic here.

case_id is the graph's thread_id source (thread_id = f"academic-integrity-{case_id}"),
and start_case() requires case_id to already be set on the input (it does
NOT auto-create the IntegrityCases row itself, unlike advisory's
load_profile) — so this router creates the row first, exactly the same
order hiring_router.py already established for JobPostings/start_job.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser
from core.graph_loader import start_case, resume_case, submit_committee_decision, submit_final_decision

router = APIRouter(prefix="/academic-integrity", tags=["academic-integrity"])


class ReportCaseRequest(BaseModel):
    student_id: int
    course_id: int
    assignment_id: int | None = None
    description: str
    similarity_score: float | None = None


class AppealRequest(BaseModel):
    appeal_argument: str


class CommitteeDecisionRequest(BaseModel):
    decision: str  # e.g. "uphold" | "dismiss" | "reduce_penalty"
    notes: str | None = None


class FinalDecisionRequest(BaseModel):
    decision: str
    notes: str | None = None


def _case_row(case_id: int) -> dict:
    row = db.query_one("SELECT * FROM IntegrityCases WHERE case_id = ?", (case_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return row


@router.post("/cases")
def report_case(body: ReportCaseRequest, user: CurrentUser = Depends(require_role("instructor"))):
    """Instructor reports a new case (instructor/integrity/new)."""
    row = db.query_one(
        """INSERT INTO IntegrityCases
               (student_id, course_id, assignment_id, reported_by, description, similarity_score, status)
           VALUES (?, ?, ?, ?, ?, ?, 'reported') RETURNING case_id""",
        (body.student_id, body.course_id, body.assignment_id, user.user_id, body.description, body.similarity_score),
    )
    case_id = row["case_id"]

    case_input = {
        "case_id": case_id,
        "student_id": body.student_id,
        "course_id": body.course_id,
        "assignment_id": body.assignment_id,
        "reported_by": user.user_id,
        "description": body.description,
        "similarity_score": body.similarity_score,
    }
    try:
        result = start_case(case_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to start: {e}")
    return {"status": "ok", "case_id": case_id, "result": _safe_state(result)}


@router.get("/cases")
def list_cases(
    student_id: int | None = None,
    course_id: int | None = None,
    user: CurrentUser = Depends(require_role("student", "instructor", "advisor", "dept_head")),
):
    if user.role == "student":
        student_id = user.user_id  # a student can only ever see their own cases
    sql = "SELECT * FROM IntegrityCases WHERE 1=1"
    params: list = []
    if student_id is not None:
        sql += " AND student_id = ?"
        params.append(student_id)
    if course_id is not None:
        sql += " AND course_id = ?"
        params.append(course_id)
    sql += " ORDER BY created_at DESC"
    return db.query_all(sql, tuple(params))


@router.get("/cases/{case_id}")
def get_case(case_id: int, user: CurrentUser = Depends(require_role("student", "instructor", "advisor", "dept_head"))):
    case = _case_row(case_id)
    if user.role == "student" and case["student_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Not your case.")
    evidence = db.query_all("SELECT * FROM IntegrityEvidence WHERE case_id = ?", (case_id,))
    appeals = db.query_all("SELECT * FROM IntegrityAppeals WHERE case_id = ?", (case_id,))
    decisions = db.query_all("SELECT * FROM IntegrityDecisions WHERE case_id = ?", (case_id,))
    return {"case": case, "evidence": evidence, "appeals": appeals, "decisions": decisions}


@router.post("/cases/{case_id}/appeal")
def submit_appeal(case_id: int, body: AppealRequest, user: CurrentUser = Depends(require_role("student"))):
    """Student submits an appeal (student/cases/:caseId/appeal). Resumes the
    graph past the await_appeal interrupt with the argument in state."""
    case = _case_row(case_id)
    if case["student_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Not your case.")
    if case["status"] not in ("awaiting_appeal",):
        raise HTTPException(status_code=409, detail=f"Case is '{case['status']}', not awaiting an appeal.")
    try:
        result = resume_case(case_id, update={"appeal_argument": body.appeal_argument})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}


@router.post("/cases/{case_id}/committee-decision")
def committee_decision(case_id: int, body: CommitteeDecisionRequest, user: CurrentUser = Depends(require_role("instructor", "advisor"))):
    """Admin resolves the first HITL gate (needs_committee_review)."""
    _case_row(case_id)
    try:
        result = submit_committee_decision(case_id, decided_by=f"{user.role}:{user.user_id}", decision=body.decision, notes=body.notes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}


@router.post("/cases/{case_id}/final-decision")
def final_decision(case_id: int, body: FinalDecisionRequest, user: CurrentUser = Depends(require_role("instructor", "advisor"))):
    """Admin resolves the second HITL gate (committee_final_decision, after
    Tree-of-Thoughts appeal evaluation)."""
    _case_row(case_id)
    try:
        result = submit_final_decision(case_id, decided_by=f"{user.role}:{user.user_id}", decision=body.decision, notes=body.notes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}


def _safe_state(result) -> dict:
    """LangGraph state comes back as a plain dict already (AddableValuesDict);
    strip the internal __interrupt__ marker into a plain, JSON-friendly shape."""
    out = dict(result)
    interrupt = out.pop("__interrupt__", None)
    if interrupt:
        out["_interrupt"] = [getattr(i, "value", i) for i in interrupt]
    return out