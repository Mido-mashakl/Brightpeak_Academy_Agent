"""
assessment_bridge.py — Connects Track Recommendation to the REAL,
already-built Adaptive Assessment graph (state_graph/adaptive_assessment)
instead of pausing and expecting a bare score handed in directly.

FIXED (CRITICAL BUG #2): nodes_intake.awaiting_diagnostic and
nodes_hitl.targeted_assessment_node used to call `interrupt(...)` and
treat whatever the caller resumed with as a finished score, e.g.
`{"Introduction to Python": 76}` — that's a fake assessment, not an
integration with the adaptive question-asking system that already exists
in this project (select_next_question / evaluate_answer /
check_mastery_or_continue in adaptive_assessment/graph.py).

The real hand-off implemented here:

    Track Recommendation (prepare node, no interrupt yet)
        -> create DiagnosticAssessments row  (assessment_id)
        -> start_adaptive_session(assessment_id, student_id, subject)
               -> adaptive_assessment.graph.start_session(...)
               -> runs the REAL adaptive loop up to its own
                  interrupt_before=["await_answer"] pause
    Track Recommendation (await node) -> interrupt(): now genuinely
        waiting on the Adaptive Assessment session, not a fabricated score.
        The platform drives THAT session directly — possibly many
        question/answer round trips — via
        adaptive_assessment.graph.resume_session(session_id, ...) until it
        reaches log_and_close (status='completed'). Only then does the
        platform resume Track Recommendation's interrupt (with a plain
        completion signal, no score attached).
    Track Recommendation (await node, on resume)
        -> get_completed_score(assessment_id) reads the REAL final_score
           computed by adaptive_assessment.graph.finalize()/record_grade()
           out of AssessmentSessions
        -> persists it into DiagnosticAssessments via db.complete_diagnostic

`assessment_id` (DiagnosticAssessments PK) IS reused as the Adaptive
Assessment `session_id` on purpose: both represent "one assessment
attempt" 1:1, so no separate mapping table is needed to join them.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import db

ADAPTIVE_ASSESSMENT_DIR = Path(__file__).resolve().parent.parent
if str(ADAPTIVE_ASSESSMENT_DIR) not in sys.path:
    sys.path.insert(0, str(ADAPTIVE_ASSESSMENT_DIR))

from adaptive_assessment import graph as aa_graph  # noqa: E402


class SubjectNotACourseError(Exception):
    """Raised when a `subject` string can't be matched to a real
    Courses.title — never invent a course_id."""


def start_adaptive_session(assessment_id: int, student_id: int, subject: str) -> dict[str, Any]:
    """Hands off to the real Adaptive Assessment graph. Runs it up to its
    own first pause (interrupt_before=['await_answer']) and returns
    whatever state it paused with — the caller (platform / demo driver)
    is responsible for actually answering that session's questions
    directly against adaptive_assessment.graph, exactly like any other
    Adaptive Assessment session."""
    course_id = db.get_course_id_by_title(subject)
    if course_id is None:
        raise SubjectNotACourseError(
            f"'{subject}' does not match any Courses.title — cannot start an "
            f"Adaptive Assessment session for it."
        )
    return aa_graph.start_session({
        "session_id": assessment_id,
        "student_id": student_id,
        "course_id": course_id,
        "topic": subject,
    })


def get_completed_score(assessment_id: int) -> float:
    """Reads the REAL final score the Adaptive Assessment graph computed
    for this session (0.0-1.0 running_score, scaled to a 0-100
    percentage to match Grades/Attendance/DiagnosticAssessments
    convention elsewhere in this graph). Raises if the session hasn't
    actually finished yet — never fabricates a number."""
    result = db.get_adaptive_session_result(assessment_id)
    if result is None:
        raise RuntimeError(f"No AssessmentSessions row for session_id={assessment_id}.")
    if result["status"] != "completed":
        raise RuntimeError(
            f"Adaptive Assessment session {assessment_id} is not completed yet "
            f"(status={result['status']!r}) — resume/finish it before completing "
            f"the diagnostic."
        )
    final_score = result["final_score"] or 0.0
    return round(final_score * 100, 1)


def adaptive_thread_id(assessment_id: int) -> str:
    return aa_graph.thread_id_for_session(assessment_id)