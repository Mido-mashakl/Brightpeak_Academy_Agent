"""
keyword_search.py
==================
Shared keyword search helper: BM25, no embeddings, no vector DB.

BM25 is the standard keyword-ranking algorithm search engines have used
for decades. It scores documents by term overlap with the query,
weighted by how rare/common each term is -- no embedding model, no API
key, nothing to install beyond `rank_bm25`.

Setup:
    pip install rank_bm25

Identical in shape to the lab template -- copied here so mcp_server/memory
is self-contained and doesn't reach outside its own folder.
"""

import re
from rank_bm25 import BM25Plus


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class KeywordStore:
    """Same shape as a vector store: upsert() to add records, query() to
    search -- just backed by BM25 instead of embeddings."""

    def __init__(self):
        self.rows = []          # [{"payload": ..., "metadata": ...}, ...]
        self._bm25 = None
        self._dirty = True

    def upsert(self, payload, metadata):
        self.rows.append({"payload": payload, "metadata": metadata})
        self._dirty = True

    def _rebuild_index(self):
        corpus = [tokenize(self._as_text(r["payload"])) for r in self.rows]
        self._bm25 = BM25Plus(corpus) if corpus else None
        self._dirty = False

    @staticmethod
    def _as_text(payload) -> str:
        if isinstance(payload, str):
            return payload
        return payload.get("event_summary") or payload.get("text") or str(payload)

    def query(self, query_text: str, top_k: int = 3, filter: dict | None = None):
        candidate_idxs = [
            i for i, r in enumerate(self.rows)
            if not filter or all(r["metadata"].get(k) == v for k, v in filter.items())
        ]
        if not candidate_idxs:
            return []

        if self._dirty:
            self._rebuild_index()
        if self._bm25 is None:
            return []

        tokens = tokenize(query_text)
        scores = self._bm25.get_scores(tokens)

        overlapping = {
            i for i in candidate_idxs
            if set(tokens) & set(tokenize(self._as_text(self.rows[i]["payload"])))
        }
        ranked = sorted(overlapping, key=lambda i: scores[i], reverse=True)
        return [self.rows[i] for i in ranked[:top_k]]
