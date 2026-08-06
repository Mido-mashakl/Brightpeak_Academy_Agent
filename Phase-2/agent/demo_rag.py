"""
Brightpeak Academy — RAG Demo (Farida)
=======================================

Demonstrates every retrieval concern firing:

  1. Ingestion + vector store with metadata filter
  2. Naive RAG answering a general question
  3. Hybrid Search answering a citation-heavy question (Protocol 4.2b)
  4. Agentic RAG answering a multi-part question
  5. Graph RAG answering a relationship question
  6. Self-RAG verification catching an unsupported answer
  7. Self-RAG verification passing a grounded answer
"""

from __future__ import annotations

import sys
from pathlib import Path

PHASE2 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PHASE2 / "rag"))

from ingestion import ingest
from naive_rag import NaiveRAG
from hybrid_rag import HybridRAG
from agentic_rag import AgenticRAG
from graph_rag import GraphRAG
from self_rag import SelfRAGVerifier
from rag_tool import search_policies, ensure_index


def main():
    print("=" * 60)
    print("Brightpeak Academy — RAG Demo")
    print("=" * 60)

    print("\n[1] Ingesting policy corpus into HNSW vector store...")
    store = ingest(reset=True)
    print(f"    Indexed {store.count()} chunks")

    # Metadata filter demo
    hits = store.query("attendance", top_k=2, where={"category": "Attendance"})
    print(f"    Metadata filter (category=Attendance) returned {len(hits)} hits")

    print("\n[2] Naive RAG — general question")
    naive = NaiveRAG(store)
    r = naive.run("What is the minimum attendance percentage?")
    print(f"    Hits: {len(r['hits'])}")
    print(f"    Top source: {r['hits'][0]['metadata'].get('document_title') if r['hits'] else 'none'}")

    print("\n[3] Hybrid Search — citation question (Protocol 4.2b)")
    hybrid = HybridRAG(store)
    r = hybrid.run("What does Protocol 4.2b say about special examination arrangements?")
    print(f"    Hits: {len(r['hits'])}")
    for h in r["hits"][:2]:
        print(f"    - score={h['score']:.3f} vec={h.get('vector_score',0):.3f} bm25={h.get('bm25_score',0):.3f}")

    print("\n[4] Agentic RAG — multi-part question")
    agentic = AgenticRAG(store)
    r = agentic.run(
        "For a student below 75% attendance who also wants a scholarship, what do the policies say?"
    )
    print(f"    Hops used: {r.get('hops_used')}")
    print(f"    Hits: {len(r['hits'])}")

    print("\n[5] Graph RAG (bonus) — relationship question")
    graph = GraphRAG(store)
    r = graph.run("Explain the relationship between the attendance threshold and examination eligibility")
    print(f"    Matched nodes: {r.get('matched_nodes')}")
    print(f"    Hits: {len(r['hits'])}")

    print("\n[6] Self-RAG — should REFUSE (unsupported answer)")
    v = SelfRAGVerifier()
    passages = ["Students must maintain at least 75% attendance."]
    bad = v.verify("What is the attendance threshold?", passages, "The minimum is 40% and free pizza is provided.")
    print(f"    action={bad.action}  reason={bad.reason}")

    print("\n[7] Self-RAG — should PASS (grounded answer)")
    good = v.verify("What is the attendance threshold?", passages, "The minimum attendance is 75%.")
    print(f"    action={good.action}  reason={good.reason}")

    print("\n[8] Unified search_policies() helper (auto architecture)")
    ensure_index()
    out = search_policies("What is the late submission penalty after 2 days?")
    print(f"    architecture={out['architecture_used']}  verification={out['verification']['action']}")
    print(f"    message={out['message']}")

    print("\n" + "=" * 60)
    print("RAG demo complete — all concerns exercised.")
    print("=" * 60)


if __name__ == "__main__":
    main()
