"""
tickets_router.py
==================
API boundary over the shared `Tickets` table (see db/schema.sql —
"shared failure/recovery path — Phase-3 graphs"). Every Phase-3 graph
(academic_integrity, adaptive_assessment, track_recommendation, advisory,
faculty_hiring) already writes a Tickets row on unrecoverable failure via
its own state_graph/<domain>/tickets.py helper; this router is the read
+ triage surface over that same table, not a new ticket-creation path.

This closes the gap called out in frontend/department-head/shared/
department-head-api.js's header comment ("Real endpoint: GET /tickets
(NOT CONFIRMED — mocked)") — there was no /tickets route anywhere in
phase-4/backend before this file.

No dedicated "ticket owner" column exists on Tickets, and nothing in the
schema links a ticket to one specific role the way IntegrityCases links
to a student — a ticket can originate from any graph, for any user, so
read access here is any authenticated staff role (instructor / advisor /
dept_head), the same breadth hiring/integrity dashboards already assume
for triage screens. Investigate/resolve are intentionally not scoped
tighter than that for the same reason; a stricter per-domain ownership
model is a real follow-up, not something to invent here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser

router = APIRouter(prefix="/tickets", tags=["tickets"])


class ResolveTicketRequest(BaseModel):
    resolution_notes: str | None = None


def _ticket_row(ticket_id: int) -> dict:
    row = db.query_one("SELECT * FROM Tickets WHERE ticket_id = ?", (ticket_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return row


@router.get("")
def list_tickets(
    status: str | None = None,
    source_graph: str | None = None,
    user: CurrentUser = Depends(require_role("instructor", "advisor", "dept_head")),
):
    sql = "SELECT * FROM Tickets WHERE 1=1"
    params: list = []
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    if source_graph is not None:
        sql += " AND source_graph = ?"
        params.append(source_graph)
    sql += " ORDER BY created_at DESC"
    return db.query_all(sql, tuple(params))


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, user: CurrentUser = Depends(require_role("instructor", "advisor", "dept_head"))):
    return _ticket_row(ticket_id)


@router.post("/{ticket_id}/investigate")
def investigate_ticket(ticket_id: int, user: CurrentUser = Depends(require_role("instructor", "advisor", "dept_head"))):
    """Marks the ticket as being looked at. Real state transition (open ->
    investigating), not a UI-only flag — persisted straight to the row
    the triage list/detail screens both read from."""
    ticket = _ticket_row(ticket_id)
    if ticket["status"] != "open":
        raise HTTPException(status_code=409, detail=f"Ticket is '{ticket['status']}', not open.")
    db.execute("UPDATE Tickets SET status = 'investigating' WHERE ticket_id = ?", (ticket_id,))
    return _ticket_row(ticket_id)


@router.post("/{ticket_id}/resolve")
def resolve_ticket(ticket_id: int, body: ResolveTicketRequest, user: CurrentUser = Depends(require_role("instructor", "advisor", "dept_head"))):
    """Marks the ticket resolved and stamps resolved_at. This does NOT by
    itself resume the underlying graph/thread_id — the ticket only
    records that a human handled the failure. Resuming the actual paused
    graph (if the failure is recoverable at all) goes through that
    domain's own resume endpoint (e.g. POST /academic-integrity/cases/
    {id}/committee-decision), using the ticket's thread_id/source_id to
    find the right one. Wiring that follow-through is a real remaining
    step — see the audit report — not something faked here."""
    ticket = _ticket_row(ticket_id)
    if ticket["status"] == "resolved":
        raise HTTPException(status_code=409, detail="Ticket is already resolved.")
    notes = body.resolution_notes
    if notes:
        existing = ticket["details"] or ""
        combined = f"{existing}\n[resolved by {user.role}:{user.user_id}] {notes}".strip()
        db.execute(
            "UPDATE Tickets SET status = 'resolved', resolved_at = DATETIME('now'), details = ? WHERE ticket_id = ?",
            (combined, ticket_id),
        )
    else:
        db.execute(
            "UPDATE Tickets SET status = 'resolved', resolved_at = DATETIME('now') WHERE ticket_id = ?",
            (ticket_id,),
        )
    return _ticket_row(ticket_id)