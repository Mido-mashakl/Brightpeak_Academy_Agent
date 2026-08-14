"""Tests for the grounded Environment. Uses a throwaway SQLite db with
known values so results are deterministic, independent of the real seed data.

Run: pytest tests/test_environment.py -v
"""

import json
import sqlite3
from pathlib import Path

import pytest

from planning.algorithms.environment import Environment, SCHOLARSHIP_MIN_AVERAGE


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_brightpeak.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE Students (
            student_id INTEGER PRIMARY KEY, name TEXT, email TEXT, level TEXT
        );
        CREATE TABLE Assignments (
            assignment_id INTEGER PRIMARY KEY, course_id INTEGER,
            title TEXT, deadline TEXT, max_score INTEGER
        );
        CREATE TABLE Grades (
            grade_id INTEGER PRIMARY KEY, student_id INTEGER,
            assignment_id INTEGER, score REAL, graded_by INTEGER
        );

        INSERT INTO Students VALUES (1, 'High Achiever', 'a@brightpeak.test', 'Advanced');
        INSERT INTO Students VALUES (2, 'Average Student', 'b@brightpeak.test', 'Intermediate');
        INSERT INTO Students VALUES (3, 'No Grades Yet', 'c@brightpeak.test', 'Beginner');

        INSERT INTO Assignments VALUES (1, 1, 'Assignment 1', '2026-01-01', 100);
        INSERT INTO Assignments VALUES (2, 1, 'Assignment 2', '2026-02-01', 100);

        INSERT INTO Grades VALUES (1, 1, 1, 95, NULL);
        INSERT INTO Grades VALUES (2, 1, 2, 95, NULL);

        INSERT INTO Grades VALUES (3, 2, 1, 70, NULL);
        INSERT INTO Grades VALUES (4, 2, 2, 70, NULL);
        """
    )
    conn.commit()
    conn.close()
    return db_path


def _state(student_id: int, decision: str) -> str:
    return json.dumps({"student_id": student_id, "decision": decision})


def test_correct_eligible_decision_passes(fixture_db):
    env = Environment(db_path=fixture_db)
    feedback = env.evaluate(_state(1, "eligible"))
    assert feedback.success is True
    assert feedback.score == 1.0


def test_correct_not_eligible_decision_passes(fixture_db):
    env = Environment(db_path=fixture_db)
    feedback = env.evaluate(_state(2, "not_eligible"))
    assert feedback.success is True


def test_wrong_decision_fails_and_explains_why(fixture_db):
    # An ungrounded self-critique would miss this: the text looks fine but
    # is factually wrong according to the database.
    env = Environment(db_path=fixture_db)
    feedback = env.evaluate(_state(2, "eligible"))
    assert feedback.success is False
    assert "70" in feedback.details[0]
    assert SCHOLARSHIP_MIN_AVERAGE == 90.0


def test_unknown_student_fails(fixture_db):
    env = Environment(db_path=fixture_db)
    feedback = env.evaluate(_state(999, "eligible"))
    assert feedback.success is False
    assert "does not exist" in feedback.details[0]


def test_student_with_no_grades_fails(fixture_db):
    env = Environment(db_path=fixture_db)
    feedback = env.evaluate(_state(3, "eligible"))
    assert feedback.success is False
    assert "no recorded grades" in feedback.details[0]


def test_malformed_state_fails_gracefully(fixture_db):
    env = Environment(db_path=fixture_db)
    feedback = env.evaluate("The student seems eligible, roughly.")
    assert feedback.success is False