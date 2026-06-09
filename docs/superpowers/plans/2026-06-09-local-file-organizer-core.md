# Local File Organizer — rdzeń (Plan 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować działające narzędzie CLI `lfo`, które skanuje katalog, wykrywa duplikaty i pliki zabezpieczone hasłem, klasyfikuje pliki trybem bazowym (type/category), planuje i (po `--apply`) wykonuje przeniesienia z możliwością cofnięcia oraz generuje raport.

**Architecture:** Modularny potok `scan → analyze → plan → apply → report`. Każdy etap to osobny moduł. „Plan" to serializowalny obiekt: dry-run go wypisuje, `--apply` wykonuje ten sam Plan. Undo log w SQLite umożliwia cofnięcie. Klasyfikacja AI jest celowo poza tym planem (Plan 2) — config może już zawierać sekcję `ai:`, jest ignorowana.

**Tech Stack:** Python 3.13, Typer (CLI), pydantic v2 (config), PyYAML, rich (raport), pypdf/py7zr/rarfile/msoffcrypto-tool (detekcja haseł), sqlite3 (undo log), pytest (testy).

**Spec:** `docs/superpowers/specs/2026-06-09-local-file-organizer-design.md`

---

## Struktura plików (Plan 1)

```
pyproject.toml                       # metadane, zależności, entry point `lfo`
local_file_organizer/
  __init__.py
  models.py        # FileEntry, PlannedMove, Plan, Reason
  config.py        # modele pydantic, load_config, walidacja
  scanner.py       # scan() → FileEntry[]
  hashing.py       # compute_hash, group_duplicates
  security.py      # detect_password
  classify/
    __init__.py
    base.py        # resolve_base
  planner.py       # build_plan → Plan
  undo.py          # UndoStore (SQLite)
  executor.py      # apply_plan
  report.py        # build_summary, render_console, write_json
  cli.py           # Typer app: run, undo
tests/
  __init__.py
  conftest.py
  test_config.py
  test_scanner.py
  test_hashing.py
  test_security.py
  test_base.py
  test_planner.py
  test_undo_executor.py
  test_report.py
  test_cli.py
```

---

### Task 1: Scaffolding projektu

**Files:**
- Create: `pyproject.toml`
- Create: `local_file_organizer/__init__.py`
- Create: `local_file_organizer/classify/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Utwórz `pyproject.toml`**

```toml
[project]
name = "local-file-organizer"
version = "0.1.0"
description = "CLI do katalogowania i reorganizacji plikow na lokalnym dysku"
requires-python = ">=3.13"
dependencies = [
  "typer>=0.12",
  "pydantic>=2.6",
  "pyyaml>=6.0",
  "rich>=13.7",
  "pypdf>=4.0",
  "py7zr>=0.21",
  "rarfile>=4.1",
  "msoffcrypto-tool>=5.4",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
lfo = "local_file_organizer.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["local_file_organizer*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Utwórz puste pliki pakietów**

Utwórz `local_file_organizer/__init__.py` z treścią:

```python
__version__ = "0.1.0"
```

Utwórz `local_file_organizer/classify/__init__.py` (pusty) oraz `tests/__init__.py` (pusty).

- [ ] **Step 3: Napisz test dymny**

`tests/test_smoke.py`:

```python
import local_file_organizer


def test_package_imports():
    assert local_file_organizer.__version__ == "0.1.0"
```

- [ ] **Step 4: Zainstaluj zależności i uruchom test**

Run:
```bash
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest tests/test_smoke.py -v
```
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml local_file_organizer/ tests/
git commit -m "chore: scaffolding pakietu i konfiguracja pytest"
```

---

### Task 2: Modele danych

**Files:**
- Create: `local_file_organizer/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_models.py`:

```python
from pathlib import Path
from local_file_organizer.models import FileEntry, PlannedMove, Plan, Reason


def test_file_entry_defaults():
    e = FileEntry(path=Path("/a/b.pdf"), size=10, ext="pdf")
    assert e.content_hash is None
    assert e.is_encrypted is False
    assert e.duplicate_of is None


def test_plan_starts_empty():
    plan = Plan()
    assert plan.moves == []
    assert plan.skipped == []
    assert plan.errors == []


def test_planned_move_reason_enum():
    m = PlannedMove(source=Path("/a"), dest=Path("/b"), reason=Reason.BASE)
    assert m.reason.value == "base"
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.models)

- [ ] **Step 3: Zaimplementuj `models.py`**

```python
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
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/models.py tests/test_models.py
git commit -m "feat: modele danych (FileEntry, PlannedMove, Plan, Reason)"
```

---

### Task 3: Konfiguracja (pydantic + YAML)

**Files:**
- Create: `local_file_organizer/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_config.py`:

