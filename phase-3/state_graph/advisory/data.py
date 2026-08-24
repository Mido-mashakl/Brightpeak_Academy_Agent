"""
data.py
=======
Reuses the *existing* Phase-2/Phase-3 data layer instead of reimplementing it:
- `mcp_server/database.py` for the student profile (Students, Enrollments, Grades,
  Attendance) and for writing the final Certificate/Scholarship decision.
- `rag/rag_tool.py` for policy retrieval (same RAG pipeline `ask_course_material` /
  `search_policies` already use, course/category-scoped).

Per the Phase-3 README: Phase-2 assets are copied locally under `phase-3/`, not
imported across phase folders, so this module reaches sideways into
`phase-3/mcp_server` and `phase-3/rag` the same way `mcp_server/tools.py` already
reaches into `phase-3/rag` — by adding the sibling folder to `sys.path`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_STATE_GRAPH_DIR = Path(__file__).resolve().parent.parent.parent  # phase-3/state_graph -> phase-3
_MCP_DIR = _STATE_GRAPH_DIR / "mcp_server"
_RAG_DIR = _STATE_GRAPH_DIR / "rag"

for _p in (_MCP_DIR, _RAG_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import database as db  # noqa: E402  (phase-3/mcp_server/database.py)
from rag_tool import search_policies as _search_policies  # noqa: E402


# -----------------------------------------------------------------------
# Student profile — read-only, same data get_student_profile()/
# get_student_grades()/get_student_attendance() already expose as MCP tools.
# -----------------------------------------------------------------------

def load_student_profile(student_id: int, course_id: int | None = None) -> dict[str, Any]:
    student = db.get_student(student_id)
    if student is None:
        raise ValueError(f"No student with id {student_id}")
    return {
        "student": student,
        "enrollments": db.get_enrollments(student_id, course_id),
        "grades": db.get_grades(student_id, course_id),
        "overall_average": db.get_overall_average(student_id),
        "attendance": db.get_attendance(student_id, course_id),
    }


# -----------------------------------------------------------------------
# Policy retrieval — same RAG pipeline as search_policies(), scoped by
# category so a certificate request never pulls scholarship policy or
# vice versa.
# -----------------------------------------------------------------------

_CATEGORY_BY_REQUEST_TYPE = {
    "certificate": "Certificate",
    "scholarship": "Scholarship",
}


def retrieve_policy(request_type: str, query: str) -> dict[str, Any]:
    category = _CATEGORY_BY_REQUEST_TYPE.get(request_type)
    return _search_policies(query, architecture="auto", category=category)


# -----------------------------------------------------------------------
# Persisting the outcome — the one bit of *new* persistent domain data
# this graph needs (see schema_additions.sql): the certificate/
# scholarship decision itself must survive after the graph run ends.
# -----------------------------------------------------------------------

def create_request_row(
    request_type: str,
    student_id: int,
    course_id: int | None,
    purpose: str | None,
) -> int:
    table = "CertificateRequests" if request_type == "certificate" else "ScholarshipApplications"
    with db._conn() as con:
        cur = con.execute(
            f"""INSERT INTO {table} (student_id, course_id, purpose, status)
                VALUES (?, ?, ?, 'pending')""",
            (student_id, course_id, purpose),
        )
        return cur.lastrowid


def mark_needs_review(request_type: str, request_id: int) -> None:
    """Written the moment human_review_node is about to pause (right before
    interrupt(), see hitl.py) — mirrors track_recommendation/nodes_hitl.py's
    `db.update_recommendation(..., status="awaiting_advisor")` pattern for
    this graph. Without this, `status` stays 'pending' (set by
    create_request_row) for the entire time the request is sitting with an
    advisor, which is indistinguishable from "just submitted, not evaluated
    yet" — an advisor has no way to tell which pending requests actually
    need a decision from them right now.

    'needs_review' is already a valid value under both tables' CHECK
    constraint (see schema.sql) and is already what the frontend
    (advisor-api.js's BP_STATUS_META / _VERDICT_BY_STATUS) expects for
    "needs advisor attention" — it just was never actually written here.
    """
    table = "CertificateRequests" if request_type == "certificate" else "ScholarshipApplications"
    id_col = "request_id" if request_type == "certificate" else "application_id"
    with db._conn() as con:
        con.execute(
            f"UPDATE {table} SET status = 'needs_review' WHERE {id_col} = ?",
            (request_id,),
        )


def finalize_request_row(
    request_type: str,
    request_id: int,
    eligibility_status: str,
    recommendation: str | None,
    decided_by: str | None,
) -> None:
    table = "CertificateRequests" if request_type == "certificate" else "ScholarshipApplications"
    id_col = "request_id" if request_type == "certificate" else "application_id"
    with db._conn() as con:
        con.execute(
            f"""UPDATE {table}
                SET status = ?, recommendation = ?, decided_by = ?,
                    decided_at = DATETIME('now')
                WHERE {id_col} = ?""",
            (eligibility_status, recommendation, decided_by, request_id),
        )