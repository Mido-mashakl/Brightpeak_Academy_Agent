"""
advisor_router.py
==================
API boundary over phase-3's Student Advisor (Certificate & Scholarship
Eligibility) graph. start_request() already auto-creates the
CertificateRequests/ScholarshipApplications row (see advisory/graph.py's
load_profile) — unlike academic_integrity/adaptive_assessment, this
router does NOT need to insert the row itself first.

Resume is Command(resume=payload), not update_state()+invoke(None) — see
core/graph_loader.py's resume_advisor_request for why (bare interrupt(),
not interrupt_before=[...]).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser
from core.graph_loader import start_advisor_request, resume_advisor_request, get_advisor_request_state

router = APIRouter(prefix="/advisor", tags=["advisor"])


class StartRequestBody(BaseModel):
    request_type: str  # "certificate" | "scholarship"
    course_id: int | None = None
    purpose: str | None = None


class StudentReplyBody(BaseModel):
    response: str


class AdminDecisionBody(BaseModel):
    decision: str  # "approve" | "reject" | "request_more_info"
    notes: str | None = None


def _safe_state(result) -> dict:
    out = dict(result)
    interrupt = out.pop("__interrupt__", None)
    if interrupt:
        out["_interrupt"] = [getattr(i, "value", i) for i in interrupt]
    return out


def _table_for(request_type: str) -> str:
    if request_type not in ("certificate", "scholarship"):
        raise HTTPException(status_code=400, detail="request_type must be 'certificate' or 'scholarship'.")
    return "CertificateRequests" if request_type == "certificate" else "ScholarshipApplications"


def _id_col_for(request_type: str) -> str:
    # CertificateRequests uses request_id as its PK; ScholarshipApplications
    # uses application_id (see db/schema.sql) — the graph's own state.request_id
    # / thread_id (f"student-advisor-{request_id}") is the same integer either
    # way (data.py's create_request_row returns lastrowid regardless of table),
    # only the SQL column name differs, so queries against the raw tables must
    # select the right column name per type.
    return "request_id" if request_type == "certificate" else "application_id"


@router.post("/certificate")
def request_certificate(body: StartRequestBody, user: CurrentUser = Depends(require_role("student"))):
    return _start(user.user_id, "certificate", body)


@router.post("/scholarship")
def request_scholarship(body: StartRequestBody, user: CurrentUser = Depends(require_role("student"))):
    return _start(user.user_id, "scholarship", body)


def _start(student_id: int, request_type: str, body: StartRequestBody):
    try:
        result = start_advisor_request(
            student_id=student_id,
            request_type=request_type,
            course_id=body.course_id,
            purpose=body.purpose,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to start: {e}")
    result = _safe_state(result)
    return {"status": "ok", "request_id": result.get("request_id"), "result": result}


@router.get("/requests")
def list_requests(
    request_type: str | None = None,
    student_id: int | None = None,
    user: CurrentUser = Depends(require_role("student", "advisor")),
):
    """Advisor's queue (advisor/requests), or a student's own history."""
    if user.role == "student":
        student_id = user.user_id

    tables = [request_type] if request_type else ["certificate", "scholarship"]
    out = []
    for t in tables:
        table = _table_for(t)
        id_col = _id_col_for(t)
        sql = f"SELECT *, {id_col} AS request_id FROM {table} WHERE 1=1"
        params: list = []
        if student_id is not None:
            sql += " AND student_id = ?"
            params.append(student_id)
        sql += f" ORDER BY {id_col} DESC"
        for row in db.query_all(sql, tuple(params)):
            row = dict(row)
            row["request_type"] = t
            out.append(row)
    out.sort(key=lambda r: r["request_id"], reverse=True)
    return out


@router.get("/requests/{request_type}/{request_id}")
def get_request(request_type: str, request_id: int, user: CurrentUser = Depends(require_role("student", "advisor"))):
    table = _table_for(request_type)
    id_col = _id_col_for(request_type)
    row = db.query_one(f"SELECT *, {id_col} AS request_id FROM {table} WHERE {id_col} = ?", (request_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    if user.role == "student" and row["student_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Not your request.")
    graph_state = get_advisor_request_state(request_id)
    return {"row": row, "graph_state": graph_state}


@router.post("/requests/{request_id}/student-response")
def student_response(request_id: int, body: StudentReplyBody, user: CurrentUser = Depends(require_role("student"))):
    """Resumes the wait_for_student interrupt with the student's reply."""
    try:
        result = resume_advisor_request(request_id, body.response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}


@router.post("/requests/{request_id}/decision")
def admin_decision(request_id: int, body: AdminDecisionBody, user: CurrentUser = Depends(require_role("advisor"))):
    """Resumes the human_review interrupt — the admin's 'resolve HITL task' button."""
    payload = {"decided_by": f"advisor:{user.user_id}", "decision": body.decision, "notes": body.notes}
    try:
        result = resume_advisor_request(request_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    return {"status": "ok", "result": _safe_state(result)}