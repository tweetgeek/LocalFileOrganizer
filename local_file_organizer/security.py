from __future__ import annotations

import zipfile
from pathlib import Path

_OFFICE = {"docx", "xlsx", "pptx"}


def detect_password(path: Path, ext: str, formats: list[str]) -> bool:
    """Best-effort: True jesli plik jest zaszyfrowany/chroniony haslem.
    Bledy detekcji traktujemy jako 'nie wiadomo' -> False."""
    if ext not in formats:
        return False
    try:
        if ext == "pdf":
            return _pdf_encrypted(path)
        if ext == "zip":
            return _zip_encrypted(path)
        if ext == "7z":
            return _sevenz_encrypted(path)
        if ext == "rar":
            return _rar_encrypted(path)
        if ext in _OFFICE:
            return _office_encrypted(path)
    except Exception:
        return False
    return False


def _pdf_encrypted(path: Path) -> bool:
    from pypdf import PdfReader

    return bool(PdfReader(str(path)).is_encrypted)


def _zip_encrypted(path: Path) -> bool:
    with zipfile.ZipFile(path) as zf:
        return any(info.flag_bits & 0x1 for info in zf.infolist())


def _sevenz_encrypted(path: Path) -> bool:
    import py7zr

    with py7zr.SevenZipFile(path) as z:
        return bool(z.needs_password())


def _rar_encrypted(path: Path) -> bool:
    import rarfile

    with rarfile.RarFile(path) as rf:
        return bool(rf.needs_password())


def _office_encrypted(path: Path) -> bool:
    import msoffcrypto

    with path.open("rb") as f:
        return bool(msoffcrypto.OfficeFile(f).is_encrypted())
