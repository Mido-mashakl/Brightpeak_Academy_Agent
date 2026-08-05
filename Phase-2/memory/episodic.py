"""
Brightpeak Academy - Memory System Extension
==============================================
Episodic Memory
-----------------

Real, persistent storage for events the Promote-or-Drop Router decided
are worth keeping (destination == "episodic"). Backed by SQLite on disk
-- not a Python list/dict -- so episodes survive past the current
process, which is the entire point of long-term memory.

Each episode answers exactly what the slides describe episodic memory
should answer: what happened, when, in what context, with what outcome.
That maps directly onto the fields `MemoryRoutingDecision` already
produces (see router.py), so the router can hand its decision straight
to `EpisodicStore.insert()` with no translation step.

This store does not decide what gets kept -- that's the router's job.
It only persists what it's told to persist and lets you read it back.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MEMORY_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = MEMORY_DIR / "store.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    event_summary TEXT    NOT NULL,
    context       TEXT,
    outcome       TEXT,
    metadata      TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(timestamp);
"""


@dataclass
class Episode:
    id: int
    timestamp: str
    event_summary: str
    context: Optional[str]
    outcome: Optional[str]
    metadata: dict

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Episode":
        return cls(
            id=row["id"],
            timestamp=row["timestamp"],
            event_summary=row["event_summary"],
            context=row["context"],
            outcome=row["outcome"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "event_summary": self.event_summary,
            "context": self.context,
            "outcome": self.outcome,
            "metadata": self.metadata,
        }


class EpisodicStore:
    """SQLite-backed episodic memory. One file on disk per store instance
    (defaults to memory/store.db in production; tests point this at a
    temp file so they never touch the real store).
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def insert(
        self,
        event_summary: str,
        context: Optional[str] = None,
        outcome: Optional[str] = None,
        metadata: Optional[dict] = None,
        timestamp: Optional[str] = None,
    ) -> Episode:
        if not event_summary or not event_summary.strip():
            raise ValueError("event_summary must be a non-empty string")

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        meta = metadata or {}

        cur = self._conn.execute(
            "INSERT INTO episodes (timestamp, event_summary, context, outcome, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, event_summary, context, outcome, json.dumps(meta)),
        )
        self._conn.commit()
        return self.get_by_id(cur.lastrowid)

    def get_by_id(self, episode_id: int) -> Optional[Episode]:
        row = self._conn.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        return Episode.from_row(row) if row else None

    def list_recent(self, limit: int = 10) -> list[Episode]:
        rows = self._conn.execute(
            "SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Episode.from_row(r) for r in rows]

    def list_by_metadata(self, filters: dict, limit: int = 50) -> list[Episode]:
        """Naive but honest metadata filtering: pulls candidates and
        filters in Python. Fine at this scale; a real production system
        would index specific metadata keys instead of scanning JSON blobs.
        """
        rows = self._conn.execute(
            "SELECT * FROM episodes ORDER BY timestamp DESC"
        ).fetchall()
        matches = []
        for row in rows:
            episode = Episode.from_row(row)
            if all(episode.metadata.get(k) == v for k, v in filters.items()):
                matches.append(episode)
                if len(matches) >= limit:
                    break
        return matches

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM episodes").fetchone()
        return row["c"]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "EpisodicStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()