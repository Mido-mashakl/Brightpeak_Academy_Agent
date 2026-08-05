"""
Brightpeak Academy - Memory System Extension
==============================================
Scratchpad
----------

Why this file exists as its own module (not a dict inside ShortTermMemory):

`short_term.py` is allowed to evict/prune messages whenever the rolling
buffer overflows. If the scratchpad lived inside the same object as the
message list, it would be extremely easy for a future refactor (or a bug)
to accidentally prune it along with everything else. Keeping it as a
separate class with its own explicit API means pruning code physically
cannot reach it -- there is no shared container to iterate over by mistake.

Concrete Brightpeak scenario this protects:
    An instructor asks the agent to check scholarship eligibility for a
    whole course roster. The agent sets:
        plan = "scholarship eligibility sweep for course 3"
        current_subgoal = "checking student 14 of 22"
    It then calls get_student_attendance, get_student_grades,
    get_student_enrollments for student after student -- each call adds a
    tool-result message to short-term memory. By student 12, the rolling
    buffer (max_turns=10) has already evicted the very message where the
    plan was set. Without a scratchpad, the agent would forget what it
    was doing and which student it was on. With a scratchpad, `plan` and
    `current_subgoal` are read from here on every step, independent of
    whatever survived pruning in the transcript.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class ScratchpadSnapshot:
    """Read-only copy of scratchpad state at a point in time, used for
    evidence logs and tests -- so we can prove the scratchpad survived a
    buffer eviction without exposing the live mutable object.
    """

    plan: Optional[str]
    current_subgoal: Optional[str]
    working_state: dict
    updated_at: str


class Scratchpad:
    """The agent's current working state: plan, sub-goal, and temporary
    variables. This is NOT conversation history -- it represents what the
    agent is doing right now, and it is never subject to the short-term
    memory eviction policy.
    """

    def __init__(self) -> None:
        self._plan: Optional[str] = None
        self._current_subgoal: Optional[str] = None
        self._working_state: dict[str, Any] = {}
        self._updated_at: str = self._now()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Plan / sub-goal
    # ------------------------------------------------------------------
    def update_plan(self, plan: str, subgoal: Optional[str] = None) -> None:
        if not plan or not plan.strip():
            raise ValueError("plan must be a non-empty string")
        self._plan = plan
        if subgoal is not None:
            self._current_subgoal = subgoal
        self._updated_at = self._now()

    def update_subgoal(self, subgoal: str) -> None:
        if not subgoal or not subgoal.strip():
            raise ValueError("subgoal must be a non-empty string")
        self._current_subgoal = subgoal
        self._updated_at = self._now()

    @property
    def plan(self) -> Optional[str]:
        return self._plan

    @property
    def current_subgoal(self) -> Optional[str]:
        return self._current_subgoal

    # ------------------------------------------------------------------
    # Arbitrary temporary working variables
    # (e.g. "students_checked": [14, 15], "roster_total": 22)
    # ------------------------------------------------------------------
    def set_var(self, key: str, value: Any) -> None:
        self._working_state[key] = value
        self._updated_at = self._now()

    def get_var(self, key: str, default: Any = None) -> Any:
        return self._working_state.get(key, default)

    def clear(self) -> None:
        """Explicit reset, called only when a task genuinely finishes --
        never called implicitly by short-term memory pruning.
        """
        self._plan = None
        self._current_subgoal = None
        self._working_state = {}
        self._updated_at = self._now()

    def snapshot(self) -> ScratchpadSnapshot:
        return ScratchpadSnapshot(
            plan=self._plan,
            current_subgoal=self._current_subgoal,
            working_state=dict(self._working_state),
            updated_at=self._updated_at,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Scratchpad(plan={self._plan!r}, "
            f"current_subgoal={self._current_subgoal!r}, "
            f"working_state={self._working_state!r})"
        )