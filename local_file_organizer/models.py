from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Reason(str, Enum):
    BASE = "base"            # tryb bazowy (type/category)
    DUPLICATE = "duplicate"  # kwarantanna duplikatu
    UNSORTED = "unsorted"    # brak dopasowania


@dataclass
class FileEntry:
    path: Path
    size: int
    ext: str  # bez kropki, lowercase
    content_hash: str | None = None
    is_encrypted: bool = False
    encrypted_format: str | None = None
    duplicate_of: Path | None = None  # jesli duplikat -> sciezka oryginalu


@dataclass
class PlannedMove:
    source: Path
    dest: Path
    reason: Reason
    category: str | None = None
    note: str | None = None


@dataclass
class Plan:
    moves: list[PlannedMove] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)  # (sciezka, powod)
    errors: list[tuple[Path, str]] = field(default_factory=list)
