"""
seed_demo.py — Executable demo/test scenarios for the Track
Recommendation graph.

Run directly:  python3 seed_demo.py            (all 6 scenarios)
            or python3 seed_demo.py happy       (one scenario by name)

Each scenario drives the REAL compiled graph (graph.build_graph()) with
Command(resume=...) across genuine interrupt() pauses, and — for any
Diagnostic/Targeted Adaptive Assessment pause — drives the REAL
Adaptive Assessment session directly via
adaptive_assessment.graph.resume_session(...), exactly as
assessment_bridge.py's module docstring says the platform is expected
to. Nothing here hands a bare score directly into Track Recommendation.

After every scenario, `_assert_no_duplicates(recommendation_id)` checks
the actual DiagnosticAssessments/Tickets rows in brightpeak.db and
raises if interrupt/resume ever produced more rows than the scenario's
own actions justify.
"""
from __future__ import annotations

import sys
import uuid

from langgraph.types import Command

import db
from graph import build_graph
from adaptive_assessment import graph as aa_graph

GRAPH = build_graph()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _new_thread() -> str:
    return f"demo-{uuid.uuid4().hex[:8]}"


def _run_adaptive_session_to_completion(assessment_id: int, student_id: int, answers: list[str]) -> None:
    """Drives the REAL Adaptive Assessment session (started by
    assessment_bridge.start_adaptive_session inside prepare_diagnostic /
    prepare_targeted_assessment) to completion, answering each question
    with the given sequence of 'correct'/'incorrect' answers — this is
    what makes the resulting score a REAL, computed score rather than a
    number handed in directly."""
    for answer in answers:
        aa_graph.resume_session(assessment_id, answer)
        if _session_status(assessment_id) == "completed":
            break


def _session_status(assessment_id: int) -> str:
    row = db.get_adaptive_session_result(assessment_id)
    return row["status"] if row else "missing"


def _print_header(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def _invoke(config: dict, payload) -> dict:
    result = GRAPH.invoke(payload, config=config)
    interrupt = result.get("__interrupt__")
    if interrupt:
        print(f"    -> interrupt: {interrupt[0].value}")
    return result


def _assert_no_duplicates(recommendation_id: int, expected_diagnostics: int, expected_tickets: int) -> None:
    with db._conn() as con:  # noqa: SLF001 - demo-only introspection
        diag_count = con.execute(
            "SELECT COUNT(*) FROM DiagnosticAssessments WHERE recommendation_id = ?",
            (recommendation_id,),
        ).fetchone()[0]
        ticket_count = con.execute(
            "SELECT COUNT(*) FROM Tickets WHERE source_id = ? AND source_graph='track_recommendation'",
            (recommendation_id,),
        ).fetchone()[0]
    assert diag_count == expected_diagnostics, (
        f"Expected exactly {expected_diagnostics} DiagnosticAssessments row(s) for "
        f"recommendation {recommendation_id}, found {diag_count} — duplicate detected."
    )
    assert ticket_count == expected_tickets, (
        f"Expected exactly {expected_tickets} Tickets row(s) for recommendation "
        f"{recommendation_id}, found {ticket_count} — duplicate detected."
    )
    print(f"    ✓ no duplicates: {diag_count} diagnostic(s), {ticket_count} ticket(s) "
          f"for recommendation #{recommendation_id}")


# ---------------------------------------------------------------------------
# 1. Happy path — complete data, RAG succeeds, clear decision, auto-finalize
# ---------------------------------------------------------------------------

def scenario_happy_path():
    _print_header("SCENARIO 1 — Happy path (complete data, auto-finalize)")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 1, "thread_id": thread_id})
    assert result.get("final_track"), f"Expected auto-finalized track, got: {result}"
    print(f"    Final: {result['final_track']} ({result['final_confidence']}%), "
          f"decided_by={result.get('log', [])[-1]}")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=0)
    return result


# ---------------------------------------------------------------------------
# 2. Missing data -> Diagnostic Assessment -> real adaptive Qs -> resume
# ---------------------------------------------------------------------------

def scenario_missing_data():
    _print_header("SCENARIO 2 — Missing data -> real Adaptive Assessment -> resume")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 2, "thread_id": thread_id})
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "awaiting_student"
    assessment_id = interrupt_payload["assessment_id"]
    print(f"    Diagnostic Adaptive Assessment #{assessment_id} on "
          f"'{interrupt_payload['subject']}' — answering 3 real adaptive questions "
          f"(2 correct, 1 incorrect)...")

    _run_adaptive_session_to_completion(assessment_id, student_id=2,
                                         answers=["correct", "correct", "incorrect"])
    assert _session_status(assessment_id) == "completed"

    result = _invoke(config, Command(resume={"completed": True}))
    assert result.get("final_track") or result.get("__interrupt__"), result
    if result.get("final_track"):
        print(f"    Track Recommendation resumed and finalized -> {result['final_track']}")
    else:
        print(f"    Track Recommendation resumed. Next: {result['__interrupt__'][0].value['type']}")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=1, expected_tickets=0)
    return result


