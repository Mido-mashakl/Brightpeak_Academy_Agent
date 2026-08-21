"""
Adaptive Assessment & Mastery Evaluation — graph definition.

Locatable concerns (per Final Project requirements):
- Graph/cycle definitions: build_adaptive_assessment_graph() below.
- Checkpointing: checkpointing.py (get_checkpointer, thread_id helper).
- HITL node type: hitl.py (used by flag_for_review).
- Ticket/failure path: tickets.py (used by the error-handling wrapper below).

Real cycle: select_next_question <-> check_mastery_or_continue. A session
keeps asking questions (adapting difficulty each time) until either it hits
max_questions or reaches mastery_threshold with enough evidence -- this is
not knowable in advance, so it cannot be a fixed-length DAG.

Real wait: await_answer pauses for however long the student takes to
answer (one sitting or several) -- resumed only when the platform posts
the student's answer via update_state.

Real branch outside the model's control: flag_for_review only fires when
finalize() finds the score within +/-5% of mastery_threshold (see hitl.py
for the written rationale) -- an admin, not the agent, makes the borderline
call, and record_grade must use whatever the admin decided.

Design note: `answers` is a PLAIN list (not an Annotated/add reducer field)
on purpose, unlike academic_integrity's `evidence`/`decisions`. Each node
that appends returns state.answers + [new_item] itself. This was a
deliberate choice over a reducer so a future "retake" path could clear the
list by returning []; the current graph doesn't reset it, but keeping the
field plain avoids locking that option out.
"""

from __future__ import annotations

from datetime import datetime

from langgraph.graph import StateGraph, END

from .state import AdaptiveAssessmentState, AnsweredQuestion
from .checkpointing import get_checkpointer, thread_id_for_session
from .hitl import flag_for_review_hitl
from .tickets import with_ticket_on_failure

import sys as _sys
from pathlib import Path as _Path
MCP_SERVER_DIR = _Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(MCP_SERVER_DIR) not in _sys.path:
    _sys.path.insert(0, str(MCP_SERVER_DIR))

from mcp_server import database as db
from mcp_server import tools as mcp_tools

MIN_QUESTIONS_BEFORE_EARLY_MASTERY = 3
FLAG_MARGIN = 0.05  # +/-5% of mastery_threshold triggers flag_for_review


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@with_ticket_on_failure(source_graph="adaptive_assessment", failure_type="session_start_failed")
def start_assessment(state: AdaptiveAssessmentState) -> dict:
    """Deterministic setup — no LLM call needed here (Week 5: only
    judgment-heavy nodes need one). Assumes the AssessmentSessions row was
    already created by the platform when the student started (same pattern
    as academic_integrity: the parent row exists before the graph runs)."""
    db.execute(
        """INSERT OR IGNORE INTO AssessmentSessions
           (session_id, student_id, course_id, topic, status)
           VALUES (?, ?, ?, ?, 'in_progress')""",
        (state.session_id, state.student_id, state.course_id, state.topic),
    )
    return {"status": "in_progress"}


@with_ticket_on_failure(source_graph="adaptive_assessment", failure_type="question_selection_failed")
def select_next_question(state: AdaptiveAssessmentState) -> dict:
    """Task decomposition addition: breaks the topic into subskills and
    picks the next untested one, at a difficulty adapted to running_score."""
    subskill, difficulty, question_text, expected_answer, options = mcp_tools.decompose_and_pick_question(
    topic=state.topic, subskills_covered=state.subskills_covered,
    current_difficulty=state.current_difficulty, running_score=state.running_score,
    )
    pending = AnsweredQuestion(
    question_text=question_text, difficulty=difficulty, student_answer="",
    expected_answer=expected_answer, options=options,   
    )
    return {
        "pending_question": pending,
        "current_difficulty": difficulty,
        "subskills_covered": state.subskills_covered + [subskill],
    }


def await_answer(state: AdaptiveAssessmentState) -> dict:
    """No-op node: the real wait is the interrupt configured in graph compile
    below. The platform's user surface calls graph.update_state(...) with
    pending_question.student_answer filled in, then graph.invoke(None, config)."""
    return {}


