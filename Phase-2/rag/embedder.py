"""
Brightpeak Academy — Embedder
==============================

Produces dense vectors for policy chunks. Separated from the vector
store so the embedding model can be swapped without touching HNSW
index logic.

Current backend: TF-IDF (sklearn) — deterministic, no API key, fast
for a policy corpus of this size. The public API (fit / encode) matches
what you would use with sentence-transformers or an embedding API, so
swapping later is a one-file change.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

RAG_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = RAG_DIR / "store" / "vectorizer.pkl"


class Embedder:
    """
    fit(texts)  → learn vocabulary / IDF from the corpus
    encode(texts) → return L2-normalised float32 matrix (n, dim)
    """

    def __init__(
        self,
        max_features: int = 4096,
        ngram_range: tuple[int, int] = (1, 2),
    ):
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.vectorizer: TfidfVectorizer | None = None
        self._dim: int | None = None

    def fit(self, texts: list[str]) -> "Embedder":
        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            stop_words="english",
            sublinear_tf=True,
        )
        self.vectorizer.fit(texts)
        self._dim = len(self.vectorizer.get_feature_names_out())
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.vectorizer is None:
            raise RuntimeError("Embedder not fitted. Call fit() first.")
        matrix = self.vectorizer.transform(texts).astype(np.float32).toarray()
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    @property
    def dim(self) -> int:
        if self._dim is None:
            raise RuntimeError("Embedder not fitted.")
        return self._dim

    def save(self, path: Path | str | None = None) -> None:
        path = Path(path) if path else DEFAULT_MODEL_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.vectorizer, f)

    def load(self, path: Path | str | None = None) -> "Embedder":
        path = Path(path) if path else DEFAULT_MODEL_PATH
        with open(path, "rb") as f:
            self.vectorizer = pickle.load(f)
        self._dim = len(self.vectorizer.get_feature_names_out())
        return self


if __name__ == "__main__":
    emb = Embedder()
    emb.fit(["Students must maintain 75% attendance.", "Scholarship requires 90% average."])
    vecs = emb.encode(["What is the attendance threshold?"])
    print(f"dim={emb.dim}, shape={vecs.shape}, norm={np.linalg.norm(vecs[0]):.3f}")
