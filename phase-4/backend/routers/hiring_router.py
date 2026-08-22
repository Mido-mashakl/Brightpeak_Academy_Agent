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


def _candidate_to_frontend_shape(row: dict, latest_score: dict | None) -> dict:
    breakdown = json.loads(latest_score["breakdown"]) if latest_score and latest_score.get("breakdown") else []
    parsed = json.loads(row["parsed_profile"]) if row.get("parsed_profile") else {}
    status = "parsing"
    if row["parse_status"] == "failed":
        status = "parsing"  # a Ticket will exist for this — see Tickets table
    elif latest_score:
        status = "ai_scored"

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
        "decision": None,  # filled in once the HITL decision endpoints exist (see NOTE below)
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
    """Candidates for one job posting, each with its latest score (if scored)."""
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
        out.append(_candidate_to_frontend_shape(c, latest_score))
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
        out.append(_candidate_to_frontend_shape(c, latest_score))
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
    job = db.query_one("SELECT status FROM JobPostings WHERE job_id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "open":
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


# NOTE: Dept Head decision endpoints (hire / interview / rescore) need the
# dept head to be authenticated first (see mcp_server/roles.py) — those
# belong in admin_router.py once auth is wired up (step 8 of the plan),
# not here. Deliberately left out of hiring_router.py on purpose.
# candidates.html's decision panel (submitHiringDecision in
# department-head-api.js) is still on localStorage mock until that lands.