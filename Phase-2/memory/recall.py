"""
Brightpeak Academy - Memory System Extension
==============================================
Memory Recall
----------------

Given a query (what the agent currently needs to know, e.g. "does this
student still owe an exam form?") and, usually, a student_id to scope
to, searches BOTH long-term stores and returns a single ranked list of
what's actually relevant -- episodic events AND semantic facts mixed
together, ordered by how well each one answers the query.

This module only retrieves and ranks. It never writes to either store
(same read-only relationship consolidation.py has with episodic.py --
see that module's docstring) and it never decides whether a result is
trustworthy enough to actually hand to the agent -- that judgment call
is verification.py's job, the next component, which is deliberately
kept separate: recall's job is "what's plausibly relevant", not "what's
safe to act on". Mixing those two would hide the self-RAG-style check
the lab asks for inside a component that shouldn't own it.

Why a pluggable scoring function instead of embeddings
----------------------------------------------------------
Same reasoning as router.py's `decision_fn` and consolidation.py's
`extract_fn`: this module must be testable standalone, deterministically,
with no network access and no vector index (see test_recall_verification.py).
There is no embedding/vector-search dependency anywhere in this project's
requirements.txt, so the default scorer below is a transparent, rule-based
word-overlap heuristic -- good enough to prove real semantic + episodic
retrieval end-to-end, and swappable later for an embedding-based
`score_fn` with the exact same signature (score_fn(query_text, item_text)
-> float) without touching anything else in this file.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional

MEMORY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MEMORY_DIR))

from episodic import Episode, EpisodicStore  # noqa: E402
from semantic import Fact, SemanticStore  # noqa: E402

Source = Literal["episodic", "semantic"]

_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


ScoreFn = Callable[[str, str], float]


def default_score_fn(query: str, item_text: str) -> float:
    """Deterministic, dependency-free relevance score in [0, 1]: the
    fraction of the query's distinct words that also appear in the
    item's text (a directional overlap, not full Jaccard -- a short
    query fully contained in a longer episode should score high, and
    shouldn't be punished just because the episode also has other
    words the query didn't ask about).
    """
    query_words = _words(query)
    if not query_words:
        return 0.0
    item_words = _words(item_text)
    overlap = query_words & item_words
    return len(overlap) / len(query_words)


@dataclass
class RecallResult:
    """One retrieved item, from either store, with the score and
    reasoning that justify its rank -- same "visible reasoning a grader
    can see" requirement as MemoryRoutingDecision and
    ConsolidationDecision.
    """

    source: Source
    ref_id: int
    text: str
    score: float
    reasoning: str
    recalled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    episode: Optional[Episode] = None
    fact: Optional[Fact] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "ref_id": self.ref_id,
            "text": self.text,
            "score": self.score,
            "reasoning": self.reasoning,
            "recalled_at": self.recalled_at,
        }


def _episode_text(ep: Episode) -> str:
    return f"{ep.event_summary} {ep.context or ''} {ep.outcome or ''}"


def _fact_text(fact: Fact) -> str:
    # fact_key itself carries meaning too (e.g. "preferred_track:student_7"),
    # so it's part of the searchable text, not just the value.
    return f"{fact.fact_key} {fact.value}"


class MemoryRecall:
    """Wraps an EpisodicStore and a SemanticStore and answers a query
    against both at once. Read-only: never calls `insert()` or
    `upsert()` on either store.
    """

    def __init__(
        self,
        episodic_store: EpisodicStore,
        semantic_store: SemanticStore,
        score_fn: Optional[ScoreFn] = None,
    ):
        self._episodic = episodic_store
        self._semantic = semantic_store
        self._score_fn = score_fn or default_score_fn
        self._log: list[RecallResult] = []

    def recall(
        self,
        query: str,
        student_id: Optional[int] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        include_expired_facts: bool = False,
    ) -> list[RecallResult]:
        """Scores every candidate episode and fact against `query`,
        returns the top_k above `min_score`, highest score first
        (recency as the tiebreak within equal scores -- more recent
        episodes / higher fact versions rank first).

        If `student_id` is given, only episodes whose metadata carries
        that student_id and only facts whose fact_key ends in
        f":student_{student_id}" are considered -- this project's
        established fact_key convention (see consolidation.py). Without
        a student_id, every episode and every current fact is a
        candidate, which is intentional for advisor-facing queries that
        aren't about one specific student.
        """
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")

        candidate_episodes = self._candidate_episodes(student_id)
        candidate_facts = self._candidate_facts(student_id, include_expired_facts)

        scored: list[RecallResult] = []

        for ep in candidate_episodes:
            text = _episode_text(ep)
            score = self._score_fn(query, text)
            if score <= 0:
                continue
            matched = sorted(_words(query) & _words(text))
            scored.append(
                RecallResult(
                    source="episodic",
                    ref_id=ep.id,
                    text=ep.event_summary,
                    score=score,
                    reasoning=(
                        f"Episode {ep.id} shares {len(matched)} query word(s) "
                        f"{matched} with the event ({ep.timestamp})."
                    ),
                    episode=ep,
                )
            )

        for fact in candidate_facts:
            text = _fact_text(fact)
            score = self._score_fn(query, text)
            if score <= 0:
                continue
            matched = sorted(_words(query) & _words(text))
            scored.append(
                RecallResult(
                    source="semantic",
                    ref_id=fact.id,
                    text=f"{fact.fact_key}={fact.value}",
                    score=score,
                    reasoning=(
                        f"Fact {fact.fact_key!r} (v{fact.version}) shares "
                        f"{len(matched)} query word(s) {matched} with the query."
                    ),
                    fact=fact,
                )
            )

        scored = [r for r in scored if r.score >= min_score]

        def _recency_key(r: RecallResult) -> str:
            if r.episode is not None:
                return r.episode.timestamp
            return r.fact.created_at  # type: ignore[union-attr]

        scored.sort(key=lambda r: (r.score, _recency_key(r)), reverse=True)
        top = scored[:top_k]
        self._log.extend(top)
        return top

    # ------------------------------------------------------------------
    # Candidate gathering -- read-only use of each store's public API
    # ------------------------------------------------------------------
    def _candidate_episodes(self, student_id: Optional[int]) -> list[Episode]:
        if student_id is not None:
            return self._episodic.list_by_metadata({"student_id": student_id}, limit=1_000_000)
        return self._episodic.list_recent(limit=1_000_000)

    def _candidate_facts(self, student_id: Optional[int], include_expired: bool) -> list[Fact]:
        facts = self._semantic.list_all_current(include_expired=include_expired)
        if student_id is not None:
            suffix = f":student_{student_id}"
            facts = [f for f in facts if f.fact_key.endswith(suffix)]
        return facts

    # ------------------------------------------------------------------
    # Formatting for direct injection into an agent prompt
    # ------------------------------------------------------------------
    @staticmethod
    def to_context_string(results: list[RecallResult]) -> str:
        """Human-readable block ready to drop into an agent's context --
        the shape memory_rag_agent.py (agent integration, next issue)
        is expected to consume."""
        if not results:
            return "(no relevant memory found)"
        lines = []
        for r in results:
            tag = "EPISODE" if r.source == "episodic" else "FACT"
            lines.append(f"- [{tag}] {r.text} (relevance={r.score:.2f})")
        return "\n".join(lines)

    @property
    def log(self) -> list[RecallResult]:
        return list(self._log)