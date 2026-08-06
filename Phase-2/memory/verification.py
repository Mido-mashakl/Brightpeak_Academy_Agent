"""
Brightpeak Academy - Memory System Extension
==============================================
Memory Verification
-----------------------

Self-RAG-style check that runs on every `RecallResult` recall.py
produces, BEFORE any of it reaches the agent. Mirrors the two grading
steps Self-RAG uses on retrieved passages, applied here to memory
instead of documents:

  1. Relevance grading ("ISREL" in the Self-RAG paper): is this result
     actually about what the query asked, or just noise that happened
     to share a word or two? recall.py already computes a score for
     this; verification.py is what turns that score into a hard
     accept/reject instead of silently trusting it.

  2. Support grading ("ISSUP"): even a genuinely relevant memory can be
     WRONG by the time it's recalled --
       - a semantic fact can have expired since it was written
         (see semantic.py's `expires_at` / `is_expired()`)
       - an episodic event can have been directly superseded by a
         later, different fact in semantic memory (e.g. the episode
         says "student picked the Data Science track", but semantic
         memory's CURRENT value for that student's preferred_track is
         now "AI" -- see the exact scenario in
         test_persistence_session_2.py). Presenting the stale episode
         to the agent as if it were still true would be a real bug,
         not just noise -- this is precisely the failure mode Self-RAG
         support-grading exists to catch.

For step 2 on episodic results, this module deliberately REUSES
consolidation.py's `default_extract_fn` rather than re-implementing its
own "what fact would this event imply" logic -- there is exactly one
place in this codebase that turns an episode into a candidate fact, and
duplicating that logic here would let the two silently drift apart.
Verification only ever READS from SemanticStore (`get_current`) -- same
as recall.py, it never writes.

Why a pluggable verify function: same testability reasoning as every
other decision point in this package (router.py, consolidation.py,
recall.py) -- deterministic, dependency-free default here, swappable
later for an LLM-backed grader with the same signature.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from consolidation import default_extract_fn  # noqa: E402
from recall import RecallResult  # noqa: E402
from semantic import SemanticStore  # noqa: E402

Verdict = Literal["supported", "unsupported", "irrelevant"]

# Deterministic relevance floor: a result must share at least ~30% of
# the query's distinct words (per recall.py's default_score_fn) to even
# be considered on-topic -- enough to separate "shares one incidental
# word" from "the memory is genuinely about what was asked", without
# being so strict that a real 2-out-of-6-word match on a short query
# gets thrown out. Below this, it's graded "irrelevant" outright
# regardless of support -- mirrors Self-RAG's ISREL gate running before
# ISSUP.
MIN_RELEVANCE_SCORE = 0.3


@dataclass
class VerificationVerdict:
    """One verdict on one RecallResult. `reasoning` is mandatory and
    always populated -- same visible-reasoning requirement as every
    other decision object in this package.
    """

    result: RecallResult
    verdict: Verdict
    reasoning: str
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "result": self.result.to_dict(),
            "verdict": self.verdict,
            "reasoning": self.reasoning,
            "verified_at": self.verified_at,
        }


VerifyFn = Callable[[str, RecallResult, SemanticStore], VerificationVerdict]


def default_verify_fn(query: str, result: RecallResult, semantic_store: SemanticStore) -> VerificationVerdict:
    """Rule-based default: relevance gate, then a source-specific
    support check. Deterministic and dependency-free on purpose (see
    module docstring) so verification.py is testable in complete
    isolation.
    """
    if result.score < MIN_RELEVANCE_SCORE:
        return VerificationVerdict(
            result=result,
            verdict="irrelevant",
            reasoning=(
                f"Relevance score {result.score:.2f} is below the "
                f"{MIN_RELEVANCE_SCORE:.2f} floor -- too little genuine word "
                f"overlap with the query to treat as on-topic, regardless of "
                f"whether the underlying memory is itself trustworthy."
            ),
        )

    if result.source == "semantic":
        fact = result.fact
        assert fact is not None  # every semantic RecallResult carries its Fact
        if fact.is_expired():
            return VerificationVerdict(
                result=result,
                verdict="unsupported",
                reasoning=(
                    f"Fact {fact.fact_key!r} (v{fact.version}) is relevant to the "
                    f"query but has EXPIRED (expires_at={fact.expires_at}) -- "
                    f"presenting an expired fact as current knowledge would be "
                    f"wrong, so it is rejected even though it matched."
                ),
            )
        return VerificationVerdict(
            result=result,
            verdict="supported",
            reasoning=(
                f"Fact {fact.fact_key!r} (v{fact.version}) is relevant and is "
                f"the current, non-expired value in semantic memory -- safe to "
                f"present to the agent as ground truth."
            ),
        )

    # source == "episodic"
    episode = result.episode
    assert episode is not None  # every episodic RecallResult carries its Episode

    candidate = default_extract_fn(episode)
    if candidate is None:
        return VerificationVerdict(
            result=result,
            verdict="supported",
            reasoning=(
                f"Episode {episode.id} implies no generalizable, checkable "
                f"claim (e.g. it's a raw logged event, not a standing status) "
                f"-- nothing in semantic memory could contradict it, so it "
                f"stands on its own as a historical record."
            ),
        )

    current = semantic_store.get_current(candidate.fact_key, include_expired=True)
    if current is None:
        return VerificationVerdict(
            result=result,
            verdict="supported",
            reasoning=(
                f"Episode {episode.id} implies {candidate.fact_key}="
                f"{candidate.value!r}, and no consolidated fact exists yet for "
                f"that key -- nothing in semantic memory contradicts it, so "
                f"this episode is still the best available record."
            ),
        )

    if current.value != candidate.value or current.is_expired():
        return VerificationVerdict(
            result=result,
            verdict="unsupported",
            reasoning=(
                f"Episode {episode.id} implies {candidate.fact_key}="
                f"{candidate.value!r}, but the CURRENT semantic fact for that "
                f"key is now {current.value!r} (v{current.version}"
                + (", expired" if current.is_expired() else "")
                + f") -- this episode has been superseded by newer, "
                f"contradicting knowledge and must not be presented as still "
                f"true."
            ),
        )

    return VerificationVerdict(
        result=result,
        verdict="supported",
        reasoning=(
            f"Episode {episode.id} implies {candidate.fact_key}="
            f"{candidate.value!r}, which matches the current semantic fact "
            f"(v{current.version}) exactly -- corroborated, not just "
            f"uncontradicted."
        ),
    )


class MemoryVerifier:
    """Wraps a verify function and keeps a running, inspectable log of
    every verdict made -- same "reasoning a grader can see" requirement
    as PromoteOrDropRouter and ConsolidationLayer.
    """

    def __init__(self, semantic_store: SemanticStore, verify_fn: Optional[VerifyFn] = None):
        self._semantic = semantic_store
        self._verify_fn = verify_fn or default_verify_fn
        self._log: list[VerificationVerdict] = []

    def verify(self, query: str, result: RecallResult) -> VerificationVerdict:
        verdict = self._verify_fn(query, result, self._semantic)
        self._log.append(verdict)
        return verdict

    def verify_batch(self, query: str, results: list[RecallResult]) -> list[VerificationVerdict]:
        return [self.verify(query, r) for r in results]

    def supported_only(self, query: str, results: list[RecallResult]) -> list[RecallResult]:
        """What should actually reach the agent: only results that
        passed both the relevance gate and the support check. This is
        the function memory_rag_agent.py (agent integration, next
        issue) is expected to call, not `recall()` directly.
        """
        verdicts = self.verify_batch(query, results)
        return [v.result for v in verdicts if v.verdict == "supported"]

    @property
    def log(self) -> list[VerificationVerdict]:
        return list(self._log)

    def log_as_text(self) -> str:
        lines = []
        for i, v in enumerate(self._log, start=1):
            lines.append(
                f"[{i}] {v.verified_at} -> {v.verdict.upper()} "
                f"(source={v.result.source}, ref_id={v.result.ref_id})\n"
                f"    reasoning: {v.reasoning}"
            )
        return "\n".join(lines)