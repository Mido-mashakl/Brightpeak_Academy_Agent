"""
Standalone test — Memory Recall + Memory Verification
=========================================================
Run directly: `python memory/test_recall_verification.py`

Tests recall.py and verification.py wired to REAL EpisodicStore and
SemanticStore instances (temp SQLite files, never memory/store.db) --
same reasoning as test_consolidation.py: these components are inherent
integrations, faking either store out wouldn't prove anything.

The scenario deliberately plants three kinds of "bad" memory a naive
recall (score-and-return, no verification step) would happily hand to
the agent, and proves the verification layer catches all three:
  1. an episode whose implied fact has since been CONTRADICTED by a
     newer, current semantic fact (stale/superseded)
  2. a semantic fact that has EXPIRED
  3. a memory that only weakly, coincidentally overlaps the query
     (irrelevant, not actually on-topic)
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
from recall import MemoryRecall  # noqa: E402
from semantic import SemanticStore  # noqa: E402
from verification import MemoryVerifier  # noqa: E402

EVIDENCE_FILE = MEMORY_DIR / "evidence" / "recall_verification_evidence.txt"
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
        "EVIDENCE — test_recall_verification.py",
        "(recall.py + verification.py + REAL EpisodicStore + REAL SemanticStore)",
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
        log("SETUP — build a real, mixed history for two students")
        log("=" * 70)

        # Student 14: track changes over time, a scholarship status that
        # will later be allowed to expire, plus one irrelevant small-talk
        # episode.
        ep_flutter = episodic.insert(
            event_summary="Student confirmed interest in the Flutter track",
            context="advising session 1",
            outcome="noted",
            metadata={"student_id": 14},
        )
        ep_ai = episodic.insert(
            event_summary="Student confirmed interest in the AI track instead",
            context="advising session 2, same week",
            outcome="noted",
            metadata={"student_id": 14},
        )
        ep_scholarship = episodic.insert(
            event_summary="Student is eligible for the merit scholarship",
            context="advising session, scholarship review",
            outcome="eligible",
            metadata={"student_id": 14},
        )
        ep_smalltalk = episodic.insert(
            event_summary="Weather is nice today, student said thanks and logged off",
            context="chit-chat at the end of the call",
            outcome=None,
            metadata={"student_id": 14},
        )
        # Student 20: unrelated attendance flag, kept isolated from student 14.
        ep_attendance = episodic.insert(
            event_summary="Student attendance is below the 75% threshold, flagged for review",
            context="course 3 sweep",
            outcome="flagged",
            metadata={"student_id": 20},
        )
        log(
            f"Episodes: flutter={ep_flutter.id} ai={ep_ai.id} scholarship={ep_scholarship.id} "
            f"smalltalk={ep_smalltalk.id} attendance(student20)={ep_attendance.id}"
        )

        decisions = layer.run()
        log(f"Consolidation ran: {len(decisions)} decisions")
        for d in decisions:
            log(f"  episode={d.episode_id} -> {d.action:17s} fact_key={d.fact_key}")

        current_track = semantic.get_current("preferred_track:student_14")
        log(f"\nCurrent preferred_track:student_14 = {current_track.value!r} (v{current_track.version})")
        if current_track.value != "Ai":
            fail(f"setup assumption broken: expected current track 'Ai', got {current_track.value!r}")

        # Deliberately expire the scholarship fact -- simulates time
        # passing since it was written, exactly what is_expired() exists
        # to catch (see semantic.py).
        semantic.expire_now("scholarship_status:student_14")
        expired_fact = semantic.get_current("scholarship_status:student_14", include_expired=True)
        log(f"Manually expired scholarship_status:student_14 (expires_at={expired_fact.expires_at})")
        if not expired_fact.is_expired():
            fail("setup assumption broken: scholarship fact should now be expired")

        recall = MemoryRecall(episodic, semantic)
        verifier = MemoryVerifier(semantic)

        log("\n" + "=" * 70)
        log("TEST 1 — RECALL: query about track surfaces both track episodes + the fact")
        log("=" * 70)
        query1 = "what track did the student pick"
        results1 = recall.recall(query1, student_id=14)
        log(f"Query: {query1!r}")
        for r in results1:
            log(f"  [{r.source}] ref_id={r.ref_id} score={r.score:.2f} text={r.text!r}")
        sources1 = {(r.source, r.ref_id) for r in results1}
        expected1 = {("episodic", ep_flutter.id), ("episodic", ep_ai.id), ("semantic", current_track.id)}
        if not expected1.issubset(sources1):
            fail(f"expected recall to surface {expected1}, got {sources1}")
        log("PASS — recall found the relevant episodes and fact across both stores.\n")

        log("=" * 70)
        log("TEST 2 — VERIFICATION catches the STALE episode (Flutter, superseded by AI)")
        log("=" * 70)
        verdicts1 = verifier.verify_batch(query1, results1)
        for v in verdicts1:
            log(f"  [{v.result.source}] ref_id={v.result.ref_id} -> {v.verdict.upper()}")
            log(f"      reasoning: {v.reasoning}")
        flutter_verdict = next(v for v in verdicts1 if v.result.source == "episodic" and v.result.ref_id == ep_flutter.id)
        ai_verdict = next(v for v in verdicts1 if v.result.source == "episodic" and v.result.ref_id == ep_ai.id)
        fact_verdict = next(v for v in verdicts1 if v.result.source == "semantic")
        if flutter_verdict.verdict != "unsupported":
            fail(
                f"the Flutter episode has been contradicted by the current 'AI' fact "
                f"and must be graded 'unsupported', got {flutter_verdict.verdict!r}"
            )
        if ai_verdict.verdict != "supported":
            fail(f"the AI episode is corroborated by the current fact and should be 'supported', got {ai_verdict.verdict!r}")
        if fact_verdict.verdict != "supported":
            fail(f"the current, non-expired track fact should be 'supported', got {fact_verdict.verdict!r}")
        log("PASS — stale episode rejected, corroborated episode and current fact both kept.\n")

        log("=" * 70)
        log("TEST 3 — supported_only() hands the agent a clean list (no stale memory leaks through)")
        log("=" * 70)
        clean1 = verifier.supported_only(query1, results1)
        clean_ids1 = {(r.source, r.ref_id) for r in clean1}
        log(f"supported_only() -> {clean_ids1}")
        if ("episodic", ep_flutter.id) in clean_ids1:
            fail("the stale Flutter episode leaked into supported_only() -- verification failed to filter it")
        if ("episodic", ep_ai.id) not in clean_ids1 or ("semantic", current_track.id) not in clean_ids1:
            fail("supported_only() dropped genuinely supported memories it should have kept")
        log("PASS — agent-facing result set is clean.\n")

        log("=" * 70)
        log("TEST 4 — VERIFICATION catches the EXPIRED fact, and the episode it agrees with too")
        log("=" * 70)
        query2 = "is the student eligible for the merit scholarship"
        results2 = recall.recall(query2, student_id=14)
        for r in results2:
            log(f"  [{r.source}] ref_id={r.ref_id} score={r.score:.2f} text={r.text!r}")
        verdicts2 = verifier.verify_batch(query2, results2)
        for v in verdicts2:
            log(f"  [{v.result.source}] ref_id={v.result.ref_id} -> {v.verdict.upper()}")
            log(f"      reasoning: {v.reasoning}")
        scholarship_ep_verdict = next(
            (v for v in verdicts2 if v.result.source == "episodic" and v.result.ref_id == ep_scholarship.id),
            None,
        )
        if scholarship_ep_verdict is None:
            fail("expected the scholarship episode itself to be recalled for this query")
        if scholarship_ep_verdict.verdict != "unsupported":
            fail(
                f"the scholarship episode implies the same value as the now-EXPIRED fact -- "
                f"must be graded 'unsupported', not {scholarship_ep_verdict.verdict!r} "
                f"(note: other, unrelated results may also appear in the same recall -- this "
                f"assertion only checks the scholarship episode itself)"
            )
        log("PASS — expiration correctly propagates to the episode it agrees with: not presented as current.\n")

        log("=" * 70)
        log("TEST 5 — VERIFICATION grades weak coincidental overlap as IRRELEVANT, not supported")
        log("=" * 70)
        query3 = "student attendance flag review"  # only shares 'student' with the small-talk episode
        results3 = recall.recall(query3, student_id=14, min_score=0.0)
        smalltalk_hit = next((r for r in results3 if r.ref_id == ep_smalltalk.id and r.source == "episodic"), None)
        if smalltalk_hit is None:
            fail("expected the small-talk episode to be recalled with some nonzero (but weak) score")
        log(f"Small-talk episode recalled with score={smalltalk_hit.score:.2f} (below relevance floor)")
        smalltalk_verdict = verifier.verify(query3, smalltalk_hit)
        log(f"  -> {smalltalk_verdict.verdict.upper()}: {smalltalk_verdict.reasoning}")
        if smalltalk_verdict.verdict != "irrelevant":
            fail(f"weak, coincidental word overlap should be graded 'irrelevant', got {smalltalk_verdict.verdict!r}")
        log("PASS — coincidental overlap correctly rejected as irrelevant, not treated as support.\n")

        log("=" * 70)
        log("TEST 6 — student scoping: student 14's query never surfaces student 20's memory, and vice versa")
        log("=" * 70)
        query4 = "attendance flagged review"
        results_for_14 = recall.recall(query4, student_id=14)
        results_for_20 = recall.recall(query4, student_id=20)
        log(f"Query {query4!r} for student 14 -> {[(r.source, r.ref_id) for r in results_for_14]}")
        log(f"Query {query4!r} for student 20 -> {[(r.source, r.ref_id) for r in results_for_20]}")
        if any(r.ref_id == ep_attendance.id for r in results_for_14):
            fail("student 20's attendance episode leaked into a student-14-scoped recall")
        if not any(r.ref_id == ep_attendance.id and r.source == "episodic" for r in results_for_20):
            fail("student 20's own attendance episode should be recalled for a student-20-scoped query")
        log("PASS — recall is correctly isolated per student.\n")

        log("=" * 70)
        log("TEST 7 — to_context_string() produces a clean, agent-ready block from a clean result set")
        log("=" * 70)
        context_block = MemoryRecall.to_context_string(clean1)
        log(context_block)
        if "Flutter" in context_block:
            fail("to_context_string() must never include memory that verification rejected")
        if "AI" not in context_block and "Ai" not in context_block:
            fail("to_context_string() should include the corroborated AI track information")
        log("PASS — formatted context block is ready to hand to the agent, stale info excluded.\n")

        episodic.close()
        semantic.close()

        log("=" * 70)
        log("ALL TESTS PASSED")
        log("=" * 70)
        write_evidence(passed=True)


if __name__ == "__main__":
    main()