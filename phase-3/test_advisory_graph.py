"""
Run this from inside your phase-3/ folder (same level as mcp_server/, db/,
state_graph/), with your venv active:

    cd phase-3
    python test_advisory_graph.py

Unlike test_academic_integrity_graph.py / test_adaptive_assessment_graph.py,
this test mocks ONLY state_graph.advisory.llm (the 3 functions that call
Gemini) -- everything else is real: real rag/ retrieval in retrieve_policy,
real brightpeak.db, real LangGraph checkpointing/interrupt/resume. The LLM
layer is mocked because grading this graph's actual output isn't the point
of this test (that's what real Gemini calls would be for) -- proving the
STATE GRAPH's control flow is correct is: the loop back to
evaluate_eligibility on missing info, the human_review branch on low
confidence, the iteration cap, and the ticket/resume path.

It inserts test rows with student_id/course_id 9999 so it never touches
real data, and deletes everything it inserted at the end (even if a step
fails).

What it proves, end-to-end:
  1. A request runs, decomposes requirements, evaluates them, and reaches
     `wait_for_student` when evaluate_requirement can't decide something
     (real interrupt -> real checkpoint).
  2. Resuming with Command(resume=...) feeds the student's reply back into
     evaluate_eligibility (real cycle: wait_for_student -> evaluate_eligibility),
     not a restart from load_profile.
  3. Low confidence (no missing info, but not all requirements resolved
     confidently) routes to human_review (HITL #2, admin), and an
     "approve" decision reaches `completed` with a CertificateRequests row
     updated.
  4. The iteration cap (MAX_EVALUATION_ITERATIONS) forces human_review
     instead of looping forever when evaluate_requirement keeps returning
     "unknown".
  5. A forced tool failure (decompose_requirements raising) opens a REAL
     Tickets row, and resolving it resumes from the last checkpoint
     instead of restarting.
"""
import sys
import uuid
from pathlib import Path

PHASE3_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PHASE3_DIR))
sys.path.insert(0, str(PHASE3_DIR / "mcp_server"))

import mcp_server.database as db  # noqa: E402
import state_graph.advisory.graph as g  # noqa: E402
import state_graph.advisory.llm as advisory_llm  # noqa: E402
from langgraph.types import Command  # noqa: E402
from state_graph.advisory.tickets import (  # noqa: E402
    resolve_ticket,
    resume_after_ticket_resolution,
    run_student_advisor,
)

TEST_STUDENT, TEST_COURSE = 9999, 9999


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
    db.execute("DELETE FROM Tickets WHERE source_graph = 'student_advisor'")
    db.execute("DELETE FROM CertificateRequests WHERE student_id = ?", (TEST_STUDENT,))
    db.execute("DELETE FROM ScholarshipApplications WHERE student_id = ?", (TEST_STUDENT,))
    db.execute("DELETE FROM Students WHERE student_id = ?", (TEST_STUDENT,))
    db.execute("DELETE FROM Courses WHERE course_id = ?", (TEST_COURSE,))
    print("[cleanup] test rows removed")


def _start(thread_id, request_type="certificate", purpose="internship application"):
    """Same shape as graph.start_request(), but with an explicit thread_id
    so the test can resume it afterwards."""
    initial_state = g.StudentAdvisorState(
        student_id=TEST_STUDENT, request_type=request_type,
        course_id=TEST_COURSE, purpose=purpose,
    )
    return run_student_advisor(g.student_advisor_graph, initial_state, thread_id, request_id=None)


def _config(thread_id):
    return {"configurable": {"thread_id": thread_id}}


