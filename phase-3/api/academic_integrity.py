"""
Academic Integrity -- platform API surface.

This is the backend contract the platform (Fatma's admin + user surfaces)
calls to drive the academic_integrity state graph. It does not render any
UI itself -- it only wraps the same functions demo_interactive_academic_integrity.py
calls (start_case, submit_committee_decision, submit_final_decision,
resolve_ticket), as real HTTP endpoints, exactly the way api/teaching.py
wraps the teaching agent.

Endpoints:
  POST /academic-integrity/cases                          -> instructor reports a case
  GET  /academic-integrity/cases/{case_id}                 -> current status (for admin + student views)
  POST /academic-integrity/cases/{case_id}/committee-decision -> HITL #1 resolve
  POST /academic-integrity/cases/{case_id}/appeal          -> student submits appeal_argument
  POST /academic-integrity/cases/{case_id}/final-decision  -> HITL #2 resolve
  GET  /academic-integrity/tickets                         -> open tickets for this graph
  POST /academic-integrity/tickets/{ticket_id}/resolve      -> resolve + resume from checkpoint
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PHASE3_DIR = Path(__file__).resolve().parent.parent
if str(PHASE3_DIR) not in sys.path:
    sys.path.insert(0, str(PHASE3_DIR))
MCP_SERVER_DIR = PHASE3_DIR / "mcp_server"
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

import mcp_server.database as db  # noqa: E402
import state_graph.academic_integrity.graph as g  # noqa: E402
from state_graph.academic_integrity.hitl import (  # noqa: E402
    submit_committee_decision,
    submit_final_decision,
)
from state_graph.academic_integrity.tickets import resolve_ticket  # noqa: E402


router = APIRouter(prefix="/academic-integrity", tags=["Academic Integrity"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ReportCaseRequest(BaseModel):
    case_id: int
    student_id: int
    course_id: int
    reported_by: int  # instructor_id
    description: str
    similarity_score: float


class CommitteeDecisionRequest(BaseModel):
    decided_by: str  # admin username, never the agent
    decision: str  # "uphold" | "dismiss" | "request_more_evidence"
    notes: Optional[str] = None


class AppealRequest(BaseModel):
    appeal_argument: str


class FinalDecisionRequest(BaseModel):
    decided_by: str
    decision: str  # "uphold" | "reduce_penalty" | "dismiss"
    notes: Optional[str] = None


class TicketResolveRequest(BaseModel):
    resolution_notes: str


# ---------------------------------------------------------------------------
# Case lifecycle
# ---------------------------------------------------------------------------

@router.post("/cases")
async def report_case(request: ReportCaseRequest):
    """Instructor reports a case through the platform. Inserts the
    IntegrityCases row (case_id + similarity_score are supplied by the
    instructor -- there is no similarity-checking MCP tool, see graph.py's
    module docstring), then starts the graph, which runs gather_evidence
    and analyze_severity and pauses at needs_committee_review unless the
    RAG-graded severity came back "minor"."""
    existing = db.query_one("SELECT case_id FROM IntegrityCases WHERE case_id = ?", (request.case_id,))
    if existing:
        raise HTTPException(status_code=409, detail=f"case_id {request.case_id} already exists")
    try:
        db.execute(
            """INSERT INTO IntegrityCases
               (case_id, student_id, course_id, reported_by, description, similarity_score)
               VALUES (?,?,?,?,?,?)""",
            (
                request.case_id, request.student_id, request.course_id,
                request.reported_by, request.description, request.similarity_score,
            ),
        )
        result = g.start_case(request.model_dump())
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start case: {exc}")


@router.get("/cases/{case_id}")
async def get_case(case_id: int):
    """Current state of the graph for this case -- what the admin panel and
    the student's own status view both read from."""
    graph = g.build_academic_integrity_graph()
    config = {"configurable": {"thread_id": g.thread_id_for_case(case_id)}}
    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail=f"No case found for case_id {case_id}")
    return {
        "case_id": case_id,
        "status": state.values.get("status"),
        "severity": state.values.get("severity"),
        "severity_rationale": state.values.get("severity_rationale"),
        "appeal_evaluation": state.values.get("appeal_evaluation"),
        "decisions": [d if isinstance(d, dict) else d.model_dump() for d in state.values.get("decisions", [])],
        "pending_node": state.next,  # non-empty tuple means the graph is paused here
    }


@router.post("/cases/{case_id}/committee-decision")
async def committee_decision(case_id: int, request: CommitteeDecisionRequest):
    """Admin resolves HITL #1 (needs_committee_review) from the platform's
    pending-tasks screen."""
    try:
        return submit_committee_decision(
            case_id, decided_by=request.decided_by,
            decision=request.decision, notes=request.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/cases/{case_id}/appeal")
async def submit_appeal(case_id: int, request: AppealRequest):
    """Student submits their appeal argument through the platform's user
    surface, resuming the graph past await_appeal into evaluate_appeal
    (Tree of Thoughts)."""
    try:
        return g.resume_case(case_id, update={"appeal_argument": request.appeal_argument})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/cases/{case_id}/final-decision")
async def final_decision(case_id: int, request: FinalDecisionRequest):
    """Admin resolves HITL #2 (committee_final_decision)."""
    try:
        return submit_final_decision(
            case_id, decided_by=request.decided_by,
            decision=request.decision, notes=request.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Tickets (unplanned failures -- separate path from HITL)
# ---------------------------------------------------------------------------

@router.get("/tickets")
async def list_open_tickets():
    """Open tickets for this graph -- the platform's failure/recovery screen."""
    rows = db.query_all(
        "SELECT * FROM Tickets WHERE source_graph = 'academic_integrity' AND status != 'resolved' "
        "ORDER BY created_at DESC",
    )
    return rows


@router.post("/tickets/{ticket_id}/resolve")
async def resolve_case_ticket(ticket_id: int, request: TicketResolveRequest):
    """Admin marks a ticket resolved; this resumes the graph from its last
    good checkpoint (the failed node re-runs, nothing before it does)."""
    try:
        return resolve_ticket(ticket_id, resolution_notes=request.resolution_notes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))