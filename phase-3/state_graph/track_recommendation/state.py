"""
state.py — Shared State definition for the Track Recommendation graph.

Every node module imports `State` from here so there's a single
source of truth for what keys exist in the graph's state.
"""
from typing import TypedDict, Optional, List, Dict, Any

CONFIDENCE_GAP_THRESHOLD = 5.0  # points; below this the top-2 are "too close to call"


class State(TypedDict, total=False):
    student_id: int
    student_name: str
    recommendation_id: int
    thread_id: str

    candidate_tracks: List[str]
    grades: Dict[str, float]
    attendance: Dict[str, float]
    missing_courses: List[str]

    track_requirements: Dict[str, Dict[str, Any]]
    rag_pending_tracks: List[str]
    rag_failed_track: Optional[str]
    force_broken_track: Optional[str]   # demo-only: simulate a bad document
    open_ticket_id: Optional[int]

    tot_result: Dict[str, Any]
    ranked: List[Any]
    confidence_gap: float
    policy_ok: bool
    decision_clear: bool
    force_hitl_review: bool

    advisor_decision: Optional[Dict[str, Any]]
    targeted_subject: Optional[str]

    final_track: Optional[str]
    final_confidence: Optional[float]

    log: List[str]

    # --- idempotency guards (prevent duplicate DB writes on node re-entry
    #     after an interrupt() resume — see nodes_intake.py / nodes_hitl.py) ---
    pending_diagnostic_ids: Dict[str, int]
    pending_assessment_id: Optional[int]
    prior_evidence_count: Optional[int]


def log_step(state: State, msg: str) -> dict:
    """Append a line to state['log'] and echo it to stdout for the demo."""
    print(f"  · {msg}")
    return {"log": state.get("log", []) + [msg]}