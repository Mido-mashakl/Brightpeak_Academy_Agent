"""
Integration test — Promote-or-Drop Router + Episodic Store, together
=======================================================================
Run directly: `python memory/test_router_episodic_integration.py`

Per the team workflow: router.py passed standalone (test_router.py),
episodic.py passed standalone (test_episodic.py) -- but neither test
proves the two actually work TOGETHER in a real scenario. This is the
"deadlock only shows up when components run together" lesson: a bug in
how the router's decision maps onto EpisodicStore.insert()'s arguments
would never be caught by either standalone test alone.

Real scenario simulated end-to-end:
  1. ShortTermMemory fills up during a scholarship-eligibility sweep
     across a course roster (tool-heavy, exactly like production).
  2. On every overflow, the evicted message is handed to the router.
  3. Every "episodic" decision is written into a REAL EpisodicStore
     (temp SQLite file, not memory/store.db).
  4. We then read the episodic store back and confirm the events that
     survived are exactly the ones that should have survived -- not by
     re-checking the router's internal log, but by querying the store
     the way a later component (recall.py) actually would.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from episodic import EpisodicStore  # noqa: E402
from router import PromoteOrDropRouter  # noqa: E402
from short_term import ShortTermMemory  # noqa: E402

EVIDENCE_FILE = MEMORY_DIR / "evidence" / "router_episodic_integration_evidence.txt"
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
        "EVIDENCE — test_router_episodic_integration.py",
        "(router.py + episodic.py wired together on a real overflow scenario)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "integration_store.db"
        store = EpisodicStore(db_path=db_path)
        router = PromoteOrDropRouter()
        stm = ShortTermMemory(max_turns=4)

        log("=" * 70)
        log("SCENARIO — scholarship eligibility sweep for course 3 roster")
        log("=" * 70)

        # A realistic tool-heavy transcript: 4 students checked in sequence.
        # Each student produces several turns; the buffer (max_turns=4) will
        # overflow repeatedly across the sweep, exactly like production.
        transcript = [
            ("user", "Run scholarship eligibility sweep for course 3."),
            ("assistant", "Starting sweep. Checking student 14 first."),
            ("tool", "get_student_attendance(14) -> 92%"),
            ("tool", "get_student_grades(14) -> avg 88, below scholarship threshold"),
            ("assistant", "Student 14: not eligible, average below threshold."),
            ("assistant", "Checking student 15 next."),
            ("tool", "get_student_attendance(15) -> 60%"),
            ("tool", "Student 15 attendance is below the 75% threshold, flagged for review."),
            ("assistant", "Noted. Checking student 16 next."),
            ("tool", "get_student_attendance(16) -> 95%"),
            ("tool", "get_student_grades(16) -> avg 93, scholarship eligible confirmed."),
            ("assistant", "Student 16: eligible, all good."),
            ("assistant", "Checking student 17, last one."),
            ("tool", "get_student_attendance(17) -> 88%"),
            ("assistant", "Sweep complete."),
        ]

        # --- Step 1 & 2: buffer fills, router decides on every eviction ---
        decisions_made = []
        for role, content in transcript:
            evicted = stm.add(role, content)
            decision = router.process_overflow(evicted)
            if decision:
                decisions_made.append(decision)

        log(f"Transcript length: {len(transcript)} turns, max_turns={stm.max_turns}")
        log(f"Total eviction/routing decisions made: {len(decisions_made)}")
        for d in decisions_made:
            log(f"  -> {d.destination:9s} | {d.source_message.content!r}")

        episodic_decisions = [d for d in decisions_made if d.destination == "episodic"]
        log(f"\nDecisions routed to episodic: {len(episodic_decisions)}")
        if len(episodic_decisions) == 0:
            fail("expected at least one episodic-worthy event in this transcript (none found)")

        # --- Step 3: write every episodic decision into the REAL store ---
        log("\n" + "=" * 70)
        log("WRITING episodic decisions into EpisodicStore")
        log("=" * 70)
        for d in episodic_decisions:
            episode = store.insert(
                event_summary=d.event_summary,
                context=d.context,
                outcome=d.outcome,
                metadata={"course_id": 3},
            )
            log(f"  Inserted episode id={episode.id}: {episode.event_summary!r}")

        if store.count() != len(episodic_decisions):
            fail(
                f"store has {store.count()} episodes but router made "
                f"{len(episodic_decisions)} episodic decisions — mismatch between the "
                f"two components when wired together"
            )

        # --- Step 4: read the store back independently, as recall.py would ---
        log("\n" + "=" * 70)
        log("READING episodic store back (as a future recall.py component would)")
        log("=" * 70)
        stored = store.list_by_metadata({"course_id": 3})
        log(f"list_by_metadata({{'course_id': 3}}) -> {len(stored)} episode(s)")

        summaries_in_store = {e.event_summary for e in stored}
        summaries_expected = {d.event_summary for d in episodic_decisions}
        if summaries_in_store != summaries_expected:
            fail(
                f"episodic store contents don't match router's decisions.\n"
                f"    expected: {summaries_expected}\n"
                f"    got:      {summaries_in_store}"
            )
        log("PASS — every episodic decision the router made is present in the store, "
            "exactly as decided, queryable independently.\n")

        # Sanity: things the router decided to FORGET must never appear.
        forgotten_contents = {d.source_message.content for d in decisions_made if d.destination == "forget"}
        leaked = forgotten_contents & summaries_in_store
        if leaked:
            fail(f"a 'forget' decision leaked into the episodic store: {leaked}")
        log("PASS — no 'forget' decisions leaked into episodic memory.\n")

        store.close()

        log("=" * 70)
        log("ALL INTEGRATION TESTS PASSED — router.py and episodic.py work correctly together")
        log("=" * 70)
        write_evidence(passed=True)


if __name__ == "__main__":
    main()