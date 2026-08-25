"""
Adaptive Assessment — checkpointing layer.

Same pattern as state_graph/academic_integrity/checkpointing.py: LangGraph's
SQLite checkpointer pointed at the SAME brightpeak.db used by the rest of
Phase-3, so a killed process resumes with graph.invoke(None, config) using
the same thread_id -- no re-execution of completed nodes, no state loss.

FIXED: this used to hardcode its own path to phase-3/db/brightpeak.db,
which is a stale, separate copy of the database -- NOT the canonical file
(phase-4/brightpeak.db) that mcp_server/database.py resolves to and that
AssessmentSessions/AssessmentAnswers actually live in (see that module's
own docstring). Having every other Phase-3 subsystem plus this
checkpointer's SqliteSaver open different physical .db files, with
different journal modes, from multiple processes (Python + Node) is a
real cause of "database disk image is malformed" / "index already
exists" corruption. Now reuses database.py's already-resolved _DB_PATH,
same pattern advisory/checkpointing.py already used correctly.
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
            ("state_graph.adaptive_assessment.state", "AnsweredQuestion"),
        ])
        _checkpointer = SqliteSaver(conn, serde=serde)
        _checkpointer.setup() 
    return _checkpointer


def thread_id_for_session(session_id: int) -> str:
    return f"adaptive-assessment-{session_id}"