"""
agents_router.py
=================
GET /agents — the platform's "AI agents" list (Dept Head / Advisor /
Instructor "Agents" pages).

There is no agent-registry table anywhere in db/schema.sql, and no
runtime tool-assignment mechanism exists yet in the MCP layer for one
agent to be "assigned"/"unassigned" from a workflow — per the project
brief (section 12), that means this must NOT invent one. What IS real
and available without fabricating anything:

  - the five Phase-3 state graphs that actually exist on disk
    (phase-3/state_graph/<domain>/), each already wired to a live
    router in this backend
  - how many of each domain's records are currently sitting in an
    open/pending state right now, straight from the same tables every
    other router already reads (IntegrityCases, AssessmentSessions,
    CertificateRequests/ScholarshipApplications, JobPostings,
    TrackRecommendations)

So each entry below is: a real graph name/description (static, like a
docstring — not per-record application data) plus a live open-item
count computed from the database. There is no "accuracy" or
"last activity timestamp" metric here because nothing in the schema
tracks per-agent evaluation results; adding fake numbers for those
would be exactly the kind of demo data this refactor removes elsewhere,
so they're left out rather than invented.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

import mcp_server.database as db
from core.auth import require_role, CurrentUser

router = APIRouter(prefix="/agents", tags=["agents"])


def _count(sql: str, params: tuple = ()) -> int:
    row = db.query_one(sql, params)
    return row["n"] if row else 0


@router.get("")
def list_agents(user: CurrentUser = Depends(require_role("instructor", "advisor", "dept_head"))):
    return [
        {
            "key": "academic_integrity",
            "name": "Academic Integrity Agent",
            "description": "Investigates reported integrity cases, runs severity analysis, and routes committee/appeal decisions.",
            "open_items": _count(
                "SELECT COUNT(*) AS n FROM IntegrityCases WHERE status NOT IN ('closed')"
            ),
        },
        {
            "key": "adaptive_assessment",
            "name": "Adaptive Assessment Agent",
            "description": "Runs adaptive question sessions and flags borderline mastery calls for instructor review.",
            "open_items": _count(
                "SELECT COUNT(*) AS n FROM AssessmentSessions WHERE status = 'in_progress'"
            ),
        },
        {
            "key": "advisory",
            "name": "Student Advisory Agent",
            "description": "Evaluates certificate/scholarship eligibility and routes borderline requests to an advisor.",
            "open_items": _count(
                "SELECT COUNT(*) AS n FROM CertificateRequests WHERE status = 'needs_review'"
            )
            + _count(
                "SELECT COUNT(*) AS n FROM ScholarshipApplications WHERE status = 'needs_review'"
            ),
        },
        {
            "key": "faculty_hiring",
            "name": "Faculty Hiring Agent",
            "description": "Parses/scores candidate CVs against job qualifications and routes shortlists to the department head.",
            "open_items": _count(
                "SELECT COUNT(*) AS n FROM JobPostings WHERE status = 'open'"
            ),
        },
        {
            "key": "track_recommendation",
            "name": "Track Recommendation Agent",
            "description": "Recommends an academic track from a student's record, running diagnostics where data is missing.",
            "open_items": _count(
                "SELECT COUNT(*) AS n FROM TrackRecommendations WHERE status NOT IN ('completed', 'failed')"
            ),
        },
    ]