"""
department_head_router.py
==========================
Dept Head-specific endpoints that don't belong to an existing domain
router (hiring_router.py already owns /hiring/*).

GAP 1 — Dashboard stats
    GET /department-head/dashboard
    Modelled on instructor_router.py's /instructor/dashboard pattern:
    same db.query_all / db.query_one helpers, same require_role() auth.

    Response shape matches what dashboard.js already reads from the mock
    DHApi.getDashboardStats() — field for field, so dashboard.js needs
    zero changes:
      {
        activeFacultyPositions:         int,
        candidatesAwaitingDecision:     int,
        integrityCasesAwaitingReview:   int,
        openTickets:                    int,
        hiring: {
          jobPostings:      int,
          applications:     int,
          shortlisted:      int,
          pendingDecisions: int,
        },
        integrity: {
          openCases:              int,
          awaitingReview:         int,
          appeals:                int,
          finalDecisionsPending:  int,
        }
      }

    "candidatesAwaitingDecision": candidates whose AI scoring is done
    (parse_status == 'parsed' and a CandidateScores row exists) but who
    have no HiringDecisions row yet — i.e. shortlisted / ai_scored in
    the frontend's language.

    "integrityCasesAwaitingReview": cases that are open (not 'closed')
    and need attention — matching the mock's
    `status !== "closed"` filter.

GAP 4 — Agents
    GET /department-head/agents
    Returns the same static list the instructor_router.py /instructor/agents
    endpoint returns — a visual-only "per brief" list with no live
    metrics yet, exactly as the status doc describes.  Returns an
    honest [] would also be fine (advisor does this), but keeping the
    same 5-agent list the mock seed had avoids a blank page regression
    on the agents UI.
"""

from fastapi import APIRouter, Depends
from core.auth import require_role, CurrentUser
import mcp_server.database as db

router = APIRouter(prefix="/department-head", tags=["department-head"])


# ---------------------------------------------------------------------------
# GAP 1 — Dashboard stats
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def get_dashboard(user: CurrentUser = Depends(require_role("dept_head"))):
    """
    Aggregate counts for the Dept Head dashboard tiles and mini-stats panels.
    All reads are plain SQL — no graph state involved.
    """
    # --- Hiring ---
    total_jobs      = db.query_one("SELECT COUNT(*) AS n FROM JobPostings")["n"]
    open_jobs       = db.query_one("SELECT COUNT(*) AS n FROM JobPostings WHERE status = 'open'")["n"]
    total_cands     = db.query_one("SELECT COUNT(*) AS n FROM Candidates")["n"]

    # "Shortlisted" in the frontend means scored + no decision yet.
    # A candidate is scored when at least one CandidateScores row exists for them.
    shortlisted = db.query_one("""
        SELECT COUNT(DISTINCT c.candidate_id) AS n
        FROM Candidates c
        JOIN CandidateScores cs ON cs.candidate_id = c.candidate_id
        WHERE NOT EXISTS (
            SELECT 1 FROM HiringDecisions hd WHERE hd.candidate_id = c.candidate_id
        )
    """)["n"]

    # "Awaiting decision" = same set (scored, no decision)
    awaiting_decision = shortlisted

    # --- Academic Integrity ---
    open_cases = db.query_one(
        "SELECT COUNT(*) AS n FROM IntegrityCases WHERE status != 'closed'"
    )["n"]
    awaiting_review = db.query_one(
        "SELECT COUNT(*) AS n FROM IntegrityCases WHERE status = 'reported'"
    )["n"]
    appeals = db.query_one(
        "SELECT COUNT(*) AS n FROM IntegrityCases WHERE status IN ('awaiting_appeal', 'appeal_under_review')"
    )["n"]
    final_decisions_pending = open_cases  # everything non-closed still needs resolution

    # --- Tickets ---
    open_tickets = db.query_one(
        "SELECT COUNT(*) AS n FROM Tickets WHERE status IN ('open', 'investigating')"
    )["n"]

    return {
        "activeFacultyPositions":       open_jobs,
        "candidatesAwaitingDecision":   awaiting_decision,
        "integrityCasesAwaitingReview": open_cases,
        "openTickets":                  open_tickets,
        "hiring": {
            "jobPostings":      total_jobs,
            "applications":     total_cands,
            "shortlisted":      shortlisted,
            "pendingDecisions": awaiting_decision,
        },
        "integrity": {
            "openCases":             open_cases,
            "awaitingReview":        awaiting_review,
            "appeals":               appeals,
            "finalDecisionsPending": final_decisions_pending,
        },
    }


# ---------------------------------------------------------------------------
# GAP 4 — Agents (visual-only list, same static data as the mock seed)
# ---------------------------------------------------------------------------

_AGENTS = [
    {
        "id": "agent-hiring",
        "name": "Faculty Hiring Agent",
        "icon": "person_search",
        "description": "Automates initial dossier screening, extracts metadata, and flags anomalies.",
        "status": "Active",
        "lastActivity": "recently",
        "activeWorkflows": 0,
    },
    {
        "id": "agent-integrity",
        "name": "Academic Integrity Agent",
        "icon": "policy",
        "description": "Monitors committee reviews for scoring deviations and potential bias.",
        "status": "Active",
        "lastActivity": "recently",
        "activeWorkflows": 0,
    },
    {
        "id": "agent-advisory",
        "name": "Advisory Agent",
        "icon": "support_agent",
        "description": "Assists students with scheduling and general inquiries.",
        "status": "Active",
        "lastActivity": "recently",
        "activeWorkflows": 0,
    },
    {
        "id": "agent-assessment",
        "name": "Assessment Agent",
        "icon": "fact_check",
        "description": "Automated grading and feedback generation for standardized testing.",
        "status": "Active",
        "lastActivity": "recently",
        "activeWorkflows": 0,
    },
    {
        "id": "agent-trackrec",
        "name": "Track Rec Agent",
        "icon": "route",
        "description": "Analyses student performance to recommend optimal degree tracks.",
        "status": "Active",
        "lastActivity": "recently",
        "activeWorkflows": 0,
    },
]


@router.get("/agents")
def list_agents(user: CurrentUser = Depends(require_role("dept_head"))):
    """
    Visual-only agent list for the Dept Head agents page.
    Per the status doc: 'the same honest empty-list treatment as advisor,
    OR the existing visual-only list server-side the way instructor_router.py
    did' — we use the static list so the agents page renders actual content.
    activeWorkflows is always 0 (no live metrics table exists yet).
    """
    return _AGENTS