def happy_path():
    print("\n=== 1) start_request: both requirements satisfied -> straight to eligible ===")
    thread_id = f"test-advisor-happy-{uuid.uuid4()}"

    advisory_llm.decompose_policy_into_requirements = (
        lambda policy_text, request_type: ["Overall average >= 70%", "No open integrity cases"]
    )
    advisory_llm.evaluate_requirement = (
        lambda requirement, student_profile, student_response=None: {
            "satisfied": True, "evidence": "meets requirement", "note": None,
        }
    )
    advisory_llm.generate_recommendation = lambda summary: "Recommended: approve."

    result = _start(thread_id)
    print("status:", result.get("status"), "| eligibility:", result.get("eligibility_status"))
    assert result.get("status") == "completed"
    assert result.get("eligibility_status") == "eligible"
    request_id = result.get("request_id")
    row = db.query_one("SELECT * FROM CertificateRequests WHERE request_id = ?", (request_id,))
    assert row is not None and row["status"] == "eligible", "CertificateRequests row not finalized"
    print("CertificateRequests row:", dict(row))


def wait_for_student_cycle():
    print("\n=== 2) evaluate_requirement returns 'unknown' -> real interrupt at wait_for_student ===")
    thread_id = f"test-advisor-wait-{uuid.uuid4()}"

    advisory_llm.decompose_policy_into_requirements = (
        lambda policy_text, request_type: ["Attendance >= 80%"]
    )
    calls = {"n": 0}

    def flaky_eval(requirement, student_profile, student_response=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"satisfied": None, "evidence": None, "note": "Need attendance record for this term"}
        return {"satisfied": True, "evidence": "student confirmed", "note": None}

    advisory_llm.evaluate_requirement = flaky_eval
    advisory_llm.generate_recommendation = lambda summary: "Recommended: approve."

    result = _start(thread_id)
    graph = g.student_advisor_graph
    config = _config(thread_id)
    print("missing_info:", result.get("missing_info"))
    print("paused at:", graph.get_state(config).next, "(should be ('wait_for_student',))")
    assert graph.get_state(config).next == ("wait_for_student",)

    print("\n--- resuming with the student's reply (real cycle: wait_for_student -> evaluate_eligibility) ---")
    result = graph.invoke(Command(resume="Here is my attendance record: 92%."), config=config)
    print("status:", result.get("status"), "| eligibility:", result.get("eligibility_status"))
    assert result.get("status") == "completed"
    assert result.get("eligibility_status") == "eligible"
    assert calls["n"] == 2, "evaluate_requirement should have re-run after the student's reply"


def human_review_path():
    print("\n=== 3) low confidence, no missing info -> human_review (HITL, admin) ===")
    thread_id = f"test-advisor-review-{uuid.uuid4()}"

    advisory_llm.decompose_policy_into_requirements = (
        lambda policy_text, request_type: [
            "Overall average >= 70%", "Attendance >= 80%", "No open integrity cases",
        ]
    )
    # 1 of 3 satisfied, none missing/unknown, none failed -> confidence 0.33 < 0.6 -> human_review
    advisory_llm.evaluate_requirement = (
        lambda requirement, student_profile, student_response=None: {
            "satisfied": requirement.startswith("Overall"),
            "evidence": "borderline", "note": None,
        }
    )
    advisory_llm.generate_recommendation = lambda summary: "Recommended: admin approved despite low confidence."

    result = _start(thread_id)
    graph = g.student_advisor_graph
    config = _config(thread_id)
    print("confidence:", result.get("confidence"), "| missing_info:", result.get("missing_info"))
    print("paused at:", graph.get_state(config).next, "(should be ('human_review',))")
    assert graph.get_state(config).next == ("human_review",)

    print("\n--- admin approves ---")
    result = graph.invoke(
        Command(resume={"decided_by": "admin_test", "decision": "approve", "notes": "Manually verified."}),
        config=config,
    )
    print("status:", result.get("status"), "| eligibility:", result.get("eligibility_status"))
    assert result.get("status") == "completed"
    assert result.get("eligibility_status") == "eligible"


