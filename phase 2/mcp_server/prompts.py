"""
prompts.py
==========
=== CONCERN: Prompts ===
Reusable, parameterised starting points for common staff tasks.
Registering them as @mcp.prompt() exposes them through prompts/list +
prompts/get, so every client gets the same carefully-worded instructions
without copy-pasting prompt text.

Usage in server.py:

    from prompts import register_prompts
    register_prompts(mcp)
"""

from __future__ import annotations


def register_prompts(mcp) -> None:
    """Attach all prompt endpoints to `mcp`.

    Called once from server.py after the FastMCP instance is created.
    """

    @mcp.prompt()
    def draft_attendance_warning(student_id: int, course_id: int) -> str:
        """Draft an attendance warning email for a student in a specific course."""
        return (
            f"Draft a polite but clear attendance warning email to student #{student_id} "
            f"for course #{course_id}. Look up their current attendance percentage and "
            f"the Attendance Policy resource, reference the specific percentage and the "
            f"75% threshold, and explain what happens if it doesn't improve."
        )

    @mcp.prompt()
    def explain_scholarship_eligibility(student_id: int) -> str:
        """Draft an explanation of a student's scholarship eligibility status."""
        return (
            f"Look up student #{student_id}'s overall grade average and the Scholarship "
            f"Policy resource, then explain clearly whether they currently qualify for "
            f"the merit scholarship and, if not, how many percentage points they need."
        )