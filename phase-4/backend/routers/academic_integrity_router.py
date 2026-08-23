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

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser
from core.graph_loader import (
    start_case,
    resume_case,
    submit_committee_decision,
    submit_final_decision,
    get_case_state,
)

router = APIRouter(prefix="/academic-integrity", tags=["academic-integrity"])

# =======================================================================
# Response-shape helpers
#
# The frontend pages (instructor/integrity/integrity.js,
# instructor/integrity/case-details.js, instructor/hitl/hitl.js,
# instructor/hitl/hitl-review.js) were all built against a flat,
# already-joined shape (student NAME not student_id, a human status
# label, a workflow timeline, etc.) — never against the raw
# IntegrityCases row this router used to return as-is. Every endpoint
# below now builds that shape here, the same pattern instructor_router.py
# already established (see its own module docstring), instead of leaving
# the frontend to guess field names that were never sent.
# =======================================================================

# status -> ordered workflow timeline, used by case-details.js's
# renderTimeline(). IntegrityCases.status values line up 1:1 with these
# keys already (see db/schema.sql's CHECK constraint), so no extra
# mapping table is needed for the "currentStep" itself.
_WORKFLOW_STEPS = [
    {"key": "reported", "label": "Reported"},
    {"key": "under_review", "label": "Committee Review"},
    {"key": "awaiting_appeal", "label": "Awaiting Appeal"},
    {"key": "appeal_under_review", "label": "Appeal Review"},
    {"key": "closed", "label": "Closed"},
]
_WORKFLOW_LABEL_BY_KEY = {s["key"]: s["label"] for s in _WORKFLOW_STEPS}

# Decision vocabulary actually recognized by the graph (see graph.py's
# route_after_committee_review for "dismiss" / "request_more_evidence";
# anything else -> notify_student, i.e. an "uphold"-style outcome). The
# final-decision gate has no routing logic reading the value at all, so
# its options are the same real committee actions minus the "kick back
# for more evidence" option (there's no evidence-gather step left to loop
# back to at that point) plus "reduce_penalty", which committee_decision
# doesn't have a code path for.
_COMMITTEE_ACTIONS = ["uphold", "dismiss", "request_more_evidence"]
_FINAL_ACTIONS = ["uphold", "dismiss", "reduce_penalty"]

_EVIDENCE_TYPE_LABELS = {
    "similarity_report": "Similarity Report",
    "instructor_note": "Instructor Note",
}


def _fmt_label(iso_ts: str | None) -> str:
    """'2026-08-23 21:02:14' -> 'Aug 23, 2026, 09:02 PM'. Falls back to the
    raw value if it doesn't parse. Same helper as instructor_router.py's
    _fmt_label; duplicated locally rather than importing across routers to
    keep each router's frontend-shaping self-contained."""
    if not iso_ts:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(iso_ts, fmt)
            return dt.strftime("%b %d, %Y, %I:%M %p") if "%H" in fmt else dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    return iso_ts


def _humanize_evidence_type(evidence_type: str) -> str:
    return _EVIDENCE_TYPE_LABELS.get(evidence_type, evidence_type.replace("_", " ").title())


def _map_evidence(rows: list[dict]) -> list[dict]:
    """IntegrityEvidence rows are text entries (a similarity score, an
    instructor's note) written by the graph, not uploaded files — there is
    no name/size/image for them the way the frontend's evidence-tile UI
    expects. Mapped honestly: 'name' is the humanized evidence_type,
    'size' is a short text preview (never a byte size that doesn't exist),
    'type' is always 'file' since nothing here is ever an image."""
    out = []
    for e in rows:
        content = e["content"] or ""
        preview = content if len(content) <= 40 else content[:37] + "..."
        out.append(
            {
                "name": _humanize_evidence_type(e["evidence_type"]),
                "size": preview,
                "type": "file",
            }
        )
    return out


