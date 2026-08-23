"""
instructor_router.py
=====================
"My Courses" / "Students" surface for the Instructor portal
(frontend/instructor/courses, frontend/instructor/students), which
previously read entirely from frontend/instructor/shared/api.js's
BP_MOCK.courseList / BP_MOCK.studentRoster / BP_MOCK.studentDetails.

Everything here is a straight read against Courses / Enrollments /
Grades / Attendance, scoped to courses the logged-in instructor
actually teaches (Courses.instructor_id) — an instructor can never
see another instructor's roster this way, matching the same
server-side authorization pattern core/auth.py already establishes.

NOTE on scope: the old mock also had a "Requests" feed (grade_update /
attendance_update approval queue). No table in db/schema.sql models a
pending grade/attendance change request — Grades/Attendance are written
directly (see mcp_server.database.upsert_grade/upsert_attendance), with
no draft/approval state. Faking that queue would mean inventing a
concept the schema doesn't have, which the brief explicitly rules out
(section 16: don't overengineer / section 1: trace where data actually
comes from). This is called out as a remaining limitation in the audit
report rather than mocked here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

import mcp_server.database as db
from core.auth import require_role, CurrentUser

router = APIRouter(prefix="/instructor", tags=["instructor"])


def _course_row(course_id: int, instructor_id: int) -> dict:
    row = db.query_one(
        "SELECT * FROM Courses WHERE course_id = ? AND instructor_id = ?",
        (course_id, instructor_id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    return row


def _course_summary(course: dict) -> dict:
    students_count = db.query_one(
        "SELECT COUNT(*) AS n FROM Enrollments WHERE course_id = ? AND status = 'active'",
        (course["course_id"],),
    )["n"]
    avg_row = db.query_one(
        """SELECT AVG(g.score) AS avg FROM Grades g
           JOIN Assignments a ON a.assignment_id = g.assignment_id
           WHERE a.course_id = ?""",
        (course["course_id"],),
    )
    return {
        "id": course["course_id"],
        "name": course["title"],
        "category": course["category"],
        "duration": course["duration"],
        "studentsCount": students_count,
        "avgGrade": round(avg_row["avg"]) if avg_row and avg_row["avg"] is not None else None,
    }


@router.get("/courses")
def list_courses(user: CurrentUser = Depends(require_role("instructor"))):
    rows = db.query_all(
        "SELECT * FROM Courses WHERE instructor_id = ? ORDER BY title", (user.user_id,)
    )
    return [_course_summary(r) for r in rows]


@router.get("/courses/{course_id}")
def get_course(course_id: int, user: CurrentUser = Depends(require_role("instructor"))):
    course = _course_row(course_id, user.user_id)
    roster = db.query_all(
        """SELECT s.student_id, s.name, s.email, e.status, e.progress
           FROM Enrollments e JOIN Students s ON s.student_id = e.student_id
           WHERE e.course_id = ? ORDER BY s.name""",
        (course_id,),
    )
    return {**_course_summary(course), "roster": roster}


@router.get("/students")
def list_students(
    search: str = "",
    course_id: int | None = None,
    user: CurrentUser = Depends(require_role("instructor")),
):
    sql = """SELECT DISTINCT s.student_id, s.name, s.email, e.course_id, c.title AS course,
                    e.status AS enrollment_status
             FROM Enrollments e
             JOIN Students s ON s.student_id = e.student_id
             JOIN Courses c ON c.course_id = e.course_id
             WHERE c.instructor_id = ?"""
    params: list = [user.user_id]
    if course_id is not None:
        sql += " AND e.course_id = ?"
        params.append(course_id)
    if search.strip():
        sql += " AND (s.name LIKE ? OR c.title LIKE ?)"
        q = f"%{search.strip()}%"
        params.extend([q, q])
    sql += " ORDER BY s.name"
    rows = db.query_all(sql, tuple(params))

    out = []
    for r in rows:
        attendance = db.query_one(
            "SELECT percentage FROM Attendance WHERE student_id = ? AND course_id = ?",
            (r["student_id"], r["course_id"]),
        )
        avg_grade = db.query_one(
            """SELECT AVG(g.score) AS avg FROM Grades g
               JOIN Assignments a ON a.assignment_id = g.assignment_id
               WHERE g.student_id = ? AND a.course_id = ?""",
            (r["student_id"], r["course_id"]),
        )
        out.append(
            {
                "id": r["student_id"],
                "name": r["name"],
                "email": r["email"],
                "courseId": r["course_id"],
                "course": r["course"],
                "attendancePct": attendance["percentage"] if attendance else None,
                "avgGrade": round(avg_grade["avg"]) if avg_grade and avg_grade["avg"] is not None else None,
            }
        )
    return out


@router.get("/students/{student_id}")
def get_student(
    student_id: int,
    course_id: int | None = None,
    user: CurrentUser = Depends(require_role("instructor")),
):
    student = db.query_one(
        """SELECT s.student_id, s.name, s.email FROM Students s
           JOIN Enrollments e ON e.student_id = s.student_id
           JOIN Courses c ON c.course_id = e.course_id
           WHERE s.student_id = ? AND c.instructor_id = ? LIMIT 1""",
        (student_id, user.user_id),
    )
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found in your courses.")

    grades_sql = """SELECT a.title AS assignment, g.score, a.max_score AS maxScore
                     FROM Grades g JOIN Assignments a ON a.assignment_id = g.assignment_id
                     JOIN Courses c ON c.course_id = a.course_id
                     WHERE g.student_id = ? AND c.instructor_id = ?"""
    params = [student_id, user.user_id]
    if course_id is not None:
        grades_sql += " AND a.course_id = ?"
        params.append(course_id)
    grades = db.query_all(grades_sql, tuple(params))

    attendance_sql = """SELECT c.title AS course, at.percentage
                         FROM Attendance at JOIN Courses c ON c.course_id = at.course_id
                         WHERE at.student_id = ? AND c.instructor_id = ?"""
    attendance = db.query_all(attendance_sql, (student_id, user.user_id))

    return {**student, "grades": grades, "attendance": attendance}