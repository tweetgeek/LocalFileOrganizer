from __future__ import annotations

from ..config import Config


def resolve_base(ext: str, config: Config) -> str | None:
    """Zwraca nazwe folderu bazowego dla rozszerzenia albo None (-> unsorted)."""
    if not ext:
        return None
    if config.mode == "type":
        return ext
    for category, exts in config.categories.items():
        if ext in {e.lower() for e in exts}:
            return category
    return None
