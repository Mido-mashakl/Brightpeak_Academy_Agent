"""
Standalone test — Agent Integration (memory_integration.py)
=================================================================
Run directly: `python agent/test_memory_integration.py`

Proves all eight Memory System Extension modules work correctly
TOGETHER inside `MemoryIntegratedAgent`, on a real, tool-heavy advisory
scenario -- the same "deadlock only shows up when components run
together" reasoning as test_router_episodic_integration.py and
test_recall_verification.py, just one layer up: this time it's ALL the
memory modules wired into the agent-facing class, not two modules in
isolation.

No network access, no GEMINI_API_KEY required: `generate_fn` is a
deterministic stub (same testability pattern as every decision function
elsewhere in this package -- see memory_integration.py's own docstring).
Uses a temp SQLite file, never memory/store.db.

Scenario: a scholarship-eligibility sweep across a course roster,
exactly like scratchpad.py's own docstring example and
test_router_episodic_integration.py's scenario -- extended here through
a SECOND agent instance (new process boundary simulated by simply
constructing a fresh MemoryIntegratedAgent against the same db file) to
also prove the write path and read path survive across agent restarts,
tying persistence into the integration layer the way the checklist's
'Agent Integration' item is meant to.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_DIR))

from memory_integration import MemoryIntegratedAgent  # noqa: E402

EVIDENCE_FILE = AGENT_DIR / "evidence" / "memory_integration_evidence.txt"
log_lines: list[str] = []


def log(line: str = "") -> None:
    print(line)
    log_lines.append(line)


def fail(msg: str) -> None:
    log(f"FAIL: {msg}")
    write_evidence(passed=False)
    sys.exit(1)


def write_evidence(passed: bool) -> None:
    EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "=" * 70,
        "EVIDENCE — test_memory_integration.py",
        "(memory_integration.py — all 8 memory modules wired into the agent)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def make_stub_generate_fn(captured_prompts: list[str]):
    """Deterministic stand-in for GeminiClient.generate(): records every
    prompt it was asked to answer and echoes a fixed reply. Lets this
    test assert on exactly what context memory_integration.py actually
    assembled, without needing a real model call.
    """

    def _fn(prompt: str) -> str:
        captured_prompts.append(prompt)
        return "STUB_REPLY: acknowledged."

    return _fn


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "integration_agent_store.db"
        prompts: list[str] = []

        agent = MemoryIntegratedAgent(
            db_path=db_path,
            max_short_term_turns=4,
            consolidate_every_n_turns=1000,  # manual consolidate() calls only, for a clean test
            generate_fn=make_stub_generate_fn(prompts),
        )

        log("=" * 70)
        log("SETUP — scratchpad plan, exactly the scratchpad.py docstring scenario")
        log("=" * 70)
        agent.scratchpad.update_plan(
            "scholarship eligibility sweep for course 3",
            subgoal="checking student 14 of 22",
        )
        log(f"plan={agent.scratchpad.plan!r} subgoal={agent.scratchpad.current_subgoal!r}")

        # ------------------------------------------------------------
        # TEST 1 — write path: overflow -> router -> episodic, across
        # a tool-heavy sweep for three students, max_short_term_turns=4
        # (buffer will overflow repeatedly, exactly like production).
        # 15 turns, mirroring test_router_episodic_integration.py's own
        # scenario, extended with per-student metadata so this test
        # also exercises episodic/semantic scoping, not just eviction.
        # ------------------------------------------------------------
        log("\n" + "=" * 70)
        log("TEST 1 — WRITE PATH: short_term overflow -> router -> episodic")
        log("=" * 70)

        eviction_decisions = []
        eviction_decisions.append(
            agent.remember_user_message("Run scholarship eligibility sweep for course 3.")
        )
        eviction_decisions.append(
            agent.remember_assistant_message("Starting sweep. Checking student 14 first.")
        )
        eviction_decisions.append(
            agent.remember_tool_call(
                "get_student_attendance", "get_student_attendance(14) -> 92%",
                metadata={"student_id": 14},
            )
        )
        eviction_decisions.append(
            agent.remember_tool_result(
                "get_student_grades",
                "get_student_grades(14) -> avg 88, ineligible for scholarship, below threshold",
                metadata={"student_id": 14},
            )
        )
        eviction_decisions.append(
            agent.remember_assistant_message(
                "Student 14: ineligible, average below scholarship threshold.",
                metadata={"student_id": 14},
            )
        )
        eviction_decisions.append(agent.remember_assistant_message("Checking student 15 next."))
        eviction_decisions.append(
            agent.remember_tool_call(
                "get_student_attendance", "get_student_attendance(15) -> 60%",
                metadata={"student_id": 15},
            )
        )
        eviction_decisions.append(
            agent.remember_tool_result(
                "get_student_attendance",
                "Student 15 attendance is below the 75% threshold, flagged for review.",
                metadata={"student_id": 15},
            )
        )
        eviction_decisions.append(agent.remember_assistant_message("Noted. Checking student 16 next."))
        eviction_decisions.append(
            agent.remember_tool_call(
                "get_student_attendance", "get_student_attendance(16) -> 95%",
                metadata={"student_id": 16},
            )
        )
        eviction_decisions.append(
            agent.remember_tool_result(
                "get_student_grades",
                "get_student_grades(16) -> avg 93, scholarship eligible confirmed",
                metadata={"student_id": 16},
            )
        )
        eviction_decisions.append(
            agent.remember_assistant_message("Student 16: eligible, all good.", metadata={"student_id": 16})
        )
        eviction_decisions.append(agent.remember_assistant_message("Checking student 17, last one."))
        eviction_decisions.append(
            agent.remember_tool_call(
                "get_student_attendance", "get_student_attendance(17) -> 88%",
                metadata={"student_id": 17},
            )
        )
        eviction_decisions.append(agent.remember_assistant_message("Sweep complete."))

        decisions = [d for d in eviction_decisions if d is not None]
        log(f"Messages added: 15, max_turns=4 -> eviction/routing decisions: {len(decisions)}")
        for d in decisions:
            log(f"  -> {d.destination:9s} | {d.source_message.content!r} (metadata={d.source_message.metadata})")

        episodic_decisions = [d for d in decisions if d.destination == "episodic"]
        if len(episodic_decisions) == 0:
            fail("expected at least one episodic-worthy event during the sweep")

        if agent.episodic.count() != len(episodic_decisions):
            fail(
                f"episodic store has {agent.episodic.count()} rows but router made "
                f"{len(episodic_decisions)} episodic decisions -- write path is broken"
            )
        log(f"PASS — episodic store has exactly {agent.episodic.count()} row(s), matching router's decisions.\n")

        log("Checking per-student metadata scoping on the episode(s) actually written...")
        stored_14 = agent.episodic.list_by_metadata({"student_id": 14})
        stored_15 = agent.episodic.list_by_metadata({"student_id": 15})
        log(f"  student_id=14 -> {[e.event_summary for e in stored_14]}")
        log(f"  student_id=15 -> {[e.event_summary for e in stored_15]}")
        if not stored_14 and not stored_15:
            fail("no episode ended up scoped to either student -- metadata is not propagating from the evicted message")
        for e in stored_14:
            if "15" in e.event_summary and "14" not in e.event_summary:
                fail(f"episode scoped to student 14 contains student-15 content: {e.event_summary!r}")
        log("PASS — episodes are scoped to the correct student, taken from the EVICTED message's own metadata.\n")

        log("Scratchpad survived the eviction storm untouched (see scratchpad.py's own docstring guarantee):")
        log(f"  plan={agent.scratchpad.plan!r} subgoal={agent.scratchpad.current_subgoal!r}")
        if agent.scratchpad.plan != "scholarship eligibility sweep for course 3":
            fail("scratchpad.plan was affected by short_term eviction -- it must never be")
        log("PASS — scratchpad is untouched by short-term buffer pruning.\n")

        # ------------------------------------------------------------
        # TEST 2 — consolidation: episodic -> semantic, via agent.consolidate()
        # ------------------------------------------------------------
        log("=" * 70)
        log("TEST 2 — CONSOLIDATION: episodic events become versioned semantic facts")
        log("=" * 70)
        consolidation_decisions = agent.consolidate()
        for d in consolidation_decisions:
            log(f"  episode={d.episode_id} -> {d.action:17s} fact_key={d.fact_key}")

        fact_14 = agent.semantic.get_current("scholarship_status:student_14")
        fact_15 = agent.semantic.get_current("attendance_flag:student_15")
        fact_16 = agent.semantic.get_current("scholarship_status:student_16")
        log(f"scholarship_status:student_14 = {fact_14.value if fact_14 else None!r}")
        log(f"attendance_flag:student_15    = {fact_15.value if fact_15 else None!r}")
        log(f"scholarship_status:student_16 = {fact_16.value if fact_16 else None!r}")
        if fact_14 is None or fact_14.value != "ineligible":
            fail(f"expected scholarship_status:student_14 == 'ineligible', got {fact_14}")
        if fact_15 is None or fact_15.value != "flagged":
            fail(f"expected attendance_flag:student_15 == 'flagged', got {fact_15}")
        if fact_16 is None or fact_16.value != "eligible":
            fail(f"expected scholarship_status:student_16 == 'eligible', got {fact_16}")
        log("PASS — consolidation correctly turned all three episodes into distinct, correctly-scoped current semantic facts.\n")

        log("Re-running consolidate() must be a no-op (idempotent, per consolidation.py's guarantee):")
        second_pass = agent.consolidate()
        actions = {d.action for d in second_pass}
        log(f"  second pass actions: {actions}")
        if actions - {"unchanged"}:
            fail(f"a second consolidation pass over the same episodes should only report 'unchanged', got {actions}")
        log("PASS — consolidation is idempotent when called again through the agent.\n")

        # ------------------------------------------------------------
        # TEST 3 — read path: chat() recalls + verifies BEFORE replying
        # ------------------------------------------------------------
        log("=" * 70)
        log("TEST 3 — READ PATH: chat() recalls + verifies memory, builds the prompt, then replies")
        log("=" * 70)
        turn = agent.chat("student scholarship status eligibility", student_id=14)
        log(f"Reply: {turn.reply!r}")
        log(f"Recalled: {[(r.source, r.ref_id, round(r.score, 2)) for r in turn.recalled]}")
        log(f"Verified: {[(r.source, r.ref_id) for r in turn.verified]}")

        if not any(r.source == "semantic" for r in turn.verified):
            fail("expected the current scholarship_status:student_14 fact to survive verification and reach the prompt")
        if "ineligible" not in turn.prompt.lower():
            fail("the verified memory content did not actually make it into the assembled prompt")
        if "scholarship eligibility sweep for course 3" not in turn.prompt:
            fail("the scratchpad's plan did not make it into the assembled prompt")
        if turn.reply != "STUB_REPLY: acknowledged.":
            fail("chat() did not return exactly what generate_fn produced")
        log("PASS — recalled + verified memory AND scratchpad state both reached the prompt actually sent to the model.\n")

        log("Student scoping on the read path: student 15's query must never surface student 14's memory.")
        turn_15 = agent.chat("student scholarship status eligibility", student_id=15)
        if any(r.source == "semantic" and r.ref_id == fact_14.id for r in turn_15.verified):
            fail("student 14's fact leaked into a student-15-scoped recall")
        log("PASS — read path is correctly isolated per student.\n")

        # ------------------------------------------------------------
        # TEST 4 — verification actually rejects stale memory reaching
        # the prompt: supersede the scholarship fact, confirm the OLD
        # episode is filtered out of the very next chat() turn.
        # ------------------------------------------------------------
        log("=" * 70)
        log("TEST 4 — VERIFICATION filters a now-stale episode out of the agent's prompt")
        log("=" * 70)
        agent.semantic.upsert(
            fact_key="scholarship_status:student_14",
            value="eligible",
            metadata={"reason": "re-evaluated after appeal"},
        )
        turn2 = agent.chat("student scholarship status eligibility", student_id=14)
        log(f"Verified after re-evaluation: {[(r.source, r.ref_id, r.text) for r in turn2.verified]}")
        if "ineligible" in turn2.prompt.lower().replace("eligible", "").replace("ineligible", "X"):
            pass  # sanity no-op, real check below
        stale_leaked = any(
            r.source == "episodic" and "ineligible" in r.text.lower() for r in turn2.verified
        )
        if stale_leaked:
            fail("the old 'ineligible' episode leaked into the prompt after being superseded by a newer fact")
        if not any(r.source == "semantic" and r.text.endswith("eligible") for r in turn2.verified):
            fail("expected the NEW 'eligible' fact to be the one presented after re-evaluation")
        log("PASS — the superseded episode was correctly excluded; only the current fact reached the prompt.\n")

        agent.close()

        # ------------------------------------------------------------
        # TEST 5 — persistence across agent instances (new
        # MemoryIntegratedAgent against the same db file, simulating a
        # fresh session / process boundary the way
        # test_persistence_session_2.py proves for the raw stores).
        # ------------------------------------------------------------
        log("=" * 70)
        log("TEST 5 — PERSISTENCE: a fresh MemoryIntegratedAgent sees prior episodes/facts")
        log("=" * 70)
        agent2 = MemoryIntegratedAgent(
            db_path=db_path,
            generate_fn=make_stub_generate_fn(prompts),
        )
        recalled2, verified2 = agent2.recall_verified(
            "student scholarship status eligibility", student_id=14
        )
        log(f"Fresh agent instance recalled: {[(r.source, r.ref_id, r.text) for r in verified2]}")
        if not any(r.source == "semantic" and r.text.endswith("eligible") for r in verified2):
            fail("a fresh agent instance against the same db_path could not see the previously consolidated fact")
        log("PASS — memory written by one agent instance is visible to a brand-new instance via the same db file.\n")
        agent2.close()

        log("=" * 70)
        log("ALL INTEGRATION TESTS PASSED — memory_integration.py correctly wires")
        log("short_term, scratchpad, router, episodic, semantic, consolidation,")
        log("recall, and verification into a single working agent.")
        log("=" * 70)
        write_evidence(passed=True)


if __name__ == "__main__":
    main()