"""
Run this from inside your phase-3/ folder (same level as mcp_server/, db/,
state_graph/), with your real .env (real GEMINI_API_KEY) and your venv
active:

    cd phase-3
    python test_adaptive_assessment_graph.py

Scenarios:
  1. happy_path()  - REAL Gemini calls throughout, proves the adaptive
     cycle, await_answer pausing across a fresh process object, etc.
  2. ticket_path()  - forces a tool failure -> real Tickets row -> resolve
     -> resumes from checkpoint.
  3. hitl_path()   - NEW. Monkeypatches both LLM-backed tools with fixed,
     deterministic outputs (no Gemini calls, no quota spent) so the running
     score lands EXACTLY on mastery_threshold, guaranteeing finalize()
     sets flagged=True and the graph actually pauses at flag_for_review.
     Then plays the admin side: submit_review_decision(..., "adjust_score")
     and shows record_grade picks up the admin's number, not the agent's.
     This is the run to use as your HITL demo evidence.

Every scenario inserts test rows under student_id/course_id 9999 and
cleans up everything it inserted at the end, even if a step fails.
"""
import sys
from pathlib import Path

PHASE3_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PHASE3_DIR))
sys.path.insert(0, str(PHASE3_DIR / "mcp_server"))

import mcp_server.database as db  # noqa: E402
import mcp_server.tools as mcp_tools  # noqa: E402
import state_graph.adaptive_assessment.graph as g  # noqa: E402
from state_graph.adaptive_assessment.hitl import submit_review_decision  # noqa: E402
from state_graph.adaptive_assessment.tickets import resolve_ticket  # noqa: E402

TEST_STUDENT, TEST_COURSE = 9999, 9999
SESSION_A, SESSION_B, SESSION_C = 8001, 8002, 8003


def seed():
    db.execute(
        "INSERT OR IGNORE INTO Students (student_id,name,email,level) VALUES (?,?,?,?)",
        (TEST_STUDENT, "Test Student", "test-student@brightpeak.test", "Beginner"),
    )
    db.execute(
        "INSERT OR IGNORE INTO Courses (course_id,title,category,duration) VALUES (?,?,?,?)",
        (TEST_COURSE, "Test Course", "test", 10),
    )


def cleanup():
    for sid in (SESSION_A, SESSION_B, SESSION_C):
        db.execute("DELETE FROM AssessmentAnswers WHERE session_id = ?", (sid,))
        db.execute("DELETE FROM Tickets WHERE source_id = ?", (sid,))
        db.execute("DELETE FROM AssessmentSessions WHERE session_id = ?", (sid,))
        # IMPORTANT: also clear the LangGraph checkpointer's own tables for
        # these thread_ids. Without this, a run that crashes partway through
        # (e.g. a 429 from Gemini) leaves a stale checkpoint behind; the next
        # run's start_session() then RESUMES that old checkpoint instead of
        # starting fresh, silently accumulating extra answers across runs
        # (confirmed: 8 -> 9 -> 10 on repeated runs without this).
        thread_id = g.thread_id_for_session(sid)
        db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        db.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
    db.execute("DELETE FROM Students WHERE student_id = ?", (TEST_STUDENT,))
    db.execute("DELETE FROM Courses WHERE course_id = ?", (TEST_COURSE,))
    print("[cleanup] test rows + checkpoints removed")


def answer_until_done(config, graph, canned_answers):
    """Drives await_answer -> evaluate_answer -> (cycle or finalize) using a
    list of canned student answers, one per question asked."""
    i = 0
    while True:
        state = graph.get_state(config)
        if not state.next:
            return state.values
        if state.next == ("await_answer",):
            answer_text = canned_answers[min(i, len(canned_answers) - 1)]
            i += 1
            pending = state.values["pending_question"]
            pending = pending.model_copy(update={"student_answer": answer_text})
            graph.update_state(config, {"pending_question": pending})
            result = graph.invoke(None, config=config)
        else:
            result = graph.invoke(None, config=config)
        if graph.get_state(config).next and graph.get_state(config).next[0] == "flag_for_review":
            return result


def happy_path():
    print("\n=== 1) start_session (real Gemini calls inside select_next_question) ===")
    g.start_session({
        "session_id": SESSION_A, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
        "topic": "Python basics",
    })
    graph = g.build_adaptive_assessment_graph()
    config = {"configurable": {"thread_id": g.thread_id_for_session(SESSION_A)}}
    print("paused at:", graph.get_state(config).next, "(should be await_answer)")

    canned = [
        "A list is a mutable ordered collection in Python.",
        "def defines a function.",
        "A dictionary stores key-value pairs.",
        "range(5) yields 0 through 4.",
        "try/except handles exceptions.",
    ]
    result = answer_until_done(config, graph, canned)
    print("status:", result.get("status"), "| questions asked:", len(result.get("answers", [])),
          "| running_score:", round(result.get("running_score", 0), 2))
    print("paused/finished at:", graph.get_state(config).next)

    if graph.get_state(config).next == ("flag_for_review",):
        print("\n=== borderline score -> admin resolves HITL ===")
        result = submit_review_decision(SESSION_A, reviewed_by="admin_test",
                                         decision="approve", notes="Looks right, approving.")
        print("status:", result.get("status"), "| final_score:", result.get("final_score"),
              "| mastery_level:", result.get("mastery_level"))
    else:
        print("(not borderline this run -- record_grade ran automatically, no HITL needed)")

    print("paused at:", graph.get_state(config).next, "(should be empty tuple = finished)")


