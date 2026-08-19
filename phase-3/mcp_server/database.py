"""
database.py
===========
SQLite-backed data layer for Brightpeak Academy MCP server.

Looks for brightpeak.db in the same folder as this file (dp/).
If the file doesn't exist, creates it and runs schema.sql.
If the DB is empty, runs seed.sql.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------------
# Paths  —  all three files live in the same folder (dp/)
# -----------------------------------------------------------------------
_DIR = Path(__file__).parent.parent / "db"
_DB_PATH = _DIR / "brightpeak.db"
_SCHEMA  = _DIR / "schema.sql"
_SEED    = _DIR / "seed.sql"

# -----------------------------------------------------------------------
# Shared connection
# -----------------------------------------------------------------------

_DB = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
_DB.row_factory = sqlite3.Row
_DB.execute("PRAGMA foreign_keys = ON")
_DB.commit()


@contextmanager
def _conn():
    try:
        yield _DB
        _DB.commit()
    except Exception:
        _DB.rollback()
        raise


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


# -----------------------------------------------------------------------
# Bootstrap  —  schema then seed
# -----------------------------------------------------------------------

def _init_db() -> None:
    with _conn() as con:
        # Run schema.sql if tables don't exist yet
        con.executescript(_SCHEMA.read_text(encoding="utf-8"))

        # Run seed.sql only if Students table is empty
        if con.execute("SELECT COUNT(*) FROM Students").fetchone()[0] == 0:
            con.executescript(_SEED.read_text(encoding="utf-8"))


# -----------------------------------------------------------------------
# READ — Students & Instructors
# -----------------------------------------------------------------------

def get_student(student_id: int) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT student_id, name, email, level FROM Students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    return _row(row)

def get_instructor(instructor_id: int):
    with _conn() as con:
        row = con.execute(
            """
            SELECT instructor_id, name, email
            FROM Instructors
            WHERE instructor_id = ?
            """,
            (instructor_id,),
        ).fetchone()
    return _row(row)


# -----------------------------------------------------------------------
# READ — Courses & Assignments
# -----------------------------------------------------------------------

def get_course(course_id: int) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT course_id, title, category, duration, instructor_id "
            "FROM Courses WHERE course_id = ?",
            (course_id,),
        ).fetchone()
    return _row(row)


def get_assignment(assignment_id: int) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT assignment_id, course_id, title, deadline, max_score "
            "FROM Assignments WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()
    return _row(row)


def get_course_assignments(course_id: int) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT assignment_id, title, deadline, max_score "
            "FROM Assignments WHERE course_id = ? ORDER BY deadline",
            (course_id,),
        ).fetchall()
    return _rows(rows)


# -----------------------------------------------------------------------
# READ — Enrollments
# -----------------------------------------------------------------------

def get_enrollments(
    student_id: int, course_id: int | None = None
) -> list[dict[str, Any]]:
    with _conn() as con:
        if course_id is None:
            rows = con.execute(
                """
                SELECT e.enrollment_id, e.student_id, e.course_id,
                       c.title AS course_title,
                       e.status, e.progress, e.enrollment_date
                FROM   Enrollments e
                JOIN   Courses c USING (course_id)
                WHERE  e.student_id = ?
                """,
                (student_id,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT e.enrollment_id, e.student_id, e.course_id,
                       c.title AS course_title,
                       e.status, e.progress, e.enrollment_date
                FROM   Enrollments e
                JOIN   Courses c USING (course_id)
                WHERE  e.student_id = ? AND e.course_id = ?
                """,
                (student_id, course_id),
            ).fetchall()
    return _rows(rows)


def list_enrolled_students(course_id: int) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT s.student_id, s.name, e.status, e.progress
            FROM   Enrollments e
            JOIN   Students s USING (student_id)
            WHERE  e.course_id = ? AND e.status = 'active'
            ORDER  BY s.name
            """,
            (course_id,),
        ).fetchall()
    return _rows(rows)


# -----------------------------------------------------------------------
# READ — Grades
# -----------------------------------------------------------------------

def get_grades(
    student_id: int, course_id: int | None = None
) -> list[dict[str, Any]]:
    with _conn() as con:
        if course_id is None:
            rows = con.execute(
                """
                SELECT g.grade_id, g.assignment_id, a.title,
                       a.max_score, g.score, g.graded_by,
                       ROUND(g.score * 100.0 / a.max_score, 1) AS percentage
                FROM   Grades g
                JOIN   Assignments a USING (assignment_id)
                WHERE  g.student_id = ?
                ORDER  BY a.deadline
                """,
                (student_id,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT g.grade_id, g.assignment_id, a.title,
                       a.max_score, g.score, g.graded_by,
                       ROUND(g.score * 100.0 / a.max_score, 1) AS percentage
                FROM   Grades g
                JOIN   Assignments a USING (assignment_id)
                WHERE  g.student_id = ? AND a.course_id = ?
                ORDER  BY a.deadline
                """,
                (student_id, course_id),
            ).fetchall()
    return _rows(rows)


