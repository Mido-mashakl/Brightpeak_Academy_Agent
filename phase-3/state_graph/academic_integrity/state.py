"""
Academic Integrity Investigation & Appeal — LangGraph state schema.

Nodes (defined later in graph.py) that read/write this state:
    gather_evidence -> analyze_severity (RAG) -> route_by_severity
        -> minor_warning
        -> needs_committee_review (HITL #1)
    -> notify_student -> await_appeal -> evaluate_appeal (Tree of Thoughts)
        -> committee_final_decision (HITL #2) -> log_and_close

Design notes:
- We use a Pydantic BaseModel, not a plain TypedDict, because this state is
  written to by an LLM (analyze_severity, evaluate_appeal) and by an admin
  through the platform's HITL UI (committee decisions) -- both are untrusted
  entry points per the Week 5 material ("validate where untrusted data
  enters"), unlike the internal-only research-loop example.
- `evidence` and `decisions` use Annotated[..., add] reducers because more
  than one node call can append to them over the life of a single case
  (gather_evidence can run more than once if new evidence shows up during
  committee review; both HITL nodes append a decision row).
- `case_id` doubles as the LangGraph thread_id source (see checkpointing.py):
  thread_id = f"academic-integrity-{case_id}".
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    evidence_id: Optional[int] = None  # set once written to IntegrityEvidence
    evidence_type: str  # e.g. "similarity_report", "instructor_note", "submission_diff"
    content: str


class DecisionRecord(BaseModel):
    decision_id: Optional[int] = None  # set once written to IntegrityDecisions
    decision_stage: Literal["committee_review", "final_decision"]
    decided_by: str  # admin username/id from the platform, never the agent
    decision: str  # e.g. "uphold", "dismiss", "reduce_penalty"
    notes: Optional[str] = None


class AcademicIntegrityState(BaseModel):
    # --- case identity (mirrors IntegrityCases columns) ---
    case_id: Optional[int] = None  # None until the case row is first inserted
    student_id: int
    course_id: int
    assignment_id: Optional[int] = None
    reported_by: int  # instructor_id
    description: str

    # --- evidence & severity ---
    evidence: Annotated[list[EvidenceItem], add] = Field(default_factory=list)
    similarity_score: Optional[float] = None
    severity: Optional[Literal["minor", "major", "severe"]] = None
    severity_rationale: Optional[str] = None  # RAG-grounded explanation, for audit

    # --- routing / workflow status ---
    status: Literal[
        "reported",
        "under_review",
        "awaiting_appeal",
        "appeal_under_review",
        "closed",
    ] = "reported"

    # --- appeal path ---
    appeal_argument: Optional[str] = None
    appeal_submitted: bool = False
    appeal_evaluation: Optional[str] = None  # Tree of Thoughts output summary
    appeal_options_considered: list[str] = Field(default_factory=list)

    # --- HITL decisions (both committee_review and final_decision land here) ---
    decisions: Annotated[list[DecisionRecord], add] = Field(default_factory=list)

    # --- failure / ticket path (kept separate from HITL) ---
    last_error: Optional[str] = None
    open_ticket_id: Optional[int] = None

    # --- bookkeeping ---
    thread_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True