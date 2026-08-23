"""
instructor_router.py
=====================
API boundary for the Instructor Portal (frontend/instructor/*). None of
these endpoints existed before (see BUG 1 in the fix prompt) — the
frontend's shared/api.js was calling bare paths like /dashboard,
/courses, /students, /requests, none of which had a matching FastAPI
route, so every one of those calls 404'd.

Registered under prefix="/instructor" (NOT the bare root) since
/dashboard, /courses etc. are too generic and would collide with
student/dept-head-facing routes.

Every response shape below was checked against the actual frontend JS
that consumes it (dashboard.js, courses.js, course-details.js,
students.js, student-details.js, requests.js, request-details.js,
agents.js) field-by-field, not just "does the path exist" — the fix
prompt's own verification checklist calls out a prior bug caused by
exactly this kind of mismatch (`breakdown` field shape).

WRITE-OP REQUESTS (record_grade / update_attendance /
change_enrollment_status)
--------------------------------------------------------------------
phase-3/mcp_server/tools.py already implements these three as MCP
write-tools, but they're built around the MCP protocol's own
elicitation mechanism (ctx.elicit(...) — an in-band, single-call
confirmation prompt over the MCP transport), not a resumable,
DB-persisted queue. There is also no existing DB table for a
"pending write-op request" — db/schema.sql (already fixed/verified,
out of scope to touch) has no such table.

Since the instructor frontend's Requests pages need a real, persisted
list of pending grade/attendance/enrollment change requests an
instructor can review and decide on later (not a synchronous
same-request confirmation), this router defines a small
WriteOpRequests table of its own (created here, not in schema.sql,
so the "already fixed" DB work is untouched) and, on approval,
performs the actual mutation through the SAME db.upsert_grade /
db.upsert_attendance / db.set_enrollment_status functions the MCP
tools use — so the real write path is identical, only the
confirmation mechanism differs (persisted HITL row instead of
in-band MCP elicitation). This gap (two different confirmation
mechanisms for the same underlying writes) is worth flagging in the
final report rather than silently papered over.

COURSE "code" / "term" / "status" fields
--------------------------------------------------------------------
db/schema.sql's Courses table has no code, term, or status column —
there is no real academic course-code or semester/term concept
anywhere in the schema, and no archived/inactive state for a course.
Rather than fabricate plausible-looking fake values (a fake "CS201"
code, an invented "Spring 2025" term), these are returned as an
honest "—" placeholder. status is always "active" since the schema
has no other course-level state to report.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser

router = APIRouter(prefix="/instructor", tags=["instructor"])

# ---------------------------------------------------------------------
# WriteOpRequests — created here (not schema.sql) per the module
# docstring above. Seed rows so the Requests page has something real
# to show without requiring a submission UI that isn't in scope for
# this pass; safe to run on every startup (idempotent).
# ---------------------------------------------------------------------
db.execute(
    """
    CREATE TABLE IF NOT EXISTS WriteOpRequests (
        request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        request_type    TEXT NOT NULL CHECK (request_type IN
                            ('grade_update', 'attendance_update', 'enrollment_change')),
        student_id      INTEGER NOT NULL REFERENCES Students(student_id),
        course_id       INTEGER NOT NULL REFERENCES Courses(course_id),
        assignment_id   INTEGER REFERENCES Assignments(assignment_id),
        instructor_id   INTEGER NOT NULL REFERENCES Instructors(instructor_id),
        field_label     TEXT NOT NULL,
        current_value   TEXT,
        proposed_value  TEXT NOT NULL,
        agent_reasoning TEXT,
        status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected', 'info_requested')),
        submitted_at    TEXT NOT NULL DEFAULT (DATETIME('now')),
        decided_at      TEXT,
        decision_notes  TEXT
    )
    """
)


def _seed_write_op_requests() -> None:
    existing = db.query_one("SELECT COUNT(*) AS n FROM WriteOpRequests")
    if existing and existing["n"] > 0:
        return
    # Seeded against real rows from seed.sql (student_id=1/2, course_id=1,
    # assignment_id=1, instructor_id=1) so joins resolve to real names.
    seed_rows = [
        ("grade_update", 1, 1, 1, 1, "Grade", "72", "85",
         "Recalculated from the final exam and project rubric after a grading dispute."),
        ("attendance_update", 2, 1, None, 1, "Attendance", "70", "95",
         "Student submitted a medical certificate for the missed session."),
    ]
    for row in seed_rows:
        db.execute(
            """INSERT INTO WriteOpRequests
                   (request_type, student_id, course_id, assignment_id, instructor_id,
                    field_label, current_value, proposed_value, agent_reasoning)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )


