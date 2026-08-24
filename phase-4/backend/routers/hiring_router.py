"""
hiring_router.py
=================
The Public / Candidate surface (from your teammate's diagram, section 7).
No auth needed here — a candidate is not a platform user, just an
Application with an ID.

Every function this router calls (start_job, add_cv, close_applications)
already exists in phase-3/state_graph/faculty_hiring/graph.py and is
already documented there as "Entry point the platform calls when..." —
we are not writing new graph logic, just exposing it over HTTP.

Read endpoints (GET /jobs, GET /candidates) are plain reads straight off
JobPostings / Candidates / CandidateScores — they don't touch the graph at
all, so they carry no auth requirement either. Only the Dept Head DECISION
endpoints (hire / interview / rescore in hitl.py) require an authenticated
dept_head session — those aren't wired yet, see the note at the bottom.
"""

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, Form
from pydantic import BaseModel

from core.graph_loader import start_job, add_cv, close_applications
from state_graph.faculty_hiring.cv_text_extraction import (
    extract_cv_text,
    UnsupportedCVFormat,
)
import mcp_server.database as db

router = APIRouter(prefix="/hiring", tags=["hiring"])


# ---------------------------------------------------------------------------
# Request schemas — mirror the dict shapes the phase-3 functions expect
# ---------------------------------------------------------------------------

class InitialCV(BaseModel):
    name: str
    raw_cv_text: str


class StartJobRequest(BaseModel):
    # job_id is NOT accepted from the client — JobPostings.job_id is
    # AUTOINCREMENT (see db/schema.sql). Letting the client pick it let
    # start_job() run against a job_id that never existed as a row.
    job_title: str
    department: str | None = None
    qualifications: list[str] = []
    application_deadline: str | None = None
    initial_cvs: list[InitialCV] = []


# ---------------------------------------------------------------------------
# Response shaping — the Dept Head frontend (jobs.js / candidates.js) was
# built against a mocked shape (see shared/department-head-api.js) before
# the real endpoints existed. Kept identical here on purpose so that file
# only needs its fetch bodies swapped in, not its callers.
# ---------------------------------------------------------------------------

def _job_to_frontend_shape(row: dict) -> dict:
    return {
        "id": row["job_id"],
        "title": row["title"],
        "department": row.get("department"),
        "qualifications": json.loads(row["qualifications"]) if row["qualifications"] else [],
        # Only 'open' accepts new CVs (see add_cv's ValueError below) — every
        # other status reads as "closed" to the UI, which only knows two states.
        "status": "open" if row["status"] == "open" else "closed",
        "closedManually": row["status"] != "open",
        "deadline": row.get("application_deadline"),
        "postedDate": row.get("created_at"),
    }


