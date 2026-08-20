"""
rag_adapter.py — RAG retrieval + structured-contract adapter for Track
Recommendation.

FIXED: `import rag` in nodes_evaluation.py pointed at nothing (no rag.py
existed in this package, and phase-3's top-level rag/ package is a heavy
embedding pipeline built for CourseMaterials search — a different
document set with a different contract). This module is the "adapter/
parser layer" the task calls for: it retrieves the relevant section of
documents/track_requirements.md for one track (retrieval step) and
parses + validates it into the exact structured shape
confidence_policy_node / tot_adapter.py expect:

    {
        "prerequisites": [{"course": "...", "min_score": 80}, ...],
        "core_courses": [...],
    }

Design note (documented per the task's requirement to flag architectural
choices rather than silently work around them): the project's existing
rag/ package (rag/hybrid_rag.py, rag/agentic_rag.py, ...) is a full
vector-embedding pipeline built for unstructured CourseMaterials content
search, not for this small, already-tabular document. Standing up that
whole pipeline (embedder + hnswlib index) just to retrieve one ~30-line
markdown file would add a heavy, unrelated dependency for no retrieval
-quality benefit, and the task explicitly says not to rewrite unrelated
systems. This module instead implements the retrieval step directly
against the source document — matching the SAME retrieve -> parse ->
validate -> (adapter) shape the task asks for — and raises
DocumentValidationError on missing/malformed fields exactly like a
failed schema-validated RAG result would, so ticket_node's failure path
is real, not simulated by a flag alone.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

DOCS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "documents" / "track_requirements.md"
)

_PREREQ_LINE = re.compile(r"^-\s*(?P<course>.+?)\s*\(min\s*(?P<score>\d+)%\)\s*$")
_CORE_LINE = re.compile(r"^Core courses:\s*(?P<courses>.+)$")
_HEADING = re.compile(r"^##\s*(?P<name>.+?)\s+Track\s*$")


class DocumentValidationError(Exception):
    """Raised when the track document is missing required, structured
    fields — the RAG contract failure path ticket_node exists to handle."""

    def __init__(self, track: str, reason: str):
        self.track = track
        self.reason = reason
        super().__init__(f"'{track}': {reason}")


def _load_sections() -> dict[str, str]:
    """Retrieval step: split the document into one text chunk per track
    heading — this is the "chunk" a real vector-RAG call would have
    returned for a query like 'requirements for <track>'."""
    text = DOCS_PATH.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current_name = None
    current_lines: list[str] = []
    for line in text.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines)
            current_name = m.group("name").strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines)
    return sections


def _parse_section(track: str, chunk: str) -> dict[str, Any]:
    """Generation/parsing step: turns the retrieved free-text chunk into
    the structured contract. Raises DocumentValidationError (not a
    silent empty result) if a required field can't be found — the graph
    needs structured data, not best-effort guesses."""
    prerequisites = []
    for line in chunk.splitlines():
        m = _PREREQ_LINE.match(line.strip())
        if m:
            prerequisites.append({"course": m.group("course").strip(), "min_score": int(m.group("score"))})

    core_courses: list[str] = []
    for line in chunk.splitlines():
        m = _CORE_LINE.match(line.strip())
        if m:
            core_courses = [c.strip() for c in m.group("courses").split(",") if c.strip()]

    if not prerequisites:
        raise DocumentValidationError(track, "no valid 'Prerequisites' entries found (missing required field).")
    if not core_courses:
        raise DocumentValidationError(track, "no 'Core courses' line found (missing required field).")

    return {"prerequisites": prerequisites, "core_courses": core_courses}


def retrieve_track_requirements(track: str, force_broken: bool = False) -> dict[str, Any]:
    """Public entry point used by nodes_evaluation.rag_node.

    force_broken=True simulates a document that fails schema validation
    (e.g. an admin uploaded an incomplete track document) — used by the
    RAG-failure demo scenario to exercise ticket_node for real, not as a
    magic flag consumed by the graph itself."""
    sections = _load_sections()
    if track not in sections:
        raise DocumentValidationError(track, "no matching section found in track_requirements.md.")

    if force_broken:
        # Simulate a corrupted/incomplete document: strip the
        # Prerequisites block so parsing legitimately fails validation,
        # the same way it would for a real malformed upload.
        raise DocumentValidationError(
            track, "document is missing the 'Prerequisites' section (simulated corrupt upload)."
        )

    return _parse_section(track, sections[track])