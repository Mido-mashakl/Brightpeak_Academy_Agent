"""
Faculty Hiring — checkpointing layer.

Uses LangGraph's SQLite checkpointer pointed at the SAME brightpeak.db used by
the rest of Phase-3 (same pattern as academic_integrity/checkpointing.py).

thread_id = f"faculty-hiring-{job_id}"

This means:
- Every job posting has exactly one persistent graph workflow.
- A new CV upload resumes the SAME thread (same job), not a new one.
- A killed process resumes via graph.invoke(None, config) with the same
  thread_id — no re-ingestion, no re-parsing, no re-scoring of old CVs.
"""

from __future__ import annotations

import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "brightpeak.db")

_checkpointer: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    """Returns a singleton checkpointer backed by brightpeak.db.

    check_same_thread=False because the web server and background resume
    calls may run on different threads from the one that created the connection.
    """
    global _checkpointer
    if _checkpointer is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
    return _checkpointer


def thread_id_for_job(job_id: int) -> str:
    """The identity of the persistent hiring workflow for one job posting."""
    return f"faculty-hiring-{job_id}"