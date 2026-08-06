"""
Brightpeak Academy — MCP-facing RAG tool helpers
=================================================

Used by the agent (and optionally registered as an MCP tool) to answer
policy questions with grounded retrieval + Self-RAG verification.

Default architecture: Hybrid Search (justified by retrieval_eval numbers).
Multi-part queries can be routed to Agentic RAG.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Optional

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

from vector_db import VectorStore  # noqa: E402
from hybrid_rag import HybridRAG  # noqa: E402
from agentic_rag import AgenticRAG  # noqa: E402
from graph_rag import GraphRAG  # noqa: E402
from self_rag import SelfRAGVerifier  # noqa: E402
from ingestion import ingest  # noqa: E402

_store: VectorStore | None = None
_hybrid: HybridRAG | None = None
_agentic: AgenticRAG | None = None
_graph: GraphRAG | None = None
_verifier = SelfRAGVerifier()


def ensure_index() -> VectorStore:
    global _store, _hybrid, _agentic, _graph
    if _store is None or _store.count() == 0:
        _store = ingest(reset=False)
        if _store.count() == 0:
            _store = ingest(reset=True)
        _hybrid = HybridRAG(_store)
        _agentic = AgenticRAG(_store)
        _graph = GraphRAG(_store)
    return _store


def _is_multipart(query: str) -> bool:
    q = query.lower()
    signals = [" and ", " also ", " as well ", " plus ", "both ", "relationship between"]
    return any(s in q for s in signals) or q.count("?") > 1


def search_policies(
    query: str,
    architecture: str = "auto",
    top_k: int = 4,
    category: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve policy passages and run Self-RAG verification.

    architecture: "auto" | "naive" | "hybrid" | "agentic" | "graph"
    """
    ensure_index()
    where = {"category": category} if category else None

    if architecture == "auto":
        architecture = "agentic" if _is_multipart(query) else "hybrid"

    if architecture == "agentic":
        result = _agentic.run(query, where=where)
    elif architecture == "graph":
        result = _graph.run(query, where=where)
    elif architecture == "naive":
        from naive_rag import NaiveRAG
        result = NaiveRAG(_store, top_k=top_k).run(query, where=where)
    else:
        result = _hybrid.run(query, where=where)

    passages = [h["document"] for h in result["hits"]]
    ver = _verifier.verify(query, passages)

    return {
        "architecture_used": result["architecture"],
        "hits": [
            {
                "text": h["document"][:500],
                "score": round(h.get("score", 0), 3),
                "source": f"{h.get('metadata', {}).get('document_title', '?')} § {h.get('metadata', {}).get('section', '?')}",
                "category": h.get("metadata", {}).get("category"),
            }
            for h in result["hits"]
        ],
        "context": result["context"],
        "verification": ver.to_dict(),
        "prompt_for_llm": result["prompt"] if ver.action == "pass" else None,
        "message": (
            "Relevant policy passages retrieved and verified."
            if ver.action == "pass"
            else f"Retrieval verification failed: {ver.reason}"
        ),
    }


if __name__ == "__main__":
    ensure_index()
    r = search_policies("What is the minimum attendance percentage?")
    print(r["architecture_used"], r["verification"]["action"])
    for h in r["hits"]:
        print(f"  - {h['source']}: {h['text'][:80]}...")
