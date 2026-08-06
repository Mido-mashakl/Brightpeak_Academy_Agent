"""
Standalone test — Semantic Memory
====================================
Run directly: `python memory/test_semantic.py`

Tests semantic.py completely alone. No consolidation.py, no episodic
store, no router. Uses a temp SQLite file. Directly exercises the two
production problems the lab calls out: versioning (image 8) and
expiration (image 9).
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from semantic import SemanticStore  # noqa: E402

EVIDENCE_FILE = MEMORY_DIR / "evidence" / "semantic_evidence.txt"
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
        "EVIDENCE — test_semantic.py (standalone, temp SQLite file)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'}",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_semantic.db"
        store = SemanticStore(db_path=db_path)

        log("=" * 70)
        log("TEST 1 — first upsert creates version 1, is 'current'")
        log("=" * 70)
        v1 = store.upsert(fact_key="preferred_track:student_14", value="Flutter",
                           source_episode_ids=[1])
        log(f"v1: id={v1.id}, version={v1.version}, value={v1.value!r}, "
            f"superseded_by={v1.superseded_by}")
        if v1.version != 1 or v1.superseded_by is not None:
            fail("first upsert should be version 1 and not superseded")
        current = store.get_current("preferred_track:student_14")
        if current is None or current.value != "Flutter":
            fail("get_current() should return the freshly inserted fact")
        log("PASS\n")

        log("=" * 70)
        log("TEST 2 — a fact CHANGE creates version 2; version 1 is superseded, not deleted")
        log("=" * 70)
        v2 = store.upsert(fact_key="preferred_track:student_14", value="AI",
                           source_episode_ids=[5])
        log(f"v2: id={v2.id}, version={v2.version}, value={v2.value!r}")

        v1_reread = store.get_by_id(v1.id)
        log(f"v1 re-read: superseded_by={v1_reread.superseded_by}, "
            f"still in DB with value={v1_reread.value!r}")
        if v1_reread.superseded_by != v2.id:
            fail("old version should be marked superseded_by the new version's id")
        if v1_reread.value != "Flutter":
            fail("old version's value must NOT be overwritten — versioning is broken")

        current2 = store.get_current("preferred_track:student_14")
        if current2.value != "AI":
            fail(f"get_current() should now return 'AI', got {current2.value!r}")

        history = store.get_history("preferred_track:student_14")
        log(f"Full history ({len(history)} versions): "
            f"{[(f.version, f.value) for f in history]}")
        if [f.value for f in history] != ["Flutter", "AI"]:
            fail("get_history() should show both versions in order, oldest first")
        log("PASS — old value preserved, new value is current, nothing silently lost.\n")

        log("=" * 70)
        log("TEST 3 — expiration: a fact with a past expires_at is not returned as current")
        log("=" * 70)
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        store.upsert(
            fact_key="internship_interest:student_20",
            value="Summer 2025 internship",
            expires_at=past,
        )
        should_be_none = store.get_current("internship_interest:student_20")
        log(f"get_current() for an already-expired fact: {should_be_none}")
        if should_be_none is not None:
            fail("expired fact should not be returned by get_current()")

        still_visible = store.get_current("internship_interest:student_20", include_expired=True)
        if still_visible is None:
            fail("expired fact should still be readable with include_expired=True — "
                 "expiration must not silently delete data")
        log(f"With include_expired=True, still readable: {still_visible.value!r}")
        log("PASS — expired fact hidden by default, still recoverable, not deleted.\n")

        log("=" * 70)
        log("TEST 4 — explicit expire_now() on a fact that had no prior expiry")
        log("=" * 70)
        store.upsert(fact_key="scholarship_status:student_30", value="eligible")
        expired = store.expire_now("scholarship_status:student_30")
        log(f"expires_at set to: {expired.expires_at}")
        if store.get_current("scholarship_status:student_30") is not None:
            fail("fact should no longer be 'current' after expire_now()")
        log("PASS\n")

        log("=" * 70)
        log("TEST 5 — list_all_current() excludes superseded and expired facts")
        log("=" * 70)
        all_current = store.list_all_current()
        keys = sorted(f.fact_key for f in all_current)
        log(f"Current facts: {keys}")
        if "preferred_track:student_14" not in keys:
            fail("preferred_track:student_14 (v2, AI) should be in current facts")
        if "internship_interest:student_20" in keys:
            fail("expired internship_interest fact leaked into list_all_current()")
        if "scholarship_status:student_30" in keys:
            fail("explicitly expired scholarship_status fact leaked into list_all_current()")
        log("PASS\n")

        store.close()

        log("=" * 70)
        log("ALL TESTS PASSED")
        log("=" * 70)
        write_evidence(passed=True)


if __name__ == "__main__":
    main()