```python
import pytest
import yaml
from local_file_organizer.config import Config, load_config


def test_minimal_config_defaults(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    cfg = Config(source_dir=src, dest_dir=tmp_path / "out")
    assert cfg.mode == "category"
    assert cfg.recursive is True
    assert cfg.conflict == "rename"
    assert cfg.dedup.action == "quarantine"
    assert "pdf" in cfg.password_detection.formats


def test_source_dir_must_exist(tmp_path):
    with pytest.raises(ValueError):
        Config(source_dir=tmp_path / "nie_ma", dest_dir=tmp_path / "out")


def test_source_and_dest_must_differ(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    with pytest.raises(ValueError):
        Config(source_dir=src, dest_dir=src)


def test_extra_keys_ignored(tmp_path):
    # sekcja ai: jest ignorowana w Planie 1
    src = tmp_path / "src"
    src.mkdir()
    cfg = Config(source_dir=src, dest_dir=tmp_path / "out", ai={"enabled": True})
    assert cfg.source_dir == src


def test_load_config_from_yaml(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(
        yaml.safe_dump({
            "source_dir": str(src),
            "dest_dir": str(tmp_path / "out"),
            "mode": "type",
        }),
        encoding="utf-8",
    )
    cfg = load_config(yaml_path)
    assert cfg.mode == "type"
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.config)

- [ ] **Step 3: Zaimplementuj `config.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DedupConfig(BaseModel):
    method: Literal["hash"] = "hash"
    action: Literal["quarantine", "report_only"] = "quarantine"


class PasswordConfig(BaseModel):
    enabled: bool = True
    formats: list[str] = Field(
        default_factory=lambda: ["pdf", "zip", "7z", "rar", "docx", "xlsx"]
    )


class ReportConfig(BaseModel):
    format: list[Literal["console", "json", "md"]] = Field(
        default_factory=lambda: ["console"]
    )
    output: Path | None = None


class CacheConfig(BaseModel):
    enabled: bool = True
    path: Path = Path("./.lfo_cache.sqlite")


class Config(BaseModel):
    # extra='ignore' -> nieznane klucze (np. ai:) sa pomijane w Planie 1
    model_config = ConfigDict(extra="ignore")

    source_dir: Path
    dest_dir: Path
    mode: Literal["type", "category"] = "category"
    recursive: bool = True
    max_depth: int = 5
    ignore: list[str] = Field(default_factory=lambda: [".git", "node_modules"])
    follow_symlinks: bool = False
    categories: dict[str, list[str]] = Field(default_factory=dict)
    unknown_dir: str = "unsorted"
    duplicates_dir: str = "duplikaty"
    conflict: Literal["rename", "skip"] = "rename"
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    password_detection: PasswordConfig = Field(default_factory=PasswordConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)

    @field_validator("source_dir")
    @classmethod
    def _source_exists(cls, v: Path) -> Path:
        if not v.exists() or not v.is_dir():
            raise ValueError(f"source_dir nie istnieje lub nie jest katalogiem: {v}")
        return v

    @model_validator(mode="after")
    def _paths_differ(self) -> "Config":
        if self.source_dir.resolve() == self.dest_dir.resolve():
            raise ValueError("source_dir i dest_dir nie moga byc tym samym katalogiem")
        return self


def load_config(path: Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config(**data)
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/config.py tests/test_config.py
git commit -m "feat: konfiguracja pydantic + loader YAML z walidacja"
```

---

### Task 4: Skaner katalogu

**Files:**
- Create: `local_file_organizer/scanner.py`
- Test: `tests/test_scanner.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_scanner.py`:

```python
from local_file_organizer.config import Config
from local_file_organizer.scanner import scan


def _cfg(tmp_path, **kw):
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    return Config(source_dir=src, dest_dir=tmp_path / "out", **kw)


def test_scan_finds_top_level_files(tmp_path):
    cfg = _cfg(tmp_path)
    (cfg.source_dir / "a.pdf").write_text("x")
    (cfg.source_dir / "b.ZIP").write_text("x")
    entries = scan(cfg)
    names = sorted(e.path.name for e in entries)
    exts = sorted(e.ext for e in entries)
    assert names == ["a.pdf", "b.ZIP"]
    assert exts == ["pdf", "zip"]  # lowercase, bez kropki


def test_scan_respects_ignore(tmp_path):
    cfg = _cfg(tmp_path, ignore=[".git", "node_modules"])
    (cfg.source_dir / "keep.txt").write_text("x")
    junk = cfg.source_dir / "node_modules"
    junk.mkdir()
    (junk / "skip.txt").write_text("x")
    entries = scan(cfg)
    assert [e.path.name for e in entries] == ["keep.txt"]


def test_scan_respects_max_depth(tmp_path):
    cfg = _cfg(tmp_path, recursive=True, max_depth=1)
    deep = cfg.source_dir / "lvl1" / "lvl2"
    deep.mkdir(parents=True)
    (cfg.source_dir / "lvl1" / "ok.txt").write_text("x")   # depth 1 -> wewnatrz
    (deep / "too_deep.txt").write_text("x")                # depth 2 -> pominiete
    entries = scan(cfg)
    assert [e.path.name for e in entries] == ["ok.txt"]


def test_scan_excludes_dest_dir(tmp_path):
    # dest pod source nie powinien byc skanowany
    src = tmp_path / "src"
    src.mkdir()
    out = src / "out"
    out.mkdir()
    (out / "already.txt").write_text("x")
    (src / "new.txt").write_text("x")
    cfg = Config(source_dir=src, dest_dir=out)
    entries = scan(cfg)
    assert [e.path.name for e in entries] == ["new.txt"]
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_scanner.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.scanner)

