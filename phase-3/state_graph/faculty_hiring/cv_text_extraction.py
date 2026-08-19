"""
Faculty Hiring — CV file -> raw_cv_text extraction.

This is the missing piece between "a real user uploads a CV file on the
platform" and "start_job()/add_cv() need a plain-text raw_cv_text string".

Nothing in the graph itself changes: ingest_cv_batch / parse_and_validate /
score_cv_against_qualifications all still only ever see plain text via
CandidateResult.raw_cv_text, exactly as before. This module is called ONCE,
by the platform's upload endpoint, before start_job()/add_cv() is invoked.

Supported formats: .pdf, .docx, .txt (most real CVs are one of these three).
Anything else is rejected with a clear error rather than silently mis-read.
"""

from __future__ import annotations

from pathlib import Path


class UnsupportedCVFormat(ValueError):
    """Raised when the uploaded file isn't a format we can safely extract text from."""


def extract_cv_text(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from an uploaded CV file.

    Args:
        file_bytes: raw bytes of the uploaded file (from the platform's
                    upload endpoint — e.g. FastAPI's `UploadFile.read()`).
        filename:   original filename, used only to pick the extractor by
                    extension.

    Returns:
        Extracted plain text, whitespace-normalized.

    Raises:
        UnsupportedCVFormat: extension isn't .pdf, .docx, or .txt.
        ValueError: the file is corrupt / unreadable / extracted to nothing
                    (an empty raw_cv_text would silently make every
                    qualification look MISSING — better to fail loudly here
                    than produce a garbage score downstream).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        text = _extract_pdf(file_bytes)
    elif ext == ".docx":
        text = _extract_docx(file_bytes)
    elif ext == ".txt":
        text = file_bytes.decode("utf-8", errors="replace")
    else:
        raise UnsupportedCVFormat(
            f"Unsupported CV file type '{ext}'. Accepted: .pdf, .docx, .txt"
        )

    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())

    if not text:
        raise ValueError(
            f"No extractable text found in '{filename}'. "
            "This is likely a scanned/image-only PDF (would need OCR, not "
            "supported here) or a corrupt file — reject the upload rather "
            "than silently creating a candidate with an empty CV."
        )

    return text


def _extract_pdf(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required for PDF CV uploads. Install with: "
            "pip install pypdf --break-system-packages"
        ) from exc

    import io

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is required for DOCX CV uploads. Install with: "
            "pip install python-docx --break-system-packages"
        ) from exc

    import io

    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs)
