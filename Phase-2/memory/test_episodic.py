"""
Standalone test — Episodic Memory
====================================
Run directly: `python memory/test_episodic.py`

Tests episodic.py completely alone. Uses a temporary SQLite file (not
memory/store.db, the real store) so this test never pollutes production
data and can be re-run safely any number of times.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from episodic import EpisodicStore  # noqa: E402

EVIDENCE_FILE = MEMORY_DIR / "evidence" / "episodic_evidence.txt"
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
        "EVIDENCE — test_episodic.py (standalone, temp SQLite file, no router)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_store.db"

        log("=" * 70)
        log("TEST 1 — store is backed by a real file on disk, not memory")
        log("=" * 70)
        store = EpisodicStore(db_path=db_path)
        if not db_path.exists():
            fail("expected SQLite file to exist immediately after EpisodicStore() init")
        log(f"DB file exists at: {db_path} ({db_path.stat().st_size} bytes)")
        log("PASS\n")

        log("=" * 70)
        log("TEST 2 — insert an episode, read it back with all fields intact")
        log("=" * 70)
        episode = store.insert(
            event_summary="Student 14 attendance is below the 75% threshold for course 3.",
            context="role=tool, msg_type=text",
            outcome="recorded",
            metadata={"student_id": 14, "course_id": 3},
        )
        log(f"Inserted episode id={episode.id}")
        log(f"  event_summary: {episode.event_summary}")
        log(f"  context:       {episode.context}")
        log(f"  outcome:       {episode.outcome}")
        log(f"  metadata:      {episode.metadata}")

        fetched = store.get_by_id(episode.id)
        if fetched is None:
            fail("get_by_id() returned None for an episode that was just inserted")
        if fetched.event_summary != episode.event_summary:
            fail("event_summary did not round-trip correctly")
        if fetched.metadata != {"student_id": 14, "course_id": 3}:
            fail(f"metadata did not round-trip correctly, got {fetched.metadata}")
        log("PASS — round-tripped exactly as stored.\n")

        log("=" * 70)
        log("TEST 3 — persistence survives closing and reopening the connection")
        log("=" * 70)
        store.close()
        reopened = EpisodicStore(db_path=db_path)
        still_there = reopened.get_by_id(episode.id)
        if still_there is None:
            fail("episode disappeared after closing and reopening the store")
        log(f"After reopen, episode {episode.id} still present: {still_there.event_summary!r}")
        log("PASS\n")

        log("=" * 70)
        log("TEST 4 — list_recent() and list_by_metadata() filtering")
        log("=" * 70)
        reopened.insert(
            event_summary="Student 15 scholarship eligibility confirmed above 90% average.",
            outcome="recorded",
            metadata={"student_id": 15, "course_id": 3},
        )
        reopened.insert(
            event_summary="Instructor requested concise report format going forward.",
            outcome="recorded",
            metadata={"instructor_id": 2},
        )

        recent = reopened.list_recent(limit=10)
        log(f"list_recent(10) returned {len(recent)} episodes total")
        if len(recent) != 3:
            fail(f"expected 3 total episodes, got {len(recent)}")

        course3_only = reopened.list_by_metadata({"course_id": 3})
        log(f"list_by_metadata({{'course_id': 3}}) returned {len(course3_only)} episodes")
        if len(course3_only) != 2:
            fail(f"expected 2 episodes for course_id=3, got {len(course3_only)}")

        student14_only = reopened.list_by_metadata({"student_id": 14})
        log(f"list_by_metadata({{'student_id': 14}}) returned {len(student14_only)} episode(s)")
        if len(student14_only) != 1 or student14_only[0].id != episode.id:
            fail("metadata filter for student_id=14 did not return the expected single episode")

        log("PASS — filtering by metadata works correctly.\n")

        reopened.close()

        log("=" * 70)
        log("ALL TESTS PASSED")
        log("=" * 70)
        write_evidence(passed=True)


if __name__ == "__main__":
    main()