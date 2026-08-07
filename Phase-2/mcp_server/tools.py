"""
tools.py
========
All tool implementations for the Brightpeak Academy MCP server.

Read-only tools are registered immediately; write tools are NOT
registered at startup — authenticate_staff in server.py adds them
at runtime after role escalation and fires tools/list_changed.

Concerns addressed here:
  - Defensive tool design   (server-side validation via validation.py)
  - Elicitation             (grade overrides + late withdrawals)
  - Sampling                (generate_academic_advisory)
  - Progress tracking       (generate_course_report via notifications.py)
"""

import asyncio
from typing import Any

import sys
from pathlib import Path

# Make the sibling `rag/` package importable from mcp_server/
RAG_DIR = Path(__file__).resolve().parent.parent / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from rag_tool import search_policies as rag_search_policies  # noqa: E402

from mcp.server.fastmcp import Context

import database as db
import roles
from auth import client_supports_elicitation, client_supports_sampling
from notifications import report_progress
from schemas import GradeOverrideConfirmation, WithdrawalConfirmation
from validation import (
    is_large_override,
    scholarship_would_change,
    validate_enrollment_status,
    validate_percentage,
    validate_score,
)


# =======================================================================
# READ-ONLY TOOLS
# Registered by register_readonly_tools(mcp) — available to every role,
# including unauthenticated front-desk sessions.
# =======================================================================

def register_readonly_tools(mcp) -> None:
    """Attach all read-only tool endpoints to `mcp`."""

    @mcp.tool()
    def get_student_profile(student_id: int) -> dict[str, Any]:
        """Look up a student's profile (name, email, level).

        Args:
            student_id: the student's numeric ID.
        """
        student = db.get_student(student_id)
        if student is None:
            return {"error": f"No student with id {student_id}"}
        return student

    @mcp.tool()
    def get_student_enrollments(
        student_id: int, course_id: int | None = None
    ) -> dict[str, Any]:
        """List a student's course enrollments and progress, optionally
        filtered to one course.

        Args:
            student_id: the student's numeric ID.
            course_id: optional course ID to filter to a single enrollment.
        """
        return {"enrollments": db.get_enrollments(student_id, course_id)}

    @mcp.tool()
    def get_student_attendance(
        student_id: int, course_id: int | None = None
    ) -> dict[str, Any]:
        """Get a student's attendance percentage, optionally filtered to one course.

        Args:
            student_id: the student's numeric ID.
            course_id: optional course ID to filter to a single course.
        """
        return {"attendance": db.get_attendance(student_id, course_id)}

    @mcp.tool()
    def get_student_grades(
        student_id: int, course_id: int | None = None
    ) -> dict[str, Any]:
        """Get a student's grades, optionally filtered to one course, plus
        their overall average across all graded assignments.

        Args:
            student_id: the student's numeric ID.
            course_id: optional course ID to filter to a single course.
        """
        grades = db.get_grades(student_id, course_id)
        avg = db.get_overall_average(student_id)
        return {"grades": grades, "overall_average": avg}

    @mcp.tool()
    def search_policies(
        query: str,
        architecture: str = "auto",
        category: str | None = None,
    ) -> dict[str, Any]:
        """Search Brightpeak policy documents (attendance, scholarship,
        academic integrity, late submission, withdrawal, exams) using RAG
        retrieval with Self-RAG verification before returning an answer.

        Args:
            query: the policy question to answer.
            architecture: "auto" | "naive" | "hybrid" | "agentic" | "graph".
            category: optional category filter, e.g. "Attendance".
        """
        return rag_search_policies(query, architecture=architecture, category=category)

    # -------------------------------------------------------------------
    # === CONCERN: Sampling ===
    # Reasoning over multiple raw facts (grades, attendance, enrollment)
    # to write a coherent narrative is a job for the CLIENT's model via
    # sampling/createMessage, not a canned template.  Degrades gracefully
    # if the client didn't declare sampling support.
    # -------------------------------------------------------------------

    @mcp.tool()
    async def generate_academic_advisory(
        student_id: int, ctx: Context
    ) -> dict[str, Any]:
        """Generate a short, personalised academic advisory note for a
        student by combining their grades, attendance, and enrollment
        status.  Uses the connected client's model (sampling).

        Args:
            student_id: the student's numeric ID.
        """
        student = db.get_student(student_id)
        if student is None:
            return {"error": f"No student with id {student_id}"}

        facts = {
            "student": student,
            "enrollments": db.get_enrollments(student_id),
            "attendance": db.get_attendance(student_id),
            "grades": db.get_grades(student_id),
            "overall_average": db.get_overall_average(student_id),
        }

        if not client_supports_sampling(ctx):
            # Graceful degradation: return raw facts instead of failing.
            return {
                "note": (
                    "Client does not support sampling; returning raw data "
                    "instead of a generated narrative."
                ),
                "facts": facts,
            }

        prompt = (
            "Write a short (3-4 sentence), encouraging academic advisory note for "
            f"a student advisor to send, based on this student data: {facts}. "
            "Mention attendance and grade trends factually, and one concrete "
            "suggestion. Do not invent facts not present in the data."
        )

        from mcp.types import SamplingMessage, TextContent

        result = await ctx.session.create_message(
            messages=[
                SamplingMessage(
                    role="user",
                    content=TextContent(type="text", text=prompt),
                )
            ],
            max_tokens=250,
        )
        narrative = (
            result.content.text
            if hasattr(result.content, "text")
            else str(result.content)
        )
        return {"advisory_note": narrative, "based_on": facts}

    # -------------------------------------------------------------------
    # === CONCERN: Progress tracking ===
    # generate_course_report walks every enrolled student; it reports real
    # intermediate progress rather than leaving the client blocked.
    # -------------------------------------------------------------------

    @mcp.tool()
    async def generate_course_report(
        course_id: int, ctx: Context
    ) -> dict[str, Any]:
        """Generate a full progress report for every student enrolled in a
        course (grades, attendance, enrollment status).  Reports progress
        as it goes because this can take a while for large courses.

        Args:
            course_id: the course's numeric ID.
        """
        course = db.get_course(course_id)
        if course is None:
            return {"error": f"No course with id {course_id}"}

        students = db.list_enrolled_students(course_id)
        total = len(students)
        report = []

        for i, s in enumerate(students, start=1):
            await report_progress(
                ctx,
                current=i,
                total=total,
                label=f"Processing {s['name']} ({i}/{total})",
            )
            grades = db.get_grades(s["student_id"], course_id)
            attendance = db.get_attendance(s["student_id"], course_id)
            report.append(
                {
                    "student_id": s["student_id"],
                    "name": s["name"],
                    "enrollment_status": s["status"],
                    "progress_pct": s["progress"],
                    "grades": grades,
                    "attendance": attendance,
                }
            )
            await asyncio.sleep(0.3)

        return {
            "course": course["title"],
            "student_count": total,
            "report": report,
        }


