"""
tickets_router.py
==================
HTTP layer over the Tickets table (db/schema.sql — already exists,
written by all four phase-3 graphs' own tickets.py files:
  state_graph/{advisory,faculty_hiring,academic_integrity,
               adaptive_assessment}/tickets.py).

Registered at /tickets. No prefix collision with any existing router.

Two endpoints only — matching exactly what department-head-api.js
documents and what tickets.js calls:

  GET  /tickets                         — list, filterable by status / source_graph
  PATCH /tickets/{ticket_id}/status     — resolve / dismiss

Auth: require_role("dept_head") on both.  Dept Head is the only role
whose UI surfaces this table directly; instructors/advisors don't
have a ticket list view.

Response shape is built to match what the existing (mock) DHApi
already returns so tickets.js / drawer doesn't need touching:
  {
    id:            "TKT-8942",      # formatted string, not raw int
    sourceGraph:   "Faculty Hiring",
    sourceId:      str(source_id),
    threadId:      thread_id,
    workflow:      failure_type,    # mock seed used failure_type as workflow label
    failureType:   failure_type,
    relatedWorkflow: failure_type,
    details:       details,
    status:        "Open" | "Investigating" | "Resolved",
    priority:      "High" | "Medium" | "Low"   # derived from source_graph
  }

Note on "priority": the Tickets table has no priority column — the
mock seed derived it from source_graph heuristically.  We keep that
same derivation here so the UI's priority chips still render without
schema changes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser
from core.graph_loader import (
    resolve_faculty_hiring_ticket,
    resolve_academic_integrity_ticket,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])

# Maps a ticket's source_graph to the function that actually resumes that
# graph from its stuck checkpoint (state_graph/*/tickets.py's own
# resolve_ticket). Marking a ticket "Resolved" without calling one of
# these only flips the DB column — the LangGraph checkpoint stays wedged
# at the node that raised, so e.g. a stuck CV parse/score never runs
# again and the job can never reach generate_shortlist. Scoped to the
# same two graphs _DEPT_HEAD_SOURCE_GRAPHS already exposes to this role.
_RESOLVE_BY_SOURCE_GRAPH = {
    "faculty_hiring": resolve_faculty_hiring_ticket,
    "academic_integrity": resolve_academic_integrity_ticket,
}

# Which source_graphs a Dept Head is actually responsible for. Matches the
# scope department_head_router.py's own /department-head/dashboard already
# uses (it aggregates Faculty Hiring + Academic Integrity only, never
# Adaptive Assessment / Track Recommendation / Advisory) — Tickets was the
# only place that scope wasn't applied, which is why Assessment-graph
# tickets were leaking into the Dept Head's ticket list.
_DEPT_HEAD_SOURCE_GRAPHS = ("faculty_hiring", "academic_integrity")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOURCE_GRAPH_LABELS = {
    "faculty_hiring":        "Faculty Hiring",
    "academic_integrity":    "Academic Integrity",
    "advisory":              "Advisory",
    "adaptive_assessment":   "Adaptive Assessment",
    "track_recommendation":  "Track Recommendation",
}

_PRIORITY_BY_GRAPH = {
    "faculty_hiring":       "High",
    "academic_integrity":   "Medium",
    "advisory":             "Low",
    "adaptive_assessment":  "Medium",
    "track_recommendation": "Low",
}

# Map DB status values to the title-case labels the frontend uses
_STATUS_DB_TO_UI = {
    "open":          "Open",
    "investigating": "Investigating",
    "resolved":      "Resolved",
}
_STATUS_UI_TO_DB = {v: k for k, v in _STATUS_DB_TO_UI.items()}


def _ticket_to_frontend(row: dict) -> dict:
    source_graph_key = row.get("source_graph", "")
    label = _SOURCE_GRAPH_LABELS.get(source_graph_key, source_graph_key.replace("_", " ").title())
    priority = _PRIORITY_BY_GRAPH.get(source_graph_key, "Medium")
    db_status = row.get("status", "open")
    ui_status = _STATUS_DB_TO_UI.get(db_status, db_status.title())

    failure_type = row.get("failure_type", "Unknown")

    return {
        # Format ticket_id as "TKT-NNNN" to match mock seed convention
        "id": f"TKT-{row['ticket_id']}",
        "sourceGraph": label,
        "sourceId": str(row.get("source_id", "")),
        "threadId": row.get("thread_id", ""),
        # "workflow" is what the drawer displays under "Workflow" — mock used failure_type as label
        "workflow": failure_type,
        "failureType": failure_type,
        "relatedWorkflow": failure_type,
        "details": row.get("details", ""),
        "status": ui_status,
        "priority": priority,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_tickets(
    status: str | None = Query(default=None, description="Filter by UI status: Open | Investigating | Resolved"),
    source_graph: str | None = Query(default=None, description="Filter by source_graph key, e.g. faculty_hiring"),
    user: CurrentUser = Depends(require_role("dept_head")),
):
    """
    List all tickets, newest first.  Optionally filter by status and/or source_graph.

    Used by:
      - tickets.js  (full list + per-filter views)
      - dashboard.js  (openTickets count, via getDashboardStats calling this route
        — see department-head-router.py)
    """
    # Scope to this role's own tickets FIRST — every other filter narrows
    # further, never widens past this. Without this clause every dept_head
    # saw every ticket from every workflow, regardless of whether it was
    # theirs to act on.
    clauses = [f"source_graph IN ({','.join('?' for _ in _DEPT_HEAD_SOURCE_GRAPHS)})"]
    params = list(_DEPT_HEAD_SOURCE_GRAPHS)

    if status:
        db_status = _STATUS_UI_TO_DB.get(status)
        if db_status is None:
            raise HTTPException(status_code=400, detail=f"Unknown status '{status}'. Use Open | Investigating | Resolved.")
        clauses.append("status = ?")
        params.append(db_status)

    if source_graph:
        clauses.append("source_graph = ?")
        params.append(source_graph)

    where = "WHERE " + " AND ".join(clauses)
    rows = db.query_all(f"SELECT * FROM Tickets {where} ORDER BY created_at DESC", tuple(params))
    return [_ticket_to_frontend(r) for r in rows]


class UpdateStatusRequest(BaseModel):
    status: str  # "Open" | "Investigating" | "Resolved"
    notes: str | None = None  # optional resolution note, only used when status == "Resolved"


@router.patch("/{ticket_id}/status")
def update_ticket_status(
    ticket_id: str,
    body: UpdateStatusRequest,
    user: CurrentUser = Depends(require_role("dept_head")),
):
    """
    Change a ticket's status (Open → Investigating → Resolved).

    ticket_id can be either the raw integer ("8942") or the UI-formatted
    string ("TKT-8942") — both are accepted so the frontend doesn't need
    to strip the prefix before calling.

    Used by tickets.js drawer's status action buttons.

    IMPORTANT — "Resolved" is not a plain status flip: a ticket exists
    because a graph node raised and its checkpoint is stuck sitting right
    before that node (see faculty_hiring/tickets.py's with_ticket_on_failure
    docstring). Marking it resolved without re-running the graph would just
    hide the ticket while the checkpoint — and everything waiting behind it
    (e.g. that job's generate_shortlist / HITL step) — stays wedged forever.
    So for the two graphs this role owns, "Resolved" delegates to that
    graph's own resolve_ticket(), which marks the row resolved AND resumes
    the thread from the stuck node. Any other target status is a plain
    column update — no resume implied.
    """
    # Accept both "TKT-8942" and "8942"
    raw_id = ticket_id.upper().removeprefix("TKT-")
    try:
        int_id = int(raw_id)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid ticket_id '{ticket_id}'.")

    db_status = _STATUS_UI_TO_DB.get(body.status)
    if db_status is None:
        raise HTTPException(status_code=400, detail=f"Unknown status '{body.status}'. Use Open | Investigating | Resolved.")

    existing = db.query_one("SELECT * FROM Tickets WHERE ticket_id = ?", (int_id,))
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found.")

    if db_status == "resolved":
        resolver = _RESOLVE_BY_SOURCE_GRAPH.get(existing.get("source_graph"))
        if resolver is None:
            raise HTTPException(
                status_code=400,
                detail=f"Don't know how to resume source_graph '{existing.get('source_graph')}' for ticket {ticket_id}.",
            )
        try:
            resolver(int_id, body.notes or f"Resolved via dashboard by {user.name}")
        except Exception as e:
            # The node was re-run and failed again (or failed differently) —
            # with_ticket_on_failure already opened a fresh ticket for that,
            # so surface this clearly rather than pretending it resolved.
            raise HTTPException(
                status_code=409,
                detail=f"Resuming the graph failed — the underlying issue isn't fixed yet: {e}",
            )
    else:
        db.execute(
            "UPDATE Tickets SET status = ?, resolved_at = NULL WHERE ticket_id = ?",
            (db_status, int_id),
        )

    updated = db.query_one("SELECT * FROM Tickets WHERE ticket_id = ?", (int_id,))
    return _ticket_to_frontend(updated)
