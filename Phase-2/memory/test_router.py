"""
Standalone test — Promote-or-Drop Router
==========================================
Run directly: `python memory/test_router.py`

Tests router.py completely alone -- no episodic store, no MCP server,
no LLM. Uses ShortTermMemory (already proven in test_short_term.py) only
as a realistic source of evicted messages, since that's exactly the
shape of input the router receives in production.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from router import MemoryRoutingDecision, PromoteOrDropRouter  # noqa: E402
from short_term import Message, ShortTermMemory  # noqa: E402

EVIDENCE_FILE = MEMORY_DIR / "evidence" / "router_evidence.txt"
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
        "EVIDENCE — test_router.py (standalone, no episodic store)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def main() -> None:
    router = PromoteOrDropRouter()

    log("=" * 70)
    log("TEST 1 — routine message is routed to 'forget' with reasoning")
    log("=" * 70)

    small_talk = Message(role="assistant", content="Sure, one moment while I look that up.")
    decision = router.route(small_talk)
    log(f"destination: {decision.destination}")
    log(f"reasoning:   {decision.reasoning}")
    if decision.destination != "forget":
        fail("routine small talk should route to 'forget'")
    if not decision.reasoning:
        fail("decision must always carry non-empty reasoning")
    log("PASS\n")

    log("=" * 70)
    log("TEST 2 — a consequential event is routed to 'episodic' with context")
    log("=" * 70)

    flagged = Message(
        role="tool",
        content="Student 14 attendance is below the 75% threshold for course 3.",
    )
    decision2 = router.route(flagged)
    log(f"destination:   {decision2.destination}")
    log(f"reasoning:     {decision2.reasoning}")
    log(f"event_summary: {decision2.event_summary}")
    log(f"context:       {decision2.context}")
    if decision2.destination != "episodic":
        fail("attendance-threshold event should route to 'episodic'")
    if not decision2.event_summary:
        fail("episodic decisions must populate event_summary")
    log("PASS\n")

    log("=" * 70)
    log("TEST 3 — router structurally cannot produce a 'semantic' destination")
    log("=" * 70)
    try:
        bad_decision = MemoryRoutingDecision(
            destination="semantic",  # type: ignore[arg-type]
            reasoning="attempting to smuggle a semantic write through the router",
            source_message=flagged,
        )
        router.route(bad_decision.source_message)  # would call default_decision_fn again, fine
        # The real guard is a custom decision_fn returning "semantic":
        def bad_decision_fn(msg):
            return bad_decision

        bad_router = PromoteOrDropRouter(decision_fn=bad_decision_fn)
        bad_router.route(flagged)
        fail("router accepted a 'semantic' destination — constraint is broken")
    except ValueError as e:
        log(f"Correctly rejected: {e}")
        log("PASS\n")

    log("=" * 70)
    log("TEST 4 — process_overflow() wraps ShortTermMemory eviction directly")
    log("=" * 70)
    stm = ShortTermMemory(max_turns=3)
    events = [
        # This important message must be OLD ENOUGH to actually get evicted —
        # it goes in first, then gets pushed out once 3 more messages arrive.
        ("tool", "Scholarship eligibility: student is now below the 75% attendance threshold."),
        ("user", "How is my son doing this semester?"),
        ("assistant", "Let me check."),
        ("tool", "Enrollment status: active."),
        ("assistant", "Noted, thanks."),
    ]
    router2 = PromoteOrDropRouter()
    decisions_made = []
    for role, content in events:
        evicted = stm.add(role, content)
        d = router2.process_overflow(evicted)
        if d:
            decisions_made.append(d)

    for d in decisions_made:
        log(f"  evicted: {d.source_message.content!r} -> {d.destination}")

    if len(decisions_made) != 2:
        fail(f"expected 2 routed decisions from overflow, got {len(decisions_made)}")

    episodic_count = sum(1 for d in decisions_made if d.destination == "episodic")
    if episodic_count != 1:
        fail(f"expected exactly 1 episodic decision among the overflow, got {episodic_count}")

    log("PASS — process_overflow() correctly consumes ShortTermMemory's eviction output.\n")

    log("=" * 70)
    log("Full router decision log (visible reasoning, as required by the lab):")
    log("=" * 70)
    log(router2.log_as_text())

    log("\n" + "=" * 70)
    log("ALL TESTS PASSED")
    log("=" * 70)
    write_evidence(passed=True)


if __name__ == "__main__":
    main()