"""Reflexion: retry the whole task across trials, carrying a capped
episodic buffer of verbal reflections from prior failed trials.

Adapted from the toolkit's algorithms/reflexion.py for Brightpeak's
scholarship-eligibility sub-task. Reward is grounded: outcome comes from
Environment.evaluate() against Students/Grades/Policies, not the model's
own opinion, so a fluent-but-wrong "eligible" call cannot pass itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..algorithms.environment import Environment
from ..models import EnvironmentFeedback


@dataclass
class ReflexionResult:
    success: bool
    trials: int
    final_state: str
    feedback: EnvironmentFeedback
    memory: list[str] = field(default_factory=list)


def reflexion(
    task: str,
    llm_act: Callable[[str, list[str]], str],
    llm_reflect: Callable[[str, str, EnvironmentFeedback], str],
    environment: Environment,
    max_trials: int = 3,
    memory_size: int = 3,
) -> ReflexionResult:
    """llm_act(task, past_reflections) -> state text for this trial
    llm_reflect(task, state, feedback) -> one verbal lesson to remember
    """
    memory: list[str] = []
    state = ""
    feedback: EnvironmentFeedback | None = None

    for trial in range(max_trials):
        state = llm_act(task, memory[-memory_size:])
        feedback = environment.evaluate(state)
        if feedback.success:
            return ReflexionResult(
                success=True, trials=trial + 1, final_state=state,
                feedback=feedback, memory=memory,
            )
        memory.append(llm_reflect(task, state, feedback))

    return ReflexionResult(
        success=False, trials=max_trials, final_state=state,
        feedback=feedback, memory=memory,
    )