# =======================================================================
# WRITE TOOLS
# Not registered at startup.  authenticate_staff (server.py) calls
# get_write_tools() and passes the list to mcp.add_tool() after a
# successful role escalation.
# =======================================================================

def get_write_tools() -> list:
    """Return the write-tool callables so server.py can register them
    after authentication without importing private names directly."""
    return [
        _record_grade_impl,
        _update_attendance_impl,
        _change_enrollment_status_impl,
    ]


# -------------------------------------------------------------------
# === CONCERN: Defensive tool design + Elicitation ===
# _record_grade_impl re-validates score against the DB, re-derives
# course ownership from the DB (never trusts caller claims), and
# elicits confirmation when the change crosses the scholarship
# threshold or overrides an existing grade by > 15 points.
# -------------------------------------------------------------------

async def _record_grade_impl(
    student_id: int,
    assignment_id: int,
    score: float,
    ctx: Context,
) -> dict[str, Any]:
    """Record or update a student's grade on an assignment.

    Requires an authenticated instructor (own course) or registrar.

    Args:
        student_id: the student's numeric ID.
        assignment_id: the assignment's numeric ID.
        score: new score (validated server-side against assignment.max_score).
    """
    if roles.SESSION.role not in ("instructor", "registrar"):
        return {"error": "Not authorized. Authenticate as instructor or registrar first."}

    assignment = db.get_assignment(assignment_id)
    if assignment is None:
        return {"error": f"No assignment with id {assignment_id}"}

    course = db.get_course(assignment["course_id"])
    if not roles.can_grade_course(
        assignment["course_id"],
        course["instructor_id"] if course else None,
    ):
        return {"error": "Not authorized to grade this course."}

    # Server-side validation — independent of whatever the client sent.
    valid, err = validate_score(score, assignment_id)
    if not valid:
        return {"error": err}

    crosses, avg_before, avg_after = scholarship_would_change(
        student_id, assignment_id, score
    )
    large_override = is_large_override(student_id, assignment_id, score)

    if crosses or large_override:
        if not client_supports_elicitation(ctx):
            return {
                "error": (
                    "This change affects scholarship eligibility or overrides an "
                    "existing grade significantly and requires human confirmation, "
                    "but this client doesn't support elicitation. Have a registrar "
                    "confirm through a client that does."
                )
            }
        reason = (
            "crosses the scholarship eligibility threshold"
            if crosses
            else "overrides an existing grade by more than 15 points"
        )
        result = await ctx.elicit(
            message=(
                f"Recording this grade ({score}/{assignment['max_score']}) for "
                f"student {student_id} {reason} (average would go from "
                f"{avg_before:.1f}% to {avg_after:.1f}%). Confirm?"
            ),
            schema=GradeOverrideConfirmation,
        )
        if result.action != "accept" or not result.data.confirmed:
            return {"success": False, "message": "Grade change was not confirmed; no changes made."}

    db.upsert_grade(
        student_id, assignment_id, score, roles.SESSION.instructor_id or 0
    )
    return {
        "success": True,
        "student_id": student_id,
        "assignment_id": assignment_id,
        "score": score,
        "average_before": avg_before,
        "average_after": avg_after,
    }


