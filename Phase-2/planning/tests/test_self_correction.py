import json
import sqlite3
from pathlib import Path

import pytest

from planning.algorithms.environment import Environment
from planning.algorithms.reflexion import reflexion
from planning.algorithms.self_refine import reflect_and_refine


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


def state(student_id: int, decision: str) -> str:
    return json.dumps({"student_id": student_id, "decision": decision})


def test_self_refine_revises_a_wrong_decision(fixture_db):
    env = Environment(db_path=fixture_db)
    calls = {"revised": False}

    def llm_generate(task: str) -> str:
        return state(2, "eligible")

    def llm_revise(task: str, draft: str, feedback) -> str:
        assert feedback.success is False
        assert "70" in feedback.details[0]
        calls["revised"] = True
        return state(2, "not_eligible")

    result = reflect_and_refine(
        "Decide scholarship eligibility for student 2.",
        llm_generate,
        llm_revise,
        env,
    )

    assert result.revised is True
    assert calls["revised"] is True
    assert result.final == state(2, "not_eligible")
    assert result.feedback.success is True