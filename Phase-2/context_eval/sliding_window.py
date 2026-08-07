"""
Brightpeak Academy - Memory System Extension
==============================================
Context Window Management -- Sliding Window Strategy
------------------------------------------------------

A context-window management strategy that keeps only the most recent
`window_size` messages (or, optionally, the most recent `max_tokens`
worth of content) when building the prompt sent to the LLM.

This is deliberately independent from `memory/short_term.py`:
- `short_term.py` decides what survives *inside the app* across a
  session (and hands overflow to the Promote-or-Drop router so nothing
  is silently lost).
- `SlidingWindow` here only decides what actually gets serialized into
  the *next prompt*. It is a read-time view, not a storage component --
  it never mutates the underlying message list, and it has no opinion
  on what should be remembered long-term.

Anything that falls outside the window is not deleted -- it's simply
excluded from this prompt. The caller can still find it in the full
message history (or in episodic/semantic memory if it was promoted
there).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


def _approx_token_count(text: str) -> int:
    """Cheap, dependency-free token estimate (~4 chars/token for English).
    Good enough for a budget check; swap for a real tokenizer if the
    caller needs exact counts.
    """
    return max(1, len(text) // 4)


@dataclass
class SlidingWindowResult:
    included: list[dict]
    excluded: list[dict]
    truncated_by: str  # "count" | "tokens" | "none"

    def __len__(self) -> int:
        return len(self.included)


class SlidingWindow:
    """Selects the most recent slice of a message list to send as context.

    Two independent caps can apply at once -- whichever is stricter wins:
      - `window_size`: max number of messages to keep.
      - `max_tokens`: max approximate token budget to keep.

    Messages are expected as dicts with at least a "content" key (the
    same shape produced by `memory.short_term.Message.to_dict()`), so
    this composes directly with `ShortTermMemory.get_context()`.
    """

    def __init__(self, window_size: int = 10, max_tokens: Optional[int] = None):
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        if max_tokens is not None and max_tokens < 1:
            raise ValueError("max_tokens must be >= 1 when provided")
        self.window_size = window_size
        self.max_tokens = max_tokens

    def select(self, messages: Sequence[dict]) -> SlidingWindowResult:
        """Returns the most recent messages that fit the window.
        Never mutates `messages`.
        """
        if not messages:
            return SlidingWindowResult(included=[], excluded=[], truncated_by="none")

        # Step 1: cap by count (most recent `window_size` messages).
        by_count = list(messages[-self.window_size:])
        count_excluded = list(messages[: len(messages) - len(by_count)])

        if self.max_tokens is None:
            truncated_by = "count" if count_excluded else "none"
            return SlidingWindowResult(
                included=by_count, excluded=count_excluded, truncated_by=truncated_by
            )

        # Step 2: further cap by token budget, still keeping the most
        # recent messages, walking backwards from the end.
        kept: list[dict] = []
        budget = self.max_tokens
        for msg in reversed(by_count):
            cost = _approx_token_count(str(msg.get("content", "")))
            if cost > budget and kept:
                # Stop once adding another message would blow the budget
                # (but always keep at least one message).
                break
            kept.append(msg)
            budget -= cost
        kept.reverse()

        token_excluded = by_count[: len(by_count) - len(kept)]
        excluded = count_excluded + token_excluded

        truncated_by = "tokens" if token_excluded else ("count" if count_excluded else "none")
        return SlidingWindowResult(included=kept, excluded=excluded, truncated_by=truncated_by)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"SlidingWindow(window_size={self.window_size}, max_tokens={self.max_tokens})"


if __name__ == "__main__":
    # Minimal runnable proof, same spirit as the other test_*.py scripts
    # in memory/ (no pytest required).
    sample = [
        {"role": "user", "content": f"message {i}"} for i in range(1, 16)
    ]

    sw = SlidingWindow(window_size=5)
    result = sw.select(sample)
    print(f"window_size=5 -> kept {len(result.included)} / {len(sample)} messages")
    print("kept:", [m["content"] for m in result.included])
    print("truncated_by:", result.truncated_by)
    assert len(result.included) == 5
    assert result.included[-1]["content"] == "message 15"

    sw_tokens = SlidingWindow(window_size=10, max_tokens=6)
    result2 = sw_tokens.select(sample)
    print(f"\nwindow_size=10,max_tokens=6 -> kept {len(result2.included)} messages")
    print("kept:", [m["content"] for m in result2.included])
    print("truncated_by:", result2.truncated_by)

    print("\nAll sliding_window.py checks passed.")