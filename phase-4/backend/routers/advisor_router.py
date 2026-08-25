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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, verify_user_query, CurrentUser
from core.graph_loader import start_advisor_request, resume_advisor_request, get_advisor_request_state
from core.notifications import event_stream, publish
from core import student_notifications as sn

router = APIRouter(prefix="/advisor", tags=["advisor"])

# All advisors share one queue (list_requests below never filters by
# advisor_id — requests aren't assigned to a specific advisor), so one
# broadcast channel matches how the queue is actually modeled.
_ADVISOR_CHANNEL = "advisor_requests"

# Per-student channel: "student:{student_id}" — used to push
# "more_info_requested" events so the student's chat page reacts without
# a manual refresh.  notifications.py is generic; no change needed there.
def _student_channel(student_id: int) -> str:
    return f"student:{student_id}"


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


def _notify_if_needs_review(result: dict) -> None:
    """Publishes to the advisor SSE channel the moment a request lands on
    human_review_node's interrupt() — i.e. exactly when data.py's
    mark_needs_review() just wrote status='needs_review' for it. Called
    from every endpoint that can cause the graph to reach that node
    (starting a request, or a student reply that re-evaluates and still
    isn't confident enough): _start() and student_response() below.
    admin_decision() doesn't need this — resuming human_review never routes
    straight back into human_review (see route_after_human_review in
    advisory/graph.py), so an admin's own decision can't retrigger it.

    request_type comes straight off the interrupt payload itself
    (human_review_node's interrupt() call includes it) rather than being
    passed in separately, so certificate and scholarship requests — same
    graph, same interrupt shape — are handled identically here."""
    for iv in result.get("_interrupt") or []:
        if isinstance(iv, dict) and iv.get("type") == "admin_review":
            publish(
                _ADVISOR_CHANNEL,
                "needs_review",
                {
                    "request_id": iv.get("request_id"),
                    "request_type": iv.get("request_type"),
                    "student_id": iv.get("student_id"),
                },
            )
            break


def _notify_if_needs_student(result: dict) -> None:
    """Publishes to the per-student SSE channel when the graph lands on
    wait_for_student_node's interrupt() — i.e. when the advisor chose
    'request_more_info' and the graph now needs the student's reply.

    The interrupt payload shape from advisory/hitl.py::wait_for_student_node:
        {
            "type": "student_info_request",
            "request_id": <int>,
            "student_id": <int>,
            "missing_info": [<str>, ...]
        }
    Called from admin_decision() — the only place a human_review resume
    can produce a wait_for_student interrupt."""
    for iv in result.get("_interrupt") or []:
        if isinstance(iv, dict) and iv.get("type") == "student_info_request":
            student_id = iv.get("student_id")
            if student_id:
                payload = {
                    "request_id": iv.get("request_id"),
                    "missing_info": iv.get("missing_info", []),
                }
                # 1) Durable — survives page close/reopen
                notification_id = sn.write_notification(student_id, "more_info_requested", payload)
                # 2) Real-time — instant if the student's chat page is open.
                # Include the DB id so the frontend can mark it read the
                # moment it's shown live, same as the poll path does —
                # otherwise a student who sees this via SSE would see the
                # same card reappear as "unread" next time they reload.
                publish(
                    _student_channel(student_id),
                    "more_info_requested",
                    {**payload, "_notification_id": notification_id},
                )
            break


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
    _notify_if_needs_review(result)
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
        sql = f"SELECT t.*, {id_col} AS request_id, s.name AS student_name FROM {table} t LEFT JOIN Students s ON t.student_id = s.student_id WHERE 1=1"
        params: list = []
        if student_id is not None:
            sql += " AND t.student_id = ?"
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
    row = db.query_one(f"SELECT t.*, {id_col} AS request_id, s.name AS student_name FROM {table} t LEFT JOIN Students s ON t.student_id = s.student_id WHERE {id_col} = ?", (request_id,))
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
    result = _safe_state(result)
    # Re-evaluating the student's new info can route straight back into
    # human_review (see route_after_evaluation in advisory/graph.py) — the
    # advisor needs to hear about that too, not just the initial submission.
    _notify_if_needs_review(result)
    return {"status": "ok", "result": result}


@router.get("/notifications/stream")
async def advisor_notifications_stream(user_id: int, role: str = "advisor"):
    """SSE stream of 'needs_review' events for the advisor queue.

    Query params instead of the usual X-User-Id/X-User-Role headers because
    the browser's EventSource API can't set custom headers — see
    core.auth.verify_user_query's docstring for the trade-off this makes.
    """
    verify_user_query(role, user_id, allowed_roles=("advisor",))
    return StreamingResponse(event_stream(_ADVISOR_CHANNEL), media_type="text/event-stream")


@router.get("/notifications/student-stream")
async def student_notifications_stream(user_id: int, role: str = "student"):
    """SSE stream of 'more_info_requested' events for a specific student.

    Mirrors /notifications/stream (advisor channel) exactly — same query-param
    auth workaround because EventSource can't send custom headers.
    The student's chat page opens this on load so it learns within seconds
    when an advisor chose 'Request More Info' instead of waiting for a refresh.
    """
    verify_user_query(role, user_id, allowed_roles=("student",))
    return StreamingResponse(event_stream(_student_channel(user_id)), media_type="text/event-stream")


@router.post("/requests/{request_id}/decision")
def admin_decision(request_id: int, body: AdminDecisionBody, user: CurrentUser = Depends(require_role("advisor"))):
    """Resumes the human_review interrupt — the admin's 'resolve HITL task' button."""
    payload = {"decided_by": f"advisor:{user.user_id}", "decision": body.decision, "notes": body.notes}
    try:
        result = resume_advisor_request(request_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    safe = _safe_state(result)
    # If the advisor chose "request_more_info", the graph routes to
    # wait_for_student_node — notify the student in real time.
    _notify_if_needs_student(safe)
    return {"status": "ok", "result": safe}