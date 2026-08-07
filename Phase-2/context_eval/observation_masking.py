"""
Brightpeak Academy - Memory System Extension
==============================================
Context Window Management -- Observation Masking Strategy
------------------------------------------------------------

A context-window management strategy for agent loops that call tools
(MCP server calls: get_student_attendance, get_grades, etc.). Tool
*observations* (results) are frequently large and mostly useful only
right after the call that produced them -- once the agent has read a
tool result and moved on, keeping the full payload in every subsequent
prompt is pure token cost with shrinking value.

`ObservationMasker` keeps the `keep_recent` most recent tool
observations verbatim, and replaces older ones with a short placeholder
that preserves *that a call happened and what it returned in brief*,
without paying for the full payload on every turn.

Like `sliding_window.py`, this is a read-time view over messages, not a
storage component:
- It never deletes anything from the underlying message list -- it
  returns a new list with older tool messages masked.
- The original, unmasked message is still available wherever the
  caller keeps full history (or in episodic memory if it was promoted
  there via the Promote-or-Drop router).

Non-tool messages (user/assistant/system) are never masked -- masking
only ever applies to `msg_type` values that look like tool activity
(default: "tool_call" and "tool_result"), so this composes safely with
`memory.short_term.Message.to_dict()` output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

DEFAULT_TOOL_MSG_TYPES = {"tool_call", "tool_result"}


def _summarize(content: str, max_chars: int = 80) -> str:
    """Cheap, dependency-free summary: first `max_chars` characters."""
    content = " ".join(content.split())  # collapse whitespace
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rstrip() + "..."


@dataclass
class MaskingResult:
    messages: list[dict]
    masked_count: int
    kept_count: int

    def __len__(self) -> int:
        return len(self.messages)


class ObservationMasker:
    """Masks older tool observations while keeping the most recent ones
    verbatim.

    Args:
        keep_recent: how many of the most recent tool observations to
            leave untouched (verbatim). Older tool observations are
            replaced with a placeholder.
        summary_chars: how many characters of the original content to
            keep in the placeholder, so the agent still has a hint of
            what the call returned.
        tool_msg_types: which `msg_type` values count as "tool
            observations" eligible for masking. Everything else
            (user/assistant/system text) always passes through
            untouched.
    """

    def __init__(
        self,
        keep_recent: int = 2,
        summary_chars: int = 80,
        tool_msg_types: Optional[set[str]] = None,
    ):
        if keep_recent < 0:
            raise ValueError("keep_recent must be >= 0")
        if summary_chars < 1:
            raise ValueError("summary_chars must be >= 1")
        self.keep_recent = keep_recent
        self.summary_chars = summary_chars
        self.tool_msg_types = tool_msg_types or set(DEFAULT_TOOL_MSG_TYPES)

    def mask(self, messages: Sequence[dict]) -> MaskingResult:
        """Returns a new list of messages with older tool observations
        replaced by short placeholders. Never mutates `messages` or the
        dicts within it.
        """
        # Find indices (in original order) of tool-observation messages.
        tool_indices = [
            i for i, m in enumerate(messages) if m.get("msg_type") in self.tool_msg_types
        ]

        # The most recent `keep_recent` tool observations stay verbatim.
        verbatim_indices = set(tool_indices[-self.keep_recent:]) if self.keep_recent else set()
        maskable_indices = set(tool_indices) - verbatim_indices

        result: list[dict] = []
        masked_count = 0
        for i, msg in enumerate(messages):
            if i in maskable_indices:
                original_content = str(msg.get("content", ""))
                masked_msg = dict(msg)  # shallow copy -- original untouched
                masked_msg["content"] = (
                    f"[masked tool observation -- {_summarize(original_content, self.summary_chars)}]"
                )
                masked_msg["masked"] = True
                result.append(masked_msg)
                masked_count += 1
            else:
                result.append(msg)

        return MaskingResult(
            messages=result,
            masked_count=masked_count,
            kept_count=len(tool_indices) - masked_count,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ObservationMasker(keep_recent={self.keep_recent}, "
            f"summary_chars={self.summary_chars})"
        )


if __name__ == "__main__":
    # Minimal runnable proof, same spirit as the other test_*.py scripts
    # in memory/ (no pytest required).
    sample = [
        {"role": "user", "content": "What's Ahmed's attendance this month?", "msg_type": "text"},
        {"role": "assistant", "content": "Let me check.", "msg_type": "text"},
        {
            "role": "tool",
            "content": "Ahmed Fathy: 18/20 sessions attended, 2 absences (2024-01-15, 2024-01-22), "
            "no late arrivals recorded.",
            "msg_type": "tool_result",
        },
        {"role": "assistant", "content": "Ahmed attended 18 of 20 sessions.", "msg_type": "text"},
        {"role": "user", "content": "What about his grades?", "msg_type": "text"},
        {
            "role": "tool",
            "content": "Ahmed Fathy: Math 88, Science 92, Arabic 79, English 85. GPA 3.6.",
            "msg_type": "tool_result",
        },
        {"role": "assistant", "content": "His GPA is 3.6.", "msg_type": "text"},
        {"role": "user", "content": "Is he eligible for the merit scholarship?", "msg_type": "text"},
        {
            "role": "tool",
            "content": "Merit scholarship rule: GPA >= 3.5 and attendance >= 85%. Ahmed: GPA 3.6, "
            "attendance 90% -- ELIGIBLE.",
            "msg_type": "tool_result",
        },
    ]

    masker = ObservationMasker(keep_recent=1)
    result = masker.mask(sample)

    print(f"tool observations: {result.kept_count} kept verbatim, {result.masked_count} masked")
    for m in result.messages:
        tag = "[MASKED]" if m.get("masked") else "        "
        print(f"{tag} {m['role']:9s} ({m['msg_type']:11s}): {m['content'][:70]}")

    # Original list must be untouched.
    assert sample[2]["content"].startswith("Ahmed Fathy: 18/20"), "original message was mutated!"
    assert result.masked_count == 2
    assert result.kept_count == 1
    assert result.messages[-1]["content"] == sample[-1]["content"], "most recent tool result must stay verbatim"

    print("\nAll observation_masking.py checks passed.")