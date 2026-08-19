"""
tickets.py
==========
The *unexpected*-failure path (an MCP tool call throws, a DB write fails), kept
deliberately separate from hitl.py's *expected*-pause path. Uses the shared
`Tickets` table (source_graph='student_advisor') already added for the Academic
Integrity graph, so admins see one ticket queue regardless of which graph failed.

How resume-from-checkpoint actually happens here:
  1. run_student_advisor() invokes the compiled graph. If a node raises, the
     checkpointer has already persisted state as of the *last successfully
     completed* node (LangGraph only checkpoints after a node returns), so the
     failing node itself never got persisted as "done".
  2. We catch the exception at the invoke boundary, open a ticket that records
     the thread_id, and re-raise (the process/request fails loudly — nothing
     is silently swallowed).
  3. An admin investigates through the platform and calls resolve_ticket().
  4. resume_after_ticket_resolution() calls graph.invoke(None, config) with the
     same thread_id. LangGraph resumes from the last checkpoint and *re-runs
     the node that previously failed* — this is the literal "kill process ->
     restart -> resume without re-executing completed nodes" behaviour the
     README's demo evidence asks for.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_MCP_DIR = Path(__file__).resolve().parent.parent.parent / "mcp_server"
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

import database as db  # noqa: E402

from .checkpointing import thread_config


def create_ticket(thread_id: str, source_id: int | None, failure_type: str, details: str) -> int:
    with db._conn() as con:
        cur = con.execute(
            """INSERT INTO Tickets (source_graph, source_id, thread_id, failure_type,
                                     status, details)
               VALUES ('student_advisor', ?, ?, ?, 'open', ?)""",
            (source_id or 0, thread_id, failure_type, details),
        )
        return cur.lastrowid


def resolve_ticket(ticket_id: int) -> None:
    with db._conn() as con:
        con.execute(
            """UPDATE Tickets SET status = 'resolved', resolved_at = DATETIME('now')
               WHERE ticket_id = ?""",
            (ticket_id,),
        )


def get_ticket(ticket_id: int) -> dict[str, Any] | None:
    with db._conn() as con:
        row = con.execute("SELECT * FROM Tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None


def run_student_advisor(graph, initial_state, thread_id: str, request_id: int | None):
    """Invoke the graph; on any uncaught exception, open a ticket before
    re-raising so the failure is never silent."""
    config = thread_config(thread_id)
    try:
        return graph.invoke(initial_state, config)
    except Exception as exc:  # noqa: BLE001 - intentionally broad: any node failure tickets
        create_ticket(
            thread_id=thread_id,
            source_id=request_id,
            failure_type=type(exc).__name__,
            details=str(exc),
        )
        raise


def resume_after_ticket_resolution(graph, ticket_id: int):
    """Resolve the ticket, then resume the graph from its last checkpoint."""
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise ValueError(f"No ticket with id {ticket_id}")
    resolve_ticket(ticket_id)
    config = thread_config(ticket["thread_id"])
    return graph.invoke(None, config)