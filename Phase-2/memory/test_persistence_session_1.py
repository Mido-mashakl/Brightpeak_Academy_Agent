"""
Standalone test — Cross-Session Persistence (SESSION 1 of 2)
================================================================
Run directly, as its own OS process: `python memory/test_persistence_session_1.py`
Then, AFTER this process has fully exited, run session 2 as a SEPARATE
process: `python memory/test_persistence_session_2.py`

Why two files instead of one script with two functions
--------------------------------------------------------
Every other "standalone" test in this suite proves a module works
correctly *within* one Python process. That is not what "long-term
memory" actually needs to prove. A dict that survives until the script
ends would pass those tests too. The one thing that separates real
persistence from an in-memory mock is that the data has to survive the
process itself dying -- no shared interpreter, no shared object
references, nothing left in RAM to cheat with.

So this test is deliberately split into two independently-invoked
scripts. Session 1 (this file) writes real rows into a real SQLite file
on disk via EpisodicStore / SemanticStore / ConsolidationLayer, closes
both connections explicitly, and calls sys.exit(0) -- the process is
gone. Session 2 is launched fresh, minutes or days later if you want,
opens brand-new store instances against that same file, and can only
see what actually made it to disk. If it can reconstruct exactly what
session 1 wrote using nothing but the file path, persistence is real.

What this session does NOT reuse from store.db
--------------------------------------------------
Deliberately does NOT touch memory/store.db (the real production file)
-- uses its own dedicated file under memory/evidence/ instead, so this
test can be re-run repeatedly without ever risking real data. Session 2
cleans that file up at the end, once it no longer needs it.
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

log_lines: list[str] = []


def log(line: str = "") -> None:
    print(line)
    log_lines.append(line)


def fail(msg: str) -> None:
    log(f"FAIL: {msg}")
    SESSION1_LOG.write_text("\n".join(log_lines), encoding="utf-8")
    sys.exit(1)


def main() -> None:
    log("=" * 70)
    log("SESSION 1 — writes real data, then this OS process exits completely")
    log("=" * 70)
    log(f"PID of this process: {os.getpid()}")

    # Fresh start every run: a leftover file from a previous, possibly
    # interrupted run must never leak into this one.
    for stale in (PERSIST_DB, SNAPSHOT_FILE, SESSION1_LOG):
        if stale.exists():
            stale.unlink()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    episodic = EpisodicStore(db_path=PERSIST_DB)
    semantic = SemanticStore(db_path=PERSIST_DB)
    log(f"Opened real SQLite file on disk: {PERSIST_DB}")

    log("\n" + "-" * 70)
    log("Writing two episodes for student 7 (advisor session, week 1)")
    log("-" * 70)
    e1 = episodic.insert(
        event_summary="Student is eligible for the merit scholarship",
        context="advising session, scholarship review",
        outcome="eligible",
        metadata={"student_id": 7},
    )
    e2 = episodic.insert(
        event_summary="Student confirmed interest in the Data Science track",
        context="advising session, track selection",
        outcome="noted",
        metadata={"student_id": 7},
    )
    log(f"episode {e1.id}: {e1.event_summary!r}")
    log(f"episode {e2.id}: {e2.event_summary!r}")

    log("\n" + "-" * 70)
    log("Running consolidation so semantic memory has real, versioned facts too")
    log("-" * 70)
    layer = ConsolidationLayer(episodic, semantic)
    decisions = layer.run()
    for d in decisions:
        log(f"  episode={d.episode_id} -> {d.action:9s} fact_key={d.fact_key}")
    if len(decisions) != 2 or any(d.action != "created" for d in decisions):
        fail(f"expected 2 'created' decisions in session 1, got {[(d.episode_id, d.action) for d in decisions]}")

    scholarship_fact = semantic.get_current("scholarship_status:student_7")
    track_fact = semantic.get_current("preferred_track:student_7")
    if scholarship_fact is None or track_fact is None:
        fail("both facts should exist in semantic memory before session 1 exits")
    log(f"scholarship_status:student_7 -> {scholarship_fact.value!r} (version {scholarship_fact.version})")
    log(f"preferred_track:student_7    -> {track_fact.value!r} (version {track_fact.version})")

    # Hand session 2 exactly what to expect -- not by keeping anything in
    # memory (this process is about to die), but by writing it to disk
    # right alongside the data itself.
    snapshot = {
        "session1_pid": os.getpid(),
        "episodes": [e1.to_dict(), e2.to_dict()],
        "facts": {
            "scholarship_status:student_7": scholarship_fact.to_dict(),
            "preferred_track:student_7": track_fact.to_dict(),
        },
    }
    SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    log(f"\nWrote expectation snapshot for session 2 to compare against: {SNAPSHOT_FILE}")

    log("\n" + "-" * 70)
    log("Closing both store connections explicitly")
    log("-" * 70)
    episodic.close()
    semantic.close()
    log("Connections closed. Nothing about this data lives in RAM anymore --")
    log("only what is on disk at " + str(PERSIST_DB) + " is real from here on.")

    SESSION1_LOG.write_text("\n".join(log_lines), encoding="utf-8")

    log("\n" + "=" * 70)
    log("SESSION 1 DONE. Now run, as a SEPARATE process:")
    log("    python memory/test_persistence_session_2.py")
    log("=" * 70)


if __name__ == "__main__":
    main()
    sys.exit(0)