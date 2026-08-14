"""Self-Refine: one draft, one critique against an explicit rubric, one revision.

Adapted from the toolkit's algorithms/self_refine.py for Brightpeak's
scholarship-eligibility sub-task.

Grounded critique: `deterministic_checks` reuses the real Environment
(Students/Grades/Policies in brightpeak.db) instead of asking the model
whether it is happy with its own decision text. That is the swap the lab
asks for: an LLM grading its own "eligible"/"not_eligible" call would
happily agree with a wrong average; the DB won't.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..algorithms.environment import Environment
from ..models import EnvironmentFeedback


@dataclass
class RefinementResult:
    draft: str
    final: str
    feedback: EnvironmentFeedback
    revised: bool


def deterministic_checks(state: str, environment: Environment) -> EnvironmentFeedback:
    """Grounded critique for the eligibility sub-task: run the same check
    LATS/Reflexion use, rather than a self-judgment."""
    return environment.evaluate(state)


def reflect_and_refine(
    task: str,
    llm_generate: Callable[[str], str],
    llm_revise: Callable[[str, str, EnvironmentFeedback], str],
    environment: Environment,
) -> RefinementResult:
    """Generate one draft, critique it once, revise once if it failed.

    llm_generate(task) -> draft state text (must embed {"student_id":..,"decision":..})
    llm_revise(task, draft, feedback) -> revised state text
    """
    draft = llm_generate(task)
    feedback = deterministic_checks(draft, environment)

    if feedback.success:
        return RefinementResult(draft=draft, final=draft, feedback=feedback, revised=False)

    revised = llm_revise(task, draft, feedback)
    final_feedback = deterministic_checks(revised, environment)
    return RefinementResult(draft=draft, final=revised, feedback=final_feedback, revised=True)