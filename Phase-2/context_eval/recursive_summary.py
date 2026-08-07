"""
Brightpeak Academy - Memory System Extension
==============================================
Context Window Management -- Recursive Summarization Strategy
------------------------------------------------------------------

A context-window management strategy that collapses older conversation
turns into a single running summary instead of dropping them outright
(sliding_window.py) or masking just the tool payloads
(observation_masking.py).

The idea is "recursive": once there are more than `trigger_at` messages,
the oldest `chunk_size` of them are folded into the *existing* summary
to produce a new summary, then discarded from the raw message list.
Each pass only ever looks at (previous_summary + one chunk) -- never the
whole history at once -- so the summarization step itself stays cheap
and bounded no matter how long the conversation runs.

Like the other two context_eval/ strategies, this is a read-time /
maintenance-time view, not a storage component:
- It never touches `memory/short_term.py`'s buffer directly.
- It doesn't decide what belongs in long-term memory -- that's still
  the Promote-or-Drop router's job (`memory/router.py`) followed by
  consolidation (`memory/consolidation.py`). This module only decides
  what a *prompt* looks like when the raw transcript has gotten long.

No LLM call is wired in here by design, so this file stays runnable
and testable with zero external dependencies. `summarizer_fn` is an
injected callable -- pass in a real LLM-backed summarizer in
production (e.g. one Claude API call per fold); the default is a
deterministic, dependency-free extractive stub used by the tests below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

SummarizerFn = Callable[[str, list[dict]], str]


def _default_summarizer(previous_summary: str, chunk: list[dict]) -> str:
    """Dependency-free extractive stub: keeps the running summary and
    appends one short line per message in the chunk. Good enough to
    prove the fold logic works; swap in a real LLM call in production
    (see module docstring).
    """
    lines = [previous_summary] if previous_summary else []
    for m in chunk:
        role = m.get("role", "?")
        content = " ".join(str(m.get("content", "")).split())
        if len(content) > 60:
            content = content[:60].rstrip() + "..."
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)


@dataclass
class SummaryFold:
    """Record of a single fold, so the process is auditable -- same
    spirit as the reasoning strings logged by router.py and
    consolidation.py.
    """
    chunk_size: int
    summary_before: str
    summary_after: str


@dataclass
class RecursiveSummaryResult:
    summary: str
    recent_messages: list[dict]
    folds: list[SummaryFold] = field(default_factory=list)

    def as_context(self, keep_recent: Optional[int] = None) -> list[dict]:
        """What actually gets sent to the LLM: the running summary as a
        synthetic system message, followed by the most recent
        `keep_recent` messages (default: all of `recent_messages` --
        pass an explicit `keep_recent` to trim further for this one
        prompt without discarding the rest from `recent_messages`).
        """
        context: list[dict] = []
        if self.summary:
            context.append({"role": "system", "msg_type": "summary", "content": self.summary})
        tail = self.recent_messages if keep_recent is None else self.recent_messages[-keep_recent:]
        context.extend(tail)
        return context


class RecursiveSummarizer:
    """Maintains a running summary of everything older than the most
    recent `chunk_size`-sized window, folding older chunks in one at a
    time as the conversation grows past `trigger_at` messages.

    Args:
        trigger_at: once the message list exceeds this length, folding
            kicks in.
        chunk_size: how many of the oldest messages get folded into the
            summary per pass.
        keep_recent: how many of the most recent messages always stay
            verbatim, never folded.
        summarizer_fn: `(previous_summary, chunk) -> new_summary`.
            Defaults to a deterministic extractive stub (see
            `_default_summarizer`); inject a real LLM-backed summarizer
            in production.
    """

    def __init__(
        self,
        trigger_at: int = 12,
        chunk_size: int = 4,
        keep_recent: int = 6,
        summarizer_fn: Optional[SummarizerFn] = None,
    ):
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if keep_recent < 0:
            raise ValueError("keep_recent must be >= 0")
        if trigger_at < keep_recent:
            raise ValueError("trigger_at must be >= keep_recent")
        self.trigger_at = trigger_at
        self.chunk_size = chunk_size
        self.keep_recent = keep_recent
        self.summarizer_fn = summarizer_fn or _default_summarizer
        self._summary: str = ""
        # How many messages (from the start of the list passed to
        # process()) have already been folded into `self._summary`.
        # Tracked so that calling process() again with a longer version
        # of the same prefix only folds the NEW messages, instead of
        # re-summarizing chunks that are already accounted for.
        self._folded_count: int = 0

    @property
    def summary(self) -> str:
        return self._summary

    def process(self, messages: Sequence[dict]) -> RecursiveSummaryResult:
        """Given the full raw message list (the same growing list each
        call -- e.g. turns 1..N, then 1..N+3 next time -- not just the
        newly-added messages), folds oldest UN-folded chunks into the
        running summary until what remains fits, then returns the
        summary plus the untouched tail. Never mutates `messages`.

        Idempotent for a given prefix: messages already folded by an
        earlier `process()` call are tracked via `self._folded_count`
        and skipped, so calling `process()` again with the same (or a
        longer, appended-to) list never re-summarizes the same chunk
        twice.
        """
        remaining = list(messages[self._folded_count :])
        folds: list[SummaryFold] = []

        # `remaining` (the un-folded tail) is what needs to fit under
        # `trigger_at` -- already-folded messages are accounted for in
        # the summary, not in this count.
        while len(remaining) > self.trigger_at and len(remaining) >= self.chunk_size:
            chunk = remaining[: self.chunk_size]
            before = self._summary
            self._summary = self.summarizer_fn(self._summary, chunk)
            folds.append(
                SummaryFold(chunk_size=len(chunk), summary_before=before, summary_after=self._summary)
            )
            remaining = remaining[self.chunk_size :]
            self._folded_count += len(chunk)

        # Whatever didn't get folded stays verbatim. We deliberately do
        # NOT further trim `remaining` down to exactly `keep_recent`:
        # doing so would silently drop messages that are neither folded
        # into the summary nor returned as recent context. They stay
        # verbatim until a later `process()` call pushes the total past
        # `trigger_at` again and folds the next chunk.
        recent = remaining

        return RecursiveSummaryResult(summary=self._summary, recent_messages=recent, folds=folds)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"RecursiveSummarizer(trigger_at={self.trigger_at}, chunk_size={self.chunk_size}, "
            f"keep_recent={self.keep_recent}, summary_len={len(self._summary)})"
        )


if __name__ == "__main__":
    # Minimal runnable proof, same spirit as the other test_*.py scripts
    # in memory/ (no pytest required).
    sample = [
        {"role": "user", "content": f"Question {i} about student records"} for i in range(1, 21)
    ]

    summarizer = RecursiveSummarizer(trigger_at=12, chunk_size=4, keep_recent=6)
    result = summarizer.process(sample)

    print(f"input messages: {len(sample)}")
    print(f"folds performed: {len(result.folds)}")
    for i, fold in enumerate(result.folds, 1):
        print(f"  fold {i}: folded {fold.chunk_size} messages into running summary")
    print(f"recent_messages kept verbatim: {len(result.recent_messages)}")
    print(f"last kept message: {result.recent_messages[-1]['content']}")
    print("\n--- running summary ---")
    print(result.summary)

    assert len(result.recent_messages) == 12  # trigger_at=12: loop stops once <= trigger_at
    assert result.recent_messages[-1]["content"] == "Question 20 about student records"
    assert len(result.folds) * 4 + len(result.recent_messages) == len(sample)
    assert "Question 1 about" in result.summary  # oldest message made it into the fold

    # Idempotency check: running process() again on the SAME messages with
    # the SAME summarizer state must not duplicate folds, since nothing
    # new was added past what's already folded.
    result2 = summarizer.process(sample)
    assert result2.folds == [], "re-processing the same prefix should not re-fold"
    assert result2.summary == result.summary, "summary should be unchanged when nothing new was folded"

    # Growth check: appending more messages and calling process() again
    # should only fold the NEW messages, not re-fold anything already
    # captured in the summary.
    grown = sample + [
        {"role": "user", "content": f"Question {i} about student records"} for i in range(21, 25)
    ]
    result3 = summarizer.process(grown)
    assert len(result3.folds) == 1, "only the newly-added chunk should be folded"
    assert result3.folds[0].summary_before == result.summary, "fold must build on the prior summary, not restart"
    assert "Question 9 about" in result3.summary  # the next un-folded chunk (messages 9-12) is now folded in
    assert "Question 1 about" in result3.summary  # earlier folds are still preserved in the running summary

    print("\nAll recursive_summary.py checks passed.")