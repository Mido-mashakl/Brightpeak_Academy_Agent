"""
Run this from inside your phase-3/ folder, with your real .env / GEMINI_API_KEY
and venv active:

    cd phase-3
    python demo_interactive_academic_integrity.py

This is NOT a scripted demo -- nothing is pre-written. You play the
instructor: you decide the committee_review verdict, you type the
student's appeal in your own words, and you decide the final_decision
verdict. The graph genuinely pauses at both HITL gates and will not move
past them until you answer.

This is also the reference for your teammate building platform/: the four
calls this script makes (start_case, graph.get_state, submit_committee_decision,
submit_final_decision) are exactly what the platform's admin backend needs
to call. Nothing about the graph itself changes for the platform -- it just
calls these same functions from a web request instead of from input().
"""
import sys
from pathlib import Path

PHASE3_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PHASE3_DIR))
sys.path.insert(0, str(PHASE3_DIR / "mcp_server"))

import mcp_server.database as db  # noqa: E402
import state_graph.academic_integrity.graph as g  # noqa: E402
from state_graph.academic_integrity.checkpointing import get_checkpointer as _aic_get_ckpt
_aic_get_ckpt()  # ensures checkpoints/writes tables exist before cleanup() touches them
from state_graph.academic_integrity.hitl import (  # noqa: E402
    submit_committee_decision,
    submit_final_decision,
)

TEST_STUDENT, TEST_COURSE, TEST_INSTRUCTOR = 9997, 9997, 9997
CASE_ID = 8501


def seed():
    db.execute(
        "INSERT OR IGNORE INTO Students (student_id,name,email,level) VALUES (?,?,?,?)",
        (TEST_STUDENT, "Test Student", "test-student2@brightpeak.test", "Beginner"),
    )
    db.execute(
        "INSERT OR IGNORE INTO Courses (course_id,title,category,duration) VALUES (?,?,?,?)",
        (TEST_COURSE, "Test Course", "test", 10),
    )
    db.execute(
        "INSERT OR IGNORE INTO Instructors (instructor_id,name,email) VALUES (?,?,?)",
        (TEST_INSTRUCTOR, "Test Instructor", "instructor-test2@brightpeak.test"),
    )


def cleanup():
    db.execute("DELETE FROM IntegrityDecisions WHERE case_id = ?", (CASE_ID,))
    db.execute("DELETE FROM IntegrityAppeals WHERE case_id = ?", (CASE_ID,))
    db.execute("DELETE FROM IntegrityEvidence WHERE case_id = ?", (CASE_ID,))
    db.execute("DELETE FROM Tickets WHERE source_id = ?", (CASE_ID,))
    db.execute("DELETE FROM IntegrityCases WHERE case_id = ?", (CASE_ID,))
    thread_id = g.thread_id_for_case(CASE_ID)
    db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
    db.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
    db.execute("DELETE FROM Students WHERE student_id = ?", (TEST_STUDENT,))
    db.execute("DELETE FROM Courses WHERE course_id = ?", (TEST_COURSE,))
    db.execute("DELETE FROM Instructors WHERE instructor_id = ?", (TEST_INSTRUCTOR,))
    print("[cleanup] test rows + checkpoints removed")


def ask_committee_decision():
    while True:
        d = input(
            "Your decision as committee [uphold / dismiss / request_more_evidence]: "
        ).strip().lower()
        if d in ("uphold", "dismiss", "request_more_evidence"):
            return d
        print("Type exactly one of: uphold, dismiss, request_more_evidence")


def ask_final_decision():
    while True:
        d = input(
            "Your final decision as committee [uphold / reduce_penalty / dismiss]: "
        ).strip().lower()
        if d in ("uphold", "reduce_penalty", "dismiss"):
            return d
        print("Type exactly one of: uphold, reduce_penalty, dismiss")


def main():
    cleanup()
    seed()
    try:
        description = input(
            "Instructor's description of what was found [Two submissions nearly identical]: "
        ).strip() or "Two submissions nearly identical"
        raw_score = input("Similarity score 0.0-1.0 [0.85]: ").strip() or "0.85"
        similarity_score = float(raw_score)

        db.execute(
            """INSERT INTO IntegrityCases
               (case_id, student_id, course_id, reported_by, description, similarity_score)
               VALUES (?,?,?,?,?,?)""",
            (CASE_ID, TEST_STUDENT, TEST_COURSE, TEST_INSTRUCTOR, description, similarity_score),
        )

        result = g.start_case({
            "case_id": CASE_ID, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
            "reported_by": TEST_INSTRUCTOR, "description": description,
            "similarity_score": similarity_score,
        })

        graph = g.build_academic_integrity_graph()
        config = {"configurable": {"thread_id": g.thread_id_for_case(CASE_ID)}}
        state = graph.get_state(config)

        print(f"\n--- analyze_severity (RAG-grounded) ---")
        print("severity:  ", state.values.get("severity"))
        print("rationale: ", state.values.get("severity_rationale"))

        if state.values.get("status") == "closed":
            print("\nMinor severity -> auto warning, case closed. Nothing more to demo here.")
            return

        # --- HITL #1: committee_review ---
        print("\n--- HITL: needs_committee_review ---")
        print("The graph is genuinely paused here -- it will not proceed")
        print("until you (the committee) submit a decision.")
        decision = ask_committee_decision()
        result = submit_committee_decision(
            CASE_ID, decided_by="live_demo_committee", decision=decision,
            notes="decided live during demo",
        )

        while result.get("status") == "reported" or (
            result.get("evidence") and decision == "request_more_evidence"
        ):
            # cycle: request_more_evidence looped back through gather_evidence -> analyze_severity
            print("\n--- looped back through gather_evidence -> analyze_severity ---")
            print("severity:  ", result.get("severity"))
            decision = ask_committee_decision()
            result = submit_committee_decision(
                CASE_ID, decided_by="live_demo_committee", decision=decision,
                notes="decided live during demo (loop)",
            )
            if decision != "request_more_evidence":
                break

        if result.get("status") == "closed":
            print("\n=== case closed at committee_review (dismissed) ===")
            return

        # --- await_appeal: real student input ---
        print("\n--- await_appeal ---")
        print("The case is now with the student. Type the appeal argument")
        print("you (playing the student) want to submit:")
        appeal_argument = input("Appeal argument: ").strip() or "I did not copy this work."
        result = graph.update_state(config, {"appeal_argument": appeal_argument})
        result = graph.invoke(None, config=config)

        print("\n--- evaluate_appeal (Tree of Thoughts) ---")
        for i, opt in enumerate(result.get("appeal_options_considered", []), start=1):
            print(f"  candidate {i}: {opt}")
        print("chosen ruling:", result.get("appeal_evaluation"))

        # --- HITL #2: committee_final_decision ---
        print("\n--- HITL: committee_final_decision ---")
        print("The graph is genuinely paused here -- it will not proceed")
        print("until you (the committee) submit the final decision.")
        final_decision = ask_final_decision()
        result = submit_final_decision(
            CASE_ID, decided_by="live_demo_committee", decision=final_decision,
            notes="final decision from live demo",
        )

        print("\n=== final result ===")
        print("status:", result.get("status"))
        print("decisions logged:", [d.decision if hasattr(d, "decision") else d.get("decision")
                                     for d in result.get("decisions", [])])
    finally:
        cleanup()


if __name__ == "__main__":
    main()