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

AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from client import GeminiClient, load_gemini_config
_gemini = GeminiClient(load_gemini_config())
 
# Make the sibling `rag/` package importable from mcp_server/
RAG_DIR = Path(__file__).resolve().parent.parent / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))
 
from rag_tool import search_policies as rag_search_policies  # noqa: E402
from rag_tool import search_course_material as rag_search_course_material  # noqa: E402
 
from mcp.server.fastmcp import Context
 
import database as db
import roles
from auth import client_supports_elicitation, client_supports_sampling
from notifications import report_progress
from schemas import GradeOverrideConfirmation, WithdrawalConfirmation
from validation import (
    is_large_override,
    scholarship_would_change,
    validate_course_id,
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
    # === Teaching assistant: course-material listing + RAG search ===
    # Kept as two separate tools on purpose:
    #   - list_course_materials is cheap metadata (DB only) so the agent
    #     can show a student "here's what's available" without spending
    #     a retrieval call.
    #   - ask_course_material is the actual RAG-backed Q&A tool, scoped
    #     to one course_id so a student can never pull answers meant for
    #     another course's material.
    # -------------------------------------------------------------------
 
    @mcp.tool()
    def list_course_materials(course_id: int) -> dict[str, Any]:
        """List the study materials registered for a course (title,
        description, type — lecture/chapter/reading/exercise). Does not
        return material content; use ask_course_material for that.
 
        Args:
            course_id: the course's numeric ID.
        """
        ok, err = validate_course_id(course_id)
        if not ok:
            return {"error": err}
        return {
            "course_id": course_id,
            "materials": db.get_course_materials(course_id),
        }
 
    @mcp.tool()
    def ask_course_material(
        query: str,
        course_id: int,
        architecture: str = "auto",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Answer a student's question using a specific course's study
        material (lectures, chapters, readings, exercises), using RAG
        retrieval with Self-RAG verification before returning an answer.
 
        Retrieval is restricted to this course_id only, so a question
        about one course can never be answered with another course's
        material.
 
        Args:
            query: the student's question about the course content.
            course_id: the course whose material should be searched.
            architecture: "auto" | "naive" | "hybrid" | "agentic" | "graph".
            top_k: number of relevant passages to retrieve.
        """
        ok, err = validate_course_id(course_id)
        if not ok:
            return {"error": err}
        return rag_search_course_material(
            query=query,
            course_id=course_id,
            architecture=architecture,
            top_k=top_k,
        )
 


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




def classify_severity_with_policy(similarity_score, description, policy_context) -> tuple[str, str]:
    prompt = (
        f"You are assessing an academic integrity case.\n"
        f"Similarity score: {similarity_score}\n"
        f"Instructor description: {description}\n"
        f"Relevant policy:\n{policy_context}\n\n"
        f"Classify severity as exactly one word: minor, major, or severe. "
        f"Then on a new line, write a one-sentence rationale citing the policy.\n"
        f"Format:\nSEVERITY: <word>\nRATIONALE: <sentence>"
    )
    text = _gemini.generate(prompt)
    severity_line = next((l for l in text.splitlines() if l.upper().startswith("SEVERITY:")), "SEVERITY: minor")
    rationale_line = next((l for l in text.splitlines() if l.upper().startswith("RATIONALE:")), "RATIONALE: unavailable")
    severity = severity_line.split(":", 1)[1].strip().lower()
    if severity not in ("minor", "major", "severe"):
        severity = "minor"
    return severity, rationale_line.split(":", 1)[1].strip()


def generate_appeal_rulings(argument: str, evidence: list[str], n: int = 3) -> list[str]:
    prompt = (
        f"A student is appealing an academic integrity decision.\n"
        f"Student's argument: {argument}\n"
        f"Evidence on file: {evidence}\n\n"
        f"Generate exactly {n} distinct, plausible rulings a committee could reach "
        f"(e.g. uphold, dismiss, reduce penalty), each as one sentence. "
        f"Number them 1 to {n}, one per line."
    )
    text = _gemini.generate(prompt)
    lines = [l.split(".", 1)[-1].strip() for l in text.splitlines() if l.strip() and l.strip()[0].isdigit()]
    return lines[:n] if lines else [text.strip()]


def score_ruling_against_policy(ruling: str, rationale: str) -> float:
    prompt = (
        f"Ruling: {ruling}\n"
        f"Case severity rationale: {rationale}\n\n"
        f"On a scale of 0.0 to 1.0, how well-supported is this ruling given the "
        f"rationale? Reply with ONLY the number."
    )
    text = _gemini.generate(prompt).strip()
    try:
        return max(0.0, min(1.0, float(text)))
    except ValueError:
        return 0.5


# =======================================================================
# Adaptive Assessment & Mastery Evaluation — LLM-call additions
#   1. Task decomposition   -> decompose_and_pick_question()
#   2. Constrained ReAct    -> evaluate_answer_constrained_react()
# =======================================================================

def decompose_and_pick_question(
    topic: str, subskills_covered: list[str], current_difficulty: str, running_score: float,
) -> tuple[str, str, str, str, list[str]]:
    prompt = (
        f"You are building an adaptive quiz on the topic: {topic}\n"
        f"Subskills already tested: {subskills_covered or 'none yet'}\n"
        f"Student's running score so far: {running_score:.2f} (0.0-1.0)\n"
        f"Current difficulty band: {current_difficulty}\n\n"
        f"Step 1 - Decompose '{topic}' into the key subskills a student must "
        f"master (pick one NOT already tested).\n"
        f"Step 2 - Choose a difficulty (easy, medium, or hard).\n"
        f"Step 3 - Write ONE multiple-choice question testing that subskill, "
        f"with exactly 4 options.\n\n"
        f"Reply in exactly this format:\n"
        f"SUBSKILL: <short name>\nDIFFICULTY: <easy|medium|hard>\n"
        f"QUESTION: <question text>\nA: <option A>\nB: <option B>\n"
        f"C: <option C>\nD: <option D>\nCORRECT: <A|B|C|D>"
    )
    text = _gemini.generate(prompt)
    lines = {l.split(":", 1)[0].strip().upper(): l.split(":", 1)[1].strip()
             for l in text.splitlines() if ":" in l}
    subskill = lines.get("SUBSKILL", topic)
    difficulty = lines.get("DIFFICULTY", current_difficulty).lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = current_difficulty
    question = lines.get("QUESTION", f"Explain a key idea in {subskill}.")
    options = [lines.get(k, "") for k in ("A", "B", "C", "D")]
    correct_letter = lines.get("CORRECT", "A").strip().upper()
    return subskill, difficulty, question, correct_letter, options


def _decide_grading_action(question_text: str, difficulty: str) -> str:
    """Thought step: the LLM's ONLY job here is to pick one of exactly two
    whitelisted actions -- it does not grade anything in this call."""
    prompt = (
        f"Question ({difficulty}): {question_text}\n\n"
        f"Pick exactly one action:\n"
        f"  GRADE_EXACT - the question has one clearly correct short answer "
        f"(a number, a keyword, a short fact) that can be checked directly.\n"
        f"  GRADE_JUDGE - the question needs free-text judgement.\n\n"
        f"Reply with ONLY the action name, nothing else."
    )
    text = _gemini.generate(prompt).strip().upper()
    return "GRADE_EXACT" if "EXACT" in text else "GRADE_JUDGE"


def _normalize_mcq_answer(answer: str) -> str:
    """'A', 'a', 'A)', ' A.' etc all collapse to a bare 'A'. Only strips a
    single leading MCQ letter -- does NOT do substring matching, so a full
    option string like 'Declares a variable' does not collapse to 'A'
    just because it contains the letter."""
    cleaned = (answer or "").strip().upper().rstrip(").:")
    return cleaned


def _grade_exact(student_answer: str, expected_answer: str) -> tuple[bool, float, str]:
    """Action #1: pure Python, NO LLM call. Real EXACT comparison against
    the expected_answer select_next_question generated alongside the
    question. Fixed after review: this used to check substring containment
    (`norm_expected in norm_student`), which meant almost any free-text
    answer counted as correct once expected_answer became a single MCQ
    letter (e.g. 'Declares a variable' contains the letter 'a' and used to
    score as correct against expected_answer='A'). MCQ answers must match
    the letter exactly."""
    norm_student = _normalize_mcq_answer(student_answer)
    norm_expected = _normalize_mcq_answer(expected_answer)
    correct = bool(norm_expected) and norm_student == norm_expected
    score = 1.0 if correct else 0.0
    rationale = f"Compared directly against expected answer '{expected_answer}'."
    return correct, score, rationale


def _grade_judge(
    question_text: str, difficulty: str, student_answer: str, options: list[str] | None = None
) -> tuple[bool, float, str]:
    """Action #2: the one LLM call allowed for actual grading judgement.
    Fixed after review: every question is MCQ now (decompose_and_pick_question
    always generates 4 options + a correct letter), but this function used to
    receive only question_text -- never the options themselves. If
    _decide_grading_action ever routed an MCQ question here (it has no way
    to know it's MCQ), the LLM would be asked to judge a bare letter like
    "A" with zero context on what A/B/C/D meant. Now the options are always
    passed through and included in the prompt so this path can never judge
    blind, even though GRADE_EXACT is the expected route for MCQ answers."""
    options_block = ""
    if options:
        labeled = "\n".join(f"{letter}: {text}" for letter, text in zip("ABCD", options))
        options_block = f"Options:\n{labeled}\n\n"
    prompt = (
        f"Question ({difficulty}): {question_text}\n"
        f"{options_block}"
        f"Student's answer: {student_answer}\n\n"
        f"Judge this answer.\n"
        f"CORRECT: <yes|no>\nSCORE: <0.0-1.0>\nRATIONALE: <one sentence>"
    )
    text = _gemini.generate(prompt)
    lines = {l.split(":", 1)[0].strip().upper(): l.split(":", 1)[1].strip()
             for l in text.splitlines() if ":" in l}
    correct = lines.get("CORRECT", "no").lower().startswith("y")
    try:
        score = max(0.0, min(1.0, float(lines.get("SCORE", "0.0"))))
    except ValueError:
        score = 1.0 if correct else 0.0
    rationale = lines.get("RATIONALE", "No rationale returned.")
    return correct, score, rationale


def evaluate_answer_constrained_react(
    question_text: str, difficulty: str, student_answer: str,
    expected_answer: str = "", options: list[str] | None = None,
) -> tuple[bool, float, str]:
    """Constrained ReAct: Thought (_decide_grading_action) picks ONE of
    exactly two whitelisted actions; a real PYTHON dispatcher -- not the
    LLM narrating a format -- then calls the matching function. Hard-capped
    at 2 LLM calls total: one to decide, at most one more to judge.
    GRADE_EXACT makes zero further LLM calls.

    `options` param added after review: threaded through so the
    GRADE_JUDGE fallback is never blind on an MCQ question (see
    _grade_judge's docstring)."""
    action = _decide_grading_action(question_text, difficulty)
    if action == "GRADE_EXACT" and expected_answer:
        return _grade_exact(student_answer, expected_answer)
    return _grade_judge(question_text, difficulty, student_answer, options=options)