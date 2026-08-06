"""
Brightpeak Academy — RAG Ingestion Pipeline
============================================

One-shot (or re-runnable) pipeline:
  documents/*.md  →  chunker  →  VectorStore.upsert

Run:
    python -m rag.ingestion
or:
    python rag/ingestion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

from chunker import chunk_all_documents  # noqa: E402
from vector_db import VectorStore  # noqa: E402


def ingest(reset: bool = True) -> VectorStore:
    store = VectorStore()
    if reset:
        store.reset()

    chunks = chunk_all_documents()
    if not chunks:
        raise RuntimeError("No chunks produced — check documents/ folder")

    store.upsert(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "document_id": c.document_id,
                "document_title": c.document_title,
                "section": c.section,
                "category": c.category,
                "last_reviewed": c.last_reviewed or "",
                "source_file": c.metadata.get("source_file", ""),
            }
            for c in chunks
        ],
    )
    print(f"[ingestion] Indexed {store.count()} chunks from {len({c.document_id for c in chunks})} documents")
    return store


if __name__ == "__main__":
    ingest(reset=True)
