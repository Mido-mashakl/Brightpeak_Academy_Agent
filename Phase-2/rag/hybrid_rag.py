"""
Brightpeak Academy — Hybrid Search (Vector + BM25)
===================================================

Combines:
  - Dense / TF-IDF vector similarity (from VectorStore)
  - Sparse keyword ranking via BM25 (rank_bm25)

Scores are normalised and fused with a weighted sum (default 0.6 vector
+ 0.4 BM25). Metadata filters are applied before both legs of the search.

This architecture is expected to win on citation-heavy and identifier-
heavy questions (e.g. "Protocol 4.2b", "Document ID BP-ATT-2025-01")
where pure vector search often fails.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Optional

from rank_bm25 import BM25Plus

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

from vector_db import VectorStore  # noqa: E402


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class HybridRAG:
    def __init__(
        self,
        store: VectorStore | None = None,
        top_k: int = 4,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ):
        self.store = store or VectorStore()
        self.top_k = top_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self._bm25: BM25Plus | None = None
        self._corpus_tokens: list[list[str]] = []
        self._rebuild_bm25()

    def _rebuild_bm25(self):
        if not self.store.documents:
            self._bm25 = None
            self._corpus_tokens = []
            return
        self._corpus_tokens = [_tokenize(d) for d in self.store.documents]
        self._bm25 = BM25Plus(self._corpus_tokens)

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        k = top_k or self.top_k
        if self._bm25 is None:
            self._rebuild_bm25()
        if self._bm25 is None:
            return []

        # Candidate set after metadata filter
        candidate_idxs = [
            i
            for i, m in enumerate(self.store.metadatas)
            if self.store._matches_filter(m, where)
        ]
        if not candidate_idxs:
            return []

        # --- Vector leg (over-fetch then filter) ---
        vec_hits = self.store.query(query_text=query, top_k=max(k * 5, 20), where=where)
        vec_scores = {h["id"]: h["score"] for h in vec_hits}

        # --- BM25 leg ---
        tokens = _tokenize(query)
        raw_bm25 = self._bm25.get_scores(tokens)
        # Normalise BM25 scores to [0, 1] over candidates
        cand_scores = [(raw_bm25[i], i) for i in candidate_idxs]
        max_b = max((s for s, _ in cand_scores), default=1.0) or 1.0
        bm25_scores = {
            self.store.ids[i]: (s / max_b) for s, i in cand_scores if s > 0
        }

        # --- Fuse ---
        all_ids = set(vec_scores) | set(bm25_scores)
        fused = []
        for doc_id in all_ids:
            v = vec_scores.get(doc_id, 0.0)
            b = bm25_scores.get(doc_id, 0.0)
            score = self.vector_weight * v + self.bm25_weight * b
            row = self.store._id_to_row[doc_id]
            fused.append(
                {
                    "id": doc_id,
                    "document": self.store.documents[row],
                    "metadata": self.store.metadatas[row],
                    "score": score,
                    "vector_score": v,
                    "bm25_score": b,
                }
            )
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused[:k]

    def format_context(self, hits: list[dict]) -> str:
        if not hits:
            return "No relevant policy passages found."
        blocks = []
        for i, h in enumerate(hits, 1):
            meta = h.get("metadata", {})
            source = f"{meta.get('document_title', '?')} § {meta.get('section', '?')}"
            blocks.append(f"[{i}] ({source}, hybrid_score={h['score']:.3f})\n{h['document']}")
        return "\n\n".join(blocks)

    def answer_prompt(
        self,
        query: str,
        hits: list[dict],
        content_type: str = "policy",
    ) -> str:
        context = self.format_context(hits)

        if content_type == "course_material":
            return (
                "You are the Brightpeak Academy teaching assistant. "
                "Answer the student's question using ONLY the retrieved "
                "course material below. "
                "Explain the concept clearly and simply, especially for "
                "beginner students. "
                "Use examples only when they are supported by the course "
                "material. "
                "Do not invent information that is not present in the "
                "retrieved material. "
                "If the material does not contain enough information to "
                "answer the question, say so clearly. "
                "Cite the document title and section when possible.\n\n"
                f"Course material passages:\n{context}\n\n"
                f"Student question: {query}\n\n"
                "Answer:"
            )

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
            "architecture": "hybrid_rag",
            "query": query,
            "hits": hits,
            "context": self.format_context(hits),
            "prompt": self.answer_prompt(query, hits),
        }


if __name__ == "__main__":
    from ingestion import ingest

    store = ingest(reset=False)
    rag = HybridRAG(store)
    result = rag.run("What does Protocol 4.2b say about special examination arrangements?")
    print(result["context"][:600])