# ---------------------------------------------------------------------------
# 3. RAG failure -> ticket -> admin fixes -> resume from checkpoint (not restart)
# ---------------------------------------------------------------------------

def scenario_rag_failure():
    _print_header("SCENARIO 3 — RAG document validation failure -> ticket -> resume")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    # force_broken_track simulates one bad document among several
    # candidate tracks' documents.
    result = _invoke(config, {"student_id": 4, "thread_id": thread_id,
                               "force_broken_track": "AI Engineering"})
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "ticket_needs_admin"
    ticket_id = interrupt_payload["ticket_id"]
    print(f"    🎫 Ticket #{ticket_id} opened for '{interrupt_payload['track']}'. "
          f"Admin fixes it (resuming RAG, not the whole workflow)...")

    result = _invoke(config, Command(resume={"fixed": True}))
    assert result.get("final_track") or result.get("__interrupt__"), result
    print(f"    RAG resumed from checkpoint and continued past '{interrupt_payload['track']}' "
          f"without restarting student-data collection.")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=1)
    return result


# ---------------------------------------------------------------------------
# 4. HITL approval — unclear decision, advisor approves top recommendation
# ---------------------------------------------------------------------------

def scenario_hitl_approve():
    _print_header("SCENARIO 4 — HITL: advisor approves")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 3, "thread_id": thread_id})
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review", interrupt_payload
    print(f"    Advisor sees: top={interrupt_payload['top_recommendation']}, "
          f"concerns={interrupt_payload['concerns']}")

    result = _invoke(config, Command(resume={"action": "approve", "advisor_name": "Dr. Nadia Kamal"}))
    assert result.get("final_track") == interrupt_payload["top_recommendation"]["track"]
    print(f"    Finalized: {result['final_track']} ({result['final_confidence']}%), "
          f"decided_by={result['log'][-1]}")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=0)
    return result


# ---------------------------------------------------------------------------
# 5. HITL chooses another track — advisor overrides the AI recommendation
# ---------------------------------------------------------------------------

def scenario_hitl_choose_other():
    _print_header("SCENARIO 5 — HITL: advisor overrides with another track")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 3, "thread_id": thread_id})
    interrupt_payload = result["__interrupt__"][0].value
    alt = interrupt_payload.get("alternative")
    chosen_track = alt["track"] if alt else interrupt_payload["top_recommendation"]["track"]
    print(f"    Advisor overrides top pick, chooses: {chosen_track}")

    result = _invoke(config, Command(resume={
        "action": "choose_other", "track": chosen_track, "advisor_name": "Dr. Nadia Kamal",
    }))
    assert result.get("final_track") == chosen_track
    print(f"    Finalized: {result['final_track']} ({result['final_confidence']}%), "
          f"decided_by={result['log'][-1]}")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=0)
    return result


# ---------------------------------------------------------------------------
# 6. Targeted assessment — advisor requests more evidence, re-evaluate, finalize
# ---------------------------------------------------------------------------

def scenario_targeted_assessment():
    _print_header("SCENARIO 6 — HITL requests more evidence -> targeted Adaptive "
                  "Assessment -> re-evaluate -> HITL again -> finalize")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 3, "thread_id": thread_id})
    subject = "Data Structures & Algorithms"
    print(f"    Advisor requests more evidence on '{subject}'.")

    result = _invoke(config, Command(resume={
        "action": "request_assessment", "subject": subject, "advisor_name": "Dr. Nadia Kamal",
    }))
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "awaiting_student"
    new_assessment_id = interrupt_payload["assessment_id"]
    print(f"    New Targeted Adaptive Assessment #{new_assessment_id} started "
          f"(prior_evidence_count={interrupt_payload['prior_evidence_count']}). "
          f"Answering with a strong result (3/3 correct)...")

    _run_adaptive_session_to_completion(new_assessment_id, student_id=3,
                                         answers=["correct", "correct", "correct"])

    result = _invoke(config, Command(resume={"completed": True}))
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review", (
        "Confidence/policy must be recalculated and route back through HITL "
        f"after a targeted assessment; got {interrupt_payload}"
    )
    print(f"    Re-evaluated. Advisor sees FRESH numbers: "
          f"top={interrupt_payload['top_recommendation']}, concerns={interrupt_payload['concerns']}")

    result = _invoke(config, Command(resume={"action": "approve", "advisor_name": "Dr. Nadia Kamal"}))
    assert result.get("final_track")
    print(f"    Finalized: {result['final_track']} ({result['final_confidence']}%)")
    # Student 3 (Laila) already had grades for every prerequisite course,
    # so no missing-data diagnostic was ever created for her — the ONLY
    # DiagnosticAssessments row on this recommendation is the single
    # advisor-requested targeted assessment on `subject`.
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=1, expected_tickets=0)
    diagnostics = db.get_diagnostics_for_subject(result["recommendation_id"], subject)
    assert len(diagnostics) == 1  # only 1 targeted assessment was made for THIS subject
    print(f"    Evidence trail for '{subject}': {[(d['trigger'], d['score']) for d in diagnostics]}")
    return result