- [ ] **Step 3: Zaimplementuj `scanner.py`**

```python
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

    def walk(directory: Path, depth: int) -> None:
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
                entries.append(
                    FileEntry(
                        path=child,
                        size=child.stat().st_size,
                        ext=child.suffix.lstrip(".").lower(),
                    )
                )

    walk(src, 0)
    return entries
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_scanner.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/scanner.py tests/test_scanner.py
git commit -m "feat: skaner katalogu (ignore, max_depth, symlinki, wykluczenie dest)"
```

---

### Task 5: Hashowanie i duplikaty

**Files:**
- Create: `local_file_organizer/hashing.py`
- Test: `tests/test_hashing.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_hashing.py`:

```python
from pathlib import Path
from local_file_organizer.hashing import compute_hash, group_duplicates
from local_file_organizer.models import FileEntry


def _entry(path: Path) -> FileEntry:
    return FileEntry(path=path, size=path.stat().st_size, ext=path.suffix.lstrip("."))


def test_compute_hash_matches_for_identical_content(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("identyczne")
    b = tmp_path / "b.txt"; b.write_text("identyczne")
    assert compute_hash(a) == compute_hash(b)


def test_group_duplicates_marks_later_copies(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("dup")
    b = tmp_path / "b.txt"; b.write_text("dup")
    c = tmp_path / "c.txt"; c.write_text("inny")
    entries = [_entry(a), _entry(b), _entry(c)]
    group_duplicates(entries)
    by_name = {e.path.name: e for e in entries}
    assert by_name["a.txt"].duplicate_of is None       # oryginal (pierwszy alfabetycznie)
    assert by_name["b.txt"].duplicate_of == a          # duplikat wskazuje na a
    assert by_name["c.txt"].duplicate_of is None        # unikalny


def test_group_duplicates_size_prefilter_skips_unique_sizes(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("krotki")
    b = tmp_path / "b.txt"; b.write_text("zdecydowanie dluzsza tresc")
    entries = [_entry(a), _entry(b)]
    group_duplicates(entries)
    # rozne rozmiary -> nie hashujemy, brak duplikatow
    assert all(e.duplicate_of is None for e in entries)
    assert all(e.content_hash is None for e in entries)
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_hashing.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.hashing)

- [ ] **Step 3: Zaimplementuj `hashing.py`**

```python
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
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_hashing.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/hashing.py tests/test_hashing.py
git commit -m "feat: hashowanie SHA-256 i grupowanie duplikatow z pre-filtrem rozmiaru"
```

---

### Task 6: Detekcja plików zabezpieczonych hasłem

**Files:**
- Create: `local_file_organizer/security.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_security.py`:

```python
import zipfile
from local_file_organizer import security
from local_file_organizer.security import detect_password


def test_unlisted_extension_returns_false(tmp_path):
    f = tmp_path / "a.txt"; f.write_text("x")
    assert detect_password(f, "txt", ["pdf", "zip"]) is False


def test_plain_zip_not_encrypted(tmp_path):
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("inside.txt", "jawne dane")
    assert detect_password(z, "zip", ["zip"]) is False


def test_detection_error_is_swallowed(tmp_path):
    # uszkodzony "pdf" nie powinien wywalic programu, tylko zwrocic False
    bad = tmp_path / "broken.pdf"; bad.write_text("to nie jest pdf")
    assert detect_password(bad, "pdf", ["pdf"]) is False


def test_pdf_dispatch_uses_detector(tmp_path, monkeypatch):
    f = tmp_path / "secret.pdf"; f.write_text("x")
    monkeypatch.setattr(security, "_pdf_encrypted", lambda p: True)
    assert detect_password(f, "pdf", ["pdf"]) is True
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_security.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.security)

- [ ] **Step 3: Zaimplementuj `security.py`**

```python
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
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_security.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/security.py tests/test_security.py
git commit -m "feat: detekcja plikow zabezpieczonych haslem (pdf/zip/7z/rar/office)"
```

---

### Task 7: Klasyfikacja bazowa (type/category)

**Files:**
- Create: `local_file_organizer/classify/base.py`
- Test: `tests/test_base.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_base.py`:

```python
from local_file_organizer.config import Config
from local_file_organizer.classify.base import resolve_base


def _cfg(tmp_path, **kw):
    src = tmp_path / "src"; src.mkdir(exist_ok=True)
    return Config(source_dir=src, dest_dir=tmp_path / "out", **kw)


def test_type_mode_returns_extension(tmp_path):
    cfg = _cfg(tmp_path, mode="type")
    assert resolve_base("pdf", cfg) == "pdf"


def test_category_mode_maps_extension(tmp_path):
    cfg = _cfg(tmp_path, mode="category",
               categories={"apps": ["zip", "dmg"], "3dprint": ["stl", "3mf"]})
    assert resolve_base("dmg", cfg) == "apps"
    assert resolve_base("stl", cfg) == "3dprint"


def test_category_mode_unmapped_returns_none(tmp_path):
    cfg = _cfg(tmp_path, mode="category", categories={"apps": ["zip"]})
    assert resolve_base("xyz", cfg) is None


def test_empty_extension_returns_none(tmp_path):
    cfg = _cfg(tmp_path, mode="type")
    assert resolve_base("", cfg) is None
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_base.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.classify.base)

- [ ] **Step 3: Zaimplementuj `classify/base.py`**

```python
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
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_base.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/classify/base.py tests/test_base.py
git commit -m "feat: klasyfikacja bazowa type/category"
```

---

### Task 8: Planer (budowa Planu)

**Files:**
- Create: `local_file_organizer/planner.py`
- Test: `tests/test_planner.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_planner.py`:

```python
from pathlib import Path
from local_file_organizer.config import Config
from local_file_organizer.models import FileEntry, Reason
from local_file_organizer.planner import build_plan


