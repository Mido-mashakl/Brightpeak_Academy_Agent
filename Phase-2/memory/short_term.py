"""
Brightpeak Academy - Memory System Extension
==============================================
Short-Term Memory
------------------

A bounded rolling buffer of the current conversation: user messages,
assistant responses, tool calls, and tool results. This is the "RAM" of
the agent -- fast, cleared on session end, and intentionally lossy once
it overflows.

Deliberately excludes the scratchpad (see scratchpad.py). Eviction here
only ever removes items from `self.messages`; it never has a reference
to the scratchpad and therefore cannot touch it, by construction.

When an item is evicted (overflow), it is not silently discarded -- it is
returned to the caller so the Promote-or-Drop Router (memory/router.py,
next component) can decide whether it deserves to live on in episodic or
semantic memory. `ShortTermMemory` itself has no opinion on that; it only
manages the buffer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

Role = Literal["user", "assistant", "tool", "system"]


@dataclass
class Message:
    role: Role
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # e.g. "tool_call:get_student_attendance", "tool_result", "text"
    msg_type: str = "text"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "msg_type": self.msg_type,
            "metadata": self.metadata,
        }


class ShortTermMemory:
    """Rolling buffer, bounded by `max_turns`. When adding a message would
    push the buffer past `max_turns`, the oldest message is evicted and
    returned from `add()` so a caller (the router) can act on it.
    """

    def __init__(self, max_turns: int = 20):
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        self.max_turns = max_turns
        self.messages: list[Message] = []

    def add(
        self,
        role: Role,
        content: str,
        msg_type: str = "text",
        metadata: Optional[dict] = None,
    ) -> Optional[Message]:
        """Appends a message. Returns the evicted Message if the buffer
        overflowed, otherwise None.
        """
        message = Message(role=role, content=content, msg_type=msg_type, metadata=metadata or {})
        self.messages.append(message)

        evicted: Optional[Message] = None
        if len(self.messages) > self.max_turns:
            evicted = self.messages.pop(0)

        return evicted

    def get_context(self) -> list[dict]:
        """What actually gets sent to the LLM on the next call."""
        return [m.to_dict() for m in self.messages]

    def is_full(self) -> bool:
        return len(self.messages) >= self.max_turns

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ShortTermMemory(len={len(self.messages)}/{self.max_turns})"