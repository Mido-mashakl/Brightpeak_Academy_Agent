"""
Brightpeak Academy - Memory System Extension
==============================================
Promote-or-Drop Router
------------------------

Fires exactly once, every time `ShortTermMemory.add()` evicts a message
(see memory/short_term.py). For that evicted item, decides one of two
outcomes ONLY:

    - forget    -> nothing kept, gone for good
    - episodic  -> written to the episodic store as a timestamped event

This router NEVER writes to semantic memory. That is enforced twice:
  1. Structurally  -- `Destination` only has two values, "forget" and
     "episodic". There is no third option to accidentally reach for.
  2. By design      -- semantic facts are only ever produced later, by a
     separate, periodic consolidation pass over the episodic store
     (memory/consolidation.py, a later issue). The router has no
     reference to a semantic store at all, so it physically cannot
     write to one.

Why a pluggable decision function instead of hard-wiring an LLM call:
This module needs to be testable standalone, deterministically, with no
network access and no API key (see test_router.py). The default decision
function below is a transparent, rule-based heuristic tuned to real
Brightpeak advisory events (scholarship flags, attendance warnings,
grade-eligibility outcomes vs. small talk / routine tool acks). When the
agent is wired up in the integration issue, this default gets swapped
for an LLM-backed function with the exact same signature (see the
`ROUTING_PROMPT` pattern from the course slides) -- nothing else in this
file changes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from short_term import Message  # noqa: E402

Destination = Literal["forget", "episodic"]

# Keywords that signal a message describes a specific, meaningful event
# worth remembering long-term for a student/instructor (vs. routine
# chatter or a tool ack that carries no lasting information).
_EPISODIC_SIGNAL_KEYWORDS = (
    "flag", "flagged", "warning", "ineligible", "eligible", "eligibility",
    "dropped", "withdrawal", "below", "threshold", "scholarship",
    "declined", "confirmed", "penicillin", "exemption", "violation",
    "probation", "risk",
)


@dataclass
class MemoryRoutingDecision:
    """The router's output for a single evicted message. `reasoning` is
    mandatory and always populated -- this is the "visible reasoning a
    grader can see" the lab requires, not an implicit if/else buried in
    control flow.
    """

    destination: Destination
    reasoning: str
    source_message: Message
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Only meaningful when destination == "episodic"
    event_summary: Optional[str] = None
    context: Optional[str] = None
    outcome: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "reasoning": self.reasoning,
            "decided_at": self.decided_at,
            "event_summary": self.event_summary,
            "context": self.context,
            "outcome": self.outcome,
            "source_message": self.source_message.to_dict(),
        }


DecisionFn = Callable[[Message], MemoryRoutingDecision]


def default_decision_fn(message: Message) -> MemoryRoutingDecision:
    """Rule-based default. Deterministic and dependency-free on purpose
    (see module docstring) so router.py is testable in complete
    isolation. Swapped for an LLM call during agent integration.
    """
    text = message.content.lower()

    hit = next((kw for kw in _EPISODIC_SIGNAL_KEYWORDS if kw in text), None)

    if hit is not None:
        return MemoryRoutingDecision(
            destination="episodic",
            reasoning=(
                f"Message contains signal keyword '{hit}', indicating a specific, "
                f"consequential event (not routine chatter) worth recording with "
                f"its context for future advisory sessions."
            ),
            source_message=message,
            event_summary=message.content.strip(),
            context=f"role={message.role}, msg_type={message.msg_type}",
            outcome="recorded",
        )

    return MemoryRoutingDecision(
        destination="forget",
        reasoning=(
            "No event-signal keywords found; message reads as routine "
            "conversational filler or a tool acknowledgement with no "
            "standalone value once the active task finishes."
        ),
        source_message=message,
    )


class PromoteOrDropRouter:
    """Wraps a decision function and keeps a running, inspectable log of
    every decision made -- required by the lab ("reasoning behind each
    decision logged somewhere a grader can see it").
    """

    def __init__(self, decision_fn: Optional[DecisionFn] = None):
        self._decision_fn = decision_fn or default_decision_fn
        self._log: list[MemoryRoutingDecision] = []

    def route(self, message: Message) -> MemoryRoutingDecision:
        decision = self._decision_fn(message)
        if decision.destination not in ("forget", "episodic"):
            # Defensive guard, not just type hints -- a custom decision_fn
            # (e.g. LLM-backed) must not be able to smuggle "semantic" through.
            raise ValueError(
                f"PromoteOrDropRouter only supports 'forget' or 'episodic', "
                f"got {decision.destination!r}. Semantic memory is only ever "
                f"written by the consolidation layer."
            )
        self._log.append(decision)
        return decision

    def process_overflow(self, evicted_message: Optional[Message]) -> Optional[MemoryRoutingDecision]:
        """Convenience wrapper matching the exact return shape of
        `ShortTermMemory.add()`: pass its return value straight in.
        Returns None if nothing was evicted this call.
        """
        if evicted_message is None:
            return None
        return self.route(evicted_message)

    @property
    def log(self) -> list[MemoryRoutingDecision]:
        return list(self._log)

    def log_as_text(self) -> str:
        lines = []
        for i, d in enumerate(self._log, start=1):
            lines.append(
                f"[{i}] {d.decided_at} -> {d.destination.upper()}\n"
                f"    message: {d.source_message.content!r}\n"
                f"    reasoning: {d.reasoning}"
            )
        return "\n".join(lines)