def _cfg(tmp_path, **kw):
    src = tmp_path / "src"; src.mkdir(exist_ok=True)
    return Config(source_dir=src, dest_dir=tmp_path / "out", **kw)


def _entry(tmp_path, name, **kw):
    p = tmp_path / "src" / name
    p.parent.mkdir(exist_ok=True)
    p.write_text("x")
    return FileEntry(path=p, size=1, ext=p.suffix.lstrip(".").lower(), **kw)


def test_category_move_goes_to_category_folder(tmp_path):
    cfg = _cfg(tmp_path, mode="category", categories={"apps": ["zip"]})
    e = _entry(tmp_path, "setup.zip")
    plan = build_plan([e], cfg)
    assert len(plan.moves) == 1
    m = plan.moves[0]
    assert m.reason == Reason.BASE
    assert m.dest == cfg.dest_dir / "apps" / "setup.zip"


def test_unmapped_goes_to_unsorted(tmp_path):
    cfg = _cfg(tmp_path, mode="category", categories={"apps": ["zip"]})
    e = _entry(tmp_path, "mystery.xyz")
    plan = build_plan([e], cfg)
    assert plan.moves[0].reason == Reason.UNSORTED
    assert plan.moves[0].dest == cfg.dest_dir / "unsorted" / "mystery.xyz"


def test_duplicate_goes_to_quarantine(tmp_path):
    cfg = _cfg(tmp_path, mode="type")
    original = _entry(tmp_path, "a.txt")
    dup = _entry(tmp_path, "b.txt", duplicate_of=original.path)
    plan = build_plan([original, dup], cfg)
    dup_move = [m for m in plan.moves if m.source == dup.path][0]
    assert dup_move.reason == Reason.DUPLICATE
    assert dup_move.dest.parent == cfg.dest_dir / "duplikaty"


def test_duplicate_report_only_is_skipped(tmp_path):
    cfg = _cfg(tmp_path, mode="type", dedup={"action": "report_only"})
    original = _entry(tmp_path, "a.txt")
    dup = _entry(tmp_path, "b.txt", duplicate_of=original.path)
    plan = build_plan([original, dup], cfg)
    assert all(m.source != dup.path for m in plan.moves)
    assert any(p == dup.path for p, _ in plan.skipped)


def test_name_conflict_rename(tmp_path):
    cfg = _cfg(tmp_path, mode="type")
    # dwa rozne pliki o tej samej nazwie w roznych podkatalogach
    a = _entry(tmp_path, "dir1/report.txt")
    b = _entry(tmp_path, "dir2/report.txt")
    plan = build_plan([a, b], cfg)
    dests = sorted(str(m.dest.name) for m in plan.moves)
    assert dests == ["report (1).txt", "report.txt"]


def test_name_conflict_skip(tmp_path):
    cfg = _cfg(tmp_path, mode="type", conflict="skip")
    a = _entry(tmp_path, "dir1/report.txt")
    b = _entry(tmp_path, "dir2/report.txt")
    plan = build_plan([a, b], cfg)
    assert len(plan.moves) == 1
    assert len(plan.skipped) == 1


def test_encrypted_note_present(tmp_path):
    cfg = _cfg(tmp_path, mode="type")
    e = _entry(tmp_path, "secret.pdf", is_encrypted=True, encrypted_format="pdf")
    plan = build_plan([e], cfg)
    assert "hasl" in plan.moves[0].note.lower()
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_planner.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.planner)

- [ ] **Step 3: Zaimplementuj `planner.py`**

