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
    global _checkpointer
    if _checkpointer is None:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        serde = JsonPlusSerializer(allowed_msgpack_modules=[
            ("state_graph.academic_integrity.state", "EvidenceItem"),
            ("state_graph.academic_integrity.state", "DecisionRecord"),
        ])
        _checkpointer = SqliteSaver(conn, serde=serde)
        _checkpointer.setup() 
    return _checkpointer

def thread_id_for_case(case_id: int) -> str:
    return f"academic-integrity-{case_id}"