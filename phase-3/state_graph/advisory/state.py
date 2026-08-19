"""
Student Advisor: Certificate & Scholarship Eligibility — LangGraph state schema.

Nodes (defined later in graph.py) that read/write this state:
    load_profile -> retrieve_policy (RAG) -> decompose_requirements (Task Decomposition)
        -> evaluate_eligibility
            -> [missing info]   -> wait_for_student (HITL-style pause) -> load_profile (loop)
            -> [low confidence] -> human_review (HITL, admin)          -> evaluate_eligibility (loop)
            -> [clear]          -> generate_recommendation -> finalize

Design notes (mirrors phase-3/state_graph/academic_integrity/state.py on purpose, so both
graphs are reviewable with the same mental model):
- Pydantic BaseModel, not a plain TypedDict, because this state is written to by an LLM
  (decompose_requirements, evaluate_eligibility, generate_recommendation) AND by a human
  through the platform's HITL UI (admin decisions, student-supplied info) -- both are
  untrusted entry points, so we want validation on write, not just on read.
- `requirement_checks` and `decisions` use Annotated[..., add] reducers because more than
  one node call can append to them over the life of a single request: evaluate_eligibility
  can run more than once (after new student info arrives, or after an admin asks for more
  detail), and both wait_for_student and human_review can each contribute more than one
  round trip before the request resolves.
- `request_id` doubles as the LangGraph thread_id source (see checkpointing.py):
  thread_id = f"student-advisor-{request_id}".
- `iteration_count` exists purely to cap the evaluate <-> wait_for_student cycle so a
  request that keeps coming back "still missing info" can't loop forever.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field

MAX_EVALUATION_ITERATIONS = 5


class RequirementCheck(BaseModel):
    requirement: str  # one atomic requirement extracted from the policy text
    satisfied: Optional[bool] = None  # None == not yet evaluated
    evidence: Optional[str] = None  # what in the student profile satisfied/failed it
    note: Optional[str] = None


class DecisionRecord(BaseModel):
    decision_id: Optional[int] = None  # set once written to AdvisorDecisions-equivalent log
    decided_by: str  # admin username/id from the platform, never the agent
    decision: Literal["approve", "reject", "request_more_info"]
    notes: Optional[str] = None


class StudentAdvisorState(BaseModel):
    # --- request identity (mirrors CertificateRequests/ScholarshipApplications columns) ---
    request_id: Optional[int] = None  # None until the request row is first inserted
    student_id: int
    request_type: Literal["certificate", "scholarship"]
    course_id: Optional[int] = None  # certificates are usually course-scoped
    purpose: Optional[str] = None  # e.g. "internship application", "need-based aid"

    # --- student profile snapshot (loaded from the existing DB, not re-entered) ---
    student_profile: Optional[dict] = None

    # --- policy (RAG) ---
    policy_text: Optional[str] = None
    policy_source: Optional[str] = None

    # --- requirements (Task Decomposition) & their evaluation ---
    requirement_checks: Annotated[list[RequirementCheck], add] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    confidence: Optional[float] = None  # 0..1, drives the human_review branch

    # --- student round trip ---
    awaiting_student: bool = False
    student_response: Optional[str] = None

    # --- outcome ---
    eligibility_status: Literal[
        "pending", "eligible", "ineligible", "needs_review"
    ] = "pending"
    recommendation: Optional[str] = None

    # --- HITL decisions (admin review) ---
    review_required: bool = False
    decisions: Annotated[list[DecisionRecord], add] = Field(default_factory=list)

    # --- failure / ticket path (kept separate from HITL) ---
    last_error: Optional[str] = None
    open_ticket_id: Optional[int] = None

    # --- workflow status ---
    status: Literal[
        "in_progress",
        "waiting_for_student",
        "waiting_for_admin",
        "failed",
        "completed",
    ] = "in_progress"

    # --- bookkeeping ---
    iteration_count: int = 0
    thread_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True