```python
from __future__ import annotations

from pathlib import Path

from .classify.base import resolve_base
from .config import Config
from .models import FileEntry, Plan, PlannedMove, Reason


def _unique_dest(desired: Path, taken: set[Path]) -> Path:
    if desired not in taken and not desired.exists():
        return desired
    stem, suffix = desired.stem, desired.suffix
    i = 1
    while True:
        candidate = desired.with_name(f"{stem} ({i}){suffix}")
        if candidate not in taken and not candidate.exists():
            return candidate
        i += 1


def build_plan(entries: list[FileEntry], config: Config) -> Plan:
    plan = Plan()
    dest_root = config.dest_dir
    taken: set[Path] = set()

    for entry in entries:
        # 1. Duplikat -> kwarantanna albo tylko raport
        if entry.duplicate_of is not None:
            if config.dedup.action == "report_only":
                plan.skipped.append((entry.path, f"duplikat: {entry.duplicate_of}"))
                continue
            desired = dest_root / config.duplicates_dir / entry.path.name
            dest = _unique_dest(desired, taken)
            taken.add(dest)
            plan.moves.append(
                PlannedMove(
                    source=entry.path,
                    dest=dest,
                    reason=Reason.DUPLICATE,
                    note=f"duplikat: {entry.duplicate_of}",
                )
            )
            continue

        # 2. Folder bazowy
        category = resolve_base(entry.ext, config)
        if category is None:
            target_dir = dest_root / config.unknown_dir
            reason = Reason.UNSORTED
        else:
            target_dir = dest_root / category
            reason = Reason.BASE

        desired = target_dir / entry.path.name
        collision = desired in taken or desired.exists()
        if collision and config.conflict == "skip":
            plan.skipped.append((entry.path, "konflikt nazwy (skip)"))
            continue
        dest = _unique_dest(desired, taken)
        taken.add(dest)

        note = (
            f"zabezpieczony haslem ({entry.encrypted_format})"
            if entry.is_encrypted
            else None
        )
        plan.moves.append(
            PlannedMove(
                source=entry.path,
                dest=dest,
                reason=reason,
                category=category,
                note=note,
            )
        )

    return plan
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_planner.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/planner.py tests/test_planner.py
git commit -m "feat: planer (kategoria/unsorted, kwarantanna, konflikty, flaga hasla)"
```

---

### Task 9: Undo store i executor

**Files:**
- Create: `local_file_organizer/undo.py`
- Create: `local_file_organizer/executor.py`
- Test: `tests/test_undo_executor.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_undo_executor.py`:

```python
from pathlib import Path
from local_file_organizer.models import Plan, PlannedMove, Reason
from local_file_organizer.undo import UndoStore
from local_file_organizer.executor import apply_plan


def test_apply_moves_files_and_records_run(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    f = src / "a.txt"; f.write_text("dane")
    dest = tmp_path / "out" / "txt" / "a.txt"
    plan = Plan(moves=[PlannedMove(source=f, dest=dest, reason=Reason.BASE)])
    store = UndoStore(tmp_path / "db.sqlite")

    result = apply_plan(plan, store)

    assert dest.exists()
    assert not f.exists()
    assert result["moved"] == 1
    assert isinstance(result["run_id"], int)


def test_undo_restores_files_and_removes_empty_dirs(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    f = src / "a.txt"; f.write_text("dane")
    dest = tmp_path / "out" / "txt" / "a.txt"
    plan = Plan(moves=[PlannedMove(source=f, dest=dest, reason=Reason.BASE)])
    store = UndoStore(tmp_path / "db.sqlite")
    result = apply_plan(plan, store)

    undo_result = store.undo_run(result["run_id"])

    assert f.exists()
    assert f.read_text() == "dane"
    assert not dest.exists()
    assert not dest.parent.exists()  # pusty utworzony folder usuniety
    assert undo_result["restored"] == 1


def test_undo_last_resolves_latest_run(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    f = src / "a.txt"; f.write_text("dane")
    dest = tmp_path / "out" / "a.txt"
    plan = Plan(moves=[PlannedMove(source=f, dest=dest, reason=Reason.BASE)])
    store = UndoStore(tmp_path / "db.sqlite")
    apply_plan(plan, store)
    assert store.last_run_id() is not None
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_undo_executor.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.undo)

- [ ] **Step 3: Zaimplementuj `undo.py`**

```python
from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path


