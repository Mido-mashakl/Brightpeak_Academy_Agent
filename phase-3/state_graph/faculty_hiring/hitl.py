"""
Faculty Hiring — Human-in-the-Loop node type.

The actual pause happens because graph.py compiles the graph with
interrupt_before=["hitl_dept_head_review", "await_interview_result"].
LangGraph stops BEFORE running these nodes, persists the checkpoint,
and returns control to the caller (the platform).

This module's responsibilities:
  1. When the graph arrives at the HITL node, write state visible to the
     admin in the platform (update JobPostings.status to 'hitl_review').
  2. Provide the functions the platform calls when the Dept Head acts.
     Each action writes a HiringDecisions row, updates state, and resumes.

Three possible Dept Head actions:
  A) hire       → record_hiring_decision → END
  B) interview  → schedule_interview → await_interview_result
  C) rescore    → re-score selected candidates → generate_shortlist → HITL again

This is intentionally different from tickets.py:
  HITL   = expected, planned decision gate (agent is not allowed to decide alone)
  Ticket = unexpected technical failure (tool error, validation failure)
"""

from __future__ import annotations

from datetime import datetime

from mcp_server import database as db
from mcp_server import roles
from .state import FacultyHiringState, HiringDecisionRecord, InterviewRecord
from .checkpointing import thread_id_for_job


class NotAuthorized(PermissionError):
    """Raised when a Dept Head action is attempted without an authenticated
    dept_head session. The AI must never make the final hiring decision, and
    the platform must never let an unauthenticated request make it either."""


def _require_dept_head() -> None:
    if not roles.is_dept_head():
        raise NotAuthorized(
            "This action requires an authenticated dept_head session. "
            "Call authenticate_staff(role='dept_head', dept_head_id=..., passcode=...) first."
        )


def _current_dept_head() -> tuple[int, str]:
    """Returns (dept_head_id, display_label) for the authenticated session.

    Never trusts a caller-supplied name — HiringDecisions.decided_by must
    reflect the real, authenticated DeptHeads row, not free text.
    """
    _require_dept_head()
    dept_head_id = roles.SESSION.dept_head_id
    row = db.get_dept_head(dept_head_id)
    name = row["name"] if row else f"dept_head_{dept_head_id}"
    return dept_head_id, f"{name} (id={dept_head_id})"


# ---------------------------------------------------------------------------
# Node function — runs once when the graph arrives at the HITL node
# (before the interrupt fires and control returns to the platform)
# ---------------------------------------------------------------------------

def dept_head_review_hitl(state: FacultyHiringState) -> dict:
    """
    Marks the job as pending HITL review so the platform's admin surface
    can show the pending task.  The real pause is the interrupt_before in
    graph.py — this node just surfaces the state to the admin.
    """
    if state.job_id:
        db.execute(
            "UPDATE JobPostings SET status = 'open', updated_at = ? WHERE job_id = ?",
            (datetime.utcnow().isoformat(), state.job_id),
        )
    return {"status": "hitl_review"}


# ---------------------------------------------------------------------------
# Called by the platform's admin surface when the Dept Head acts
# ---------------------------------------------------------------------------

def submit_hire_decision(
    job_id: int,
    candidate_id: int,
    notes: str | None = None,
):
    """
    Dept Head chose: Hire.
    Writes a HiringDecisions row and resumes the graph to record_hiring_decision.

    The reviewer's identity comes from the authenticated session
    (roles.authenticate(role='dept_head', dept_head_id=..., passcode=...)),
    never from a caller-supplied string.
    """
    dept_head_id, decided_by = _current_dept_head()
    from .graph import resume_job  # local import avoids circular import

    db.execute(
        """INSERT INTO HiringDecisions
               (job_id, candidate_id, dept_head_id, decided_by, decision, notes)
           VALUES (?, ?, ?, ?, 'hire', ?)""",
        (job_id, candidate_id, dept_head_id, decided_by, notes),
    )
    record = HiringDecisionRecord(
        decided_by=decided_by,
        decision="hire",
        candidate_ids=[candidate_id],
        notes=notes,
    )
    return resume_job(job_id, update={"hitl_decisions": [record]})


def submit_interview_request(
    job_id: int,
    candidate_id: int,
    notes: str | None = None,
):
    """
    Dept Head chose: Request Interview.
    Creates an Interviews row (status='scheduled') and resumes to schedule_interview.
    """
    dept_head_id, decided_by = _current_dept_head()
    from .graph import resume_job

    row = db.query_one(
        """INSERT INTO Interviews (job_id, candidate_id, status)
           VALUES (?, ?, 'scheduled') RETURNING interview_id""",
        (job_id, candidate_id),
    )
    interview_id = row["interview_id"] if row else None

    db.execute(
        """INSERT INTO HiringDecisions
               (job_id, candidate_id, dept_head_id, decided_by, decision, notes)
           VALUES (?, ?, ?, ?, 'interview', ?)""",
        (job_id, candidate_id, dept_head_id, decided_by, notes),
    )
    record = HiringDecisionRecord(
        decided_by=decided_by,
        decision="interview",
        candidate_ids=[candidate_id],
        notes=notes,
    )
    interview = InterviewRecord(
        interview_id=interview_id,
        candidate_id=candidate_id,
        status="scheduled",
    )
    return resume_job(
        job_id,
        update={
            "hitl_decisions": [record],
            "interviews": [interview],
        },
    )


def submit_rescore_request(
    job_id: int,
    candidate_ids: list[int],
    reason: str | None = None,
):
    """
    Dept Head chose: Re-score selected candidates.
    Only the named candidate_ids will be re-scored; others keep their current scores.

    Payload:
        {
            "type": "rescore",
            "candidate_ids": [12, 15],
            "reason": "Teaching experience should have higher importance"
        }
    """
    dept_head_id, decided_by = _current_dept_head()
    from .graph import resume_job

    db.execute(
        """INSERT INTO HiringDecisions
               (job_id, candidate_id, dept_head_id, decided_by, decision, notes)
           VALUES (?, ?, ?, ?, 'rescore', ?)""",
        (job_id, 0, dept_head_id, decided_by, reason),  # candidate_id=0 = "multiple/see notes"
    )
    record = HiringDecisionRecord(
        decided_by=decided_by,
        decision="rescore",
        candidate_ids=candidate_ids,
        notes=reason,
    )
    return resume_job(
        job_id,
        update={
            "hitl_decisions": [record],
            "rescore_candidate_ids": candidate_ids,
        },
    )


def submit_interview_result(
    job_id: int,
    interview_id: int,
    candidate_id: int,
    result: str,            # "pass" | "fail"
    score: float | None = None,
    notes: str | None = None,
):
    """
    Interview result arrives.  Update Interviews row and resume the graph
    from await_interview_result back to hitl_dept_head_review.
    """
    from .graph import resume_job

    db.execute(
        """UPDATE Interviews
           SET status = 'completed', result = ?, score = ?, notes = ?, updated_at = ?
           WHERE interview_id = ?""",
        (result, score, notes, datetime.utcnow().isoformat(), interview_id),
    )
    interview = InterviewRecord(
        interview_id=interview_id,
        candidate_id=candidate_id,
        status="completed",
        result=result,
        score=score,
        notes=notes,
    )
    return resume_job(job_id, update={"interviews": [interview]})