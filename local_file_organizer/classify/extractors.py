from __future__ import annotations

import logging
from pathlib import Path

# pypdf loguje ostrzezenia (WARNING) dla uszkodzonych/nie-PDF plikow; nasz kod
# i tak je obsluguje (zwraca None), wiec wyciszamy ten szum na konsoli.
logging.getLogger("pypdf").setLevel(logging.ERROR)

_PLAIN = {"txt", "md", "csv", "log"}


def extract_text(path: Path, ext: str, max_chars: int) -> str | None:
    """Zwraca fragment tekstu (do max_chars) albo None, jesli sie nie da."""
    try:
        if ext in _PLAIN:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        if ext == "pdf":
            return _extract_pdf(path, max_chars)
        if ext == "docx":
            return _extract_docx(path, max_chars)
    except Exception:
        return None
    return None


def _extract_pdf(path: Path, max_chars: int) -> str | None:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        return None
    chunks: list[str] = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        chunks.append(text)
        total += len(text)
        if total >= max_chars:
            break
    joined = "\n".join(chunks).strip()
    return joined[:max_chars] if joined else None


def _extract_docx(path: Path, max_chars: int) -> str | None:
    import docx

    document = docx.Document(str(path))
    joined = "\n".join(p.text for p in document.paragraphs).strip()
    return joined[:max_chars] if joined else None
