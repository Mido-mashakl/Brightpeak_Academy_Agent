"""
Academic Integrity — ticket/failure-recovery path.

Different code path from hitl.py on purpose: this fires on UNEXPECTED node
failures (a tool call errored, the model returned something unusable) not
on an expected decision point. `with_ticket_on_failure` wraps any node
function; on exception it writes a real Tickets row (status='open') with
the thread_id needed to resume, then re-raises so LangGraph does NOT mark
the node as completed — the checkpoint before this node stays the resume
point.
"""

from __future__ import annotations

import functools
import json
from datetime import datetime

from mcp_server import database as db
from .checkpointing import thread_id_for_case


def with_ticket_on_failure(source_graph: str, failure_type: str):
    def decorator(node_fn):
        @functools.wraps(node_fn)
        def wrapped(state):
            try:
                return node_fn(state)
            except Exception as exc:
                source_id = getattr(state, "case_id", None) or getattr(state, "session_id", None)
                thread_id = thread_id_for_case(source_id) if source_id else "unknown"
                db.execute(
                    """INSERT INTO Tickets
                       (source_graph, source_id, thread_id, failure_type, status, details, created_at)
                       VALUES (?, ?, ?, ?, 'open', ?, ?)""",
                    (
                        source_graph,
                        source_id,
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
    checkpoint (the failed node re-runs, since it never completed — nothing
    before it re-executes)."""
    from .graph import resume_case  # local import avoids circular import

    row = db.query_one("SELECT source_graph, source_id FROM Tickets WHERE ticket_id = ?", (ticket_id,))
    db.execute(
        "UPDATE Tickets SET status = 'resolved', resolved_at = ?, details = details || ? WHERE ticket_id = ?",
        (datetime.utcnow().isoformat(), f" | resolved: {resolution_notes}", ticket_id),
    )
    if row["source_graph"] == "academic_integrity":
        return resume_case(row["source_id"])
    raise ValueError(f"Unknown source_graph on ticket {ticket_id}: {row['source_graph']}")