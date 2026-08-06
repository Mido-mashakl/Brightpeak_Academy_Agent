"""
Standalone test — Consolidation Layer
========================================
Run directly: `python memory/test_consolidation.py`

Tests consolidation.py wired to REAL EpisodicStore and SemanticStore
instances (temp SQLite files, never memory/store.db) -- this component
is inherently an integration between the two, so faking either store
out would not prove anything. Directly exercises the two production
problems the lab calls out for this component: conflict resolution and
the versioning trigger.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from consolidation import ConsolidationLayer  # noqa: E402
from episodic import EpisodicStore  # noqa: E402
from semantic import SemanticStore  # noqa: E402

EVIDENCE_FILE = MEMORY_DIR / "evidence" / "consolidation_conflict_evidence.txt"
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
        "EVIDENCE — test_consolidation.py",
        "(consolidation.py + REAL EpisodicStore + REAL SemanticStore, temp files)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        episodic = EpisodicStore(db_path=Path(tmp) / "episodic_test.db")
        semantic = SemanticStore(db_path=Path(tmp) / "semantic_test.db")
        layer = ConsolidationLayer(episodic, semantic)

        log("=" * 70)
        log("SCENARIO — Ahmed (student 14) changes his mind on track, mid-sweep")
        log("=" * 70)

        # Episode 1: Ahmed first says Flutter.
        e1 = episodic.insert(
            event_summary="Student confirmed interest in the Flutter track",
            context="advising session 1",
            outcome="noted",
            metadata={"student_id": 14},
        )
        # Episode 2 (later, same batch): Ahmed changes his mind to AI.
        e2 = episodic.insert(
            event_summary="Student confirmed interest in the AI track instead",
            context="advising session 2, same week",
            outcome="noted",
            metadata={"student_id": 14},
        )
        # Episode 3: an unrelated flagged-attendance event for student 20.
        e3 = episodic.insert(
            event_summary="Student attendance is below the 75% threshold, flagged for review",
            context="course 3 sweep",
            outcome="flagged",
            metadata={"student_id": 20},
        )
        # Episode 4: small talk -- implies no stable fact at all.
        e4 = episodic.insert(
            event_summary="Student said thanks and logged off",
            context="advising session 2",
            outcome=None,
            metadata={"student_id": 14},
        )
        log(f"Inserted episodes into REAL episodic store: {e1.id}, {e2.id}, {e3.id}, {e4.id}")

        log("\n" + "=" * 70)
        log("TEST 1 — run() processes all 4 pending episodes")
        log("=" * 70)
        decisions = layer.run()
        log(f"Decisions this pass: {len(decisions)}")
        for d in decisions:
            log(f"  episode={d.episode_id} -> {d.action:17s} fact_key={d.fact_key}")
        if len(decisions) != 4:
            fail(f"expected 4 decisions (one per episode), got {len(decisions)}")
        log("PASS\n")

        log("=" * 70)
        log("TEST 2 — CONFLICT RESOLUTION: episode 1 (Flutter) loses to episode 2 (AI)")
        log("=" * 70)
        e1_decision = next(d for d in decisions if d.episode_id == e1.id)
        e2_decision = next(d for d in decisions if d.episode_id == e2.id)
        log(f"episode {e1.id} (Flutter, earlier) -> action={e1_decision.action}")
        log(f"    reasoning: {e1_decision.reasoning}")
        log(f"episode {e2.id} (AI, later)       -> action={e2_decision.action}")
        log(f"    reasoning: {e2_decision.reasoning}")

        if e1_decision.action != "conflict_resolved":
            fail(
                f"episode {e1.id} implied a conflicting, older value for the same "
                f"fact_key and should have been marked 'conflict_resolved', "
                f"got {e1_decision.action!r}"
            )
        if e2_decision.action != "created":
            fail(
                f"episode {e2.id} is the more recent, winning episode for a brand "
                f"new fact_key and should be 'created', got {e2_decision.action!r}"
            )

        current_track = semantic.get_current("preferred_track:student_14")
        log(f"semantic.get_current('preferred_track:student_14') -> {current_track.value!r}")
        if current_track is None or current_track.value != "Ai":
            fail(
                f"the AI track (episode {e2.id}, the more recent one) should have won "
                f"and be the current fact, got {current_track!r}"
            )
        history = semantic.get_history("preferred_track:student_14")
        log(f"Full fact history: {[(f.version, f.value) for f in history]}")
        if len(history) != 1:
            fail(
                "the LOSING episode in a conflict must never itself trigger a write -- "
                "only one version should exist after a single consolidation pass"
            )
        log("PASS — more recent episode won, older conflicting episode logged but never "
            "written to semantic memory, exactly one fact version exists.\n")

        log("=" * 70)
        log("TEST 3 — unrelated fact (attendance flag, student 20) created independently")
        log("=" * 70)
        e3_decision = next(d for d in decisions if d.episode_id == e3.id)
        log(f"episode {e3.id} -> action={e3_decision.action}, fact_key={e3_decision.fact_key}")
        if e3_decision.action != "created" or e3_decision.fact_key != "attendance_flag:student_20":
            fail("student 20's attendance flag should be created as its own, unrelated fact")
        flag_fact = semantic.get_current("attendance_flag:student_20")
        if flag_fact is None or flag_fact.value != "flagged":
            fail("attendance_flag:student_20 should be 'flagged' in semantic memory")
        log("PASS — unrelated students' facts never interfere with each other.\n")

        log("=" * 70)
        log("TEST 4 — small talk (episode 4) has no extractable fact, skipped honestly")
        log("=" * 70)
        e4_decision = next(d for d in decisions if d.episode_id == e4.id)
        log(f"episode {e4.id} -> action={e4_decision.action}")
        if e4_decision.action != "skipped_no_fact":
            fail("small talk with no stable information should be 'skipped_no_fact', not forced into a fact")
        log("PASS\n")

        log("=" * 70)
        log("TEST 5 — VERSIONING TRIGGER: re-running run() with no new episodes is a no-op")
        log("=" * 70)
        decisions_again = layer.run()
        log(f"Decisions on an empty pass (nothing new pending): {len(decisions_again)}")
        if decisions_again:
            fail("run() should do nothing when there are no new episodes since the last pass")
        log("PASS — no new episodes, no new decisions, no new fact versions.\n")

        log("=" * 70)
        log("TEST 6 — VERSIONING TRIGGER: a NEW episode with the SAME value must not create "
            "a spurious version (idempotent under repeated confirmation)")
        log("=" * 70)
        e5 = episodic.insert(
            event_summary="Student re-confirmed interest in the AI track instead",
            context="advising session 3",
            outcome="noted",
            metadata={"student_id": 14},
        )
        decisions3 = layer.run()
        log(f"Decisions after inserting a re-confirming episode {e5.id}: {len(decisions3)}")
        for d in decisions3:
            log(f"  episode={d.episode_id} -> {d.action:17s} fact_key={d.fact_key}")
        e5_decision = next(d for d in decisions3 if d.episode_id == e5.id)
        if e5_decision.action != "unchanged":
            fail(
                f"re-confirming the SAME value should be 'unchanged' (no spurious new "
                f"version), got {e5_decision.action!r}"
            )
        history_after = semantic.get_history("preferred_track:student_14")
        log(f"Fact history after re-confirmation: {[(f.version, f.value) for f in history_after]}")
        if len(history_after) != 1:
            fail(
                f"re-confirming an unchanged fact must NOT create a new version -- "
                f"expected 1 version total, got {len(history_after)}"
            )
        log("PASS — versioning only triggers on an actual change, confirmed idempotent.\n")

        log("=" * 70)
        log("TEST 7 — a genuine LATER change still versions correctly (not stuck forever)")
        log("=" * 70)
        e6 = episodic.insert(
            event_summary="Student confirmed interest in the Cybersecurity track instead",
            context="advising session 4",
            outcome="noted",
            metadata={"student_id": 14},
        )
        decisions4 = layer.run()
        e6_decision = next(d for d in decisions4 if d.episode_id == e6.id)
        log(f"episode {e6.id} -> action={e6_decision.action}")
        if e6_decision.action != "versioned":
            fail(f"a genuine change to an existing fact_key should be 'versioned', got {e6_decision.action!r}")
        final_history = semantic.get_history("preferred_track:student_14")
        log(f"Final fact history: {[(f.version, f.value) for f in final_history]}")
        if [f.value for f in final_history] != ["Ai", "Cybersecurity"]:
            fail(f"expected exactly 2 versions (Ai then Cybersecurity), got {[f.value for f in final_history]}")
        log("PASS — real changes still create a new version; old value preserved in history.\n")

        episodic.close()
        semantic.close()

        log("=" * 70)
        log("ALL TESTS PASSED")
        log("=" * 70)
        write_evidence(passed=True)


if __name__ == "__main__":
    main()