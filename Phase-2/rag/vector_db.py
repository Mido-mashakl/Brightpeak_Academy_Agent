"""
Brightpeak Academy — Vector Database
=====================================

Real vector store (not a list of floats in a dict) with:
  - ANN index via HNSW (hnswlib)
  - Metadata payload store
  - Metadata index that filters *before* similarity search

Uses rag/embedder.py for vectors. The interface (upsert / query with
metadata filter) is identical to what you would use with Chroma or Qdrant,
so swapping the backend later is a one-file change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import hnswlib
import numpy as np

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

from embedder import Embedder  # noqa: E402

DEFAULT_PERSIST = RAG_DIR / "store"


class VectorStore:
    """
    ANN vector store with metadata filtering.

    Public API mirrors common vector-DB shapes:
        upsert(ids, documents, metadatas, embeddings=None)
        query(query_text, top_k, where=None) -> list[dict]
    """

    def __init__(
        self,
        persist_dir: Path | str | None = None,
        space: str = "cosine",
        ef_construction: int = 200,
        M: int = 16,
    ):
        self.persist_dir = Path(persist_dir) if persist_dir else DEFAULT_PERSIST
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.space = space
        self.ef_construction = ef_construction
        self.M = M

        self.embedder = Embedder()
        self.index: hnswlib.Index | None = None
        self.ids: list[str] = []
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        self._id_to_row: dict[str, int] = {}
        self._dim: int | None = None

        self._load()

    def _paths(self):
        return {
            "embedder": self.persist_dir / "vectorizer.pkl",
            "index": self.persist_dir / "hnsw.bin",
            "payload": self.persist_dir / "payload.json",
        }

    def _load(self):
        paths = self._paths()
        if not paths["payload"].exists():
            return
        with open(paths["payload"], "r", encoding="utf-8") as f:
            payload = json.load(f)
        self.ids = payload["ids"]
        self.documents = payload["documents"]
        self.metadatas = payload["metadatas"]
        self._id_to_row = {i: r for r, i in enumerate(self.ids)}
        if paths["embedder"].exists():
            self.embedder.load(paths["embedder"])
            self._dim = self.embedder.dim
            self.index = hnswlib.Index(space=self.space, dim=self._dim)
            self.index.load_index(str(paths["index"]))
            self.index.set_ef(50)

    def persist(self):
        paths = self._paths()
        with open(paths["payload"], "w", encoding="utf-8") as f:
            json.dump(
                {"ids": self.ids, "documents": self.documents, "metadatas": self.metadatas},
                f,
                ensure_ascii=False,
            )
        if self.embedder.vectorizer is not None:
            self.embedder.save(paths["embedder"])
        if self.index is not None:
            self.index.save_index(str(paths["index"]))

    def _rebuild_index(self, vectors: np.ndarray):
        n, dim = vectors.shape
        self._dim = dim
        self.index = hnswlib.Index(space=self.space, dim=dim)
        self.index.init_index(
            max_elements=max(n, 100),
            ef_construction=self.ef_construction,
            M=self.M,
        )
        self.index.add_items(vectors, list(range(n)))
        self.index.set_ef(50)

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        embeddings: Optional[list[list[float]]] = None,
    ):
        """Add or replace documents. Rebuilds the full index (fine for lab corpus size)."""
        assert len(ids) == len(documents) == len(metadatas)

        for i, doc_id in enumerate(ids):
            if doc_id in self._id_to_row:
                row = self._id_to_row[doc_id]
                self.documents[row] = documents[i]
                self.metadatas[row] = metadatas[i]
            else:
                self._id_to_row[doc_id] = len(self.ids)
                self.ids.append(doc_id)
                self.documents.append(documents[i])
                self.metadatas.append(metadatas[i])

        self.embedder.fit(self.documents)
        dense = self.embedder.encode(self.documents)
        self._rebuild_index(dense)
        self.persist()

    def _matches_filter(self, meta: dict, where: dict | None) -> bool:
        if not where:
            return True
        for key, expected in where.items():
            actual = meta.get(key)
            if isinstance(expected, dict):
                if "$eq" in expected and actual != expected["$eq"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
            else:
                if actual != expected:
                    return False
        return True

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        if self.index is None or self.embedder.vectorizer is None or not self.ids:
            return []

        candidate_idxs = [
            i for i, m in enumerate(self.metadatas) if self._matches_filter(m, where)
        ]
        if not candidate_idxs:
            return []

        q = self.embedder.encode([query_text])

        k_search = min(max(top_k * 10, top_k), len(self.ids))
        labels, distances = self.index.knn_query(q, k=k_search)
        labels = labels[0]
        distances = distances[0]

        candidate_set = set(candidate_idxs)
        results = []
        for label, dist in zip(labels, distances):
            if int(label) not in candidate_set:
                continue
            score = 1.0 - float(dist) if self.space == "cosine" else float(dist)
            results.append(
                {
                    "id": self.ids[int(label)],
                    "document": self.documents[int(label)],
                    "metadata": self.metadatas[int(label)],
                    "score": score,
                }
            )
            if len(results) >= top_k:
                break

        if len(results) < top_k and candidate_idxs:
            scored = []
            for i in candidate_idxs:
                vec = self.embedder.encode([self.documents[i]])
                sim = float(np.dot(q, vec.T)[0, 0])
                scored.append((sim, i))
            scored.sort(reverse=True)
            seen = {r["id"] for r in results}
            for sim, i in scored:
                if self.ids[i] in seen:
                    continue
                results.append(
                    {
                        "id": self.ids[i],
                        "document": self.documents[i],
                        "metadata": self.metadatas[i],
                        "score": sim,
                    }
                )
                if len(results) >= top_k:
                    break

        return results

    def count(self) -> int:
        return len(self.ids)

    def reset(self):
        self.ids = []
        self.documents = []
        self.metadatas = []
        self._id_to_row = {}
        self.embedder = Embedder()
        self.index = None
        for p in self._paths().values():
            if p.exists():
                p.unlink()


if __name__ == "__main__":
    from chunker import chunk_all_documents

    store = VectorStore()
    store.reset()
    chunks = chunk_all_documents()
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
            }
            for c in chunks
        ],
    )
    print(f"Indexed {store.count()} chunks")
    hits = store.query("What is the minimum attendance percentage?", top_k=3)
    for h in hits:
        print(f"  score={h['score']:.3f}  [{h['metadata']['category']}] {h['document'][:90]}...")
