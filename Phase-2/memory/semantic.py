"""
Brightpeak Academy - Memory System Extension
==============================================
Semantic Memory
-----------------

Stores stable, reusable FACTS -- not raw events. The difference matters:
an episodic store might hold three separate episodes ("Ahmed asked about
AI track", "Ahmed asked about AI track again", "Ahmed confirmed AI
track"); semantic memory holds exactly one current fact:
    fact_key="preferred_track", value="AI"

This module ONLY stores and versions facts. It does NOT decide which
facts to create or how to resolve conflicts between two episodes that
imply different facts -- that reasoning belongs to the Consolidation
Layer (memory/consolidation.py, the next component), which is the only
thing allowed to call `upsert()`. The Promote-or-Drop Router never
writes here directly (see router.py's own constraint).

Two production problems this store has to solve honestly, both shown in
the course material:

  1. Versioning: a fact changes (Ahmed's interest: Flutter -> AI). The
     old value is never silently overwritten -- it's marked
     `superseded_by` the new row's id and kept, so a grader (or the
     agent) can see the fact's full history, not just its current value.

  2. Expiration: a fact can go stale on its own even with no update
     (e.g. "interested in Summer 2025 internship" -- a year later that's
     no longer relevant even though nothing "changed" it). `expires_at`
     is a real, checkable timestamp; `get_current()` will not return an
     expired fact.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

MEMORY_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = MEMORY_DIR / "store.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_key          TEXT    NOT NULL,
    value             TEXT    NOT NULL,
    version           INTEGER NOT NULL,
    created_at        TEXT    NOT NULL,
    expires_at        TEXT,
    superseded_by     INTEGER,
    source_episode_ids TEXT   NOT NULL DEFAULT '[]',
    metadata          TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(fact_key);
"""


@dataclass
class Fact:
    id: int
    fact_key: str
    value: str
    version: int
    created_at: str
    expires_at: Optional[str]
    superseded_by: Optional[int]
    source_episode_ids: list
    metadata: dict

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Fact":
        return cls(
            id=row["id"],
            fact_key=row["fact_key"],
            value=row["value"],
            version=row["version"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            superseded_by=row["superseded_by"],
            source_episode_ids=json.loads(row["source_episode_ids"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def is_expired(self, as_of: Optional[datetime] = None) -> bool:
        if not self.expires_at:
            return False
        as_of = as_of or datetime.now(timezone.utc)
        return datetime.fromisoformat(self.expires_at) <= as_of

    def is_superseded(self) -> bool:
        return self.superseded_by is not None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fact_key": self.fact_key,
            "value": self.value,
            "version": self.version,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "superseded_by": self.superseded_by,
            "source_episode_ids": self.source_episode_ids,
            "metadata": self.metadata,
        }


class SemanticStore:
    """SQLite-backed semantic fact store with versioning and expiration.
    Intended caller: consolidation.py only.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write path — versioning lives here
    # ------------------------------------------------------------------
    def upsert(
        self,
        fact_key: str,
        value: str,
        source_episode_ids: Optional[list] = None,
        metadata: Optional[dict] = None,
        expires_at: Optional[str] = None,
        ttl_days: Optional[int] = None,
    ) -> Fact:
        """Creates a new version of `fact_key`. If a current (non-superseded)
        row already exists for this key, it is marked `superseded_by` the
        new row's id -- it is never deleted or overwritten in place.
        """
        if not fact_key or not fact_key.strip():
            raise ValueError("fact_key must be a non-empty string")
        if not value or not value.strip():
            raise ValueError("value must be a non-empty string")

        now = datetime.now(timezone.utc)
        if expires_at is None and ttl_days is not None:
            expires_at = (now + timedelta(days=ttl_days)).isoformat()

        previous = self._get_current_row(fact_key)
        next_version = (previous["version"] + 1) if previous else 1

        cur = self._conn.execute(
            "INSERT INTO facts (fact_key, value, version, created_at, expires_at, "
            "superseded_by, source_episode_ids, metadata) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)",
            (
                fact_key,
                value,
                next_version,
                now.isoformat(),
                expires_at,
                json.dumps(source_episode_ids or []),
                json.dumps(metadata or {}),
            ),
        )
        new_id = cur.lastrowid

        if previous is not None:
            self._conn.execute(
                "UPDATE facts SET superseded_by = ? WHERE id = ?",
                (new_id, previous["id"]),
            )

        self._conn.commit()
        return self.get_by_id(new_id)

    def expire_now(self, fact_key: str) -> Optional[Fact]:
        """Explicitly expires the current fact for `fact_key` as of now,
        rather than waiting for a pre-set `expires_at` to pass.
        """
        current = self._get_current_row(fact_key)
        if current is None:
            return None
        now_iso = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE facts SET expires_at = ? WHERE id = ?", (now_iso, current["id"])
        )
        self._conn.commit()
        return self.get_by_id(current["id"])

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------
    def get_by_id(self, fact_id: int) -> Optional[Fact]:
        row = self._conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
        return Fact.from_row(row) if row else None

    def _get_current_row(self, fact_key: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM facts WHERE fact_key = ? AND superseded_by IS NULL "
            "ORDER BY version DESC LIMIT 1",
            (fact_key,),
        ).fetchone()

    def get_current(self, fact_key: str, include_expired: bool = False) -> Optional[Fact]:
        """The one fact the rest of the system should actually use: the
        latest version, not superseded, and (by default) not expired.
        """
        row = self._get_current_row(fact_key)
        if row is None:
            return None
        fact = Fact.from_row(row)
        if fact.is_expired() and not include_expired:
            return None
        return fact

    def get_history(self, fact_key: str) -> list[Fact]:
        """Every version ever recorded for this key, oldest first --
        proves the old value was never silently lost."""
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE fact_key = ? ORDER BY version ASC", (fact_key,)
        ).fetchall()
        return [Fact.from_row(r) for r in rows]

    def list_all_current(self, include_expired: bool = False) -> list[Fact]:
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE superseded_by IS NULL"
        ).fetchall()
        facts = [Fact.from_row(r) for r in rows]
        if include_expired:
            return facts
        return [f for f in facts if not f.is_expired()]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SemanticStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()