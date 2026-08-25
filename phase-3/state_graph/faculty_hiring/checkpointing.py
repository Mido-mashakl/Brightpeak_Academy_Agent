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

import sqlite3
import sys
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from .state import FacultyHiringState, CandidateResult, HiringDecisionRecord, InterviewRecord

# FIXED: this used to hardcode its own path to phase-3/db/brightpeak.db, a
# stale separate copy -- NOT the canonical file (phase-4/brightpeak.db)
# mcp_server/database.py resolves to and JobPostings/etc. actually live
# in. See adaptive_assessment/checkpointing.py's docstring for the full
# rationale. Now reuses database.py's already-resolved _DB_PATH.
_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

import database as db  # noqa: E402

DB_PATH = str(db._DB_PATH)

_checkpointer: SqliteSaver | None = None

# Our own Pydantic models get stored in checkpoints (FacultyHiringState nests
# CandidateResult, HiringDecisionRecord, InterviewRecord). Newer
# langgraph-checkpoint versions warn — and will eventually refuse — to
# deserialize "unregistered" types via msgpack unless explicitly allowlisted.
# Passing the classes themselves (not raw tuples) matches exactly the
# (module, qualname) pair the deserializer checks against.
_ALLOWED_MSGPACK_MODULES = [
    FacultyHiringState, CandidateResult, HiringDecisionRecord, InterviewRecord,
]


def get_checkpointer() -> SqliteSaver:
    """Returns a singleton checkpointer backed by brightpeak.db.

    check_same_thread=False because the web server and background resume
    calls may run on different threads from the one that created the connection.
    """
    global _checkpointer
    if _checkpointer is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES)
        _checkpointer = SqliteSaver(conn, serde=serde)
        _checkpointer.setup()  # creates the checkpointer's own tables (checkpoints, writes)
                                # on first use — without this, the first checkpoint write fails.
    return _checkpointer


def thread_id_for_job(job_id: int) -> str:
    """The identity of the persistent hiring workflow for one job posting."""
    return f"faculty-hiring-{job_id}"