def _available_actions(status: str) -> tuple[list[str], str | None]:
    """(actions, pendingWith) for the HITL review screen. 'actions' is
    only non-empty while the case is actually paused at a HITL gate the
    instructor/advisor can resolve, matching interrupt_before=[...] in
    phase-3/state_graph/academic_integrity/graph.py."""
    if status == "under_review":
        return _COMMITTEE_ACTIONS, None
    if status == "appeal_under_review":
        return _FINAL_ACTIONS, None
    if status == "reported":
        return [], "system (evidence is still being gathered)"
    if status == "awaiting_appeal":
        return [], "student (awaiting their appeal)"
    return [], None  # closed — nothing pending


def _case_with_names(case: dict) -> dict:
    """Join student/course names onto a raw IntegrityCases row."""
    student = db.get_student(case["student_id"])
    course = db.get_course(case["course_id"])
    return {
        **case,
        "student_name": student["name"] if student else f"Student #{case['student_id']}",
        "course_name": course["title"] if course else f"Course #{case['course_id']}",
    }


def _reported_by_name(instructor_id: int) -> str:
    instructor = db.get_instructor(instructor_id)
    return instructor["name"] if instructor else f"Instructor #{instructor_id}"


def _severity_or_pending(severity: str | None) -> str:
    # analyze_severity runs synchronously right after gather_evidence inside
    # start_case()/resume_case(), so severity is populated by the time a
    # case is readable in almost every real state; 'pending' only shows up
    # for a case whose graph run is still literally in flight.
    return severity or "pending"


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
    search: str = "",
    status: str = "all",
    user: CurrentUser = Depends(require_role("student", "instructor", "advisor", "dept_head")),
):
    """instructor/integrity/integrity.js reads: id, student, course,
    severity, status, reportedLabel — a flat, human-readable row, never
    the raw case_id/student_id/course_id/created_at this used to return."""
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
    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = db.query_all(sql, tuple(params))

    out = []
    for c in rows:
        joined = _case_with_names(c)
        out.append(
            {
                "id": c["case_id"],
                "student": joined["student_name"],
                "course": joined["course_name"],
                "severity": _severity_or_pending(c["severity"]),
                "status": c["status"],
                "reportedLabel": _fmt_label(c["created_at"]),
            }
        )

    if search.strip():
        q = search.strip().lower()
        out = [
            r
            for r in out
            if q in r["student"].lower() or q in r["course"].lower() or q in str(r["id"])
        ]
    return out


@router.get("/cases/hitl")
def list_hitl_cases(
    user: CurrentUser = Depends(require_role("instructor", "advisor")),
):
    """instructor/hitl/hitl.js reads: {needsAttention, awaitingAppeal,
    committeeDecisions}, each a list of cards with id, student, course,
    severity, workflowStep, evidenceCount, policyMatchPct, and
    (optionally) pendingWith. Registered BEFORE /cases/{case_id} below so
    FastAPI/Starlette matches this literal path first — otherwise
    "hitl" gets swallowed by {case_id}'s int parser and 422s."""
    rows = db.query_all(
        "SELECT * FROM IntegrityCases WHERE status IN ('under_review','awaiting_appeal','appeal_under_review') "
        "ORDER BY updated_at DESC"
    )

    def _card(c: dict) -> dict:
        joined = _case_with_names(c)
        evidence_count = db.query_one(
            "SELECT COUNT(*) AS n FROM IntegrityEvidence WHERE case_id = ?", (c["case_id"],)
        )["n"]
        _actions, pending_with = _available_actions(c["status"])
        card = {
            "id": c["case_id"],
            "student": joined["student_name"],
            "course": joined["course_name"],
            "severity": _severity_or_pending(c["severity"]),
            "workflowStep": _WORKFLOW_LABEL_BY_KEY.get(c["status"], c["status"]),
            "evidenceCount": evidence_count,
            "policyMatchPct": round(c["similarity_score"]) if c["similarity_score"] is not None else "—",
        }
        if pending_with:
            card["pendingWith"] = pending_with
        return card

    needs_attention = [_card(c) for c in rows if c["status"] in ("under_review", "appeal_under_review")]
    awaiting_appeal = [_card(c) for c in rows if c["status"] == "awaiting_appeal"]
    committee_decisions_rows = db.query_all(
        """SELECT DISTINCT ic.* FROM IntegrityCases ic
           JOIN IntegrityDecisions d ON d.case_id = ic.case_id
           WHERE d.decision_stage = 'committee_review'
           ORDER BY ic.updated_at DESC"""
    )
    committee_decisions = [_card(c) for c in committee_decisions_rows]

    return {
        "needsAttention": needs_attention,
        "awaitingAppeal": awaiting_appeal,
        "committeeDecisions": committee_decisions,
    }


