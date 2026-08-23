"""
dashboard_router.py
====================
Aggregated counters for the three staff dashboards (Instructor, Advisor,
Dept Head). Every number here is a straight COUNT/AVG against the same
tables the rest of the platform already reads/writes — nothing here is
computed from or falls back to demo data. Where a number the old mock
fixtures showed has no real column behind it at all (e.g. "AI insights"
like accuracy percentages, or week-over-week deltas with no history
table to diff against), it is left out rather than invented; see the
audit report for the full list.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

import mcp_server.database as db
from core.auth import require_role, CurrentUser

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _count(sql: str, params: tuple = ()) -> int:
    row = db.query_one(sql, params)
    return row["n"] if row else 0


@router.get("/instructor")
def instructor_dashboard(user: CurrentUser = Depends(require_role("instructor"))):
    courses = _count(
        "SELECT COUNT(*) AS n FROM Courses WHERE instructor_id = ?", (user.user_id,)
    )
    students = _count(
        """SELECT COUNT(DISTINCT e.student_id) AS n
           FROM Enrollments e JOIN Courses c ON c.course_id = e.course_id
           WHERE c.instructor_id = ? AND e.status = 'active'""",
        (user.user_id,),
    )
    reports = _count(
        "SELECT COUNT(*) AS n FROM IntegrityCases WHERE reported_by = ?", (user.user_id,)
    )
    pending_reviews = _count(
        """SELECT COUNT(*) AS n FROM AssessmentSessions ases
           JOIN Courses c ON c.course_id = ases.course_id
           WHERE c.instructor_id = ? AND ases.status = 'flagged_for_review'""",
        (user.user_id,),
    )
    recent_cases = db.query_all(
        "SELECT * FROM IntegrityCases WHERE reported_by = ? ORDER BY created_at DESC LIMIT 5",
        (user.user_id,),
    )
    return {
        "stats": {
            "courses": courses,
            "students": students,
            "reports": reports,
            "pendingReviews": pending_reviews,
        },
        "recentCases": recent_cases,
    }


@router.get("/advisor")
def advisor_dashboard(user: CurrentUser = Depends(require_role("advisor"))):
    total = _count("SELECT COUNT(*) AS n FROM CertificateRequests") + _count(
        "SELECT COUNT(*) AS n FROM ScholarshipApplications"
    )
    pending_review = _count(
        "SELECT COUNT(*) AS n FROM CertificateRequests WHERE status = 'needs_review'"
    ) + _count("SELECT COUNT(*) AS n FROM ScholarshipApplications WHERE status = 'needs_review'")
    completed = _count(
        "SELECT COUNT(*) AS n FROM CertificateRequests WHERE status IN ('eligible','ineligible')"
    ) + _count(
        "SELECT COUNT(*) AS n FROM ScholarshipApplications WHERE status IN ('eligible','ineligible')"
    )
    in_progress = total - pending_review - completed
    needing_attention = db.query_all(
        """SELECT request_id, student_id, course_id, purpose, status, created_at, 'certificate' AS request_type
           FROM CertificateRequests WHERE status = 'needs_review'
           UNION ALL
           SELECT application_id AS request_id, student_id, course_id, purpose, status, created_at, 'scholarship' AS request_type
           FROM ScholarshipApplications WHERE status = 'needs_review'
           ORDER BY created_at DESC LIMIT 5"""
    )
    return {
        "total": total,
        "inProgress": max(in_progress, 0),
        "pendingReview": pending_review,
        "completed": completed,
        "needingAttention": needing_attention,
    }


@router.get("/dept-head")
def dept_head_dashboard(user: CurrentUser = Depends(require_role("dept_head"))):
    open_jobs = _count("SELECT COUNT(*) AS n FROM JobPostings WHERE status = 'open'")
    awaiting_decision = _count(
        """SELECT COUNT(*) AS n FROM Candidates c
           WHERE c.parse_status = 'parsed'
             AND NOT EXISTS (SELECT 1 FROM HiringDecisions hd WHERE hd.candidate_id = c.candidate_id)"""
    )
    integrity_awaiting = _count(
        "SELECT COUNT(*) AS n FROM IntegrityCases WHERE status NOT IN ('closed')"
    )
    open_tickets = _count("SELECT COUNT(*) AS n FROM Tickets WHERE status != 'resolved'")
    return {
        "activeFacultyPositions": open_jobs,
        "candidatesAwaitingDecision": awaiting_decision,
        "integrityCasesAwaitingReview": integrity_awaiting,
        "openTickets": open_tickets,
        "hiring": {
            "jobPostings": _count("SELECT COUNT(*) AS n FROM JobPostings"),
            "applications": _count("SELECT COUNT(*) AS n FROM Candidates"),
            "shortlisted": _count(
                "SELECT COUNT(DISTINCT candidate_id) AS n FROM ShortlistEntries"
            ),
            "pendingDecisions": awaiting_decision,
        },
        "integrity": {
            "openCases": integrity_awaiting,
            "awaitingReview": _count(
                "SELECT COUNT(*) AS n FROM IntegrityCases WHERE status = 'reported'"
            ),
            "appeals": _count(
                "SELECT COUNT(*) AS n FROM IntegrityCases WHERE status = 'awaiting_appeal'"
            ),
            "finalDecisionsPending": integrity_awaiting,
        },
    }