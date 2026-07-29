"""
validation.py
=============
=== CONCERN: Defensive tool design ===
Server-side validation helpers that run independently of whatever the
client's JSON-schema layer already checked.  The golden rule: never
trust a caller-supplied value when the DB holds the ground truth.

All helpers return (is_valid: bool, error_message: str | None).
"""

from __future__ import annotations

import database as db


def validate_score(score: float, assignment_id: int) -> tuple[bool, str | None]:
    """Confirm `score` is in [0, assignment.max_score].

    Re-fetches max_score from the DB instead of relying on anything the
    caller provided.
    """
    assignment = db.get_assignment(assignment_id)
    if assignment is None:
        return False, f"No assignment with id {assignment_id}"
    if not (0 <= score <= assignment["max_score"]):
        return False, (
            f"score must be between 0 and {assignment['max_score']} "
            f"for assignment {assignment_id}."
        )
    return True, None


def validate_percentage(percentage: float) -> tuple[bool, str | None]:
    """Confirm `percentage` is in [0, 100]."""
    if not (0 <= percentage <= 100):
        return False, "percentage must be between 0 and 100."
    return True, None


def validate_enrollment_status(status: str) -> tuple[bool, str | None]:
    """Confirm `status` is one of the accepted enrollment state strings."""
    allowed = ("active", "completed", "dropped")
    if status not in allowed:
        return False, f"status must be one of {allowed}."
    return True, None


def scholarship_would_change(student_id: int, assignment_id: int, new_score: float) -> tuple[bool, float, float]:
    """Return (crosses_threshold, avg_before, avg_after).

    Simulates the new overall average without touching the DB, so the
    caller can decide whether to elicit confirmation before committing.
    Threshold is 90 % (Scholarship Policy).
    """
    avg_before = db.get_overall_average(student_id)
    grades = db.get_grades(student_id)
    assignment = db.get_assignment(assignment_id)

    pct_list = [
        (g["score"] / g["max_score"]) * 100
        for g in grades
        if g["assignment_id"] != assignment_id
    ]
    pct_list.append((new_score / assignment["max_score"]) * 100)
    avg_after = sum(pct_list) / len(pct_list)

    crosses = avg_before is not None and ((avg_before >= 90) != (avg_after >= 90))
    return crosses, (avg_before or 0.0), avg_after


def is_large_override(student_id: int, assignment_id: int, new_score: float, threshold: float = 15.0) -> bool:
    """Return True if this overwrites an existing grade by more than `threshold` points."""
    existing = db.get_existing_grade(student_id, assignment_id)
    if existing is None:
        return False
    return abs(existing["score"] - new_score) > threshold