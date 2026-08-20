"""
Adaptive Assessment — ticket/failure-recovery path.

Same pattern as state_graph/academic_integrity/tickets.py: fires on
UNEXPECTED node failures (a tool call errored, the model returned something
unusable), not on an expected pause. `with_ticket_on_failure` wraps a node
function; on exception it writes a real Tickets row (status='open') with
the thread_id needed to resume, then re-raises so LangGraph does NOT mark
the node as completed -- the checkpoint before this node stays the resume
point.
"""

from __future__ import annotations

import functools
import json
from datetime import datetime

import sys as _sys
from pathlib import Path as _Path
MCP_SERVER_DIR = _Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(MCP_SERVER_DIR) not in _sys.path:
    _sys.path.insert(0, str(MCP_SERVER_DIR))

from mcp_server import database as db
from .checkpointing import thread_id_for_session


def with_ticket_on_failure(source_graph: str, failure_type: str):
    def decorator(node_fn):
        @functools.wraps(node_fn)
        def wrapped(state):
            try:
                return node_fn(state)
            except Exception as exc:
                session_id = getattr(state, "session_id", None)
                thread_id = thread_id_for_session(session_id) if session_id else "unknown"
                db.execute(
                    """INSERT INTO Tickets
                       (source_graph, source_id, thread_id, failure_type, status, details, created_at)
                       VALUES (?, ?, ?, ?, 'open', ?, ?)""",
                    (
                        source_graph,
                        session_id,
                        thread_id,
                        failure_type,
                        json.dumps({"node": node_fn.__name__, "error": str(exc)}),
                        datetime.utcnow().isoformat(),
                    ),
                )
                raise  # do NOT swallow: the node did not complete, checkpoint stays put
        return wrapped
    return decorator


# --- Called by the platform's admin surface when an admin resolves a ticket ---

def resolve_ticket(ticket_id: int, resolution_notes: str):
    """Marks the ticket resolved and resumes the graph from its last good
    checkpoint (the failed node re-runs, since it never completed)."""
    from .graph import resume_session  # local import avoids circular import

    row = db.query_one("SELECT source_graph, source_id FROM Tickets WHERE ticket_id = ?", (ticket_id,))
    db.execute(
        "UPDATE Tickets SET status = 'resolved', resolved_at = ?, details = details || ? WHERE ticket_id = ?",
        (datetime.utcnow().isoformat(), f" | resolved: {resolution_notes}", ticket_id),
    )
    if row["source_graph"] == "adaptive_assessment":
        return resume_session(row["source_id"])
    raise ValueError(f"Unknown source_graph on ticket {ticket_id}: {row['source_graph']}")