"""
Faculty Hiring — ticket/failure-recovery path.

Intentionally separate from hitl.py:
  - HITL = expected pause for a decision the agent cannot make alone.
  - Ticket = UNPLANNED failure: tool errored, LLM output unparseable,
    schema validation failed, DB write failed, etc.

`with_ticket_on_failure` wraps a node function. On exception it:
  1. Opens a Tickets row (status='open') with enough info for an admin to
     investigate from the platform's admin surface.
  2. Re-raises — the node is NOT marked complete, so LangGraph's checkpoint
     remains at the state just BEFORE this node. Resume = re-run this node,
     nothing before it repeats.

Pattern is identical to academic_integrity/tickets.py.
"""

from __future__ import annotations

import functools
import json
import sys
from datetime import datetime
from pathlib import Path

_PHASE3_DIR = Path(__file__).resolve().parent.parent.parent
if str(_PHASE3_DIR) not in sys.path:
    sys.path.insert(0, str(_PHASE3_DIR))

from mcp_server import database as db
from .checkpointing import thread_id_for_job


def with_ticket_on_failure(source_graph: str, failure_type: str):
    """Decorator — wrap any graph node to open a Ticket on unexpected failure."""
    def decorator(node_fn):
        @functools.wraps(node_fn)
        def wrapped(state):
            try:
                return node_fn(state)
            except Exception as exc:
                job_id = getattr(state, "job_id", None)
                tid = thread_id_for_job(job_id) if job_id else "unknown"
                db.execute(
                    """INSERT INTO Tickets
                       (source_graph, source_id, thread_id, failure_type, status, details, created_at)
                       VALUES (?, ?, ?, ?, 'open', ?, ?)""",
                    (
                        source_graph,
                        job_id or 0,
                        tid,
                        failure_type,
                        json.dumps({"node": node_fn.__name__, "error": str(exc)}),
                        datetime.utcnow().isoformat(),
                    ),
                )
                raise  # never swallow: checkpoint stays at the pre-node state
        return wrapped
    return decorator


# ---------------------------------------------------------------------------
# Called by the platform's admin surface when a ticket is resolved
# ---------------------------------------------------------------------------

def resolve_ticket(ticket_id: int, resolution_notes: str):
    """
    1. Marks the ticket resolved.
    2. Resumes the graph from its last checkpoint (the failed node reruns;
       nothing before it repeats).

    Called by the admin through the platform UI after investigating the failure.
    """
    from .graph import resume_job  # local import avoids circular import

    row = db.query_one(
        "SELECT source_graph, source_id FROM Tickets WHERE ticket_id = ?",
        (ticket_id,),
    )
    if not row:
        raise ValueError(f"Ticket {ticket_id} not found")

    db.execute(
        """UPDATE Tickets
           SET status = 'resolved', resolved_at = ?,
               details = details || ?
           WHERE ticket_id = ?""",
        (
            datetime.utcnow().isoformat(),
            f" | resolved: {resolution_notes}",
            ticket_id,
        ),
    )

    if row["source_graph"] == "faculty_hiring":
        return resume_job(row["source_id"])

    raise ValueError(
        f"Unknown source_graph on ticket {ticket_id}: {row['source_graph']}"
    )