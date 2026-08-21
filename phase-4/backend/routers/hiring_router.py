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
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.graph_loader import start_job, add_cv, close_applications

router = APIRouter(prefix="/hiring", tags=["hiring"])


# ---------------------------------------------------------------------------
# Request schemas — mirror the dict shapes the phase-3 functions expect
# ---------------------------------------------------------------------------

class InitialCV(BaseModel):
    name: str
    raw_cv_text: str


class StartJobRequest(BaseModel):
    job_id: int
    job_title: str
    qualifications: list[str] = []
    initial_cvs: list[InitialCV] = []


class AddCVRequest(BaseModel):
    name: str
    raw_cv_text: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/jobs")
def create_job(body: StartJobRequest):
    """Admin/Dept Head opens a new job posting (can include an initial CV batch)."""
    try:
        job_input = body.model_dump()
        result = start_job(job_input)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs/{job_id}/cv")
def submit_cv(job_id: int, body: AddCVRequest):
    """A candidate uploads a CV for an already-open job.
    Resumes the existing graph thread for this job_id — does not start a new one."""
    try:
        result = add_cv(job_id=job_id, name=body.name, raw_cv_text=body.raw_cv_text)
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