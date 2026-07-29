"""
database.py
===========
SQLite-backed data layer for Brightpeak Academy MCP server.

Tables
------
  students          – student profiles
  courses           – course catalogue
  instructors       – instructor records
  assignments       – assignments belonging to courses
  enrollments       – student ↔ course membership + progress
  grades            – one row per (student, assignment)
  attendance        – one row per (student, course)

All write functions use INSERT OR REPLACE (upsert) so callers
never have to distinguish insert vs update.
"""

import sqlite3
from contextlib import contextmanager
from typing import Any

# -----------------------------------------------------------------------
# Connection helpers
# -----------------------------------------------------------------------

# Shared in-memory database — same connection reused across the process
# so all callers see the same data without writing anything to disk.
_DB = sqlite3.connect(":memory:", check_same_thread=False)
_DB.row_factory = sqlite3.Row
_DB.execute("PRAGMA foreign_keys = ON")
_DB.commit()


@contextmanager
def _conn():
    """Yield the shared in-memory connection and auto-commit / rollback."""
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
# Schema bootstrap  (called once at import time)
# -----------------------------------------------------------------------

def _init_db() -> None:
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS instructors (
            instructor_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            email          TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS students (
            student_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            level       TEXT NOT NULL DEFAULT 'beginner'
                        CHECK(level IN ('beginner','intermediate','advanced'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            course_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            title          TEXT NOT NULL,
            instructor_id  INTEGER NOT NULL REFERENCES instructors(instructor_id),
            start_date     TEXT NOT NULL,   -- ISO-8601 date
            max_students   INTEGER NOT NULL DEFAULT 30
        );

        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id      INTEGER NOT NULL REFERENCES courses(course_id),
            title          TEXT NOT NULL,
            max_score      REAL NOT NULL DEFAULT 100.0
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            student_id       INTEGER NOT NULL REFERENCES students(student_id),
            course_id        INTEGER NOT NULL REFERENCES courses(course_id),
            status           TEXT NOT NULL DEFAULT 'active'
                             CHECK(status IN ('active','completed','dropped')),
            progress         REAL NOT NULL DEFAULT 0.0,   -- 0-100 %
            enrollment_date  TEXT NOT NULL,               -- ISO-8601 date
            PRIMARY KEY (student_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS grades (
            student_id     INTEGER NOT NULL REFERENCES students(student_id),
            assignment_id  INTEGER NOT NULL REFERENCES assignments(assignment_id),
            score          REAL NOT NULL,
            graded_by      INTEGER NOT NULL REFERENCES instructors(instructor_id),
            graded_at      TEXT NOT NULL DEFAULT (date('now')),
            PRIMARY KEY (student_id, assignment_id)
        );

        CREATE TABLE IF NOT EXISTS attendance (
            student_id   INTEGER NOT NULL REFERENCES students(student_id),
            course_id    INTEGER NOT NULL REFERENCES courses(course_id),
            percentage   REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (student_id, course_id)
        );
        """)
    _seed_demo_data()


def _seed_demo_data() -> None:
    """Insert demo rows only when the DB is empty."""
    with _conn() as con:
        if con.execute("SELECT COUNT(*) FROM students").fetchone()[0] > 0:
            return   # already seeded

        # Instructors
        con.execute("INSERT INTO instructors(name,email) VALUES(?,?)",
                    ("Dr. Sara Hassan", "sara.hassan@brightpeak.edu"))
        con.execute("INSERT INTO instructors(name,email) VALUES(?,?)",
                    ("Prof. Omar Fathy", "omar.fathy@brightpeak.edu"))

        # Students
        for name, email, level in [
            ("Ahmed Ali",    "ahmed.ali@student.bp",    "intermediate"),
            ("Mona Tarek",   "mona.tarek@student.bp",   "beginner"),
            ("Khaled Nour",  "khaled.nour@student.bp",  "advanced"),
            ("Nadia Salem",  "nadia.salem@student.bp",  "beginner"),
            ("Youssef Magd", "youssef.m@student.bp",    "intermediate"),
        ]:
            con.execute(
                "INSERT INTO students(name,email,level) VALUES(?,?,?)",
                (name, email, level),
            )

        # Courses
        con.execute(
            "INSERT INTO courses(title,instructor_id,start_date) VALUES(?,?,?)",
            ("Python Fundamentals", 1, "2025-02-01"),
        )
        con.execute(
            "INSERT INTO courses(title,instructor_id,start_date) VALUES(?,?,?)",
            ("Data Structures", 2, "2025-03-01"),
        )

        # Assignments  (course 1)
        for title, max_score in [
            ("Quiz 1", 20), ("Midterm", 50), ("Final Project", 100)
        ]:
            con.execute(
                "INSERT INTO assignments(course_id,title,max_score) VALUES(?,?,?)",
                (1, title, max_score),
            )
        # Assignments  (course 2)
        for title, max_score in [
            ("Problem Set 1", 30), ("Problem Set 2", 30), ("Final Exam", 100)
        ]:
            con.execute(
                "INSERT INTO assignments(course_id,title,max_score) VALUES(?,?,?)",
                (2, title, max_score),
            )

        # Enrollments
        import datetime
        today = datetime.date.today().isoformat()
        past  = "2025-02-01"   # well outside the 14-day window
        for sid, cid, status, progress, enrolled in [
            (1, 1, "active",    60.0, past),
            (2, 1, "active",    30.0, past),
            (3, 1, "completed", 100.0, past),
            (4, 2, "active",    45.0, today),  # inside 14-day window
            (5, 2, "active",    80.0, past),
        ]:
            con.execute(
                "INSERT INTO enrollments VALUES(?,?,?,?,?)",
                (sid, cid, status, progress, enrolled),
            )

        # Grades
        for sid, aid, score in [
            (1, 1, 16), (1, 2, 38),
            (2, 1, 10),
            (3, 1, 20), (3, 2, 47), (3, 3, 91),
            (4, 4, 25), (4, 5, 22),
            (5, 4, 28), (5, 5, 29), (5, 6, 88),
        ]:
            con.execute(
                "INSERT INTO grades(student_id,assignment_id,score,graded_by) VALUES(?,?,?,?)",
                (sid, aid, score, 1),
            )

        # Attendance
        for sid, cid, pct in [
            (1, 1, 85.0), (2, 1, 60.0), (3, 1, 95.0),
            (4, 2, 70.0), (5, 2, 90.0),
        ]:
            con.execute(
                "INSERT INTO attendance VALUES(?,?,?)",
                (sid, cid, pct),
            )


# -----------------------------------------------------------------------
# READ  –  students
# -----------------------------------------------------------------------

def get_student(student_id: int) -> dict[str, Any] | None:
    """Return student profile dict or None if not found."""
    with _conn() as con:
        row = con.execute(
            "SELECT student_id, name, email, level FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    return _row(row)


# -----------------------------------------------------------------------
# READ  –  courses & assignments
# -----------------------------------------------------------------------

def get_course(course_id: int) -> dict[str, Any] | None:
    """Return course dict (including instructor_id) or None."""
    with _conn() as con:
        row = con.execute(
            "SELECT course_id, title, instructor_id, start_date, max_students "
            "FROM courses WHERE course_id = ?",
            (course_id,),
        ).fetchone()
    return _row(row)


def get_assignment(assignment_id: int) -> dict[str, Any] | None:
    """Return assignment dict (including course_id and max_score) or None."""
    with _conn() as con:
        row = con.execute(
            "SELECT assignment_id, course_id, title, max_score "
            "FROM assignments WHERE assignment_id = ?",
            (assignment_id,),
        ).fetchone()
    return _row(row)


def get_course_assignments(course_id: int) -> list[dict[str, Any]]:
    """Return all assignments for a course."""
    with _conn() as con:
        rows = con.execute(
            "SELECT assignment_id, title, max_score FROM assignments WHERE course_id = ?",
            (course_id,),
        ).fetchall()
    return _rows(rows)


# -----------------------------------------------------------------------
# READ  –  enrollments
# -----------------------------------------------------------------------

def get_enrollments(
    student_id: int, course_id: int | None = None
) -> list[dict[str, Any]]:
    """Return enrollments for a student, optionally filtered to one course."""
    with _conn() as con:
        if course_id is None:
            rows = con.execute(
                """
                SELECT e.student_id, e.course_id, c.title AS course_title,
                       e.status, e.progress, e.enrollment_date
                FROM   enrollments e
                JOIN   courses c USING (course_id)
                WHERE  e.student_id = ?
                """,
                (student_id,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT e.student_id, e.course_id, c.title AS course_title,
                       e.status, e.progress, e.enrollment_date
                FROM   enrollments e
                JOIN   courses c USING (course_id)
                WHERE  e.student_id = ? AND e.course_id = ?
                """,
                (student_id, course_id),
            ).fetchall()
    return _rows(rows)


def list_enrolled_students(course_id: int) -> list[dict[str, Any]]:
    """Return all *active* students enrolled in a course."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT s.student_id, s.name, e.status, e.progress
            FROM   enrollments e
            JOIN   students s USING (student_id)
            WHERE  e.course_id = ? AND e.status = 'active'
            ORDER  BY s.name
            """,
            (course_id,),
        ).fetchall()
    return _rows(rows)


# -----------------------------------------------------------------------
# READ  –  grades
# -----------------------------------------------------------------------

def get_grades(
    student_id: int, course_id: int | None = None
) -> list[dict[str, Any]]:
    """Return grade rows for a student, optionally filtered to one course."""
    with _conn() as con:
        if course_id is None:
            rows = con.execute(
                """
                SELECT g.assignment_id, a.title, a.max_score,
                       g.score, g.graded_at,
                       ROUND(g.score * 100.0 / a.max_score, 1) AS percentage
                FROM   grades g
                JOIN   assignments a USING (assignment_id)
                WHERE  g.student_id = ?
                ORDER  BY g.graded_at
                """,
                (student_id,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT g.assignment_id, a.title, a.max_score,
                       g.score, g.graded_at,
                       ROUND(g.score * 100.0 / a.max_score, 1) AS percentage
                FROM   grades g
                JOIN   assignments a USING (assignment_id)
                WHERE  g.student_id = ? AND a.course_id = ?
                ORDER  BY g.graded_at
                """,
                (student_id, course_id),
            ).fetchall()
    return _rows(rows)


def get_overall_average(student_id: int) -> float | None:
    """Return the student's average score as a percentage across all graded
    assignments, or None if they have no grades yet."""
    with _conn() as con:
        row = con.execute(
            """
            SELECT ROUND(AVG(g.score * 100.0 / a.max_score), 1) AS avg_pct
            FROM   grades g
            JOIN   assignments a USING (assignment_id)
            WHERE  g.student_id = ?
            """,
            (student_id,),
        ).fetchone()
    if row is None:
        return None
    return row["avg_pct"]  # may still be None if no grades


def get_grade_for_assignment(
    student_id: int, assignment_id: int
) -> dict[str, Any] | None:
    """Return a single grade row or None (used by validation.py)."""
    with _conn() as con:
        row = con.execute(
            """
            SELECT g.score, a.max_score,
                   ROUND(g.score * 100.0 / a.max_score, 1) AS percentage
            FROM   grades g
            JOIN   assignments a USING (assignment_id)
            WHERE  g.student_id = ? AND g.assignment_id = ?
            """,
            (student_id, assignment_id),
        ).fetchone()
    return _row(row)


# -----------------------------------------------------------------------
# READ  –  attendance
# -----------------------------------------------------------------------

def get_attendance(
    student_id: int, course_id: int | None = None
) -> list[dict[str, Any]]:
    """Return attendance rows for a student, optionally filtered to one course."""
    with _conn() as con:
        if course_id is None:
            rows = con.execute(
                """
                SELECT a.student_id, a.course_id, c.title AS course_title,
                       a.percentage
                FROM   attendance a
                JOIN   courses c USING (course_id)
                WHERE  a.student_id = ?
                """,
                (student_id,),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT a.student_id, a.course_id, c.title AS course_title,
                       a.percentage
                FROM   attendance a
                JOIN   courses c USING (course_id)
                WHERE  a.student_id = ? AND a.course_id = ?
                """,
                (student_id, course_id),
            ).fetchall()
    return _rows(rows)


# -----------------------------------------------------------------------
# WRITE  –  grades
# -----------------------------------------------------------------------

def upsert_grade(
    student_id: int,
    assignment_id: int,
    score: float,
    graded_by: int,
) -> None:
    """Insert or update a grade.  graded_at is refreshed on every update."""
    with _conn() as con:
        con.execute(
            """
            INSERT INTO grades(student_id, assignment_id, score, graded_by, graded_at)
            VALUES (?, ?, ?, ?, date('now'))
            ON CONFLICT(student_id, assignment_id) DO UPDATE SET
                score      = excluded.score,
                graded_by  = excluded.graded_by,
                graded_at  = excluded.graded_at
            """,
            (student_id, assignment_id, score, graded_by),
        )


# -----------------------------------------------------------------------
# WRITE  –  attendance
# -----------------------------------------------------------------------

def upsert_attendance(
    student_id: int, course_id: int, percentage: float
) -> None:
    """Insert or update an attendance record."""
    with _conn() as con:
        con.execute(
            """
            INSERT INTO attendance(student_id, course_id, percentage)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id, course_id) DO UPDATE SET
                percentage = excluded.percentage
            """,
            (student_id, course_id, percentage),
        )


# -----------------------------------------------------------------------
# WRITE  –  enrollments
# -----------------------------------------------------------------------

def set_enrollment_status(
    student_id: int, course_id: int, status: str
) -> None:
    """Update enrollment status.  Caller must validate status beforehand."""
    with _conn() as con:
        con.execute(
            """
            UPDATE enrollments SET status = ?
            WHERE  student_id = ? AND course_id = ?
            """,
            (status, student_id, course_id),
        )


# -----------------------------------------------------------------------
# Bootstrap
# -----------------------------------------------------------------------

_init_db()