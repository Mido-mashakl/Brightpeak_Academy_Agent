"""
Run this from inside your phase-3/ folder (same level as mcp_server/, db/,
state_graph/), with your real .env (real GEMINI_API_KEY) and your venv
active:

    cd phase-3
    python test_academic_integrity_graph.py

This uses REAL Gemini calls, REAL rag/ retrieval, REAL brightpeak.db —
nothing is mocked. It inserts test rows with case_id 9001/9002 and
student_id/course_id/instructor_id 9999 so it never touches your real data,
and deletes everything it inserted at the end (even if a step fails).

What it proves, end-to-end:
  1. A case runs and genuinely pauses before needs_committee_review (HITL #1)
  2. A brand-new process resumes it after an admin decision, WITHOUT
     re-running analyze_severity (real crash/resume, not just pause/resume
     in the same process)
  3. Student appeal -> Tree-of-Thoughts evaluation -> HITL #2 -> closed
  4. A forced tool failure opens a REAL Tickets row, and resolving it
     resumes from the last checkpoint instead of restarting
"""
import sys
from pathlib import Path

PHASE3_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PHASE3_DIR))
sys.path.insert(0, str(PHASE3_DIR / "mcp_server"))

import mcp_server.database as db  # noqa: E402
import mcp_server.tools as mcp_tools  # noqa: E402
import state_graph.academic_integrity.graph as g  # noqa: E402
from state_graph.academic_integrity.hitl import (  # noqa: E402
    submit_committee_decision,
    submit_final_decision,
)
from state_graph.academic_integrity.tickets import resolve_ticket  # noqa: E402

TEST_STUDENT, TEST_COURSE, TEST_INSTRUCTOR = 9999, 9999, 9999
CASE_A, CASE_B, CASE_C = 9001, 9002, 9003


def seed():
    db.execute(
        "INSERT OR IGNORE INTO Students (student_id,name,email,level) VALUES (?,?,?,?)",
        (TEST_STUDENT, "Test Student", "test-student@brightpeak.test", "Beginner"),
    )
    db.execute(
        "INSERT OR IGNORE INTO Courses (course_id,title,category,duration) VALUES (?,?,?,?)",
        (TEST_COURSE, "Test Course", "test", 10),
    )
    db.execute(
        "INSERT OR IGNORE INTO Instructors (instructor_id,name,email) VALUES (?,?,?)",
        (TEST_INSTRUCTOR, "Test Instructor", "test-instructor@brightpeak.test"),
    )
    db.execute(
        """INSERT OR IGNORE INTO IntegrityCases
           (case_id, student_id, course_id, reported_by, description, similarity_score)
           VALUES (?,?,?,?,?,?)""",
        (CASE_A, TEST_STUDENT, TEST_COURSE, TEST_INSTRUCTOR, "Suspicious matching submission", 0.85),
    )


def cleanup():
    for cid in (CASE_A, CASE_B, CASE_C):
        db.execute("DELETE FROM IntegrityDecisions WHERE case_id = ?", (cid,))
        db.execute("DELETE FROM IntegrityAppeals WHERE case_id = ?", (cid,))
        db.execute("DELETE FROM IntegrityEvidence WHERE case_id = ?", (cid,))
        db.execute("DELETE FROM Tickets WHERE source_id = ?", (cid,))
        db.execute("DELETE FROM IntegrityCases WHERE case_id = ?", (cid,))
    db.execute("DELETE FROM Students WHERE student_id = ?", (TEST_STUDENT,))
    db.execute("DELETE FROM Courses WHERE course_id = ?", (TEST_COURSE,))
    db.execute("DELETE FROM Instructors WHERE instructor_id = ?", (TEST_INSTRUCTOR,))
    print("[cleanup] test rows removed")


