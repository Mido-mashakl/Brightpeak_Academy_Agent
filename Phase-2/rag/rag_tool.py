"""
Brightpeak Academy — RAG Tool
==============================

MCP-facing RAG helpers for:

1. Policy retrieval
2. Course-material retrieval for the teaching assistant

The existing policy RAG is preserved.

Course-material retrieval is isolated using metadata filters:
    content_type = "course_material"
    course_id    = <requested course>

This prevents course questions from accidentally retrieving
policy documents or material from another course.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

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
    signals = [" and ", " also ", " as well ", " plus ", "both ", "relationship between" ,"difference between","compare ",]
    return any(signal in q for signal in signals) or q.count("?") > 1

def _run_retrieval(
    query: str,
    architecture: str,
    top_k: int,
    where: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Shared retrieval logic used by both policy and course-material RAG.
    """

    ensure_index()

    if architecture == "auto":
        architecture = "agentic" if _is_multipart(query) else "hybrid"

    if architecture == "agentic":
        return _agentic.run(query, where=where)

    if architecture == "graph":
        return _graph.run(query, where=where)

    if architecture == "naive":
        from naive_rag import NaiveRAG

        return NaiveRAG(_store, top_k=top_k).run(
            query,
            where=where,
        )

    # Default
    return _hybrid.run(query, where=where)


def _format_hits(
    hits: list[dict[str, Any]],
    content_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convert internal retrieval results into a stable public format.
    """

    formatted = []

    for hit in hits:
        metadata = hit.get("metadata", {})

        item = {
            "text": hit.get("document", "")[:1000],
            "score": round(float(hit.get("score", 0)), 3),
            "source": (
                f"{metadata.get('document_title', '?')} "
                f"§ {metadata.get('section', '?')}"
            ),
            "document_id": metadata.get("document_id"),
            "document_title": metadata.get("document_title"),
            "section": metadata.get("section"),
            "source_file": metadata.get("source_file"),
            "category": metadata.get("category"),
        }

        if content_type:
            item["content_type"] = content_type

        if "course_id" in metadata:
            item["course_id"] = metadata["course_id"]

        if "material_id" in metadata:
            item["material_id"] = metadata["material_id"]

        formatted.append(item)

    return formatted


def search_policies(
    query: str,
    architecture: str = "auto",
    top_k: int = 4,
    category: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve policy passages and run Self-RAG verification.

    architecture:
        "auto" | "naive" | "hybrid" | "agentic" | "graph"

    This function preserves the existing Phase-2 policy behavior.
    """

    where = {
        "content_type": "policy",
    }

    if category:
        where["category"] = category

    result = _run_retrieval(
        query=query,
        architecture=architecture,
        top_k=top_k,
        where=where,
    )

    passages = [
        h["document"]
        for h in result.get("hits", [])
    ]

    ver = _verifier.verify(
        query,
        passages,
    )

    return {
        "architecture_used": result.get(
            "architecture",
            architecture,
        ),
        "hits": _format_hits(
            result.get("hits", []),
            content_type="policy",
        ),
        "context": result.get("context", ""),
        "verification": ver.to_dict(),
        "prompt_for_llm": (
            result.get("prompt")
            if ver.action == "pass"
            else None
        ),
        "message": (
            "Relevant policy passages retrieved and verified."
            if ver.action == "pass"
            else f"Retrieval verification failed: {ver.reason}"
        ),
    }

def search_course_material(
    query: str,
    course_id: int | str,
    architecture: str = "auto",
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Retrieve course-material passages for a specific course.

    Parameters
    ----------
    query:
        Student's question.

    course_id:
        ID of the course whose material should be searched.

    architecture:
        "auto" | "naive" | "hybrid" | "agentic" | "graph"

    top_k:
        Number of relevant chunks to retrieve.

    Returns
    -------
    dict
        Retrieval results, Self-RAG verification, context,
        and an LLM-ready grounded prompt.

    Important:
        Retrieval is restricted to:

            content_type = "course_material"
            course_id = requested course_id

        This prevents cross-course retrieval.
    """

    where = {
        "content_type": "course_material",
        "course_id": course_id,
    }

    result = _run_retrieval(
        query=query,
        architecture=architecture,
        top_k=top_k,
        where=where,
    )

    hits = result.get("hits", [])

    passages = [
        h["document"]
        for h in hits
    ]

    # No relevant material found.
    if not passages:
        return {
            "architecture_used": result.get(
                "architecture",
                architecture,
            ),
            "course_id": course_id,
            "hits": [],
            "context": "",
            "verification": {
                "action": "reject",
                "reason": (
                    "No relevant course material was found "
                    "for the requested course."
                ),
            },
            "prompt_for_llm": None,
            "message": (
                "I couldn't find relevant information in the "
                "available course material."
            ),
        }

    # Verify that the retrieved material actually supports
    # answering the student's question.
    ver = _verifier.verify(
        query,
        passages,
    )

    return {
        "architecture_used": result.get(
            "architecture",
            architecture,
        ),
        "course_id": course_id,
        "hits": _format_hits(
            hits,
            content_type="course_material",
        ),
        "context": result.get("context", ""),
        "verification": ver.to_dict(),
        "prompt_for_llm": (
            result.get("prompt")
            if ver.action == "pass"
            else None
        ),
        "message": (
            "Relevant course material retrieved and verified."
            if ver.action == "pass"
            else (
                "The retrieved course material does not "
                "provide enough information to answer "
                "the student's question safely."
            )
        ),
    }



if __name__ == "__main__":
    ensure_index()

    print("=" * 70)
    print("POLICY RAG TEST")
    print("=" * 70)

    policy_result = search_policies(
        "What is the minimum attendance percentage?"
    )

    print(
        "Architecture:",
        policy_result["architecture_used"],
    )

    print(
        "Verification:",
        policy_result["verification"],
    )

    for hit in policy_result["hits"]:
        print(
            f"- {hit['source']} "
            f"(score={hit['score']}): "
            f"{hit['text'][:100]}"
        )

    print("\n" + "=" * 70)
    print("COURSE MATERIAL RAG TEST")
    print("=" * 70)

    course_result = search_course_material(
        query="What is a function in Python?",
        course_id=1,
    )

    print(
        "Architecture:",
        course_result["architecture_used"],
    )

    print(
        "Verification:",
        course_result["verification"],
    )

    for hit in course_result["hits"]:
        print(
            f"- {hit['source']} "
            f"(score={hit['score']}): "
            f"{hit['text'][:100]}"
        )

    print("\nMessage:")
    print(course_result["message"])

    result = search_course_material(
    "What is a function in Python?",
    course_id=1
)