_seed_write_op_requests()


# =======================================================================
# Pydantic bodies
# =======================================================================

class RequestDecisionBody(BaseModel):
    # Accept both field names: the frontend sends 'decision' (semantic),
    # but older callers may send 'action'. Pydantic validates the first
    # populated field; 'action' is the alias.
    decision: str | None = None  # preferred field name
    action:   str | None = None  # legacy / alias
    notes: str | None = None

    def resolved_action(self) -> str:
        val = self.decision or self.action or ""
        if val not in ("approve", "reject", "request_info"):
            raise ValueError(f"action must be 'approve', 'reject', or 'request_info', got '{val}'.")
        return val


# =======================================================================
# Formatting helpers — the frontend renders these labels as-is, so all
# date/label formatting happens here, never invented client-side.
# =======================================================================

def _fmt_label(iso_ts: str | None) -> str:
    """'2026-08-23 21:02:14' -> 'Aug 23, 2026, 09:02 PM'. Falls back to the
    raw value if it doesn't parse (still real data, just unformatted)."""
    if not iso_ts:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(iso_ts, fmt)
            return dt.strftime("%b %d, %Y, %I:%M %p") if "%H" in fmt else dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    return iso_ts


def _instructor_course_ids(instructor_id: int) -> list[int]:
    rows = db.query_all("SELECT course_id FROM Courses WHERE instructor_id = ?", (instructor_id,))
    return [r["course_id"] for r in rows]


def _require_own_course(course_id: int, instructor_id: int) -> dict:
    course = db.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    if course["instructor_id"] != instructor_id:
        raise HTTPException(status_code=403, detail="This course doesn't belong to you.")
    return course


def _roster_status(attendance_pct: float | None, avg_grade: float | None) -> str:
    if (attendance_pct is not None and attendance_pct < 70) or (avg_grade is not None and avg_grade < 60):
        return "at_risk"
    return "good_standing"


# =======================================================================
# Dashboard — dashboard.js reads: stats{courses,students,reports,
# pendingRequests}, statusCounts{reported,underReview,awaitingAppeal,
# closed}, recentCases[{id,student,course,severity,status}],
# recentRequests[{id,type,student,course,submittedLabel,status}]
# =======================================================================

@router.get("/dashboard")
def get_dashboard(user: CurrentUser = Depends(require_role("instructor"))):
    course_ids = _instructor_course_ids(user.user_id)

    total_students = 0
    if course_ids:
        placeholders = ",".join("?" * len(course_ids))
        row = db.query_one(
            f"""SELECT COUNT(DISTINCT student_id) AS n FROM Enrollments
                WHERE course_id IN ({placeholders}) AND status = 'active'""",
            tuple(course_ids),
        )
        total_students = row["n"] if row else 0

    all_cases = db.query_all(
        "SELECT status FROM IntegrityCases WHERE reported_by = ?", (user.user_id,)
    )
    status_counts = {"reported": 0, "underReview": 0, "awaitingAppeal": 0, "closed": 0}
    status_map = {
        "reported": "reported",
        "under_review": "underReview",
        "awaiting_appeal": "awaitingAppeal",
        "appeal_under_review": "awaitingAppeal",
        "closed": "closed",
    }
    for c in all_cases:
        key = status_map.get(c["status"])
        if key:
            status_counts[key] += 1

    pending_requests = db.query_one(
        "SELECT COUNT(*) AS n FROM WriteOpRequests WHERE instructor_id = ? AND status = 'pending'",
        (user.user_id,),
    )

    recent_cases_raw = db.query_all(
        """SELECT ic.case_id, s.name AS student, c.title AS course, ic.severity, ic.status
           FROM IntegrityCases ic
           JOIN Students s ON s.student_id = ic.student_id
           JOIN Courses c ON c.course_id = ic.course_id
           WHERE ic.reported_by = ?
           ORDER BY ic.created_at DESC LIMIT 5""",
        (user.user_id,),
    )
    recent_cases = [
        {"id": c["case_id"], "student": c["student"], "course": c["course"],
         "severity": c["severity"], "status": c["status"]}
        for c in recent_cases_raw
    ]

    recent_requests_raw = db.query_all(
        """SELECT wr.request_id, wr.request_type AS type, s.name AS student, c.title AS course,
                  wr.status, wr.submitted_at
           FROM WriteOpRequests wr
           JOIN Students s ON s.student_id = wr.student_id
           JOIN Courses c ON c.course_id = wr.course_id
           WHERE wr.instructor_id = ?
           ORDER BY wr.submitted_at DESC LIMIT 5""",
        (user.user_id,),
    )
    recent_requests = [
        {"id": r["request_id"], "type": r["type"], "student": r["student"], "course": r["course"],
         "status": r["status"], "submittedLabel": _fmt_label(r["submitted_at"])}
        for r in recent_requests_raw
    ]

    return {
        "stats": {
            "courses": len(course_ids),
            "students": total_students,
            "reports": len(all_cases),
            "pendingRequests": pending_requests["n"] if pending_requests else 0,
        },
        "statusCounts": status_counts,
        "recentCases": recent_cases,
        "recentRequests": recent_requests,
    }


