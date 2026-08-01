"""
episodic_store.py
==================
=== CONCERN (Add-On Lab): Option B -- Agent Memory ===

Lets an advisor leave a short note about a student that the server
recalls automatically the NEXT time anyone asks for that student's
academic advisory -- even in a completely separate server process
(a real "session 2").

Design notes
------------
- Retrieval is BM25 keyword search (see keyword_search.py), not
  embeddings -- no API key required, same trade-off as Option A.
- Memory is scoped to ONE entity: student_id. A note written for
  student 3 is never visible when recalling for student 7.
- Persisted to a JSON file on disk (advisor_notes.json, next to this
  file) instead of an in-memory list. This project's demo restarts the
  MCP server as a fresh subprocess for every session (stdio transport),
  so anything kept only in memory would "forget" the instant the
  process exits. Writing to disk is what makes "session 2 recalls it
  on its own" actually true rather than a scripted illusion.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .keyword_search import KeywordStore

_STORE_PATH = Path(__file__).parent / "advisor_notes.json"

_store = KeywordStore()


def _load_from_disk() -> None:
    """Populate the in-memory KeywordStore from the JSON file, if any."""
    if not _STORE_PATH.exists():
        return
    try:
        rows = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    for row in rows:
        _store.upsert(payload=row["payload"], metadata=row["metadata"])


def _persist_to_disk() -> None:
    """Write the full current set of notes back to the JSON file."""
    _STORE_PATH.write_text(
        json.dumps(_store.rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


_load_from_disk()


# ---------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------

def remember_note(student_id: int, note_text: str, author_role: str) -> dict:
    """Store a short structured note about a student.

    Args:
        student_id:  the student this note is scoped to.
        note_text:   what the advisor wants remembered (their own words).
        author_role: 'instructor' or 'registrar' -- who left the note,
                     for audit purposes only, not used for filtering.
    """
    record = {
        "event_summary": note_text,
        "recorded_by": author_role,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    _store.upsert(
        payload=record,
        metadata={"entity_id": str(student_id)},
    )
    _persist_to_disk()
    return record


# ---------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------

def recall_notes(student_id: int, query: Optional[str] = None, top_k: int = 3) -> list[str]:
    """Return the most relevant past notes for this student.

    If `query` is omitted, falls back to the most recently written
    notes for this student (still scoped, just not keyword-ranked) --
    this is what a fresh advisory-generation session calls with no
    specific question in mind.
    """
    filter_ = {"entity_id": str(student_id)}

    if query:
        matches = _store.query(query_text=query, top_k=top_k, filter=filter_)
    else:
        matches = [
            row for row in _store.rows
            if row["metadata"].get("entity_id") == str(student_id)
        ][-top_k:]

    return [m["payload"]["event_summary"] for m in matches]
