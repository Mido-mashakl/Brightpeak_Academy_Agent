"""
db.py — Real SQLite data layer for the Track Recommendation graph.

FIXED: this module did not exist before — every `import db` in
nodes_intake.py / nodes_evaluation.py / nodes_hitl.py pointed at nothing,
so the graph could not run at all. This file implements every function
those node modules call, against the REAL schema in db/schema.sql
(Students, Courses, Grades, Attendance, Tracks, TrackRecommendations,
DiagnosticAssessments, Tickets) — no invented tables, no free text.

Connection pattern mirrors checkpointing.py / mcp_server/database.py:
one shared sqlite3 connection to the SAME brightpeak.db used by every
other Phase-3 graph (adaptive_assessment, academic_integrity, advisory),
with WAL mode so concurrent connections from those other subsystems
don't hit "database is locked" during a demo run.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_PHASE4 = Path(__file__).resolve().parent.parent.parent.parent / "phase-4" / "brightpeak.db"
_PHASE3 = Path(__file__).resolve().parent.parent.parent / "db" / "brightpeak.db"
DB_PATH = _PHASE4 if _PHASE4.exists() else _PHASE3

_DB = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
_DB.row_factory = sqlite3.Row
_DB.execute("PRAGMA foreign_keys = ON")
# FIXED: this used to also set "PRAGMA journal_mode = WAL" here, while
# mcp_server/database.py (the connection nearly everything else in the
# app goes through) and advisory/checkpointing.py leave the default
# rollback-journal mode. Multiple sqlite3 connections -- from this
# module, database.py, several SqliteSaver checkpointers, AND the
# Node/better-sqlite3 process (server.js) -- all opening the SAME
# physical brightpeak.db with inconsistent journal modes across
# processes is a real, reproducible cause of "database disk image is
# malformed" corruption, especially on Windows. Matching the default
# mode everyone else already uses (with a busy-timeout instead, same as
# advisory/checkpointing.py) removes that inconsistency.
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


def _now() -> str:
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Bootstrap — Tracks is seeded independently of seed.sql's Students-empty
# guard, since a DB that already has Students (from an earlier partial seed)
# would otherwise leave Tracks/TrackRecommendations/DiagnosticAssessments
# permanently empty. This is idempotent (INSERT OR IGNORE by unique `name`).
# ---------------------------------------------------------------------------
_DEFAULT_TRACKS = [
    (1, "Data Science",
     "Focuses on extracting insight from data using statistics, Python, and machine learning.",
     [{"course": "Introduction to Python", "min_score": 70},
      {"course": "Database Design & SQL", "min_score": 65}],
     ["Machine Learning Fundamentals", "Data Visualization with Python"]),
    (2, "AI Engineering",
     "Focuses on building and deploying machine learning and deep learning systems in production.",
     [{"course": "Introduction to Python", "min_score": 80},
      {"course": "Machine Learning Fundamentals", "min_score": 75}],
     ["Data Visualization with Python", "Advanced Python & OOP"]),
    (3, "Software Engineering",
     "Focuses on building, testing, and deploying robust software systems and backend services.",
     [{"course": "Introduction to Python", "min_score": 75},
      {"course": "Data Structures & Algorithms", "min_score": 70}],
     ["Advanced Python & OOP", "Node.js & Backend Development", "Database Design & SQL"]),
    (4, "Web Development",
     "Focuses on building modern, full-stack web applications with front-end and back-end frameworks.",
     [{"course": "Introduction to Python", "min_score": 65}],
     ["Web Development with React", "Node.js & Backend Development", "Database Design & SQL"]),
    (5, "Mobile Development",
     "Focuses on building cross-platform mobile applications.",
     [{"course": "Introduction to Python", "min_score": 65}],
     ["Mobile App Development with Flutter"]),
]


def _ensure_tracks_seeded() -> None:
    with _conn() as con:
        count = con.execute("SELECT COUNT(*) FROM Tracks").fetchone()[0]
        if count > 0:
            return
        for track_id, name, desc, prereqs, core in _DEFAULT_TRACKS:
            con.execute(
                """INSERT OR IGNORE INTO Tracks
                   (track_id, name, description, prerequisites_json, core_courses_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (track_id, name, desc, json.dumps(prereqs), json.dumps(core)),
            )


_ensure_tracks_seeded()


# ---------------------------------------------------------------------------
# READ — Students / Courses / Grades / Attendance
# ---------------------------------------------------------------------------

