"""
Brightpeak Academy — RAG Chunker
=================================

Splits policy and handbook documents into overlapping chunks suitable
for embedding and retrieval. Each chunk carries metadata that the
vector store will index for pre-filtering (document_id, section,
category, last_reviewed).

Chunking strategy:
  - Split on markdown headings first (keeps semantic units intact).
  - Further split long sections by paragraph / sentence boundary.
  - Overlap of ~50 tokens between consecutive chunks to avoid cutting
    mid-sentence facts that a query might need.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "documents"

COURSE_MATERIALS_DIR = DOCUMENTS_DIR / "course_materials"

COURSE_METADATA = {
    "python/basics.md": {
        "course_id": 1,
        "course_name": "Introduction to Python",
        "material_id": 1,
    },
    "python/variables.md": {
        "course_id": 1,
        "course_name": "Introduction to Python",
        "material_id": 2,
    },
    "python/functions.md": {
        "course_id": 1,
        "course_name": "Introduction to Python",
        "material_id": 3,
    },
    "data_structures/arrays.md": {
        "course_id": 2,
        "course_name": "Data Structures & Algorithms",
        "material_id": 4,
    },
    "data_structures/linked_lists.md": {
        "course_id": 2,
        "course_name": "Data Structures & Algorithms",
        "material_id": 5,
    },
    "data_structures/stacks.md": {
        "course_id": 2,
        "course_name": "Data Structures & Algorithms",
        "material_id": 6,
    },
}


@dataclass
class Chunk:
    chunk_id: str
    text: str
    document_id: str
    document_title: str
    section: str
    category: str
    last_reviewed: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "section": self.section,
            "category": self.category,
            "last_reviewed": self.last_reviewed,
            "metadata": self.metadata,
        }


def _stable_id(text: str, document_id: str, idx: int) -> str:
    h = hashlib.sha1(f"{document_id}:{idx}:{text[:80]}".encode()).hexdigest()[:12]
    return f"{document_id}-{idx}-{h}"


def _extract_header_meta(raw: str) -> dict:
    """Pull Document ID, Last Reviewed, category-ish fields from the header."""
    meta = {}
    m = re.search(r"\*\*Document ID:\*\*\s*(.+)", raw)
    if m:
        meta["document_id"] = m.group(1).strip()
    m = re.search(r"\*\*Last Reviewed:\*\*\s*(.+)", raw)
    if m:
        meta["last_reviewed"] = m.group(1).strip()
    m = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
    if m:
        meta["document_title"] = m.group(1).strip()
    # Infer category from title keywords
    title = meta.get("document_title", "").lower()
    if "attendance" in title:
        meta["category"] = "Attendance"
    elif "scholarship" in title:
        meta["category"] = "Scholarship"
    elif "integrity" in title:
        meta["category"] = "Academic Integrity"
    elif "late" in title or "submission" in title:
        meta["category"] = "Late Submission"
    elif "withdrawal" in title:
        meta["category"] = "Course Withdrawal"
    elif "exam" in title or "assessment" in title:
        meta["category"] = "Examination"
    elif "handbook" in title:
        meta["category"] = "Handbook"
    else:
        meta["category"] = "General"
    return meta


def _split_into_sections(raw: str) -> list[tuple[str, str]]:
    """Return list of (section_heading, section_body)."""
    parts = re.split(r"(?=^##\s+)", raw, flags=re.MULTILINE)
    sections = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n", 1)
        heading = lines[0].lstrip("# ").strip() if lines[0].startswith("#") else "Introduction"
        body = lines[1].strip() if len(lines) > 1 else part
        sections.append((heading, body))
    return sections


def _chunk_text(text: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
    """Greedy paragraph-aware splitter with character overlap."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # If a single paragraph is huge, hard-split it
            if len(para) > max_chars:
                start = 0
                while start < len(para):
                    end = start + max_chars
                    chunks.append(para[start:end].strip())
                    start = end - overlap
            else:
                current = para
    if current:
        chunks.append(current)

    # Add overlap from previous chunk
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append((prev_tail + " " + chunks[i]).strip())
        chunks = overlapped
    return chunks


def chunk_document(path: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(DOCUMENTS_DIR).as_posix()
    course_meta = COURSE_METADATA.get(relative_path)
    header_meta = _extract_header_meta(raw)
    document_id = header_meta.get("document_id", path.stem)
    document_title = header_meta.get("document_title", path.stem)
    category = header_meta.get("category", "General")
    last_reviewed = header_meta.get("last_reviewed")

    sections = _split_into_sections(raw)
    all_chunks: list[Chunk] = []
    idx = 0
    for section_heading, body in sections:
        for piece in _chunk_text(body):
            if len(piece) < 40:  # skip tiny fragments
                continue
            cid = _stable_id(piece, document_id, idx)
            all_chunks.append(
                Chunk(
                    chunk_id=cid,
                    text=piece,
                    document_id=document_id,
                    document_title=document_title,
                    section=section_heading,
                    category=category,
                    last_reviewed=last_reviewed,
                    metadata={
    "source_file": str(path.relative_to(DOCUMENTS_DIR)),
    "content_type": "course_material" if course_meta else "policy",
    **(course_meta or {}),
},
                )
            )
            idx += 1
    return all_chunks


def chunk_all_documents(docs_dir: Path | None = None) -> list[Chunk]:
    docs_dir = docs_dir or DOCUMENTS_DIR
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(chunk_document(path))
    return chunks


if __name__ == "__main__":
    chunks = chunk_all_documents()
    print(f"Total chunks: {len(chunks)}")
    for c in chunks[:3]:
        print(f"  [{c.chunk_id}] {c.category} / {c.section} — {c.text[:80]}...")
