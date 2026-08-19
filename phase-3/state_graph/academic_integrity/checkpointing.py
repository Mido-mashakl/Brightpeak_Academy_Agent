"""
Academic Integrity — checkpointing layer.

Uses LangGraph's SQLite checkpointer pointed at the SAME brightpeak.db used
by the rest of Phase-3 (not a separate checkpoint file), so a killed process
resumes with `graph.invoke(None, config)` using the same thread_id, no
re-execution of completed nodes, no state loss.
"""

from __future__ import annotations

import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "brightpeak.db")

_checkpointer: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    """Returns a singleton checkpointer backed by brightpeak.db.

    check_same_thread=False because the platform (web server) and any
    background resume calls may run on different threads than the one
    that created the connection.
    """
    global _checkpointer
    if _checkpointer is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _checkpointer = SqliteSaver(conn)
    return _checkpointer


def thread_id_for_case(case_id: int) -> str:
    return f"academic-integrity-{case_id}"