async def _update_attendance_impl(
    student_id: int,
    course_id: int,
    percentage: float,
    ctx: Context,
) -> dict[str, Any]:
    """Update a student's attendance percentage for a course.

    Requires an authenticated instructor (own course) or registrar.

    Args:
        student_id: the student's numeric ID.
        course_id: the course's numeric ID.
        percentage: attendance percentage (0–100).
    """
    if roles.SESSION.role not in ("instructor", "registrar"):
        return {"error": "Not authorized. Authenticate as instructor or registrar first."}

    course = db.get_course(course_id)
    if course is None:
        return {"error": f"No course with id {course_id}"}
    if not roles.can_grade_course(course_id, course["instructor_id"]):
        return {"error": "Not authorized to update attendance for this course."}

    valid, err = validate_percentage(percentage)
    if not valid:
        return {"error": err}

    db.upsert_attendance(student_id, course_id, percentage)
    return {
        "success": True,
        "student_id": student_id,
        "course_id": course_id,
        "percentage": percentage,
    }


# -------------------------------------------------------------------
# === CONCERN: Elicitation ===
# Dropping a student outside the 14-day no-penalty window requires
# explicit human confirmation (Course Withdrawal Policy).
# -------------------------------------------------------------------

async def _change_enrollment_status_impl(
    student_id: int,
    course_id: int,
    status: str,
    ctx: Context,
) -> dict[str, Any]:
    """Change a student's enrollment status (active / completed / dropped).

    Requires an authenticated instructor (own course) or registrar.
    Dropping past the 14-day no-penalty window requires human confirmation.

    Args:
        student_id: the student's numeric ID.
        course_id: the course's numeric ID.
        status: one of 'active', 'completed', 'dropped'.
    """
    if roles.SESSION.role not in ("instructor", "registrar"):
        return {"error": "Not authorized. Authenticate as instructor or registrar first."}

    valid, err = validate_enrollment_status(status)
    if not valid:
        return {"error": err}

    course = db.get_course(course_id)
    if course is None:
        return {"error": f"No course with id {course_id}"}
    if not roles.can_grade_course(course_id, course["instructor_id"]):
        return {"error": "Not authorized to change enrollment status for this course."}

    enrollments = db.get_enrollments(student_id, course_id)
    if not enrollments:
        return {"error": "No such enrollment."}

    from datetime import date, datetime

    enrollment = enrollments[0]
    enrolled_on = datetime.strptime(enrollment["enrollment_date"], "%Y-%m-%d").date()
    days_enrolled = (date.today() - enrolled_on).days
    past_window = days_enrolled > 14

    if status == "dropped" and past_window:
        if not client_supports_elicitation(ctx):
            return {
                "error": (
                    "Dropping this student is past the no-penalty withdrawal window "
                    "and requires human confirmation, but this client doesn't support "
                    "elicitation."
                )
            }
        result = await ctx.elicit(
            message=(
                f"Student {student_id} enrolled {days_enrolled} days ago, past the "
                f"14-day no-penalty withdrawal window. Confirm marking as dropped "
                f"(this will be recorded as a penalised withdrawal)?"
            ),
            schema=WithdrawalConfirmation,
        )
        if result.action != "accept" or not result.data.confirmed:
            return {
                "success": False,
                "message": "Status change was not confirmed; no changes made.",
            }

    db.set_enrollment_status(student_id, course_id, status)
    return {
        "success": True,
        "student_id": student_id,
        "course_id": course_id,
        "status": status,
    }