@router.get("/cases/{case_id}")
def get_case(case_id: int, user: CurrentUser = Depends(require_role("student", "instructor", "advisor", "dept_head"))):
    """Serves BOTH getIntegrityCase() (case-details.js) and getHITLCase()
    (hitl-review.js) — the frontend's shared/api.js calls the same GET
    /academic-integrity/cases/{id} for both. The two pages read different
    field names for the same underlying case, so this response is a
    superset carrying both shapes rather than picking one and breaking
    the other consumer:
      case-details.js:  id, student, course, reportedBy, reportedOnLabel,
                         status, incidentType, description, evidence[],
                         aiAssessment{severity,policyMatchPct,reasoning},
                         workflow{steps,currentStep}
      hitl-review.js:    id, severity, student, course, workflowStep,
                         policyMatchPct, availableActions[], pendingWith,
                         details{incidentType,description,evidence[],
                         aiAssessment{reasoning}}
    """
    case = _case_row(case_id)
    if user.role == "student" and case["student_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Not your case.")

    joined = _case_with_names(case)
    evidence_rows = db.query_all("SELECT * FROM IntegrityEvidence WHERE case_id = ?", (case_id,))
    evidence = _map_evidence(evidence_rows)

    # The AI's actual reasoning (severity_rationale) is only ever held in
    # the LangGraph checkpoint, never written to IntegrityCases — read it
    # from the graph's own state rather than leaving it blank. If the
    # graph state can't be loaded (e.g. GEMINI_API_KEY not configured in
    # this environment), degrade to "not yet available" instead of 500ing
    # the whole case page over a missing rationale.
    rationale = None
    try:
        state = get_case_state(case_id)
        if state:
            rationale = state.get("severity_rationale")
    except Exception:
        rationale = None

    severity = _severity_or_pending(case["severity"])
    policy_match_pct = round(case["similarity_score"]) if case["similarity_score"] is not None else None

    ai_assessment = None
    if case["severity"] is not None:
        ai_assessment = {
            "severity": severity,
            "policyMatchPct": policy_match_pct if policy_match_pct is not None else 0,
            "reasoning": rationale or "AI reasoning not available for this case.",
        }

    workflow = {"steps": _WORKFLOW_STEPS, "currentStep": case["status"]}

    actions, pending_with = _available_actions(case["status"])

    incident_type = "—"  # no incident-type column exists in IntegrityCases (see schema.sql);
    # honest placeholder rather than a guessed category, same convention
    # instructor_router.py uses for course "code"/"term".

    details = {
        "incidentType": incident_type,
        "description": case["description"],
        "evidence": evidence,
        "aiAssessment": {"reasoning": rationale or "AI reasoning not available for this case."} if ai_assessment else None,
    }

    return {
        "id": case["case_id"],
        "status": case["status"],
        "severity": severity,
        "student": joined["student_name"],
        "course": joined["course_name"],
        "reportedBy": _reported_by_name(case["reported_by"]),
        "reportedOnLabel": _fmt_label(case["created_at"]),
        "incidentType": incident_type,
        "description": case["description"],
        "evidence": evidence,
        "aiAssessment": ai_assessment,
        "workflow": workflow,
        "workflowStep": _WORKFLOW_LABEL_BY_KEY.get(case["status"], case["status"]),
        "policyMatchPct": policy_match_pct if policy_match_pct is not None else "—",
        "availableActions": actions,
        "pendingWith": pending_with,
        "details": details,
    }


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