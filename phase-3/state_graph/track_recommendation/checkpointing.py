"""
checkpointing.py — SQLite-backed checkpointer for the Track
Recommendation graph.

This is what makes every `interrupt()` a REAL pause: state is persisted
to disk, so execution can resume with `Command(resume=...)` on the same
thread_id even after the process restarts.
"""
import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "checkpoints.sqlite")


def get_checkpointer() -> SqliteSaver:
    conn = sqlite3.connect(CHECKPOINT_PATH, check_same_thread=False)
    return SqliteSaver(conn)