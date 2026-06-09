from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from .models import FileEntry

_CHUNK = 1 << 20  # 1 MiB


def compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def group_duplicates(entries: list[FileEntry]) -> None:
    """Ustawia content_hash i duplicate_of in-place. Hashuje tylko pliki
    o powtarzajacym sie rozmiarze (pre-filtr). Oryginal = pierwszy wg sciezki."""
    by_size: dict[int, list[FileEntry]] = defaultdict(list)
    for e in entries:
        by_size[e.size].append(e)

    seen: dict[str, FileEntry] = {}
    for group in by_size.values():
        if len(group) < 2:
            continue
        for e in sorted(group, key=lambda x: str(x.path)):
            e.content_hash = compute_hash(e.path)
            original = seen.get(e.content_hash)
            if original is None:
                seen[e.content_hash] = e
            else:
                e.duplicate_of = original.path
