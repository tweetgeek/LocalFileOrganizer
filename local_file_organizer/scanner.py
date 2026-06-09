from __future__ import annotations

import fnmatch
from pathlib import Path

from .config import Config
from .models import FileEntry


def _ignored(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def scan(config: Config) -> list[FileEntry]:
    src = config.source_dir.resolve()
    dst = config.dest_dir.resolve()
    entries: list[FileEntry] = []
    visited: set[Path] = set()

    def walk(directory: Path, depth: int) -> None:
        real = directory.resolve()
        if real in visited:
            return  # ochrona przed cyklami symlinkow
        visited.add(real)
        try:
            children = sorted(directory.iterdir())
        except PermissionError:
            return
        for child in children:
            if _ignored(child.name, config.ignore):
                continue
            if child.is_symlink() and not config.follow_symlinks:
                continue
            resolved = child.resolve()
            if resolved == dst or dst in resolved.parents:
                continue  # nie skanuj katalogu docelowego
            if child.is_dir():
                if config.recursive and depth < config.max_depth:
                    walk(child, depth + 1)
            elif child.is_file():
                try:
                    size = child.stat().st_size
                except OSError:
                    continue  # plik zniknal lub niedostepny -> pomijamy
                entries.append(
                    FileEntry(
                        path=child,
                        size=size,
                        ext=child.suffix.lstrip(".").lower(),
                    )
                )

    walk(src, 0)
    return entries