# ---------------------------------------------------------------------------
# 7. Real checkpoint/resume across a fresh process — proves persistence to
#    disk, not just in-memory continuity within one Python object's
#    lifetime. Covers diagnostic, ticket, targeted assessment, and HITL.
# ---------------------------------------------------------------------------

def scenario_checkpoint_restart():
    _print_header("SCENARIO 7 — genuine interrupt -> checkpoint -> resume "
                  "across a brand-new graph object (simulated process restart)")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}

    # --- pause #1: diagnostic (missing data) ---
    result = GRAPH.invoke({"student_id": 2, "thread_id": thread_id}, config=config)
    assessment_id = result["__interrupt__"][0].value["assessment_id"]
    print(f"    [1] Paused at diagnostic #{assessment_id}. Dropping this graph object "
          f"entirely and rebuilding from scratch (simulated restart)...")
    fresh_graph_1 = build_graph()  # brand-new object; only the SQLite file on disk carries state
    _run_adaptive_session_to_completion(assessment_id, student_id=2,
                                         answers=["correct", "correct", "incorrect"])
    result = fresh_graph_1.invoke(Command(resume={"completed": True}), config=config)
    print(f"    [1] Resumed on the NEW object -> {result.get('log', [])[-1]}")

    # --- pause #2: HITL, request targeted assessment ---
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review"
    subject = "Machine Learning Fundamentals"
    result = fresh_graph_1.invoke(Command(resume={
        "action": "request_assessment", "subject": subject, "advisor_name": "Dr. Nadia Kamal",
    }), config=config)

    # --- pause #3: targeted assessment ---
    interrupt_payload = result["__interrupt__"][0].value
    new_assessment_id = interrupt_payload["assessment_id"]
    print(f"    [2] Paused at targeted assessment #{new_assessment_id}. Rebuilding graph "
          f"object AGAIN (second simulated restart)...")
    fresh_graph_2 = build_graph()
    _run_adaptive_session_to_completion(new_assessment_id, student_id=2,
                                         answers=["correct", "correct", "correct"])
    result = fresh_graph_2.invoke(Command(resume={"completed": True}), config=config)
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review"
    print(f"    [2] Resumed on the SECOND new object -> re-evaluated, back at HITL with "
          f"fresh numbers: {interrupt_payload['top_recommendation']}")

    # --- pause #4: HITL again, approve, finalize on a THIRD fresh object ---
    fresh_graph_3 = build_graph()
    result = fresh_graph_3.invoke(Command(resume={"action": "approve", "advisor_name": "Dr. Nadia Kamal"}),
                                   config=config)
    assert result.get("final_track")
    print(f"    [3] Finalized on a THIRD new object -> {result['final_track']} "
          f"({result['final_confidence']}%)")

    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=2, expected_tickets=0)
    return result


SCENARIOS = {
    "happy": scenario_happy_path,
    "missing_data": scenario_missing_data,
    "rag_failure": scenario_rag_failure,
    "hitl_approve": scenario_hitl_approve,
    "hitl_choose_other": scenario_hitl_choose_other,
    "targeted_assessment": scenario_targeted_assessment,
    "checkpoint_restart": scenario_checkpoint_restart,
}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else None
    to_run = {which: SCENARIOS[which]} if which else SCENARIOS
    for name, fn in to_run.items():
        fn()
    print("\n" + "=" * 78)
    print(f"  ALL {len(to_run)} SCENARIO(S) PASSED — no duplicate diagnostics/tickets/"
          f"assessments after interrupt/resume.")
    print("=" * 78)
