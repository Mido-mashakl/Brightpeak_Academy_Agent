"""
Deterministic tests for the RAG pipeline core components:
vector store, naive RAG retrieval, and Self-RAG verification.

Uses a small fixed corpus (not the real policy documents) so results
are reproducible and don't depend on document content changing.
"""

import sys
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(RAG_DIR))

import pytest
from vector_db import VectorStore
from naive_rag import NaiveRAG
from self_rag import SelfRAGVerifier


FIXTURE_DOCS = [
    {
        "id": "doc-attendance-1",
        "text": "Students must maintain at least 75% attendance to be eligible for final exams.",
        "meta": {"document_title": "Attendance Policy", "section": "Eligibility", "category": "Attendance"},
    },
    {
        "id": "doc-scholarship-1",
        "text": "Scholarship renewal requires a minimum GPA of 3.0 and no academic integrity violations.",
        "meta": {"document_title": "Scholarship Policy", "section": "Renewal", "category": "Scholarship"},
    },
    {
        "id": "doc-integrity-1",
        "text": "A first academic integrity violation results in a warning and mandatory ethics workshop.",
        "meta": {"document_title": "Academic Integrity Policy", "section": "Sanctions", "category": "Integrity"},
    },
]


@pytest.fixture
def store(tmp_path):
    """A fresh, isolated VectorStore seeded with the fixed fixture corpus."""
    vs = VectorStore(persist_dir=tmp_path / "test_store")
    vs.upsert(
        ids=[d["id"] for d in FIXTURE_DOCS],
        documents=[d["text"] for d in FIXTURE_DOCS],
        metadatas=[d["meta"] for d in FIXTURE_DOCS],
    )
    return vs


def test_vector_store_indexes_all_documents(store):
    assert store.count() == len(FIXTURE_DOCS)


def test_vector_store_retrieves_relevant_document(store):
    hits = store.query("What is the minimum attendance percentage?", top_k=1)
    assert len(hits) == 1
    assert hits[0]["metadata"]["category"] == "Attendance"


def test_vector_store_metadata_filter_excludes_other_categories(store):
    hits = store.query("policy", top_k=5, where={"category": "Scholarship"})
    assert all(h["metadata"]["category"] == "Scholarship" for h in hits)


def test_naive_rag_returns_grounded_context(store):
    rag = NaiveRAG(store, top_k=2)
    result = rag.run("What GPA is required to keep a scholarship?")
    assert result["architecture"] == "naive_rag"
    assert "3.0" in result["context"]


def test_self_rag_passes_supported_answer():
    verifier = SelfRAGVerifier()
    passages = ["Students must maintain at least 75% attendance."]
    result = verifier.verify(
        query="What is the attendance threshold?",
        passages=passages,
        answer="The minimum attendance is 75%.",
    )
    assert result.action == "pass"
    assert result.is_supported is True


def test_self_rag_refuses_unsupported_answer():
    verifier = SelfRAGVerifier()
    passages = ["Students must maintain at least 75% attendance."]
    result = verifier.verify(
        query="What is the attendance threshold?",
        passages=passages,
        answer="The minimum is 40% and free pizza is provided.",
    )
    assert result.action == "refuse"
    assert result.is_supported is False


def test_self_rag_refuses_irrelevant_passages():
    verifier = SelfRAGVerifier()
    passages = ["The cafeteria menu changes every Monday."]
    result = verifier.verify(
        query="What is the attendance threshold?",
        passages=passages,
    )
    assert result.action == "refuse"
    assert result.is_relevant is False