def get_student(student_id: int) -> Optional[dict[str, Any]]:
    with _conn() as con:
        row = con.execute(
            "SELECT student_id, name, email, level FROM Students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    return _row(row)


def get_course_id_by_title(title: str) -> Optional[int]:
    with _conn() as con:
        row = con.execute("SELECT course_id FROM Courses WHERE title = ?", (title,)).fetchone()
    return row["course_id"] if row else None


def get_student_grades(student_id: int) -> dict[str, float]:
    """Per-course grade percentage (average across that course's graded
    assignments), keyed by Courses.title so it lines up 1:1 with
    Tracks.prerequisites_json / core_courses_json course names."""
    with _conn() as con:
        rows = con.execute(
            """SELECT c.title AS course, AVG(g.score * 100.0 / a.max_score) AS pct
               FROM Grades g
               JOIN Assignments a USING (assignment_id)
               JOIN Courses c USING (course_id)
               WHERE g.student_id = ?
               GROUP BY c.title""",
            (student_id,),
        ).fetchall()
    return {r["course"]: round(r["pct"], 1) for r in rows}


def get_student_attendance(student_id: int) -> dict[str, float]:
    with _conn() as con:
        rows = con.execute(
            """SELECT c.title AS course, a.percentage AS pct
               FROM Attendance a
               JOIN Courses c USING (course_id)
               WHERE a.student_id = ?""",
            (student_id,),
        ).fetchall()
    return {r["course"]: r["pct"] for r in rows}


# ---------------------------------------------------------------------------
# READ/WRITE — Tracks
# ---------------------------------------------------------------------------

def list_track_names() -> list[str]:
    with _conn() as con:
        rows = con.execute("SELECT name FROM Tracks ORDER BY track_id").fetchall()
    return [r["name"] for r in rows]


def get_track_row(track_name: str) -> Optional[dict[str, Any]]:
    with _conn() as con:
        row = con.execute(
            "SELECT track_id, name, description, prerequisites_json, core_courses_json "
            "FROM Tracks WHERE name = ?",
            (track_name,),
        ).fetchone()
    return _row(row)


# ---------------------------------------------------------------------------
# WRITE — TrackRecommendations
# ---------------------------------------------------------------------------

def create_recommendation(student_id: int) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO TrackRecommendations (student_id, status) VALUES (?, 'pending')",
            (student_id,),
        )
    return cur.lastrowid


def update_recommendation(recommendation_id: int, status: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE TrackRecommendations SET status = ? WHERE recommendation_id = ?",
            (status, recommendation_id),
        )


def finalize_recommendation(
    recommendation_id: int,
    final_track: str,
    runner_up_track: Optional[str],
    final_score: float,
    advisor_decision: Optional[str],
    decided_by: str,
) -> None:
    with _conn() as con:
        con.execute(
            """UPDATE TrackRecommendations
               SET recommended_track = ?, runner_up_track = ?, confidence = ?,
                   advisor_decision = ?, decided_by = ?, status = 'completed',
                   decided_at = ?
               WHERE recommendation_id = ?""",
            (final_track, runner_up_track, final_score, advisor_decision,
             decided_by, _now(), recommendation_id),
        )


# ---------------------------------------------------------------------------
# WRITE — DiagnosticAssessments
# ---------------------------------------------------------------------------

def create_diagnostic(recommendation_id: int, student_id: int, subject: str, trigger: str) -> int:
    """One row per assessment ATTEMPT (never overwritten) — trigger
    distinguishes the missing-data diagnostic from an advisor-requested
    targeted assessment, so both stay queryable as separate evidence."""
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO DiagnosticAssessments
               (recommendation_id, student_id, subject, trigger, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (recommendation_id, student_id, subject, trigger),
        )
    return cur.lastrowid


def complete_diagnostic(assessment_id: int, score: float) -> None:
    with _conn() as con:
        con.execute(
            """UPDATE DiagnosticAssessments
               SET score = ?, status = 'completed', completed_at = ?
               WHERE assessment_id = ?""",
            (score, _now(), assessment_id),
        )


def get_diagnostics_for_subject(recommendation_id: int, subject: str) -> list[dict[str, Any]]:
    """All prior assessment attempts (any trigger) for this subject, on
    this recommendation run — used to report `prior_evidence_count`
    without ever discarding earlier results."""
    with _conn() as con:
        rows = con.execute(
            """SELECT assessment_id, subject, trigger, score, status, created_at, completed_at
               FROM DiagnosticAssessments
               WHERE recommendation_id = ? AND subject = ?
               ORDER BY assessment_id""",
            (recommendation_id, subject),
        ).fetchall()
    return _rows(rows)


def get_diagnostic(assessment_id: int) -> Optional[dict[str, Any]]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM DiagnosticAssessments WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchone()
    return _row(row)


# ---------------------------------------------------------------------------
# WRITE — Tickets (RAG document-validation failure path)
# ---------------------------------------------------------------------------

def open_ticket(source_id: int, thread_id: str, failure_type: str, details: str) -> int:
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO Tickets (source_graph, source_id, thread_id, failure_type, status, details)
               VALUES ('track_recommendation', ?, ?, ?, 'open', ?)""",
            (source_id, thread_id, failure_type, details),
        )
    return cur.lastrowid


def resolve_ticket(ticket_id: int) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE Tickets SET status = 'resolved', resolved_at = ? WHERE ticket_id = ?",
            (_now(), ticket_id),
        )


def get_ticket(ticket_id: int) -> Optional[dict[str, Any]]:
    with _conn() as con:
        row = con.execute("SELECT * FROM Tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    return _row(row)


# ---------------------------------------------------------------------------
# READ — Adaptive Assessment session results (cross-subsystem read only;
# writes to AssessmentSessions/AssessmentAnswers stay owned by
# state_graph/adaptive_assessment — see diagnostics integration notes in
# nodes_intake.py / nodes_hitl.py).
# ---------------------------------------------------------------------------

def get_adaptive_session_result(session_id: int) -> Optional[dict[str, Any]]:
    with _conn() as con:
        row = con.execute(
            "SELECT session_id, status, final_score, mastery_level "
            "FROM AssessmentSessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return _row(row)