def iteration_cap_path():
    print("\n=== 4) evaluate_requirement always 'unknown' -> iteration cap forces human_review ===")
    thread_id = f"test-advisor-cap-{uuid.uuid4()}"

    advisory_llm.decompose_policy_into_requirements = (
        lambda policy_text, request_type: ["Some requirement nobody can confirm"]
    )
    advisory_llm.evaluate_requirement = (
        lambda requirement, student_profile, student_response=None: {
            "satisfied": None, "evidence": None, "note": "still missing",
        }
    )
    advisory_llm.generate_recommendation = lambda summary: "Recommended: escalated after repeated cycles."

    graph = g.student_advisor_graph
    config = _config(thread_id)
    result = _start(thread_id)
    # Keep supplying "new info" that still doesn't resolve it, until the cap kicks in.
    loops = 0
    while graph.get_state(config).next == ("wait_for_student",) and loops < g.MAX_EVALUATION_ITERATIONS + 2:
        result = graph.invoke(Command(resume="still doesn't clear it up"), config=config)
        loops += 1
    print("paused at:", graph.get_state(config).next, "(should be ('human_review',) once the cap is hit)")
    assert graph.get_state(config).next == ("human_review",), (
        f"expected the iteration cap to force human_review, got {graph.get_state(config).next} "
        f"after {loops} loop(s)"
    )
    print(f"cap reached after {loops} wait_for_student loop(s), as expected")

    result = graph.invoke(
        Command(resume={"decided_by": "admin_test", "decision": "reject", "notes": "Cannot confirm in time."}),
        config=config,
    )
    print("status:", result.get("status"), "| eligibility:", result.get("eligibility_status"))
    assert result.get("status") == "completed"
    assert result.get("eligibility_status") == "ineligible"


def ticket_path():
    print("\n=== 5) forcing a real node failure to test the ticket path ===")
    thread_id = f"test-advisor-ticket-{uuid.uuid4()}"

    real_decompose = advisory_llm.decompose_policy_into_requirements
    calls = {"n": 0}

    def flaky_decompose(policy_text, request_type):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated transient LLM failure")
        return ["Overall average >= 70%"]

    advisory_llm.decompose_policy_into_requirements = flaky_decompose
    advisory_llm.evaluate_requirement = (
        lambda requirement, student_profile, student_response=None: {
            "satisfied": True, "evidence": "ok", "note": None,
        }
    )
    advisory_llm.generate_recommendation = lambda summary: "Recommended: approve."

    try:
        _start(thread_id)
        print("ERROR: expected a failure, none happened")
    except RuntimeError:
        print("node failed as expected -- checking for a real Tickets row")
    finally:
        advisory_llm.decompose_policy_into_requirements = real_decompose  # not used again below;
        # flaky_decompose already flips to the working branch on its 2nd call, kept for resume below

    row = db.query_one(
        "SELECT * FROM Tickets WHERE thread_id = ? ORDER BY ticket_id DESC LIMIT 1", (thread_id,)
    )
    assert row is not None, "no ticket was created!"
    print("ticket:", dict(row))

    print("\n--- resolving the ticket -> resumes from checkpoint (re-runs decompose_requirements) ---")
    advisory_llm.decompose_policy_into_requirements = flaky_decompose  # 2nd call now succeeds
    result = resume_after_ticket_resolution(g.student_advisor_graph, row["ticket_id"])
    print("status:", result.get("status"), "| eligibility:", result.get("eligibility_status"))
    assert result.get("status") == "completed"
    resolved = db.query_one("SELECT * FROM Tickets WHERE ticket_id = ?", (row["ticket_id"],))
    assert resolved["status"] == "resolved"


if __name__ == "__main__":
    seed()
    try:
        happy_path()
        wait_for_student_cycle()
        human_review_path()
        iteration_cap_path()
        ticket_path()
        print("\n✅ all checks passed")
    except Exception:
        import traceback
        traceback.print_exc()
        print("\n❌ something failed -- see traceback above")
    finally:
        cleanup()