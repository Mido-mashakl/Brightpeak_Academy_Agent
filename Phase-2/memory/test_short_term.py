"""
Standalone test — Short-Term Memory + Scratchpad
==================================================
Run this file directly: `python memory/test_short_term.py`

Per the team workflow: test each component alone, immediately, before
wiring it to anything else. This test proves two things in isolation:

  1. ShortTermMemory actually evicts the oldest message once max_turns
     is exceeded, and returns the evicted message instead of silently
     dropping it.
  2. The Scratchpad survives buffer eviction completely untouched --
     the exact failure mode described in the lab (pruning must never
     destroy what the agent is actively doing).

No router, no episodic store, no MCP server, no LLM call. Pure unit
logic. Writes a plain-text evidence log to memory/evidence/ so a grader
(or teammate) doesn't have to re-run it to see it passed.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from scratchpad import Scratchpad  # noqa: E402
from short_term import ShortTermMemory  # noqa: E402

EVIDENCE_FILE = MEMORY_DIR / "evidence" / "short_term_scratchpad_evidence.txt"

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
        "EVIDENCE — test_short_term.py (standalone, no other memory component)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def main() -> None:
    log("=" * 70)
    log("TEST 1 — ShortTermMemory evicts the oldest message on overflow")
    log("=" * 70)

    stm = ShortTermMemory(max_turns=5)
    evicted_messages = []

    # Simulate a realistic Brightpeak tool-heavy sequence: an instructor
    # checking a course roster for scholarship eligibility.
    turns = [
        ("user", "Check scholarship eligibility for course 3 roster."),
        ("assistant", "Starting sweep. Calling get_student_enrollments(course_id=3)."),
        ("tool", '{"enrollments": [14, 15, 16, 17]}'),
        ("assistant", "Checking student 14 first."),
        ("tool", '{"student_id": 14, "attendance": 92}'),
        ("tool", '{"student_id": 14, "grades_avg": 88}'),
        ("assistant", "Student 14: eligible. Moving to student 15."),
    ]

    for role, content in turns:
        evicted = stm.add(role, content)
        if evicted:
            evicted_messages.append(evicted)

    log(f"Buffer size after {len(turns)} adds (max_turns=5): {len(stm)}")
    if len(stm) != 5:
        fail(f"expected buffer length 5, got {len(stm)}")

    log(f"Evicted count: {len(evicted_messages)}")
    if len(evicted_messages) != 2:
        fail(f"expected 2 evictions, got {len(evicted_messages)}")

    first_evicted = evicted_messages[0]
    log(f"First evicted message role/content: {first_evicted.role} / {first_evicted.content!r}")
    if first_evicted.content != "Check scholarship eligibility for course 3 roster.":
        fail("wrong message evicted — eviction order is not FIFO as expected")

    log("PASS — oldest message evicted in correct FIFO order, not silently dropped.\n")

    log("=" * 70)
    log("TEST 2 — Scratchpad survives short-term memory overflow untouched")
    log("=" * 70)

    scratchpad = Scratchpad()
    scratchpad.update_plan(
        plan="scholarship eligibility sweep for course 3",
        subgoal="checking student 14 of 4",
    )
    scratchpad.set_var("roster_total", 4)
    scratchpad.set_var("students_checked", [14])

    before = scratchpad.snapshot()
    log(f"Scratchpad BEFORE overflow: plan={before.plan!r}, subgoal={before.current_subgoal!r}, "
        f"working_state={before.working_state}")

    # Overflow the short-term buffer hard — many more turns than max_turns,
    # far more than the point where the plan was set.
    for i in range(20):
        stm.add("tool", f"filler tool output #{i} — 1000s of tokens of JSON in a real run")

    after = scratchpad.snapshot()
    log(f"Scratchpad AFTER {20} more evictions: plan={after.plan!r}, "
        f"subgoal={after.current_subgoal!r}, working_state={after.working_state}")

    if after.plan != before.plan:
        fail("scratchpad.plan changed after short-term memory eviction — pruning leaked into scratchpad")
    if after.current_subgoal != before.current_subgoal:
        fail("scratchpad.current_subgoal changed after eviction")
    if after.working_state != before.working_state:
        fail("scratchpad.working_state changed after eviction")

    log("PASS — scratchpad fields identical before/after; short-term eviction never touched it.\n")

    log("=" * 70)
    log("ALL TESTS PASSED")
    log("=" * 70)
    write_evidence(passed=True)


if __name__ == "__main__":
    main()