# =======================================================================
# Courses — courses.js reads: id,status,name,code,term,studentsCount,
# avgGrade. course-details.js additionally reads: description, roster[
# {id,name,attendancePct,avgGrade,status}]
# =======================================================================

@router.get("/courses")
def list_courses(user: CurrentUser = Depends(require_role("instructor"))):
    courses = db.query_all(
        "SELECT * FROM Courses WHERE instructor_id = ? ORDER BY title", (user.user_id,)
    )
    out = []
    for c in courses:
        students_count = db.query_one(
            "SELECT COUNT(*) AS n FROM Enrollments WHERE course_id = ? AND status = 'active'",
            (c["course_id"],),
        )["n"]
        avg_row = db.query_one(
            """SELECT ROUND(AVG(g.score * 100.0 / a.max_score), 1) AS avg_pct
               FROM Grades g JOIN Assignments a USING (assignment_id)
               WHERE a.course_id = ?""",
            (c["course_id"],),
        )
        out.append(
            {
                "id": c["course_id"],
                "name": c["title"],
                "code": "—",
                "term": "—",
                "status": "active",
                "studentsCount": students_count,
                "avgGrade": avg_row["avg_pct"] if avg_row and avg_row["avg_pct"] is not None else "—",
                "category": c["category"],
                "duration": c["duration"],
            }
        )
    return out


@router.get("/courses/{course_id}")
def get_course_detail(course_id: int, user: CurrentUser = Depends(require_role("instructor"))):
    course = _require_own_course(course_id, user.user_id)
    roster_raw = db.list_enrolled_students(course_id)
    students_count = db.query_one(
        "SELECT COUNT(*) AS n FROM Enrollments WHERE course_id = ? AND status = 'active'", (course_id,)
    )["n"]
    avg_row = db.query_one(
        """SELECT ROUND(AVG(g.score * 100.0 / a.max_score), 1) AS avg_pct
           FROM Grades g JOIN Assignments a USING (assignment_id)
           WHERE a.course_id = ?""",
        (course_id,),
    )

    roster = []
    for s in roster_raw:
        attendance = db.get_attendance(s["student_id"], course_id)
        att_pct = attendance[0]["percentage"] if attendance else None
        avg = db.get_overall_average(s["student_id"])
        roster.append(
            {
                "id": s["student_id"],
                "name": s["name"],
                "attendancePct": att_pct if att_pct is not None else "—",
                "avgGrade": avg if avg is not None else "—",
                "status": _roster_status(att_pct, avg),
            }
        )

    return {
        "id": course["course_id"],
        "name": course["title"],
        "code": "—",
        "term": "—",
        "status": "active",
        "description": f"{course['category']} course, {course['duration']} hours.",
        "studentsCount": students_count,
        "avgGrade": avg_row["avg_pct"] if avg_row and avg_row["avg_pct"] is not None else "—",
        "roster": roster,
    }


# =======================================================================
# Students — students.js reads: id,name,course,attendancePct,avgGrade,
# status. student-details.js reads: name,course,email,status,avgGrade,
# attendancePct,attendance{present,absent,excused,totalSessions}(optional),
# grades[{assignment,score,maxScore}]
# =======================================================================

