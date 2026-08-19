"""
checkpointing.py
=================
LangGraph checkpointer for the Student Advisor graph.

Per the Phase-3 README, the checkpointer writes to the *same*
`brightpeak.db` used everywhere else in Phase-3 (see data.py /
mcp_server/database.py), so a single admin view of the database shows
both domain rows (CertificateRequests / ScholarshipApplications) and
the graph's own checkpoint state -- no separate checkpoint store to
keep in sync.

`request_id` is the source of the thread_id: thread_id =
f"student-advisor-{request_id}" (see graph.py's load_profile node and
state.py's docstring). Passing the same thread_id back into
`thread_config()` is what lets interrupt()/Command(resume=...) in
hitl.py, and the retry in tickets.py, pick a paused/failed run back up
from its last persisted checkpoint instead of starting over.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402

import database as db  # noqa: E402  (phase-3/mcp_server/database.py)

_checkpointer: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    """Process-wide singleton SqliteSaver bound to database.py's own
    sqlite3 connection (`db._DB`), rather than opening a second
    connection to the same file -- avoids the two layers stepping on
    each other's transactions/locks on brightpeak.db."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = SqliteSaver(db._DB)
        _checkpointer.setup()
    return _checkpointer


def thread_config(thread_id: str) -> dict:
    """LangGraph `config` for a given thread_id. Reusing the same
    thread_id across calls (start_request -> Command(resume=...) in
    hitl.py -> resume_after_ticket_resolution() in tickets.py) is what
    makes a run resumable across interrupts, failures, and process
    restarts."""
    return {"configurable": {"thread_id": thread_id}}