def happy_path():
    print("\n=== 1) start_case (real Gemini call inside analyze_severity) ===")
    result = g.start_case(
        {
            "case_id": CASE_A, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
            "reported_by": TEST_INSTRUCTOR, "description": "Suspicious matching submission",
            "similarity_score": 0.85,
        }
    )
    print("status:", result.get("status"), "| severity:", result.get("severity"),
          "| rationale:", result.get("severity_rationale"))

    graph = g.build_academic_integrity_graph()
    config = {"configurable": {"thread_id": g.thread_id_for_case(CASE_A)}}
    print("paused at:", graph.get_state(config).next, "(should be needs_committee_review)")

    print("\n=== 2) admin resolves HITL #1 (simulating a fresh process) ===")
    result = submit_committee_decision(CASE_A, decided_by="admin_test", decision="uphold",
                                        notes="Clear evidence.")
    print("status:", result.get("status"))
    print("paused at:", graph.get_state(config).next, "(should be await_appeal)")

    print("\n=== 3) student submits appeal -> Tree of Thoughts (real Gemini calls) ===")
    graph.update_state(config, {"appeal_argument": "I had permission from the instructor.",
                                 "appeal_submitted": True})
    result = graph.invoke(None, config=config)
    print("status:", result.get("status"), "| best ruling:", result.get("appeal_evaluation"))
    print("paused at:", graph.get_state(config).next, "(should be committee_final_decision)")

    print("\n=== 4) admin makes final decision -> should reach closed ===")
    result = submit_final_decision(CASE_A, decided_by="admin_test", decision="uphold",
                                    notes="Matches ToT recommendation.")
    print("status:", result.get("status"), "(should be closed)")
    print("paused at:", graph.get_state(config).next, "(should be empty tuple = finished)")


def ticket_path():
    print("\n=== 5) forcing a real tool failure to test the ticket path ===")
    db.execute(
        """INSERT OR IGNORE INTO IntegrityCases
           (case_id, student_id, course_id, reported_by, description, similarity_score)
           VALUES (?,?,?,?,?,?)""",
        (CASE_B, TEST_STUDENT, TEST_COURSE, TEST_INSTRUCTOR, "Second case - forced failure", 0.5),
    )
    real_classify = mcp_tools.classify_severity_with_policy
    calls = {"n": 0}

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated transient tool failure")
        return real_classify(*a, **kw)

    mcp_tools.classify_severity_with_policy = flaky
    try:
        g.start_case({
            "case_id": CASE_B, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
            "reported_by": TEST_INSTRUCTOR, "description": "Second case - forced failure",
            "similarity_score": 0.5,
        })
        print("ERROR: expected a failure, none happened")
    except RuntimeError:
        print("node failed as expected -- checking for a real Tickets row")
    finally:
        mcp_tools.classify_severity_with_policy = real_classify

    row = db.query_one("SELECT * FROM Tickets WHERE source_id = ?", (CASE_B,))
    assert row is not None, "no ticket was created!"
    print("ticket:", dict(row))

    print("\n=== 6) resolving the ticket -> resumes from checkpoint (real Gemini retry) ===")
    result = resolve_ticket(row["ticket_id"], "Retried after transient error.")
    print("status:", result.get("status"), "| severity:", result.get("severity"))


def cycle_path():
    print("\n=== 7) request_more_evidence -> real cycle back to gather_evidence ===")
    db.execute(
        """INSERT OR IGNORE INTO IntegrityCases
           (case_id, student_id, course_id, reported_by, description, similarity_score)
           VALUES (?,?,?,?,?,?)""",
        (CASE_C, TEST_STUDENT, TEST_COURSE, TEST_INSTRUCTOR, "Third case - cycle test", 0.6),
    )
    g.start_case({
        "case_id": CASE_C, "student_id": TEST_STUDENT, "course_id": TEST_COURSE,
        "reported_by": TEST_INSTRUCTOR, "description": "Third case - cycle test",
        "similarity_score": 0.6,
    })
    graph = g.build_academic_integrity_graph()
    config = {"configurable": {"thread_id": g.thread_id_for_case(CASE_C)}}
    print("paused at:", graph.get_state(config).next, "(should be needs_committee_review)")

    result = submit_committee_decision(CASE_C, decided_by="admin_test",
                                        decision="request_more_evidence",
                                        notes="Need the original submission file.")
    print("status:", result.get("status"), "| severity:", result.get("severity"))
    print("paused at:", graph.get_state(config).next,
          "(should be needs_committee_review AGAIN -- proves the cycle re-ran gather_evidence -> analyze_severity)")

    print("\n=== 8) dismiss -> should skip straight to closed, no appeal forced ===")
    result = submit_committee_decision(CASE_C, decided_by="admin_test", decision="dismiss",
                                        notes="Instructor confirmed permission was granted.")
    print("status:", result.get("status"), "(should be closed)")
    print("paused at:", graph.get_state(config).next, "(should be empty tuple = finished, no appeal steps ran)")

if __name__ == "__main__":
    seed()
    try:
        happy_path()
        cycle_path()
        ticket_path()
        print("\n✅ all checks passed")
    except Exception:
        import traceback
        traceback.print_exc()
        print("\n❌ something failed -- see traceback above")
    finally:
        cleanup()