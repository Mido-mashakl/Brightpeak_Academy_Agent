"""
Brightpeak Academy — Agentic RAG
=================================

A multi-step retrieval loop:

  1. Decide whether the current context is sufficient.
  2. If not, rewrite / decompose the query and retrieve again.
  3. Observe the new passages, grade relevance, decide whether to stop.
  4. Cap at max_hops to bound cost.

This is the architecture that should win on multi-part questions that
need decomposition (e.g. "for a student below 75% attendance who also
wants a scholarship, what happens?").
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

from hybrid_rag import HybridRAG  # noqa: E402
from vector_db import VectorStore  # noqa: E402


# Simple rule-based "grader" and "rewriter" so the module is testable
# without an LLM. When the agent is wired up, these are swapped for
# real Gemini calls with the same signatures.

def default_relevance_grade(query: str, passage: str) -> float:
    """Return a rough relevance score in [0, 1] based on token overlap."""
    q_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    p_tokens = set(re.findall(r"[a-z0-9]+", passage.lower()))
    if not q_tokens:
        return 0.0
    return len(q_tokens & p_tokens) / len(q_tokens)


def default_should_continue(query: str, hits: list[dict], hop: int, max_hops: int) -> bool:
    if hop >= max_hops:
        return False
    if not hits:
        return True
    # If the best hit has low overlap, keep going
    best = max(default_relevance_grade(query, h["document"]) for h in hits)
    return best < 0.45


def default_rewrite(query: str, previous_hits: list[dict], hop: int) -> list[str]:
    """
    Decompose multi-part questions into focused sub-queries.
    Rule-based for offline testing; replaced by LLM in production.
    """
    q = query.lower()
    sub = []

    # Common Brightpeak multi-part patterns
    if "attendance" in q and ("scholarship" in q or "eligible" in q):
        sub.append("minimum attendance percentage required")
        sub.append("scholarship eligibility grade average threshold")
    if "withdraw" in q or "drop" in q:
        sub.append("course withdrawal window 14 days")
        if "attendance" in q:
            sub.append("attendance policy below 75 percent")
    if "protocol 4.2b" in q or "special arrangement" in q or "extra time" in q:
        sub.append("Protocol 4.2b special arrangements examination")
    if "late" in q and ("submit" in q or "assignment" in q):
        sub.append("late submission penalty percentage per day")
    if "integrity" in q or "plagiarism" in q:
        sub.append("academic integrity sanctions plagiarism cheating")

    if not sub:
        # Generic decomposition: split on "and" / "also"
        parts = re.split(r"\band\b|\balso\b|\bplus\b", query, flags=re.IGNORECASE)
        sub = [p.strip() for p in parts if len(p.strip()) > 10]

    if not sub:
        sub = [query]
    return sub[:3]


class AgenticRAG:
    def __init__(
        self,
        store: VectorStore | None = None,
        top_k: int = 3,
        max_hops: int = 3,
        relevance_fn: Callable[[str, str], float] | None = None,
        should_continue_fn: Callable | None = None,
        rewrite_fn: Callable | None = None,
    ):
        self.base = HybridRAG(store=store, top_k=top_k)
        self.top_k = top_k
        self.max_hops = max_hops
        self.relevance_fn = relevance_fn or default_relevance_grade
        self.should_continue_fn = should_continue_fn or default_should_continue
        self.rewrite_fn = rewrite_fn or default_rewrite

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        k = top_k or self.top_k
        all_hits: dict[str, dict] = {}
        current_queries = [query]
        hop = 0

        while hop < self.max_hops:
            hop += 1
            for q in current_queries:
                hits = self.base.retrieve(q, top_k=k, where=where)
                for h in hits:
                    existing = all_hits.get(h["id"])
                    if existing is None or h["score"] > existing["score"]:
                        h = dict(h)
                        h["hop"] = hop
                        h["sub_query"] = q
                        all_hits[h["id"]] = h

            ranked = sorted(all_hits.values(), key=lambda x: x["score"], reverse=True)
            if not self.should_continue_fn(query, ranked[:k], hop, self.max_hops):
                break
            current_queries = self.rewrite_fn(query, ranked, hop)

        ranked = sorted(all_hits.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:k]

    def format_context(self, hits: list[dict]) -> str:
        if not hits:
            return "No relevant policy passages found."
        blocks = []
        for i, h in enumerate(hits, 1):
            meta = h.get("metadata", {})
            source = f"{meta.get('document_title', '?')} § {meta.get('section', '?')}"
            hop_info = f", hop={h.get('hop', 1)}"
            blocks.append(f"[{i}] ({source}{hop_info})\n{h['document']}")
        return "\n\n".join(blocks)

    def answer_prompt(self, query: str, hits: list[dict]) -> str:
        context = self.format_context(hits)
        return (
            "You are the Brightpeak Academy academic assistant. "
            "Answer the user's question using ONLY the policy passages below. "
            "If the passages do not contain the answer, say so clearly. "
            "Cite the document title and section when possible.\n\n"
            f"Policy passages:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )

    def run(self, query: str, where: dict | None = None) -> dict[str, Any]:
        hits = self.retrieve(query, where=where)
        return {
            "architecture": "agentic_rag",
            "query": query,
            "hits": hits,
            "context": self.format_context(hits),
            "prompt": self.answer_prompt(query, hits),
            "hops_used": max((h.get("hop", 1) for h in hits), default=0),
        }


if __name__ == "__main__":
    from ingestion import ingest

    store = ingest(reset=False)
    rag = AgenticRAG(store)
    q = (
        "For a student whose attendance is below 75% and who also wants to know "
        "if they can still apply for a scholarship, what do the policies say?"
    )
    result = rag.run(q)
    print(f"Hops used: {result['hops_used']}")
    print(result["context"][:700])