def get_overall_average(student_id: int) -> float | None:
    with _conn() as con:
        row = con.execute(
            """
            SELECT ROUND(AVG(g.score * 100.0 / a.max_score), 1) AS avg_pct
            FROM   Grades g
            JOIN   Assignments a USING (assignment_id)
            WHERE  g.student_id = ?
            """,
            (student_id,),
        ).fetchone()
    return row["avg_pct"] if row else None


def get_grade_for_assignment(
    student_id: int, assignment_id: int
) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            """
            SELECT g.score, a.max_score,
                   ROUND(g.score * 100.0 / a.max_score, 1) AS percentage
            FROM   Grades g
            JOIN   Assignments a USING (assignment_id)
            WHERE  g.student_id = ? AND g.assignment_id = ?
            """,
            (student_id, assignment_id),
        ).fetchone()
    return _row(row)


# -----------------------------------------------------------------------
# READ — Attendance
# -----------------------------------------------------------------------

def get_attendance(
    student_id: int, course_id: int | None = None
) -> list[dict[str, Any]]:
    with _conn() as con:
        if course_id is None:
            rows = con.execute(
                """
                SELECT a.attendance_id, a.student_id, a.course_id,
                       c.title AS course_title, a.percentage
                FROM   Attendance a
                JOIN   Courses c USING (course_id)
                WHERE  a.student_id = ?
                """,
                (student_id,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT a.attendance_id, a.student_id, a.course_id,
                       c.title AS course_title, a.percentage
                FROM   Attendance a
                JOIN   Courses c USING (course_id)
                WHERE  a.student_id = ? AND a.course_id = ?
                """,
                (student_id, course_id),
            ).fetchall()
    return _rows(rows)


# -----------------------------------------------------------------------
# READ — Policies
# -----------------------------------------------------------------------

def get_all_policies() -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT policy_id, title, category, content FROM Policies ORDER BY category, title"
        ).fetchall()
    return _rows(rows)


def get_policy(policy_id: int) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT policy_id, title, category, content FROM Policies WHERE policy_id = ?",
            (policy_id,),
        ).fetchone()
    return _row(row)



# -----------------------------------------------------------------------
# READ — Course Materials
# -----------------------------------------------------------------------
 
def get_course_materials(course_id: int) -> list[dict[str, Any]]:
    """List every material row registered for a course (metadata only —
    the actual text lives in documents/course_materials/ and is reached
    through rag.search_course_material, not through this table)."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT material_id, course_id, title, description,
                   material_type, source_file, created_at, updated_at
            FROM   CourseMaterials
            WHERE  course_id = ?
            ORDER  BY material_id
            """,
            (course_id,),
        ).fetchall()
    return _rows(rows)
 
 
def get_course_material(material_id: int) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            """
            SELECT material_id, course_id, title, description,
                   material_type, source_file, created_at, updated_at
            FROM   CourseMaterials
            WHERE  material_id = ?
            """,
            (material_id,),
        ).fetchone()
    return _row(row)
 

# -----------------------------------------------------------------------
# WRITE — Grades
# -----------------------------------------------------------------------

def upsert_grade(
    student_id: int,
    assignment_id: int,
    score: float,
    graded_by: int,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO Grades(student_id, assignment_id, score, graded_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id, assignment_id) DO UPDATE SET
                score     = excluded.score,
                graded_by = excluded.graded_by
            """,
            (student_id, assignment_id, score, graded_by),
        )


# -----------------------------------------------------------------------
# WRITE — Attendance
# -----------------------------------------------------------------------

def upsert_attendance(
    student_id: int, course_id: int, percentage: float
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO Attendance(student_id, course_id, percentage)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id, course_id) DO UPDATE SET
                percentage = excluded.percentage
            """,
            (student_id, course_id, percentage),
        )


# -----------------------------------------------------------------------
# WRITE — Enrollments
# -----------------------------------------------------------------------

def set_enrollment_status(
    student_id: int, course_id: int, status: str
) -> None:
    with _conn() as con:
        con.execute(
            """
            UPDATE Enrollments SET status = ?
            WHERE  student_id = ? AND course_id = ?
            """,
            (status, student_id, course_id),
        )


# -----------------------------------------------------------------------
# Bootstrap
# -----------------------------------------------------------------------

_init_db()

def execute(sql: str, params: tuple = ()) -> None:
    with _conn() as conn:
        conn.execute(sql, params)


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    with _conn() as conn:
        return _row(conn.execute(sql, params).fetchone())