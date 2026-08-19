"""
Faculty Hiring — LangGraph state schema.

Graph flow (defined in graph.py):
    START
    → ingest_cv_batch
    → parse_and_validate
    → score_cv_against_qualifications
    → awaiting_more_applications          ← waits here (interrupt_before)

    On NEW CV event (same thread, incoming_batch = [new_candidate_only]):
    awaiting_more_applications
    → ingest_cv_batch → parse_and_validate → score_cv_against_qualifications
    → awaiting_more_applications

    On DEADLINE event (deadline_reached command):
    awaiting_more_applications
    → generate_shortlist
    → hitl_dept_head_review               ← HITL pause (interrupt_before)

    HITL outcomes (resume from hitl_dept_head_review):
      hire       → record_hiring_decision → END
      interview  → schedule_interview → await_interview_result → hitl_dept_head_review
      rescore    → score_cv_against_qualifications (selected ids only)
                 → generate_shortlist → hitl_dept_head_review

Design notes:
- `candidates` uses Annotated[..., add] reducer so it accumulates across events.
  Each new CV upload appends its CandidateResult to this list without touching old entries.
- `incoming_batch` does NOT use add: it is replaced wholesale each event (initial batch,
  then a single new CV, then cleared to []). This is what prevents reprocessing old CVs.
- `hitl_decisions` uses add because the Dept Head may act multiple times (rescore → review again).
- `job_id` doubles as the thread_id source: thread_id = f"faculty-hiring-{job_id}".
- Pydantic BaseModel (not TypedDict) because LLM output and platform HITL input are both
  untrusted entry points — validation on write matters here.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class CandidateResult(BaseModel):
    """One candidate's complete processing result, stored in state.candidates."""
    candidate_id: Optional[int] = None       # set once the DB row is created
    name: str
    raw_cv_text: str
    parsed_profile: Optional[dict] = None    # None until parse_and_validate runs
    parse_status: Literal[
        "pending", "parsed", "failed", "missing_fields"
    ] = "pending"
    score: Optional[float] = None            # None until scored
    score_id: Optional[int] = None           # FK to CandidateScores
    breakdown: Optional[dict] = None         # per-qualification breakdown dict
    parse_error: Optional[str] = None        # populated if parse failed


class HiringDecisionRecord(BaseModel):
    """One Dept Head action at the HITL node."""
    decision_id: Optional[int] = None
    decided_by: str
    decision: Literal["hire", "reject", "interview", "rescore"]
    candidate_ids: list[int] = Field(default_factory=list)  # relevant for rescore/interview
    notes: Optional[str] = None


class InterviewRecord(BaseModel):
    """One scheduled or completed interview."""
    interview_id: Optional[int] = None
    candidate_id: int
    status: Literal["scheduled", "completed", "cancelled"] = "scheduled"
    result: Optional[Literal["pass", "fail", "pending"]] = None
    score: Optional[float] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Main state
# ---------------------------------------------------------------------------

class FacultyHiringState(BaseModel):
    # --- job identity ---
    job_id: Optional[int] = None           # set when the job posting is created
    job_title: str = ""
    qualifications: list[str] = Field(default_factory=list)  # from JobPostings.qualifications

    # --- DYNAMIC: current batch being processed right now ---
    # Does NOT use add reducer — replaced each event so old CVs are never reprocessed.
    incoming_batch: list[CandidateResult] = Field(default_factory=list)

    # --- PERSISTENT: archive of ALL processed candidates across all events ---
    # Uses add reducer so each new CV appends without overwriting old entries.
    candidates: Annotated[list[CandidateResult], add] = Field(default_factory=list)

    # --- workflow control ---
    # Set by external events before graph.invoke/resume:
    #   "new_cv"          → process incoming_batch only
    #   "deadline_reached" → move to generate_shortlist
    #   None              → initial batch processing
    pending_event: Optional[Literal["new_cv", "deadline_reached"]] = None

    # IDs of candidates to re-score (populated by HITL rescore action)
    rescore_candidate_ids: list[int] = Field(default_factory=list)

    # --- RAG: hiring policy context ---
    policy_context: Optional[str] = None

    # --- shortlist ---
    current_shortlist_id: Optional[int] = None

    # --- HITL decisions (Dept Head, may happen multiple times) ---
    hitl_decisions: Annotated[list[HiringDecisionRecord], add] = Field(default_factory=list)

    # --- interviews ---
    interviews: Annotated[list[InterviewRecord], add] = Field(default_factory=list)

    # --- workflow status (mirrors JobPostings.status) ---
    status: Literal[
        "ingesting",
        "parsing",
        "scoring",
        "awaiting_more_applications",
        "generating_shortlist",
        "hitl_review",
        "interviewing",
        "completed",
    ] = "ingesting"

    # --- failure / ticket path (separate from HITL) ---
    last_error: Optional[str] = None
    open_ticket_id: Optional[int] = None

    # --- bookkeeping ---
    thread_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True