@with_ticket_on_failure(source_graph="adaptive_assessment", failure_type="answer_evaluation_failed")
def evaluate_answer(state: AdaptiveAssessmentState) -> dict:
    """Constrained ReAct addition: a Python dispatcher (not the LLM
    narrating a format) picks between two whitelisted grading actions --
    see mcp_tools.evaluate_answer_constrained_react."""
    q = state.pending_question
    is_correct, score, rationale = mcp_tools.evaluate_answer_constrained_react(
        question_text=q.question_text, difficulty=q.difficulty, student_answer=q.student_answer,
        expected_answer=q.expected_answer or "", options=q.options,
    )
    import json
    db.execute(
        """INSERT INTO AssessmentAnswers
           (session_id, question_text, difficulty, student_answer, expected_answer, is_correct, score_awarded, options)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (state.session_id, q.question_text, q.difficulty, q.student_answer, q.expected_answer, int(is_correct), score,
         json.dumps(q.options) if q.options else None),
    )
    answered = AnsweredQuestion(
    question_text=q.question_text, difficulty=q.difficulty, student_answer=q.student_answer,
    expected_answer=q.expected_answer, options=q.options,   
    is_correct=is_correct, score_awarded=score,
    )
    new_answers = state.answers + [answered]
    running_score = sum(a.score_awarded for a in new_answers) / len(new_answers)
    return {"answers": new_answers, "pending_question": None, "running_score": running_score}


def check_mastery_or_continue(state: AdaptiveAssessmentState) -> str:
    """Pure routing function — the real cycle lives here: keeps sending the
    graph back to select_next_question until max_questions is hit or the
    student has shown mastery over enough evidence."""
    asked = len(state.answers)
    if asked >= state.max_questions:
        return "finalize"
    if asked >= MIN_QUESTIONS_BEFORE_EARLY_MASTERY and state.running_score >= state.mastery_threshold:
        return "finalize"
    return "select_next_question"


def _mastery_bucket(score: float, mastery_threshold: float) -> str:
    """Single source of truth for score -> mastery_level, used by both
    finalize() and record_grade() so an admin's adjust_score decision is
    bucketed by the exact same rule as the graph's own first pass."""
    if score >= mastery_threshold:
        return "mastered"
    if score >= mastery_threshold - 0.20:
        return "proficient"
    if score >= 0.40:
        return "developing"
    return "novice"


@with_ticket_on_failure(source_graph="adaptive_assessment", failure_type="finalize_failed")
def finalize(state: AdaptiveAssessmentState) -> dict:
    """Deterministic: computes the outcome and decides whether the score is
    too close to call automatically (see FLAG_MARGIN, written rationale in
    hitl.py). The AssessmentSessions status write for a flagged case has to
    happen HERE, not inside flag_for_review_hitl -- that node is a no-op
    (interrupt_before means it never runs until AFTER an admin resumes it),
    same fix as Week 5's own await_manager example."""
    score = state.running_score
    level = _mastery_bucket(score, state.mastery_threshold)

    flagged = abs(score - state.mastery_threshold) <= FLAG_MARGIN
    reason = None
    if flagged:
        reason = (
            f"final_score {score:.2f} is within {FLAG_MARGIN:.0%} of the "
            f"{state.mastery_threshold:.0%} mastery threshold"
        )
        db.execute(
            "UPDATE AssessmentSessions SET status = 'flagged_for_review' WHERE session_id = ?",
            (state.session_id,),
        )
    return {"final_score": score, "mastery_level": level, "flagged": flagged, "flag_reason": reason}


def route_after_finalize(state: AdaptiveAssessmentState) -> str:
    return "flag_for_review" if state.flagged else "record_grade"


def route_after_review(state: AdaptiveAssessmentState) -> str:
    # Every review outcome (approve / adjust_score / retake) proceeds to
    # record_grade -- record_grade itself reads review_decision /
    # adjusted_score and must act on whichever the admin actually chose.
    return "record_grade"


@with_ticket_on_failure(source_graph="adaptive_assessment", failure_type="record_grade_failed")
def record_grade(state: AdaptiveAssessmentState) -> dict:
    final_score = state.final_score
    mastery_level = state.mastery_level
    if state.review_decision == "adjust_score" and state.adjusted_score is not None:
        final_score = state.adjusted_score
        mastery_level = _mastery_bucket(final_score, state.mastery_threshold)

    db.execute(
        "UPDATE AssessmentSessions SET mastery_level = ?, final_score = ? WHERE session_id = ?",
        (mastery_level, final_score, state.session_id),
    )
    return {"final_score": final_score, "mastery_level": mastery_level}


def log_and_close(state: AdaptiveAssessmentState) -> dict:
    db.execute(
        "UPDATE AssessmentSessions SET status = 'completed', completed_at = ? WHERE session_id = ?",
        (datetime.utcnow().isoformat(), state.session_id),
    )
    return {"status": "completed"}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_adaptive_assessment_graph():
    builder = StateGraph(AdaptiveAssessmentState)

    builder.add_node("start_assessment", start_assessment)
    builder.add_node("select_next_question", select_next_question)
    builder.add_node("await_answer", await_answer)
    builder.add_node("evaluate_answer", evaluate_answer)
    builder.add_node("finalize", finalize)
    builder.add_node("flag_for_review", flag_for_review_hitl)  # HITL
    builder.add_node("record_grade", record_grade)
    builder.add_node("log_and_close", log_and_close)

    builder.set_entry_point("start_assessment")
    builder.add_edge("start_assessment", "select_next_question")
    builder.add_edge("select_next_question", "await_answer")
    builder.add_edge("await_answer", "evaluate_answer")
    builder.add_conditional_edges(
        "evaluate_answer",
        check_mastery_or_continue,
        {"select_next_question": "select_next_question", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "finalize",
        route_after_finalize,
        {"flag_for_review": "flag_for_review", "record_grade": "record_grade"},
    )
    builder.add_conditional_edges(
        "flag_for_review",
        route_after_review,
        {"record_grade": "record_grade"},
    )
    builder.add_edge("record_grade", "log_and_close")
    builder.add_edge("log_and_close", END)

    return builder.compile(
        checkpointer=get_checkpointer(),
        interrupt_before=["await_answer", "flag_for_review"],
    )


def start_session(session_input: dict):
    """Entry point the platform calls when a student starts an assessment."""
    graph = build_adaptive_assessment_graph()
    config = {"configurable": {"thread_id": thread_id_for_session(session_input["session_id"])}}
    return graph.invoke(session_input, config=config)


def resume_session(session_id: int, update: dict | None = None):
    """Entry point the platform calls after the student answers a question
    (await_answer), an admin resolves a HITL review (flag_for_review), or a
    ticket is resolved."""
    graph = build_adaptive_assessment_graph()
    config = {"configurable": {"thread_id": thread_id_for_session(session_id)}}
    if update:
        graph.update_state(config, update)
    return graph.invoke(None, config=config)