class UndoStore:
    def __init__(self, db_path: Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY, ts REAL, done INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS moves (run_id INTEGER, source TEXT, dest TEXT);
            CREATE TABLE IF NOT EXISTS dirs (run_id INTEGER, path TEXT);
            """
        )
        self.conn.commit()

    def start_run(self) -> int:
        cur = self.conn.execute("INSERT INTO runs (ts) VALUES (?)", (time.time(),))
        self.conn.commit()
        return int(cur.lastrowid)

    def record_move(self, run_id: int, source: Path, dest: Path) -> None:
        self.conn.execute(
            "INSERT INTO moves VALUES (?, ?, ?)", (run_id, str(source), str(dest))
        )
        self.conn.commit()

    def record_dir(self, run_id: int, path: Path) -> None:
        self.conn.execute("INSERT INTO dirs VALUES (?, ?)", (run_id, str(path)))
        self.conn.commit()

    def finish_run(self, run_id: int) -> None:
        self.conn.execute("UPDATE runs SET done = 1 WHERE id = ?", (run_id,))
        self.conn.commit()

    def last_run_id(self) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return int(row[0]) if row else None

    def undo_run(self, run_id: int) -> dict:
        moves = self.conn.execute(
            "SELECT source, dest FROM moves WHERE run_id = ?", (run_id,)
        ).fetchall()
        restored = 0
        for source, dest in moves:
            src_p, dst_p = Path(source), Path(dest)
            if dst_p.exists():
                src_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst_p), str(src_p))
                restored += 1
        dirs = [
            Path(r[0])
            for r in self.conn.execute(
                "SELECT path FROM dirs WHERE run_id = ?", (run_id,)
            ).fetchall()
        ]
        for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
            try:
                d.rmdir()  # usuwa tylko puste
            except OSError:
                pass
        self.conn.execute("DELETE FROM moves WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM dirs WHERE run_id = ?", (run_id,))
        self.conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        self.conn.commit()
        return {"restored": restored}
```

- [ ] **Step 4: Zaimplementuj `executor.py`**

```python
from __future__ import annotations

import shutil

from .models import Plan
from .undo import UndoStore


def apply_plan(plan: Plan, undo_store: UndoStore) -> dict:
    run_id = undo_store.start_run()
    moved = 0
    created_dirs: set = set()
    for move in plan.moves:
        try:
            parent = move.dest.parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
                if parent not in created_dirs:
                    created_dirs.add(parent)
                    undo_store.record_dir(run_id, parent)
            shutil.move(str(move.source), str(move.dest))
            undo_store.record_move(run_id, move.source, move.dest)
            moved += 1
        except Exception as exc:  # blad per plik -> log i kontynuuj
            plan.errors.append((move.source, str(exc)))
    undo_store.finish_run(run_id)
    return {"run_id": run_id, "moved": moved}
```

- [ ] **Step 5: Uruchom testy — mają przejść**

Run: `.venv/bin/python -m pytest tests/test_undo_executor.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add local_file_organizer/undo.py local_file_organizer/executor.py tests/test_undo_executor.py
git commit -m "feat: executor (move) + undo store w SQLite"
```

---

### Task 10: Raport i podsumowanie

**Files:**
- Create: `local_file_organizer/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_report.py`:

```python
import json
from pathlib import Path
from local_file_organizer.models import FileEntry, Plan, PlannedMove, Reason
from local_file_organizer.report import build_summary, human_size, write_json


def test_human_size_formats_units():
    assert human_size(0) == "0.0 B"
    assert human_size(1536) == "1.5 KB"


def test_build_summary_counts_and_bytes():
    src = Path("/src/a.zip")
    entries = [
        FileEntry(path=src, size=2048, ext="zip"),
        FileEntry(path=Path("/src/secret.pdf"), size=10, ext="pdf",
                  is_encrypted=True, encrypted_format="pdf"),
    ]
    plan = Plan(moves=[
        PlannedMove(source=src, dest=Path("/out/apps/a.zip"),
                    reason=Reason.BASE, category="apps"),
    ])
    summary = build_summary(plan, entries, applied=True)
    assert summary["moved_count"] == 1
    assert summary["moved_bytes"] == 2048
    assert summary["moved_human"] == "2.0 KB"
    assert len(summary["encrypted"]) == 1
    assert summary["applied"] is True


def test_write_json_roundtrip(tmp_path):
    summary = {"moved_count": 3, "moved_human": "1.0 KB"}
    out = tmp_path / "r.json"
    write_json(summary, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["moved_count"] == 3
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_report.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.report)

- [ ] **Step 3: Zaimplementuj `report.py`**

```python
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .models import FileEntry, Plan, Reason


def human_size(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def build_summary(plan: Plan, entries: list[FileEntry], applied: bool) -> dict:
    size_by_source = {e.path: e.size for e in entries}
    moved_bytes = sum(size_by_source.get(m.source, 0) for m in plan.moves)
    duplicates = sum(1 for m in plan.moves if m.reason == Reason.DUPLICATE)
    unsorted = sum(1 for m in plan.moves if m.reason == Reason.UNSORTED)
    encrypted = [e for e in entries if e.is_encrypted]
    per_folder = Counter(str(m.dest.parent) for m in plan.moves)
    return {
        "applied": applied,
        "moved_count": len(plan.moves),
        "moved_bytes": moved_bytes,
        "moved_human": human_size(moved_bytes),
        "duplicates": duplicates,
        "unsorted": unsorted,
        "encrypted": [(str(e.path), e.encrypted_format) for e in encrypted],
        "skipped": len(plan.skipped),
        "errors": len(plan.errors),
        "per_folder": dict(per_folder),
    }


def render_console(summary: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    verb = "Przeniesiono" if summary["applied"] else "Zostaloby przeniesione"
    table = Table(title="Local File Organizer — podsumowanie")
    table.add_column("Metryka")
    table.add_column("Wartosc", justify="right")
    table.add_row(verb, str(summary["moved_count"]))
    table.add_row("Rozmiar", summary["moved_human"])
    table.add_row("Duplikaty", str(summary["duplicates"]))
    table.add_row("Zabezpieczone haslem", str(len(summary["encrypted"])))
    table.add_row("Unsorted", str(summary["unsorted"]))
    table.add_row("Pominiete", str(summary["skipped"]))
    table.add_row("Bledy", str(summary["errors"]))
    console.print(table)
    if summary["encrypted"]:
        console.print("\n[bold]Pliki zabezpieczone haslem:[/bold]")
        for path, fmt in summary["encrypted"]:
            console.print(f"  - {path} ({fmt})")


def write_json(summary: dict, output: Path) -> None:
    Path(output).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

- [ ] **Step 4: Uruchom test — ma przejść**

Run: `.venv/bin/python -m pytest tests/test_report.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/report.py tests/test_report.py
git commit -m "feat: raport (podsumowanie, konsola rich, eksport JSON)"
```

---

### Task 11: CLI (Typer) — komendy `run` i `undo`

**Files:**
- Create: `local_file_organizer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_cli.py`:

```python
import yaml
from typer.testing import CliRunner
from local_file_organizer.cli import app

runner = CliRunner()


def _make_yaml(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "setup.zip").write_text("x")
    (src / "model.stl").write_text("x")
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(tmp_path / "out"),
        "mode": "category",
        "categories": {"apps": ["zip"], "3dprint": ["stl"]},
        "password_detection": {"enabled": False},
    }
    p = tmp_path / "lfo.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p, src, tmp_path / "out"


def test_run_dry_run_does_not_move(tmp_path):
    yaml_path, src, out = _make_yaml(tmp_path)
    result = runner.invoke(app, ["run", "--config", str(yaml_path)])
    assert result.exit_code == 0
    assert (src / "setup.zip").exists()       # nic nie ruszone
    assert not out.exists()


def test_run_apply_moves_files(tmp_path):
    yaml_path, src, out = _make_yaml(tmp_path)
    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 0
    assert (out / "apps" / "setup.zip").exists()
    assert (out / "3dprint" / "model.stl").exists()
    assert not (src / "setup.zip").exists()


def test_undo_last_restores(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "setup.zip").write_text("x")
    out = tmp_path / "out"
    db = tmp_path / "cache.sqlite"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"apps": ["zip"]},
        "password_detection": {"enabled": False},
        "cache": {"path": str(db)},
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert (out / "apps" / "setup.zip").exists()

    result = runner.invoke(app, ["undo", "last", "--db", str(db)])
    assert result.exit_code == 0
    assert (src / "setup.zip").exists()
    assert not (out / "apps" / "setup.zip").exists()


def test_cli_source_dest_override(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.txt").write_text("x")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["run", "--source", str(src), "--dest", str(out), "--mode", "type", "--apply"],
    )
    assert result.exit_code == 0
    assert (out / "txt" / "a.txt").exists()
```

- [ ] **Step 2: Uruchom test — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL (ModuleNotFoundError: local_file_organizer.cli)

- [ ] **Step 3: Zaimplementuj `cli.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from .config import Config
from .executor import apply_plan
from .hashing import group_duplicates
from .planner import build_plan
from .report import build_summary, render_console, write_json
from .scanner import scan
from .security import detect_password
from .undo import UndoStore

app = typer.Typer(add_completion=False, help="Local File Organizer (lfo)")


def _resolve_config(
    config: Optional[Path],
    source: Optional[Path],
    dest: Optional[Path],
    mode: Optional[str],
) -> Config:
    data: dict = {}
    if config is not None:
        data = yaml.safe_load(Path(config).read_text(encoding="utf-8")) or {}
    if source is not None:
        data["source_dir"] = str(source)
    if dest is not None:
        data["dest_dir"] = str(dest)
    if mode is not None:
        data["mode"] = mode
    return Config(**data)


@app.command()
def run(
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    source: Optional[Path] = typer.Option(None, "--source"),
    dest: Optional[Path] = typer.Option(None, "--dest"),
    mode: Optional[str] = typer.Option(None, "--mode"),
    apply: bool = typer.Option(False, "--apply", help="Wykonaj realne przeniesienia"),
) -> None:
    cfg = _resolve_config(config, source, dest, mode)
    entries = scan(cfg)
    group_duplicates(entries)
    if cfg.password_detection.enabled:
        for e in entries:
            if detect_password(e.path, e.ext, cfg.password_detection.formats):
                e.is_encrypted = True
                e.encrypted_format = e.ext
    plan = build_plan(entries, cfg)

    applied = False
    if apply:
        store = UndoStore(cfg.cache.path)
        result = apply_plan(plan, store)
        applied = True
        typer.echo(
            f"Wykonano (run_id={result['run_id']}). Cofnij: "
            f"lfo undo {result['run_id']} --db {cfg.cache.path}"
        )

    summary = build_summary(plan, entries, applied)
    if "console" in cfg.report.format:
        render_console(summary)
    if "json" in cfg.report.format and cfg.report.output is not None:
        write_json(summary, cfg.report.output)


@app.command()
def undo(
    run_id: str = typer.Argument("last", help="ID przebiegu lub 'last'"),
    db: Path = typer.Option(Path("./.lfo_cache.sqlite"), "--db"),
) -> None:
    store = UndoStore(db)
    target = store.last_run_id() if run_id == "last" else int(run_id)
    if target is None:
        typer.echo("Brak przebiegow do cofniecia.")
        raise typer.Exit(code=1)
    result = store.undo_run(target)
    typer.echo(f"Cofnieto przebieg {target}: przywrocono {result['restored']} plikow.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/cli.py tests/test_cli.py
git commit -m "feat: CLI Typer (run z dry-run/--apply, undo)"
```

---

### Task 12: Pełny przebieg + dokumentacja użycia

**Files:**
- Create: `README.md`
- Create: `examples/lfo.yaml`
- Test: cała suita

- [ ] **Step 1: Uruchom całą suitę testów**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS (wszystkie testy zielone)

- [ ] **Step 2: Test end-to-end z prawdziwego CLI (ręczny smoke)**

```bash
mkdir -p /tmp/lfo_demo/src
echo "x" > /tmp/lfo_demo/src/setup.zip
echo "x" > /tmp/lfo_demo/src/model.stl
.venv/bin/lfo run --source /tmp/lfo_demo/src --dest /tmp/lfo_demo/out --mode type
# dry-run: nic nie ruszone, tabela podsumowania
.venv/bin/lfo run --source /tmp/lfo_demo/src --dest /tmp/lfo_demo/out --mode type --apply
ls /tmp/lfo_demo/out/zip /tmp/lfo_demo/out/stl
```
Expected: dry-run pokazuje „Zostaloby przeniesione 2"; po `--apply` pliki w `out/zip` i `out/stl`.

- [ ] **Step 3: Utwórz `examples/lfo.yaml`**

```yaml
source_dir: /sciezka/balagan
dest_dir:   /sciezka/uporzadkowane
mode: category
recursive: true
max_depth: 5
ignore: [".git", "node_modules", ".*"]
follow_symlinks: false

categories:
  apps:      [zip, dmg, exe, pkg]
  3dprint:   [stl, 3mf, obj, gcode]
  dokumenty: [pdf, doc, docx, odt]
  obrazy:    [jpg, png, gif, webp]

unknown_dir:    unsorted
duplicates_dir: duplikaty
conflict:       rename

dedup:   { method: hash, action: quarantine }
password_detection: { enabled: true, formats: [pdf, zip, 7z, rar, docx, xlsx] }

report: { format: [console, json], output: ./lfo-report.json }
cache:  { enabled: true, path: ./.lfo_cache.sqlite }
```

- [ ] **Step 4: Utwórz `README.md`**

```markdown
# Local File Organizer (lfo)

CLI do katalogowania i reorganizacji plikow na lokalnym dysku.

## Instalacja

    python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"

## Uzycie

Dry-run (domyslnie, nic nie rusza):

    lfo run --config examples/lfo.yaml

Wykonanie:

    lfo run --config examples/lfo.yaml --apply

Cofniecie ostatniego przebiegu:

    lfo undo last --db ./.lfo_cache.sqlite

Parametry bez pliku konfiguracyjnego:

    lfo run --source ./balagan --dest ./uporzadkowane --mode type --apply

## Tryby klasyfikacji bazowej

- `type` — folder na kazde rozszerzenie (zip/, stl/, ...)
- `category` — mapa rozszerzenie -> kategoria (z sekcji `categories`)

Duplikaty (po hashu) trafiaja do `duplikaty/`, pliki bez dopasowania do `unsorted/`.
Pliki zabezpieczone haslem sa wykrywane i oznaczane w raporcie.

> Klasyfikacja AI (Ollama) jest dostarczana w osobnym planie (Plan 2).
```

- [ ] **Step 5: Commit**

```bash
git add README.md examples/lfo.yaml
git commit -m "docs: README i przykladowy plik konfiguracyjny; pelny przebieg"
```

---

## Self-Review (pokrycie spec → plan)

- Sekcja 3 spec (przepływ scan→analyze→plan→apply→report): Task 4, 5/6, 8, 9, 10. ✔
- Sekcja 4 (struktura modułów): odwzorowana w „Struktura plików". ✔
- Sekcja 5 (config YAML + CLI, dry-run domyślnie): Task 3, Task 11. ✔ (sekcja `ai:`/`review_dir` ignorowane do Planu 2 — patrz `extra="ignore"`).
- Sekcja 6 (dry-run vs apply, undo log, konflikt rename/skip nigdy overwrite, duplikaty oryginał+kwarantanna, wykluczenie dest): Task 8, 9, 11 + test `test_scan_excludes_dest_dir`. ✔
- Sekcja 7 (detekcja haseł pdf/zip/7z/rar/office): Task 6. ✔ (ekstrakcja tekstu → Plan 2).
- Sekcja 8 (klasyfikacja AI): **celowo poza zakresem — Plan 2.**
- Sekcja 9 (raport: przeniesiono, rozmiar, duplikaty, zabezpieczone hasłem): Task 10. ✔
- Sekcja 10 (testowanie/błędy: dry-run nic nie rusza, apply+undo wraca, konflikt nie nadpisuje, dest wykluczony, błąd per plik): Task 6/8/9/11. ✔ (`on_error fallback` Ollamy → Plan 2).

Brak placeholderów w krokach implementacyjnych (cały kod podany dosłownie). Spójność typów sprawdzona: `FileEntry`/`PlannedMove`/`Plan`/`Reason` używane identycznie w Task 2/8/9/10/11; `UndoStore` API (`start_run`, `record_move`, `record_dir`, `finish_run`, `last_run_id`, `undo_run`) spójne między Task 9 i 11.

## Co dalej — Plan 2 (nakładka AI)

Osobny plan obejmie: `classify/extractors.py` (ekstrakcja tekstu), `cache.py` (SQLite cache po hashu+model+taksonomia), `classify/ai.py` (klient Ollamy, prompt z taksonomią, próg pewności, `on_error`), rozszerzenie `planner.py` o podkategorię AI i `do_przejrzenia/` (`Reason.AI`, `Reason.REVIEW`), rozszerzenie configu o sekcję `ai:` i `review_dir`, oraz statystyki AI w raporcie.
