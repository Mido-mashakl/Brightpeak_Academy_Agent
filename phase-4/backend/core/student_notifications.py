"""
core/student_notifications.py
==============================
Durable per-student notifications — the missing layer between the
in-process SSE pub/sub (notifications.py, fire-and-forget) and the
student's frontend.

WHY THIS EXISTS
---------------
notifications.py is intentionally ephemeral: if no SSE subscriber is
listening when publish() is called the event is silently dropped. That is
correct for the advisor channel (advisors have a dedicated requests page
they keep open), but wrong for students: a student who isn't looking at
the chat when their advisor replies "need more info" would miss it
entirely and have no way to know unless they happened to reopen the page
and we actively check.

This module adds a thin DB-backed layer:
  - write_notification()  — called alongside publish() so there is always
                            a durable record, even if the SSE was dropped.
  - get_unread()          — called on page load; returns anything not yet
                            seen so the UI can reconstruct missed events.
  - mark_read()           — called when the student sees or acts on a card.

The table is created lazily on first write (CREATE TABLE IF NOT EXISTS),
so no schema.sql change is needed and existing brightpeak.db files are
upgraded automatically on first use.

CHANNEL NAMING
--------------
type values mirror the SSE event names so the frontend can handle both
code paths (SSE arrival + page-load unread fetch) with the same logic:
  "more_info_requested"  — advisor chose request_more_info on a
                           certificate/scholarship request
  "assessment_requested" — advisor chose request_assessment on a
                           track recommendation
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import mcp_server.database as _mcp_db


def _conn():
    """Reuse the same brightpeak.db connection factory as the rest of the
    backend — one file, one pragma, consistent behaviour."""
    return _mcp_db._conn()


def _ensure_table() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS StudentNotifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  INTEGER NOT NULL,
                type        TEXT    NOT NULL,
                payload     TEXT    NOT NULL DEFAULT '{}',
                read        INTEGER NOT NULL DEFAULT 0,
                created_at  DATETIME DEFAULT (DATETIME('now'))
            )
        """)


def write_notification(student_id: int, type: str, payload: dict[str, Any]) -> int:
    """Persist a notification and return its new id."""
    _ensure_table()
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO StudentNotifications (student_id, type, payload)
               VALUES (?, ?, ?)""",
            (student_id, type, json.dumps(payload)),
        )
        return cur.lastrowid


def get_unread(student_id: int) -> list[dict[str, Any]]:
    """Return all unread notifications for this student, oldest first."""
    _ensure_table()
    with _conn() as con:
        rows = con.execute(
            """SELECT id, type, payload, created_at
               FROM StudentNotifications
               WHERE student_id = ? AND read = 0
               ORDER BY id ASC""",
            (student_id,),
        ).fetchall()
    out = []
    for row in rows:
        entry = dict(row)
        try:
            entry["payload"] = json.loads(entry["payload"])
        except (json.JSONDecodeError, TypeError):
            entry["payload"] = {}
        out.append(entry)
    return out


def mark_read(notification_id: int, student_id: int) -> bool:
    """Mark one notification as read. student_id guards against another
    student marking someone else's notification. Returns True if a row
    was actually updated."""
    _ensure_table()
    with _conn() as con:
        cur = con.execute(
            "UPDATE StudentNotifications SET read = 1 WHERE id = ? AND student_id = ?",
            (notification_id, student_id),
        )
        return cur.rowcount > 0


def mark_all_read(student_id: int) -> int:
    """Mark every unread notification for this student as read.
    Returns the count of rows updated."""
    _ensure_table()
    with _conn() as con:
        cur = con.execute(
            "UPDATE StudentNotifications SET read = 1 WHERE student_id = ? AND read = 0",
            (student_id,),
        )
        return cur.rowcount
