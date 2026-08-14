import json
import sqlite3

from planning.algorithms.environment import Environment
from planning.algorithms.reflexion import reflexion


def create_test_db(path):
    conn = sqlite3.connect(path)

    conn.executescript(
        """
        CREATE TABLE Students (
            student_id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            level TEXT
        );

        CREATE TABLE Assignments (
            assignment_id INTEGER PRIMARY KEY,
            course_id INTEGER,
            title TEXT,
            deadline TEXT,
            max_score INTEGER
        );

        CREATE TABLE Grades (
            grade_id INTEGER PRIMARY KEY,
            student_id INTEGER,
            assignment_id INTEGER,
            score REAL,
            graded_by INTEGER
        );

        INSERT INTO Students VALUES
        (2, 'Test Student', 'test@brightpeak.test', 'Intermediate');

        INSERT INTO Assignments VALUES
        (1, 1, 'Assignment 1', '2026-01-01', 100),
        (2, 1, 'Assignment 2', '2026-02-01', 100);

        INSERT INTO Grades VALUES
        (1, 2, 1, 70, NULL),
        (2, 2, 2, 70, NULL);
        """
    )

    conn.commit()
    conn.close()


def test_reflexion_carries_reflection_to_next_trial(tmp_path):
    db_path = tmp_path / "test_brightpeak.db"
    create_test_db(db_path)

    environment = Environment(db_path=db_path)
    seen_memories = []

    def llm_act(task, memories):
        seen_memories.append(list(memories))

        if memories:
            return json.dumps({
                "student_id": 2,
                "decision": "not_eligible"
            })

        return json.dumps({
            "student_id": 2,
            "decision": "eligible"
        })

    def llm_reflect(task, state, feedback):
        assert feedback.success is False
        return "Verify the student's average before deciding scholarship eligibility."

    result = reflexion(
        task="Decide scholarship eligibility for student 2.",
        llm_act=llm_act,
        llm_reflect=llm_reflect,
        environment=environment,
        max_trials=3,
        memory_size=2,
    )

    assert result.success is True
    assert result.trials == 2
    assert seen_memories[0] == []
    assert seen_memories[1] == [
        "Verify the student's average before deciding scholarship eligibility."
    ]
    assert json.loads(result.final_state)["decision"] == "not_eligible"