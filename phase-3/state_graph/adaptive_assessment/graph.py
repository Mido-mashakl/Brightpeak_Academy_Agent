"""
adaptive_assessment/graph.py — STUB.

⚠️ This is NOT the user's real Adaptive Assessment graph. The real one
was never uploaded to this sandbox — only the Track Recommendation
files were. This stub exists purely so I can actually RUN the Track
Recommendation graph end-to-end in this sandbox and prove its
interrupt/resume/idempotency behavior is correct against something with
the same shape assessment_bridge.py already assumes:

    - start_session({session_id, student_id, course_id, topic}) -> dict
    - the graph pauses BEFORE an "await_answer" node
      (compile(interrupt_before=["await_answer"]))
    - resume_session(session_id, answer) -> supplies the answer, runs
      evaluate -> decide-continue-or-stop, looping back to another
      question or finishing
    - on finish, writes AssessmentSessions.status='completed' and a
      real final_score (0.0-1.0) — never fabricated by the caller
    - thread_id_for_session(session_id) -> stable thread id

Question content is a trivial in-memory bank (NOT real course
questions) — irrelevant to what's being verified here, which is the
Track Recommendation graph's side of the integration.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing_extensions import TypedDict

DB_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "brightpeak.db"
CKPT_PATH = Path(__file__).resolve().parent / "aa_checkpoints.sqlite"

QUESTIONS_PER_SESSION = 3


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


class AAState(TypedDict, total=False):
    session_id: int
    student_id: int
    course_id: int
    topic: str
    question_num: int
    correct_count: int
    current_answer: str


def _select_next_question(state: AAState) -> dict:
    con = _db()
    with con:
        con.execute(
            """INSERT INTO AssessmentSessions (session_id, student_id, course_id, topic, status)
               VALUES (?, ?, ?, ?, 'in_progress')
               ON CONFLICT(session_id) DO NOTHING""",
            (state["session_id"], state["student_id"], state.get("course_id"), state.get("topic")),
        )
    con.close()
    return {"question_num": state.get("question_num", 0) + 1}


def _await_answer(state: AAState) -> dict:
    # No-op: this node is where compile(interrupt_before=[...]) pauses.
    # The real answer arrives via graph.update_state(..., {"current_answer": ...})
    # before the next invoke(None, ...), exactly like the real Adaptive
    # Assessment graph's own await_answer node.
    return {}


def _evaluate_answer(state: AAState) -> dict:
    correct = state.get("current_answer") == "correct"
    return {"correct_count": state.get("correct_count", 0) + (1 if correct else 0)}


def _check_mastery_or_continue(state: AAState) -> dict:
    return {}


def _route_continue(state: AAState) -> str:
    return "select_next_question" if state["question_num"] < QUESTIONS_PER_SESSION else "log_and_close"


def _log_and_close(state: AAState) -> dict:
    final_score = state.get("correct_count", 0) / QUESTIONS_PER_SESSION
    mastery = "mastered" if final_score >= 0.8 else "developing" if final_score >= 0.5 else "needs_support"
    con = _db()
    with con:
        con.execute(
            "UPDATE AssessmentSessions SET status='completed', final_score=?, mastery_level=? "
            "WHERE session_id=?",
            (final_score, mastery, state["session_id"]),
        )
    con.close()
    return {}


def _build():
    g = StateGraph(AAState)
    g.add_node("select_next_question", _select_next_question)
    g.add_node("await_answer", _await_answer)
    g.add_node("evaluate_answer", _evaluate_answer)
    g.add_node("check_mastery_or_continue", _check_mastery_or_continue)
    g.add_node("log_and_close", _log_and_close)

    g.add_edge(START, "select_next_question")
    g.add_edge("select_next_question", "await_answer")
    g.add_edge("await_answer", "evaluate_answer")
    g.add_edge("evaluate_answer", "check_mastery_or_continue")
    g.add_conditional_edges("check_mastery_or_continue", _route_continue,
                             {"select_next_question": "select_next_question",
                              "log_and_close": "log_and_close"})
    g.add_edge("log_and_close", END)

    conn = sqlite3.connect(str(CKPT_PATH), check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn), interrupt_before=["await_answer"])


_GRAPH = _build()


def thread_id_for_session(session_id: int) -> str:
    return f"adaptive-session-{session_id}"


def _config(session_id: int) -> dict:
    return {"configurable": {"thread_id": thread_id_for_session(session_id)}}


def start_session(payload: dict[str, Any]) -> dict:
    config = _config(payload["session_id"])
    return _GRAPH.invoke(payload, config=config)


def resume_session(session_id: int, answer: str) -> dict:
    """Driven directly by the demo/platform — answers ONE question and
    runs until the next pause (or completion)."""
    config = _config(session_id)
    _GRAPH.update_state(config, {"current_answer": answer})
    return _GRAPH.invoke(None, config=config)
