"""
Academic Integrity — checkpointing layer.

Uses LangGraph's SQLite checkpointer pointed at the SAME brightpeak.db used
by the rest of Phase-3 (not a separate checkpoint file), so a killed process
resumes with `graph.invoke(None, config)` using the same thread_id, no
re-execution of completed nodes, no state loss.

FIXED: this used to hardcode its own path to phase-3/db/brightpeak.db, a
stale separate copy -- NOT the canonical file (phase-4/brightpeak.db)
mcp_server/database.py resolves to and IntegrityCases/etc. actually live
in. See adaptive_assessment/checkpointing.py's docstring for the full
rationale (multiple physical .db files + mixed journal modes is a real
corruption risk). Now reuses database.py's already-resolved _DB_PATH.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

import database as db  # noqa: E402

DB_PATH = str(db._DB_PATH)

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