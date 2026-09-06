"""Paper-input boundary for the audit UI.

The Agent consumes text, never an opaque PDF object.  Keeping extraction here
makes the boundary explicit: the extracted text is shown to the user before it
reaches a model, and a missing PDF dependency stops with an actionable error
rather than silently sending no paper at all.
"""
from __future__ import annotations

from io import BytesIO


MAX_PAPER_CHARS = 120_000


def paper_text(payload: bytes, filename: str) -> str:
    """Decode an uploaded text/Markdown/PDF paper into bounded, non-empty text."""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
            raise ModuleNotFoundError(
                "PDF upload needs pypdf. Install it with: "
                "micromamba run -n verdict pip install pypdf") from exc
        reader = PdfReader(BytesIO(payload))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix in {"txt", "md", "markdown"}:
        text = payload.decode("utf-8", errors="replace")
    else:
        raise ValueError("upload a .txt, .md, or .pdf paper")
    text = text.strip()
    if not text:
        raise ValueError("no extractable text found in the uploaded paper")
    if len(text) > MAX_PAPER_CHARS:
        raise ValueError(
            f"paper text is {len(text):,} characters; limit is {MAX_PAPER_CHARS:,}. "
            "Upload the abstract, methods, and main-results sections, or a shorter text export.")
    return text