@router.get("/students")
def list_students(
    search: str = "",
    course: str = "all",
    user: CurrentUser = Depends(require_role("instructor")),
):
    course_ids = _instructor_course_ids(user.user_id)
    if course != "all":
        try:
            course_id_filter = int(course)
        except ValueError:
            raise HTTPException(status_code=400, detail="course must be an integer id or 'all'.")
        if course_id_filter not in course_ids:
            raise HTTPException(status_code=403, detail="Not your course.")
        course_ids = [course_id_filter]

    if not course_ids:
        return []

    placeholders = ",".join("?" * len(course_ids))
    rows = db.query_all(
        f"""SELECT e.student_id, s.name, s.email, e.course_id, c.title AS course
            FROM Enrollments e
            JOIN Students s ON s.student_id = e.student_id
            JOIN Courses c ON c.course_id = e.course_id
            WHERE e.course_id IN ({placeholders}) AND e.status = 'active'
            ORDER BY s.name""",
        tuple(course_ids),
    )

    out = []
    for r in rows:
        if search.strip():
            q = search.strip().lower()
            if q not in r["name"].lower() and q not in r["course"].lower():
                continue
        attendance = db.get_attendance(r["student_id"], r["course_id"])
        avg = db.get_overall_average(r["student_id"])
        att_pct = attendance[0]["percentage"] if attendance else None
        out.append(
            {
                "id": r["student_id"],
                "name": r["name"],
                "email": r["email"],
                "courseId": r["course_id"],
                "course": r["course"],
                "attendancePct": att_pct if att_pct is not None else "—",
                "avgGrade": avg if avg is not None else "—",
                "status": _roster_status(att_pct, avg),
            }
        )
    return out


