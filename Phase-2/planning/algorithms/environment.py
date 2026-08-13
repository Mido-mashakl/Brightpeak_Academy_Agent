"""Replaces the random evaluator with a real check against the Brightpeak DB.

Checks a scholarship-eligibility decision against Policies.policy_id = 2
("Scholarship Policy"): students with an overall average above 90% are
eligible.

Expected `state` format (JSON somewhere in the text):
    {"student_id": 7, "decision": "eligible"}
    {"student_id": 7, "decision": "not_eligible"}
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from ..models import EnvironmentFeedback

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "brightpeak.db"

SCHOLARSHIP_POLICY_ID = 2
SCHOLARSHIP_MIN_AVERAGE = 90.0


class Environment:
    def __init__(self, db_path: Path | str = _DEFAULT_DB_PATH):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_student(self, conn: sqlite3.Connection, student_id: int) -> dict | None:
        row = conn.execute(
            "SELECT student_id, name FROM Students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        return dict(row) if row else None

    def _get_overall_average(
        self, conn: sqlite3.Connection, student_id: int
    ) -> float | None:
        row = conn.execute(
            """
            SELECT ROUND(AVG(g.score * 100.0 / a.max_score), 1) AS avg_pct
            FROM Grades g
            JOIN Assignments a USING (assignment_id)
            WHERE g.student_id = ?
            """,
            (student_id,),
        ).fetchone()
        return row["avg_pct"] if row and row["avg_pct"] is not None else None

    def _extract_json(self, state: str) -> dict | None:
        match = re.search(r"\{.*\}", state, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def evaluate(self, state: str) -> EnvironmentFeedback:
        payload = self._extract_json(state)
        if payload is None:
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["Could not find a JSON object with 'student_id' and 'decision'."],
            )

        student_id = payload.get("student_id")
        decision = payload.get("decision")

        if not isinstance(student_id, int):
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["'student_id' is missing or not an integer."],
            )
        if decision not in ("eligible", "not_eligible"):
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["'decision' must be 'eligible' or 'not_eligible'."],
            )

        conn = self._connect()
        try:
            student = self._get_student(conn, student_id)
            if student is None:
                return EnvironmentFeedback(
                    success=False,
                    score=0.0,
                    details=[f"student_id {student_id} does not exist in Students."],
                )

            average = self._get_overall_average(conn, student_id)
            if average is None:
                return EnvironmentFeedback(
                    success=False,
                    score=0.0,
                    details=[f"student_id {student_id} has no recorded grades."],
                )

            actual_eligible = average > SCHOLARSHIP_MIN_AVERAGE
            claimed_eligible = decision == "eligible"

            if actual_eligible == claimed_eligible:
                return EnvironmentFeedback(
                    success=True,
                    score=1.0,
                    details=[
                        f"{student['name']}'s average is {average}%, threshold is "
                        f">{SCHOLARSHIP_MIN_AVERAGE}%. Decision '{decision}' matches the DB."
                    ],
                )

            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=[
                    f"{student['name']}'s average is {average}%, threshold is "
                    f">{SCHOLARSHIP_MIN_AVERAGE}%. Decision was '{decision}' but the DB says "
                    f"{'eligible' if actual_eligible else 'not eligible'}."
                ],
            )
        finally:
            conn.close()