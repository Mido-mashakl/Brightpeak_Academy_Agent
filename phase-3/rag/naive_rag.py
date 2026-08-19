"""
Brightpeak Academy — Naive RAG
===============================

Baseline: chunk → embed → index → retrieve top-k by vector similarity →
stuff into a prompt → generate.

No keyword component, no multi-hop, no verification beyond the caller's
Self-RAG check.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

from vector_db import VectorStore  # noqa: E402


class NaiveRAG:
    def __init__(self, store: VectorStore | None = None, top_k: int = 4):
        self.store = store or VectorStore()
        self.top_k = top_k

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        k = top_k or self.top_k
        return self.store.query(query_text=query, top_k=k, where=where)

    def format_context(self, hits: list[dict]) -> str:
        if not hits:
            return "No relevant policy passages found."
        blocks = []
        for i, h in enumerate(hits, 1):
            meta = h.get("metadata", {})
            source = f"{meta.get('document_title', '?')} § {meta.get('section', '?')}"
            blocks.append(f"[{i}] ({source})\n{h['document']}")
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
            "architecture": "naive_rag",
            "query": query,
            "hits": hits,
            "context": self.format_context(hits),
            "prompt": self.answer_prompt(query, hits),
        }


if __name__ == "__main__":
    from ingestion import ingest

    store = ingest(reset=False)
    rag = NaiveRAG(store)
    result = rag.run("What is the minimum attendance required to sit final exams?")
    print(result["context"][:500])
    print("---")
    print(result["prompt"][:300])