def _candidate_to_frontend_shape(row: dict, latest_score: dict | None, latest_decision: dict | None = None) -> dict:
    breakdown = json.loads(latest_score["breakdown"]) if latest_score and latest_score.get("breakdown") else []
    parsed = json.loads(row["parsed_profile"]) if row.get("parsed_profile") else {}
    status = "parsing"
    if row["parse_status"] == "failed":
        status = "parsing"  # a Ticket will exist for this — see Tickets table
    elif latest_score:
        status = "ai_scored"

    decision = None
    # A recorded HiringDecisions row (hire/interview/rescore, from the
    # decision endpoint below) always wins over the plain "ai_scored"
    # state above — without this, candidates.js's UI would keep showing
    # "AI Scored" forever after a Dept Head decision was actually made,
    # even though the graph really did resume and record it.
    if latest_decision:
        status = {
            "hire": "hired",
            "interview": "interview",
            "rescore": "rescore_requested",
        }.get(latest_decision["decision"], status)
        decision = {
            "action": latest_decision["decision"],
            "by": latest_decision["decided_by"],
            "note": latest_decision.get("notes"),
            "at": latest_decision.get("decided_at"),
        }

    return {
        "id": row["candidate_id"],
        "jobId": row["job_id"],
        "name": row["name"],
        "university": parsed.get("education") or "Pending parse",
        "experienceYears": parsed.get("years_experience"),
        "skills": parsed.get("skills", []),
        "teachingExperienceYears": parsed.get("teaching_experience_years"),
        "aiScore": latest_score["score"] if latest_score else None,
        "status": status,
        "aiRecommendation": None,
        "keyStrengths": [b.get("evidence") for b in breakdown if b.get("status") == "PASS" and b.get("evidence")],
        "decision": decision,
        "source": "upload",
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/jobs")
def list_jobs():
    """Dept Head hiring board — every job posting, newest first."""
    rows = db.query_all("SELECT * FROM JobPostings ORDER BY created_at DESC")
    return [_job_to_frontend_shape(r) for r in rows]


@router.get("/jobs/{job_id}/candidates")
def list_job_candidates(job_id: int):
    """Candidates for one job posting, each with its latest score (if scored)
    and its latest recorded Dept Head decision (if any)."""
    candidates = db.query_all(
        "SELECT * FROM Candidates WHERE job_id = ? ORDER BY submitted_at DESC", (job_id,)
    )
    out = []
    for c in candidates:
        latest_score = db.query_one(
            """SELECT * FROM CandidateScores WHERE candidate_id = ?
               ORDER BY scored_at DESC LIMIT 1""",
            (c["candidate_id"],),
        )
        latest_decision = db.query_one(
            """SELECT * FROM HiringDecisions WHERE candidate_id = ?
               ORDER BY decided_at DESC LIMIT 1""",
            (c["candidate_id"],),
        )
        out.append(_candidate_to_frontend_shape(c, latest_score, latest_decision))
    return out


@router.get("/candidates")
def list_all_candidates():
    """Every candidate across every job — used for the hiring board's
    per-card application counts (jobs.html calls this with no job filter)."""
    candidates = db.query_all("SELECT * FROM Candidates ORDER BY submitted_at DESC")
    out = []
    for c in candidates:
        latest_score = db.query_one(
            """SELECT * FROM CandidateScores WHERE candidate_id = ?
               ORDER BY scored_at DESC LIMIT 1""",
            (c["candidate_id"],),
        )
        latest_decision = db.query_one(
            """SELECT * FROM HiringDecisions WHERE candidate_id = ?
               ORDER BY decided_at DESC LIMIT 1""",
            (c["candidate_id"],),
        )
        out.append(_candidate_to_frontend_shape(c, latest_score, latest_decision))
    return out


@router.post("/jobs")
def create_job(body: StartJobRequest):
    """Admin/Dept Head opens a new job posting (can include an initial CV batch).

    Creates the JobPostings row FIRST (same order as demo_faculty_hiring.py
    step 1), then runs the graph via start_job() using the job_id the DB
    just generated. Without this insert, start_job() still runs the graph
    fine (checkpoints, RAG, etc. all work), but there is no JobPostings row
    for it to belong to — so close_applications()'s later
    `UPDATE JobPostings SET status=... WHERE job_id=?` silently updates zero
    rows, and any page that lists JobPostings will never show this job.
    """
    try:
        row = db.query_one(
            """INSERT INTO JobPostings (title, department, qualifications, application_deadline, status)
               VALUES (?, ?, ?, ?, 'open') RETURNING job_id""",
            (
                body.job_title,
                body.department,
                json.dumps(body.qualifications),
                body.application_deadline,
            ),
        )
        job_id = row["job_id"]

        job_input = {
            "job_id": job_id,
            "job_title": body.job_title,
            "qualifications": body.qualifications,
            "initial_cvs": [cv.model_dump() for cv in body.initial_cvs],
        }
        result = start_job(job_input)
        return {"status": "ok", "job_id": job_id, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs/{job_id}/cv")
async def submit_cv(job_id: int, cv_file: UploadFile, candidate_name: str = Form(None)):
    """A candidate uploads a CV file for an already-open job. Extracts plain
    text from the file first (cv_text_extraction.py), then resumes the
    existing graph thread for this job_id — does not start a new one."""
    job = db.query_one(
        "SELECT status, application_deadline FROM JobPostings WHERE job_id = ?", (job_id,)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # application_deadline was previously "display/validation only" (see
    # db/schema.sql's own comment) — nothing actually stopped an upload
    # after the deadline passed unless someone had already clicked "Close
    # Applications" (status='closed'). Enforced here for real now, using
    # the same 409/APPLICATIONS_CLOSED shape jobs.js already handles, so
    # no frontend change is needed.
    deadline_passed = False
    if job["application_deadline"]:
        try:
            deadline_passed = datetime.fromisoformat(job["application_deadline"]) < datetime.utcnow()
        except ValueError:
            deadline_passed = False

    if job["status"] != "open" or deadline_passed:
        # Matches jobs.js's APPLICATIONS_CLOSED handling.
        raise HTTPException(status_code=409, detail="APPLICATIONS_CLOSED")

    try:
        file_bytes = await cv_file.read()
        raw_cv_text = extract_cv_text(file_bytes, cv_file.filename)
    except UnsupportedCVFormat as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    name = candidate_name or cv_file.filename.rsplit(".", 1)[0]

    try:
        result = add_cv(job_id=job_id, name=name, raw_cv_text=raw_cv_text)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs/{job_id}/close")
def close_job(job_id: int):
    """Admin clicks 'Close Applications / Generate Shortlist'."""
    try:
        result = close_applications(job_id)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Dept Head decision endpoint — hire / interview / rescore.
# Matches the exact shape department-head-api.js already documents and
# calls (POST /hiring/candidates/{candidate_id}/decision), so only that
# file's fetch needs to swap from mock to real, not its callers.
#
# TWO independent gates, both required:
#   1. core.auth.require_role("dept_head") — the FastAPI-level check so an
#      unauthenticated caller can't even reach this endpoint.
#   2. mcp_server.roles.authenticate(...) — phase-3's own, stricter,
#      passcode-based gate (see hitl.py's NotAuthorized / _require_dept_head),
#      re-run per request here because roles.SESSION is a process-global
#      singleton (not per-request) — see the note in DecisionRequest below.
# ---------------------------------------------------------------------------

from fastapi import Depends
from pydantic import Field
from core.auth import require_role, CurrentUser
from core.graph_loader import (
    submit_hire_decision,
    submit_interview_request,
    submit_rescore_request,
)
import mcp_server.roles as roles


class DecisionRequest(BaseModel):
    decision: str  # "hire" | "reject" | "interview" | "rescore"
    notes: str | None = None
    # Bridges to phase-3's existing passcode-gated dept_head auth
    # (mcp_server/roles.py) — that mechanism predates this platform and is
    # deliberately NOT bypassed. Default passcode documented in roles.py's
    # own comments (change before prod): "brightpeak-depthead-2026".
    passcode: str = Field(..., description="Dept Head passcode, per mcp_server/roles.py")


def _candidate_job_id(candidate_id: int) -> int:
    row = db.query_one("SELECT job_id FROM Candidates WHERE candidate_id = ?", (candidate_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return row["job_id"]


@router.post("/candidates/{candidate_id}/decision")
def submit_candidate_decision(
    candidate_id: int,
    body: DecisionRequest,
    user: CurrentUser = Depends(require_role("dept_head")),
):
    job_id = _candidate_job_id(candidate_id)

    # KNOWN LIMITATION (see roles.py): SESSION is one global object shared by
    # every concurrent request in this process, not per-request/per-user
    # state. Re-authenticating right before the action minimizes the window
    # where a second request from a different user could interleave, but
    # does not eliminate it under real concurrency. Flagged in the final
    # report as a genuine architectural gap inherited from phase-3, not
    # something safe to silently paper over here.
    ok, message = roles.authenticate(role="dept_head", dept_head_id=user.user_id, passcode=body.passcode)
    if not ok:
        raise HTTPException(status_code=401, detail=message)

    try:
        if body.decision == "hire":
            result = submit_hire_decision(job_id=job_id, candidate_id=candidate_id, notes=body.notes)
        elif body.decision == "interview":
            result = submit_interview_request(job_id=job_id, candidate_id=candidate_id, notes=body.notes)
        elif body.decision == "rescore":
            result = submit_rescore_request(job_id=job_id, candidate_ids=[candidate_id], reason=body.notes)
        elif body.decision == "reject":
            # No analog exists in phase-3/state_graph/faculty_hiring/hitl.py —
            # only hire / interview / rescore are real graph actions (see
            # HiringDecisions.decision CHECK constraint in db/schema.sql).
            # Reporting this honestly instead of inventing a fake accepted
            # state; see the final report's Remaining TODOs.
            raise HTTPException(
                status_code=501,
                detail="'reject' has no corresponding action in the Faculty Hiring graph yet "
                       "(only hire/interview/rescore exist in hitl.py). Needs a graph-side addition, "
                       "not something safe to fake at the router level.",
            )
        else:
            raise HTTPException(status_code=400, detail="decision must be hire|reject|interview|rescore.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph failed to resume: {e}")
    finally:
        roles.SESSION.reset()

    return {"status": "ok", "candidate_id": candidate_id, "result": dict(result) if result else None}