def ticket_path():
    print("\n=== forcing a real tool failure to test the ticket path ===")
    real_pick = mcp_tools.decompose_and_pick_question
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated transient tool failure")
        return real_pick(*a, **kw)

    mcp_tools.decompose_and_pick_question = flaky
    try:
        g.start_session({
            "session_id": SESSION_B, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
            "topic": "Python basics",
        })
        print("ERROR: expected a failure, none happened")
    except RuntimeError:
        print("node failed as expected -- checking for a real Tickets row")
    finally:
        mcp_tools.decompose_and_pick_question = real_pick

    row = db.query_one("SELECT * FROM Tickets WHERE source_id = ?", (SESSION_B,))
    assert row is not None, "no ticket was created!"
    print("ticket:", dict(row))

    print("\n=== resolving the ticket -> resumes from checkpoint (real Gemini retry) ===")
    result = resolve_ticket(row["ticket_id"], "Retried after transient error.")
    print("status:", result.get("status"), "| pending question set:",
          result.get("pending_question") is not None)


def hitl_path():
    """Deterministic HITL demo: no real Gemini calls (both LLM-backed tools
    are monkeypatched), guarantees the score lands exactly on
    mastery_threshold so finalize() flags it and the graph genuinely pauses
    at flag_for_review. Then plays the admin side and proves record_grade
    picks up the admin's adjusted_score, not the agent's own number."""
    print("\n=== 3) forcing a borderline score to trigger flag_for_review (HITL) ===")

    real_pick = mcp_tools.decompose_and_pick_question
    real_eval = mcp_tools.evaluate_answer_constrained_react

    q_counter = {"n": 0}

    def fixed_pick(*a, **kw):
        q_counter["n"] += 1
        return f"subskill_{q_counter['n']}", "medium", f"Fixed test question #{q_counter['n']}", "expected answer"
    # 3 scores whose average is exactly 0.75 == mastery_threshold, so
    # finalize()'s abs(score - threshold) <= FLAG_MARGIN (0.05) is True.
    fixed_scores = [0.8, 0.7, 0.75]
    score_counter = {"n": 0}

    def fixed_eval(*a, **kw):
        s = fixed_scores[min(score_counter["n"], len(fixed_scores) - 1)]
        score_counter["n"] += 1
        return (s >= 0.5, s, "deterministic test score")

    mcp_tools.decompose_and_pick_question = fixed_pick
    mcp_tools.evaluate_answer_constrained_react = fixed_eval
    try:
        g.start_session({
            "session_id": SESSION_C, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
            "topic": "Python basics",
        })
        graph = g.build_adaptive_assessment_graph()
        config = {"configurable": {"thread_id": g.thread_id_for_session(SESSION_C)}}

        canned = ["answer 1", "answer 2", "answer 3"]  # text doesn't matter, scoring is mocked
        result = answer_until_done(config, graph, canned)
        print("running_score:", round(result.get("running_score", 0), 2),
              "| questions asked:", len(result.get("answers", [])))
        print("paused at:", graph.get_state(config).next, "(should be ('flag_for_review',))")
        assert graph.get_state(config).next == ("flag_for_review",), \
            "expected the graph to pause at flag_for_review -- HITL did not trigger!"
    finally:
        mcp_tools.decompose_and_pick_question = real_pick
        mcp_tools.evaluate_answer_constrained_react = real_eval

    print("\n=== admin resolves the borderline case, overriding the score ===")
    result = submit_review_decision(
        SESSION_C, reviewed_by="admin_test", decision="adjust_score",
        notes="Reviewed manually, raising to reflect partial credit.",
        adjusted_score=0.90,
    )
    print("status:", result.get("status"), "| final_score:", result.get("final_score"),
          "(should be 0.9, the admin's number, not the agent's 0.75)",
          "| mastery_level:", result.get("mastery_level"))
    assert result.get("final_score") == 0.90, "record_grade did not pick up the admin's adjusted_score!"
    print("paused at:", g.build_adaptive_assessment_graph().get_state(config).next,
          "(should be empty tuple = finished)")


if __name__ == "__main__":
    cleanup()  # defensive: wipe any stale checkpoints left by earlier crashed runs first
    seed()
    try:
        happy_path()
        ticket_path()
        hitl_path()
        print("\n✅ all checks passed")
    except Exception:
        import traceback
        traceback.print_exc()
        print("\n❌ something failed -- see traceback above")
    finally:
        cleanup()