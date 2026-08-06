"""
Standalone test — Cross-Session Persistence (SESSION 2 of 2)
================================================================
Run directly, as its own OS process, AFTER test_persistence_session_1.py
has finished and exited: `python memory/test_persistence_session_2.py`

See test_persistence_session_1.py's docstring for why this is two
separate scripts rather than one. This file assumes nothing carried
over from session 1 except what is sitting on disk -- it does not
import, call, or share any object with session 1 in any way.

Beyond just reading back what session 1 wrote, this session also proves
a subtler, easy-to-get-wrong point about ConsolidationLayer: its
`_last_consolidated_id` read-position (see consolidation.py) lives only
in the Python object, not in SQLite -- so it is genuinely gone once
session 1's process exits. A brand-new ConsolidationLayer built here
starts back at 0 and will re-scan session 1's already-consolidated
episodes from scratch. The versioning-trigger diff against
SemanticStore.get_current() (not the in-memory read-position) is what
has to be relied on to keep that safe -- so this test deliberately
re-runs consolidation over old + new episodes together and checks that
the old ones come back "unchanged" rather than creating duplicate fact
versions.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from consolidation import ConsolidationLayer  # noqa: E402
from episodic import EpisodicStore  # noqa: E402
from semantic import SemanticStore  # noqa: E402

EVIDENCE_DIR = MEMORY_DIR / "evidence"
PERSIST_DB = EVIDENCE_DIR / "_persistence_cross_session.db"
SNAPSHOT_FILE = EVIDENCE_DIR / "_persistence_snapshot.json"
SESSION1_LOG = EVIDENCE_DIR / "_persistence_session1.log"
EVIDENCE_FILE = EVIDENCE_DIR / "persistence_across_sessions_evidence.txt"

log_lines: list[str] = []


def log(line: str = "") -> None:
    print(line)
    log_lines.append(line)


def fail(msg: str) -> None:
    log(f"FAIL: {msg}")
    write_evidence(passed=False)
    sys.exit(1)


def write_evidence(passed: bool) -> None:
    session1_text = SESSION1_LOG.read_text(encoding="utf-8") if SESSION1_LOG.exists() else "(session 1 log missing)"
    header = [
        "=" * 70,
        "EVIDENCE — test_persistence_session_1.py + test_persistence_session_2.py",
        "(two SEPARATE OS processes, real SQLite file on disk, no shared memory)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
        "----- SESSION 1 LOG -----",
        session1_text,
        "",
        "----- SESSION 2 LOG -----",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def main() -> None:
    log("=" * 70)
    log("SESSION 2 — a brand-new OS process, opened separately from session 1")
    log("=" * 70)
    log(f"PID of this process: {os.getpid()}")

    if not SNAPSHOT_FILE.exists() or not PERSIST_DB.exists():
        fail(
            "no snapshot / db file found -- run "
            "'python memory/test_persistence_session_1.py' first and let it finish."
        )
    snapshot = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    log(f"Loaded session 1's expectation snapshot (written by PID {snapshot['session1_pid']}).")
    if snapshot["session1_pid"] == os.getpid():
        fail("this is not actually a separate process from session 1 -- PIDs must differ")
    log("Confirmed: this process's PID differs from session 1's -- genuinely separate process.\n")

    episodic = EpisodicStore(db_path=PERSIST_DB)
    semantic = SemanticStore(db_path=PERSIST_DB)
    log(f"Opened NEW, independent connections to the SAME file: {PERSIST_DB}")

    log("\n" + "=" * 70)
    log("TEST 1 — episodes written in session 1 are readable, byte-for-byte, in session 2")
    log("=" * 70)
    for expected_ep in snapshot["episodes"]:
        actual = episodic.get_by_id(expected_ep["id"])
        log(f"episode {expected_ep['id']}: expected={expected_ep['event_summary']!r}")
        log(f"episode {expected_ep['id']}: actual  ={actual.event_summary if actual else None!r}")
        if actual is None:
            fail(f"episode {expected_ep['id']} written in session 1 is missing in session 2")
        if actual.to_dict() != expected_ep:
            fail(f"episode {expected_ep['id']} does not match what session 1 wrote:\n  expected={expected_ep}\n  actual={actual.to_dict()}")
    log("PASS — every episode survived the process restart unchanged.\n")

    log("=" * 70)
    log("TEST 2 — semantic facts written in session 1 are readable in session 2")
    log("=" * 70)
    for fact_key, expected_fact in snapshot["facts"].items():
        actual = semantic.get_current(fact_key)
        log(f"{fact_key}: expected value={expected_fact['value']!r} version={expected_fact['version']}")
        log(f"{fact_key}: actual   value={actual.value if actual else None!r} version={actual.version if actual else None}")
        if actual is None or actual.to_dict() != expected_fact:
            fail(f"fact {fact_key} does not match what session 1 wrote")
    log("PASS — every fact and its version number survived the process restart.\n")

    log("=" * 70)
    log("TEST 3 — AUTOINCREMENT continues from where session 1 left off")
    log("=" * 70)
    last_id = max(ep["id"] for ep in snapshot["episodes"])
    e3 = episodic.insert(
        event_summary="Student confirmed interest in the AI track instead",
        context="advising session, week 2 (session 2)",
        outcome="noted",
        metadata={"student_id": 7},
    )
    log(f"Last episode id from session 1: {last_id}. New episode id in session 2: {e3.id}")
    if e3.id != last_id + 1:
        fail(f"expected the new episode's id to continue the sequence ({last_id + 1}), got {e3.id}")
    log("PASS — SQLite's own id sequence persisted; it did not reset with the process.\n")

    log("=" * 70)
    log("TEST 4 — a FRESH ConsolidationLayer (read-position reset to 0) re-sweeps old + ")
    log("new episodes together, and still stays correct via SemanticStore's own diffing")
    log("=" * 70)
    layer = ConsolidationLayer(episodic, semantic)  # brand-new object, _last_consolidated_id = 0
    decisions = layer.run()
    for d in decisions:
        log(f"  episode={d.episode_id} -> {d.action:17s} fact_key={d.fact_key}")
    if len(decisions) != 3:
        fail(f"expected 3 decisions (episodes {snapshot['episodes'][0]['id']}, "
             f"{snapshot['episodes'][1]['id']}, {e3.id} all re-seen), got {len(decisions)}")

    scholarship_decision = next(d for d in decisions if d.fact_key == "scholarship_status:student_7")
    if scholarship_decision.action != "unchanged":
        fail(
            f"the scholarship episode from session 1 was re-swept (in-memory read-position "
            f"reset across the process restart) but its value hasn't changed -- must be "
            f"'unchanged', not a duplicate write. Got {scholarship_decision.action!r}"
        )
    log("scholarship_status:student_7 -> 'unchanged' as expected: re-sweeping an old, "
        "already-consolidated episode after a restart must NOT create a duplicate fact version.")

    track_decisions = [d for d in decisions if d.fact_key == "preferred_track:student_7"]
    old_track_decision = next(d for d in track_decisions if d.episode_id == snapshot["episodes"][1]["id"])
    new_track_decision = next(d for d in track_decisions if d.episode_id == e3.id)
    log(f"old episode {old_track_decision.episode_id} (Data Science) -> {old_track_decision.action}")
    log(f"new episode {new_track_decision.episode_id} (AI, session 2) -> {new_track_decision.action}")
    if old_track_decision.action != "conflict_resolved":
        fail("the older Data Science episode should lose to the newer AI episode in this re-sweep")
    if new_track_decision.action != "versioned":
        fail("the AI episode is a genuine change from the on-disk current value and must version")
    log("PASS — even with zero in-memory tracking carried over, on-disk versioning kept "
        "every outcome exactly correct.\n")

    log("=" * 70)
    log("TEST 5 — final fact history reflects the true order of events across both sessions")
    log("=" * 70)
    final_history = semantic.get_history("preferred_track:student_7")
    values = [f.value for f in final_history]
    log(f"preferred_track:student_7 full history: {values}")
    if values != ["Data Science", "Ai"]:
        fail(f"expected history ['Data Science', 'Ai'] across both sessions, got {values}")
    scholarship_history = semantic.get_history("scholarship_status:student_7")
    if len(scholarship_history) != 1:
        fail(f"scholarship fact should still have exactly 1 version, got {len(scholarship_history)}")
    log("PASS — full, correct history spans both processes as if it had been one continuous run.\n")

    episodic.close()
    semantic.close()

    log("\n" + "=" * 70)
    log("ALL TESTS PASSED — persistence across independent OS processes confirmed")
    log("=" * 70)
    # Evidence is written BEFORE cleanup below, since it embeds session 1's
    # log file -- deleting that file first would leave the evidence
    # incomplete even though every test genuinely passed.
    write_evidence(passed=True)

    log("\n" + "=" * 70)
    log("Cleaning up dedicated test file(s) -- never touched memory/store.db")
    log("=" * 70)
    for f in (PERSIST_DB, SNAPSHOT_FILE, SESSION1_LOG):
        if f.exists():
            f.unlink()
            log(f"removed {f}")


if __name__ == "__main__":
    main()