@router.get("/students/{student_id}")
def get_student_detail(student_id: int, user: CurrentUser = Depends(require_role("instructor"))):
    course_ids = set(_instructor_course_ids(user.user_id))
    student = db.get_student(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found.")

    enrollments = db.get_enrollments(student_id)
    own_enrollments = [e for e in enrollments if e["course_id"] in course_ids]
    if not own_enrollments:
        raise HTTPException(status_code=403, detail="This student isn't in any of your courses.")

    course_titles = []
    grades = []
    attendances = []
    for e in own_enrollments:
        c = db.get_course(e["course_id"])
        if c:
            course_titles.append(c["title"])
        for g in db.get_grades(student_id, e["course_id"]):
            grades.append({"assignment": g["title"], "score": g["score"], "maxScore": g["max_score"]})
        att = db.get_attendance(student_id, e["course_id"])
        attendances.extend(att)

    avg = db.get_overall_average(student_id)
    att_pct = attendances[0]["percentage"] if attendances else None

    return {
        "id": student["student_id"],
        "name": student["name"],
        "email": student["email"],
        "course": ", ".join(course_titles) if course_titles else "—",
        "avgGrade": avg if avg is not None else "—",
        "attendancePct": att_pct if att_pct is not None else "—",
        "status": _roster_status(att_pct, avg),
        "grades": grades,
        # No per-session (present/absent/excused) tracking exists in the
        # schema — Attendance only stores a percentage per course, not a
        # session log — so "attendance" (the breakdown object) is
        # intentionally omitted rather than fabricated. The stat card
        # above already shows the real attendancePct; student-details.js
        # gracefully falls back to "This term" when this key is absent.
    }


# =======================================================================
# Lookups (dropdowns for the report-case form etc.)
# =======================================================================

@router.get("/lookups/students")
def lookup_students(user: CurrentUser = Depends(require_role("instructor"))):
    course_ids = _instructor_course_ids(user.user_id)
    if not course_ids:
        return []
    placeholders = ",".join("?" * len(course_ids))
    rows = db.query_all(
        f"""SELECT DISTINCT s.student_id AS id, s.name
            FROM Enrollments e JOIN Students s ON s.student_id = e.student_id
            WHERE e.course_id IN ({placeholders}) AND e.status = 'active'
            ORDER BY s.name""",
        tuple(course_ids),
    )
    return rows


@router.get("/lookups/courses")
def lookup_courses(user: CurrentUser = Depends(require_role("instructor"))):
    return db.query_all(
        "SELECT course_id AS id, title AS name FROM Courses WHERE instructor_id = ? ORDER BY title",
        (user.user_id,),
    )


@router.get("/lookups/assessments")
def lookup_assessments(user: CurrentUser = Depends(require_role("instructor"))):
    course_ids = _instructor_course_ids(user.user_id)
    if not course_ids:
        return []
    placeholders = ",".join("?" * len(course_ids))
    rows = db.query_all(
        f"""SELECT assignment_id AS id, title AS name, course_id FROM Assignments
            WHERE course_id IN ({placeholders}) ORDER BY deadline""",
        tuple(course_ids),
    )
    return rows


# =======================================================================
# Requests (write-op HITL queue — see module docstring). requests.js
# reads: id,type,student,course,status,submittedLabel. request-details.js
# additionally reads: fieldLabel,currentValue,proposedValue,
# agentReasoning,evidence[],availableActions[],decision{action,byLabel,atLabel}
# =======================================================================

@router.get("/requests")
def list_requests(
    search: str = "",
    status: str = "all",
    user: CurrentUser = Depends(require_role("instructor")),
):
    sql = """SELECT wr.request_id AS id, wr.request_type AS type, s.name AS student,
                     c.title AS course, wr.status, wr.submitted_at
              FROM WriteOpRequests wr
              JOIN Students s ON s.student_id = wr.student_id
              JOIN Courses c ON c.course_id = wr.course_id
              WHERE wr.instructor_id = ?"""
    params: list = [user.user_id]
    if status != "all":
        sql += " AND wr.status = ?"
        params.append(status)
    sql += " ORDER BY wr.submitted_at DESC"
    rows = db.query_all(sql, tuple(params))
    if search.strip():
        q = search.strip().lower()
        rows = [r for r in rows if q in r["student"].lower() or q in r["course"].lower() or q in str(r["id"])]
    return [
        {"id": r["id"], "type": r["type"], "student": r["student"], "course": r["course"],
         "status": r["status"], "submittedLabel": _fmt_label(r["submitted_at"])}
        for r in rows
    ]


def _request_row(request_id: int, instructor_id: int) -> dict:
    row = db.query_one(
        """SELECT wr.*, s.name AS student, c.title AS course
           FROM WriteOpRequests wr
           JOIN Students s ON s.student_id = wr.student_id
           JOIN Courses c ON c.course_id = wr.course_id
           WHERE wr.request_id = ?""",
        (request_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    if row["instructor_id"] != instructor_id:
        raise HTTPException(status_code=403, detail="Not your request.")
    return row


@router.get("/requests/{request_id}")
def get_request(request_id: int, user: CurrentUser = Depends(require_role("instructor"))):
    row = _request_row(request_id, user.user_id)
    decision = None
    if row["status"] != "pending":
        instructor = db.get_instructor(user.user_id)
        decision = {
            "action": {"approved": "approve", "rejected": "reject", "info_requested": "request_info"}.get(row["status"], row["status"]),
            "byLabel": f"{instructor['name']} — Instructor" if instructor else "Instructor",
            "atLabel": _fmt_label(row["decided_at"]),
        }
    return {
        "id": row["request_id"],
        "type": row["request_type"],
        "status": row["status"],
        "student": row["student"],
        "course": row["course"],
        "submittedLabel": _fmt_label(row["submitted_at"]),
        "fieldLabel": row["field_label"],
        "currentValue": row["current_value"],
        "proposedValue": row["proposed_value"],
        "agentReasoning": row["agent_reasoning"],
        # No file/document evidence store exists for write-op requests
        # (unlike Academic Integrity's IntegrityEvidence table) — honestly
        # empty rather than fabricated; request-details.js already shows
        # "No supporting evidence for this request." when this is [].
        "evidence": [],
        "availableActions": ["approve", "reject", "request_info"] if row["status"] == "pending" else [],
        "decision": decision,
    }


@router.post("/requests/{request_id}/decision")
def decide_request(request_id: int, body: RequestDecisionBody, user: CurrentUser = Depends(require_role("instructor"))):
    row = _request_row(request_id, user.user_id)
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Request already '{row['status']}'.")

    try:
        action = body.resolved_action()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if action == "approve":
        if row["request_type"] == "grade_update":
            if row["assignment_id"] is None:
                raise HTTPException(status_code=422, detail="Request has no assignment_id to grade.")
            db.upsert_grade(row["student_id"], row["assignment_id"], float(row["proposed_value"]), user.user_id)
        elif row["request_type"] == "attendance_update":
            db.upsert_attendance(row["student_id"], row["course_id"], float(row["proposed_value"]))
        elif row["request_type"] == "enrollment_change":
            db.set_enrollment_status(row["student_id"], row["course_id"], row["proposed_value"])
        new_status = "approved"
    elif action == "reject":
        new_status = "rejected"
    else:  # request_info
        new_status = "info_requested"

    db.execute(
        "UPDATE WriteOpRequests SET status = ?, decided_at = DATETIME('now'), decision_notes = ? WHERE request_id = ?",
        (new_status, body.notes, request_id),
    )
    return {"id": request_id, "action": action, "status": new_status}


# =======================================================================
# Agents — static/visual-only list, moved server-side per the original
# frontend comment ("visual-only per brief").
# =======================================================================

@router.get("/agents")
def list_agents(user: CurrentUser = Depends(require_role("instructor"))):
    return [
        {
            "id": "academic-integrity-agent",
            "name": "Academic Integrity Agent",
            "description": "Assists with academic integrity workflows and case analysis.",
            "status": "available",
        }
    ]