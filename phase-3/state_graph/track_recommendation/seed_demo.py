"""
seed_demo.py — Executable demo/test scenarios for the Track
Recommendation graph.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

# ── path bootstrap ────────────────────────────────────────────────────────────
_HERE     = Path(__file__).resolve().parent
_SG_DIR   = _HERE.parent
_PH3_DIR  = _SG_DIR.parent
_MCP_DIR  = _PH3_DIR / "mcp_server"

for _p in (_HERE, _SG_DIR, _PH3_DIR, _MCP_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
# ─────────────────────────────────────────────────────────────────────────────

from langgraph.types import Command

import db
from graph import build_graph
from adaptive_assessment import graph as aa_graph

GRAPH = build_graph()

def _new_thread() -> str:
    return f"demo-{uuid.uuid4().hex[:8]}"

def _run_adaptive_session_to_completion(assessment_id: int, student_id: int, answers: list[str]) -> None:
    """Drives the REAL Adaptive Assessment session to completion."""
    graph = aa_graph.build_adaptive_assessment_graph()
    config = {"configurable": {"thread_id": aa_graph.thread_id_for_session(assessment_id)}}
    
    for answer in answers:
        state = graph.get_state(config)
        if not state or not state.values:
            break
            
        pending = state.values.get("pending_question")
        if pending is None:
            break
            
        # Convert to dict to avoid Pydantic validation errors during update
        if hasattr(pending, "model_dump"):
            new_pending = pending.model_dump()
        elif isinstance(pending, dict):
            new_pending = pending.copy()
        else:
            new_pending = dict(pending)
            
        new_pending["student_answer"] = answer
        
        graph.update_state(config, {"pending_question": new_pending})
        graph.invoke(None, config=config)
        
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
    with db._conn() as con:
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
# 1. Happy path
# ---------------------------------------------------------------------------
def scenario_happy_path():
    _print_header("SCENARIO 1 — Happy path (complete data, auto-finalize)")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 3, "thread_id": thread_id})
    assert result.get("final_track"), f"Expected auto-finalized track, got: {result}"
    print(f"    Final: {result['final_track']} ({result['final_confidence']}%), "
          f"decided_by={result.get('log', [])[-1]}")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=0)
    return result

# ---------------------------------------------------------------------------
# 2. Missing data
# ---------------------------------------------------------------------------
def scenario_missing_data():
    _print_header("SCENARIO 2 — Missing data (Ahmed) -> real Adaptive Assessment(s) -> resume")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 1, "thread_id": thread_id})

    diagnostics_completed = 0
    while result.get("__interrupt__") and result["__interrupt__"][0].value["type"] == "awaiting_student":
        interrupt_payload = result["__interrupt__"][0].value
        assessment_id = interrupt_payload["assessment_id"]
        print(f"    Diagnostic Adaptive Assessment #{assessment_id} on "
              f"'{interrupt_payload['subject']}' — answering 3 real adaptive questions...")

        _run_adaptive_session_to_completion(assessment_id, student_id=1,
                                             answers=["correct", "correct", "incorrect"])
        assert _session_status(assessment_id) == "completed"

        result = _invoke(config, Command(resume={"completed": True}))
        diagnostics_completed += 1

    assert diagnostics_completed == 3, (
        f"Expected 3 Diagnostic Adaptive Assessments, completed {diagnostics_completed}."
    )
    assert result.get("final_track") or result.get("__interrupt__"), result
    if result.get("final_track"):
        print(f"    Track Recommendation resumed and finalized -> {result['final_track']}")
    else:
        print(f"    Track Recommendation resumed. Next: {result['__interrupt__'][0].value['type']}")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=3, expected_tickets=0)
    return result

# ---------------------------------------------------------------------------
# 3. RAG failure
# ---------------------------------------------------------------------------
def scenario_rag_failure():
    _print_header("SCENARIO 3 — RAG document validation failure -> ticket -> resume")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 3, "thread_id": thread_id,
                               "force_broken_track": "AI Engineering"})
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "ticket_needs_admin"
    ticket_id = interrupt_payload["ticket_id"]
    print(f"    🎫 Ticket #{ticket_id} opened for '{interrupt_payload['track']}'.")

    result = _invoke(config, Command(resume={"fixed": True}))
    assert result.get("final_track") or result.get("__interrupt__"), result
    print(f"    RAG resumed from checkpoint and continued past '{interrupt_payload['track']}'")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=1)
    return result

# ---------------------------------------------------------------------------
# 4. HITL approval
# ---------------------------------------------------------------------------
def scenario_hitl_approve():
    _print_header("SCENARIO 4 — HITL: advisor approves")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 3, "thread_id": thread_id})
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review", interrupt_payload
    print(f"    Advisor sees: top={interrupt_payload['top_recommendation']}")

    result = _invoke(config, Command(resume={"action": "approve", "advisor_name": "Dr. Nadia Kamal"}))
    assert result.get("final_track") == interrupt_payload["top_recommendation"]["track"]
    print(f"    Finalized: {result['final_track']} ({result['final_confidence']}%)")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=0)
    return result

# ---------------------------------------------------------------------------
# 5. HITL chooses another track
# ---------------------------------------------------------------------------
def scenario_hitl_choose_other():
    _print_header("SCENARIO 5 — HITL: advisor overrides with another track")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}
    result = _invoke(config, {"student_id": 3, "thread_id": thread_id})
    interrupt_payload = result["__interrupt__"][0].value
    alt = interrupt_payload.get("alternative")
    chosen_track = alt["track"] if alt else interrupt_payload["top_recommendation"]["track"]

    result = _invoke(config, Command(resume={
        "action": "choose_other", "track": chosen_track, "advisor_name": "Dr. Nadia Kamal",
    }))
    assert result.get("final_track") == chosen_track
    print(f"    Finalized: {result['final_track']} ({result['final_confidence']}%)")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=0, expected_tickets=0)
    return result

# ---------------------------------------------------------------------------
# 6. Targeted assessment
# ---------------------------------------------------------------------------
def scenario_targeted_assessment():
    _print_header("SCENARIO 6 — HITL requests more evidence -> targeted Adaptive Assessment")
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
    print(f"    New Targeted Adaptive Assessment #{new_assessment_id} started.")

    _run_adaptive_session_to_completion(new_assessment_id, student_id=3,
                                         answers=["correct", "correct", "correct"])

    result = _invoke(config, Command(resume={"completed": True}))
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review", interrupt_payload
    print(f"    Re-evaluated. Advisor sees FRESH numbers.")

    result = _invoke(config, Command(resume={"action": "approve", "advisor_name": "Dr. Nadia Kamal"}))
    assert result.get("final_track")
    print(f"    Finalized: {result['final_track']} ({result['final_confidence']}%)")
    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=1, expected_tickets=0)
    return result

# ---------------------------------------------------------------------------
# 7. Real checkpoint/resume
# ---------------------------------------------------------------------------
def scenario_checkpoint_restart():
    _print_header("SCENARIO 7 — genuine interrupt -> checkpoint -> resume")
    thread_id = _new_thread()
    config = {"configurable": {"thread_id": thread_id}}

    result = GRAPH.invoke({"student_id": 2, "thread_id": thread_id}, config=config)
    
    fresh_graph_1 = build_graph()
    while result.get("__interrupt__") and result["__interrupt__"][0].value["type"] == "awaiting_student":
        assessment_id = result["__interrupt__"][0].value["assessment_id"]
        print(f"    [1] Paused at diagnostic #{assessment_id}. Rebuilding graph object...")
        fresh_graph_1 = build_graph()
        _run_adaptive_session_to_completion(assessment_id, student_id=2,
                                             answers=["correct", "correct", "incorrect"])
        result = fresh_graph_1.invoke(Command(resume={"completed": True}), config=config)
        print(f"    [1] Resumed on the NEW object -> {result.get('log', [])[-1]}")

    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review"
    subject = "Machine Learning Fundamentals"
    result = fresh_graph_1.invoke(Command(resume={
        "action": "request_assessment", "subject": subject, "advisor_name": "Dr. Nadia Kamal",
    }), config=config)

    interrupt_payload = result["__interrupt__"][0].value
    new_assessment_id = interrupt_payload["assessment_id"]
    print(f"    [2] Paused at targeted assessment #{new_assessment_id}. Rebuilding graph object AGAIN...")
    fresh_graph_2 = build_graph()
    _run_adaptive_session_to_completion(new_assessment_id, student_id=2,
                                         answers=["correct", "correct", "correct"])
    result = fresh_graph_2.invoke(Command(resume={"completed": True}), config=config)
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["type"] == "advisor_review"

    fresh_graph_3 = build_graph()
    result = fresh_graph_3.invoke(Command(resume={"action": "approve", "advisor_name": "Dr. Nadia Kamal"}),
                                   config=config)
    assert result.get("final_track")
    print(f"    [3] Finalized on a THIRD new object -> {result['final_track']} ({result['final_confidence']}%)")

    _assert_no_duplicates(result["recommendation_id"], expected_diagnostics=3, expected_tickets=0)
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
    print(f"  ALL {len(to_run)} SCENARIO(S) PASSED — no duplicate diagnostics/tickets/assessments after interrupt/resume.")
    print("=" * 78)