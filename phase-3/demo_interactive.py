"""
Run this from inside your phase-3/ folder (same as your other test
scripts), with your real .env / GEMINI_API_KEY and venv active:

    cd phase-3
    python demo_interactive.py

This is NOT a scripted demo -- nothing is pre-written. You type real
answers, Gemini generates real questions live, and if the score lands
borderline YOU play the instructor and type a real decision.

This is also the reference for your teammate building platform/: the four
calls this script makes (start_session, graph.get_state, graph.update_state
+ graph.invoke, submit_review_decision) are exactly what the platform's
backend needs to call. Nothing about the graph itself changes for the
platform -- it just calls these same functions from a web request instead
of from input().
"""
import sys
from pathlib import Path

PHASE3_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PHASE3_DIR))
sys.path.insert(0, str(PHASE3_DIR / "mcp_server"))

import mcp_server.database as db  # noqa: E402
import state_graph.adaptive_assessment.graph as g  # noqa: E402
from state_graph.adaptive_assessment.hitl import submit_review_decision  # noqa: E402

TEST_STUDENT, TEST_COURSE = 9999, 9999
SESSION_ID = 8502


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
    db.execute("DELETE FROM AssessmentAnswers WHERE session_id = ?", (SESSION_ID,))
    db.execute("DELETE FROM Tickets WHERE source_id = ?", (SESSION_ID,))
    db.execute("DELETE FROM AssessmentSessions WHERE session_id = ?", (SESSION_ID,))
    thread_id = g.thread_id_for_session(SESSION_ID)
    db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
    db.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
    db.execute("DELETE FROM Students WHERE student_id = ?", (TEST_STUDENT,))
    db.execute("DELETE FROM Courses WHERE course_id = ?", (TEST_COURSE,))
    print("[cleanup] test rows + checkpoints removed")


def ask_admin_decision():
    """Real human input, played by whoever is running this script -- stands
    in for the instructor acting through the platform's HITL screen."""
    while True:
        decision = input(
            "Your decision as instructor [approve / adjust_score / retake]: "
        ).strip().lower()
        if decision in ("approve", "adjust_score", "retake"):
            break
        print("Type exactly one of: approve, adjust_score, retake")

    adjusted_score = None
    if decision == "adjust_score":
        while True:
            raw = input("New score (0.0 - 1.0): ").strip()
            try:
                adjusted_score = float(raw)
                if 0.0 <= adjusted_score <= 1.0:
                    break
            except ValueError:
                pass
            print("Enter a number between 0.0 and 1.0")

    notes = input("Notes (optional, press Enter to skip): ").strip()
    return decision, adjusted_score, notes


def main():
    g.get_checkpointer()
    cleanup()
    seed()
    try:
        topic = input("Topic for this assessment [Python basics]: ").strip() or "Python basics"

        g.start_session({
            "session_id": SESSION_ID, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
            "topic": topic,
        })
        graph = g.build_adaptive_assessment_graph()
        config = {"configurable": {"thread_id": g.thread_id_for_session(SESSION_ID)}}

        q_num = 0
        while True:
            state = graph.get_state(config)
            if not state.next:
                break

            if state.next == ("await_answer",):
                pending = state.values["pending_question"]
                q_num += 1

                print(f"\n--- Question {q_num} ---")
                print("difficulty:", pending.difficulty)
                print("question:  ", pending.question_text)

                if pending.options:
                    letters = ["A", "B", "C", "D"]
                    for letter, opt in zip(letters, pending.options):
                        print(f"  {letter}) {opt}")
                    while True:
                        answer_text = input("Your answer [A/B/C/D]: ").strip().upper()
                        if answer_text in letters[:len(pending.options)]:
                            break
                        print(f"Type one of: {', '.join(letters[:len(pending.options)])}")
                else:
                    answer_text = input("Your answer: ").strip()

                pending = pending.model_copy(update={"student_answer": answer_text})
                graph.update_state(config, {"pending_question": pending})
                graph.invoke(None, config=config)

                latest = graph.get_state(config).values["answers"][-1]
                mark = "CORRECT" if latest.is_correct else "WRONG"
                print(f"result:        {mark}  (score: {latest.score_awarded})")
                if not latest.is_correct:
                    if latest.options and latest.expected_answer in ("A", "B", "C", "D"):
                        idx = "ABCD".index(latest.expected_answer)
                        print(f"correct answer: {latest.expected_answer}) {latest.options[idx]}")
                    else:
                        print("expected answer:", latest.expected_answer)

            elif state.next == ("flag_for_review",):
                values = state.values
                print("\n--- HITL: flag_for_review ---")
                print("flag_reason:      ", values.get("flag_reason"))
                print("running_score:    ", round(values.get("running_score", 0), 3))
                print("mastery_threshold:", values.get("mastery_threshold", 0.75))
                print("The graph is genuinely paused here -- it will not")
                print("proceed until you (the instructor) submit a decision.")

                decision, adjusted_score, notes = ask_admin_decision()
                result = submit_review_decision(
                    SESSION_ID, reviewed_by="live_demo_instructor",
                    decision=decision, adjusted_score=adjusted_score, notes=notes,
                )
                print("\nafter admin intervention:")
                print("final_score:  ", result.get("final_score"))
                print("mastery_level:", result.get("mastery_level"))

            else:
                graph.invoke(None, config=config)

        final_state = graph.get_state(config).values
        print("\n=== final result ===")
        print("status:       ", final_state.get("status"))
        print("final_score:  ", final_state.get("final_score"))
        print("mastery_level:", final_state.get("mastery_level"))
    finally:
        cleanup()


if __name__ == "__main__":
    main()