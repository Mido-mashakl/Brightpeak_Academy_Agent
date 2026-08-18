import sqlite3
from pathlib import Path

from planning.algorithms.environment import Environment


DB_PATH = Path(__file__).resolve().parents[2] / "db" / "brightpeak.db"


def test_environment_reads_real_brightpeak_database():
    assert DB_PATH.exists()

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name FROM Students WHERE student_id = ?",
        (2,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "Farida Ibrahim"


def test_environment_validates_against_real_student_data():
    environment = Environment(db_path=DB_PATH)

    feedback = environment.evaluate(
        '{"student_id": 2, "decision": "eligible"}'
    )

    assert feedback.success is False
    assert "85.0%" in feedback.details[0]
    assert "not eligible" in feedback.details[0]


def test_environment_accepts_correct_real_database_decision():
    environment = Environment(db_path=DB_PATH)

    feedback = environment.evaluate(
        '{"student_id": 2, "decision": "not_eligible"}'
    )

    assert feedback.success is True