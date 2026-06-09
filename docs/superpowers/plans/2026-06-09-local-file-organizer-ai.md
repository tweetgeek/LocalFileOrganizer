# Local File Organizer — nakładka AI (Plan 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Wymaga ukończonego Planu 1** (`docs/superpowers/plans/2026-06-09-local-file-organizer-core.md`).

**Goal:** Dodać opcjonalną klasyfikację treści przez Ollamę: ekstrakcja tekstu, klient Ollamy z zamkniętą taksonomią, próg pewności, cache po hashu pliku, kierowanie do podkategorii (`dokumenty/faktury/`) lub do `do_przejrzenia/`, oraz statystyki AI w raporcie.

**Architecture:** Nowy etap `analyze` (po detekcji haseł, przed `build_plan`): `classify_entries` ustawia in-place pola AI na `FileEntry` (jak `group_duplicates`). Planer czyta te pola i decyduje o podkatalogu/review. AI działa tylko dla rozszerzeń z `ai.extensions`, plików czytelnych i nie-duplikatów. Cache (SQLite) kluczowany hashem treści + modelem + hashem taksonomii. `on_error: fallback` schodzi do trybu bazowego, `abort` przerywa.

**Tech Stack:** httpx (HTTP do Ollamy), python-docx (ekstrakcja docx), pypdf (ekstrakcja pdf — już z Planu 1), sqlite3 (cache).

**Spec:** `docs/superpowers/specs/2026-06-09-local-file-organizer-design.md` (sekcja 8).

---

## Struktura plików (Plan 2)

```
local_file_organizer/
  models.py        # MODYFIKACJA: Reason.AI/REVIEW, PlannedMove.subcategory, pola ai_* w FileEntry
  config.py        # MODYFIKACJA: AIConfig, review_dir, pole ai
  classify/
    extractors.py  # NOWY: extract_text per rozszerzenie
    ai.py          # NOWY: OllamaClient, build_prompt, interpret, classify_entries
  cache.py         # NOWY: AICache (SQLite) + make_key
  planner.py       # MODYFIKACJA: build_plan uwzglednia nakladke AI
  report.py        # MODYFIKACJA: statystyki AI w podsumowaniu
  cli.py           # MODYFIKACJA: etap AI w potoku run
pyproject.toml     # MODYFIKACJA: httpx, python-docx
tests/
  test_extractors.py
  test_cache.py
  test_ai.py
  test_planner_ai.py
  test_report_ai.py
  test_cli_ai.py
```

---

### Task 1: Zależności + rozszerzenie modeli

**Files:**
- Modify: `pyproject.toml` (sekcja `dependencies`)
- Modify: `local_file_organizer/models.py`
- Test: `tests/test_models.py` (dopisanie przypadków)

- [ ] **Step 1: Dodaj zależności do `pyproject.toml`**

W sekcji `dependencies` dodaj dwie pozycje, tak aby lista wyglądała:

```toml
dependencies = [
  "typer>=0.12",
  "pydantic>=2.6",
  "pyyaml>=6.0",
  "rich>=13.7",
  "pypdf>=4.0",
  "py7zr>=0.21",
  "rarfile>=4.1",
  "msoffcrypto-tool>=5.4",
  "httpx>=0.27",
  "python-docx>=1.1",
]
```

- [ ] **Step 2: Reinstaluj pakiet**

Run: `.venv/bin/python -m pip install -e ".[dev]"`
Expected: instalacja `httpx` i `python-docx` bez błędów.

- [ ] **Step 3: Dopisz failing testy do `tests/test_models.py`**

Dodaj na końcu pliku:

```python
def test_reason_has_ai_and_review():
    assert Reason.AI.value == "ai"
    assert Reason.REVIEW.value == "review"


def test_file_entry_ai_defaults():
    from pathlib import Path as _P
    e = FileEntry(path=_P("/a/b.pdf"), size=1, ext="pdf")
    assert e.ai_category is None
    assert e.ai_review is False
    assert e.ai_suggestion is None
    assert e.ai_from_cache is False


def test_planned_move_has_subcategory():
    from pathlib import Path as _P
    m = PlannedMove(source=_P("/a"), dest=_P("/b"), reason=Reason.AI,
                    category="dokumenty", subcategory="faktury")
    assert m.subcategory == "faktury"
```

- [ ] **Step 4: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL (AttributeError: AI / brak pola subcategory / brak ai_category)

- [ ] **Step 5: Zastąp `local_file_organizer/models.py` pełną wersją**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Reason(str, Enum):
    BASE = "base"            # tryb bazowy (type/category)
    DUPLICATE = "duplicate"  # kwarantanna duplikatu
    UNSORTED = "unsorted"    # brak dopasowania
    AI = "ai"                # podkategoria nadana przez AI
    REVIEW = "review"        # do_przejrzenia


@dataclass
class FileEntry:
    path: Path
    size: int
    ext: str  # bez kropki, lowercase
    content_hash: str | None = None
    is_encrypted: bool = False
    encrypted_format: str | None = None
    duplicate_of: Path | None = None
    # --- nakladka AI (Plan 2) ---
    ai_category: str | None = None     # klucz taksonomii zaakceptowany przez AI
    ai_review: bool = False            # True -> do_przejrzenia
    ai_suggestion: str | None = None   # zaproponowana nowa nazwa kategorii
    ai_from_cache: bool = False        # czy wynik pochodzil z cache


@dataclass
class PlannedMove:
    source: Path
    dest: Path
    reason: Reason
    category: str | None = None
    subcategory: str | None = None
    note: str | None = None


@dataclass
class Plan:
    moves: list[PlannedMove] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)  # (sciezka, powod)
    errors: list[tuple[Path, str]] = field(default_factory=list)
```

- [ ] **Step 6: Uruchom testy — mają przejść**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (6 passed — 3 z Planu 1 + 3 nowe)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml local_file_organizer/models.py tests/test_models.py
git commit -m "feat: zaleznosci AI + rozszerzenie modeli (Reason.AI/REVIEW, pola ai_*)"
```

---

### Task 2: Rozszerzenie konfiguracji o sekcję `ai`

**Files:**
- Modify: `local_file_organizer/config.py`
- Test: `tests/test_config.py` (dopisanie przypadków)

- [ ] **Step 1: Dopisz failing testy do `tests/test_config.py`**

Dodaj na końcu pliku:

```python
def test_ai_defaults(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cfg = Config(source_dir=src, dest_dir=tmp_path / "out")
    assert cfg.ai.enabled is False
    assert cfg.ai.model == "llama3.2"
    assert cfg.ai.confidence_threshold == 0.7
    assert cfg.ai.on_error == "fallback"
    assert cfg.review_dir == "do_przejrzenia"


def test_ai_taxonomy_parsed(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cfg = Config(
        source_dir=src, dest_dir=tmp_path / "out",
        ai={"enabled": True, "taxonomy": {"faktury": "zawiera NIP"}},
    )
    assert cfg.ai.enabled is True
    assert cfg.ai.taxonomy["faktury"] == "zawiera NIP"
```

- [ ] **Step 2: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_config.py::test_ai_defaults -v`
Expected: FAIL (AttributeError: 'Config' object has no attribute 'ai')

- [ ] **Step 3: Dodaj `AIConfig` i pola do `config.py`**

Dodaj klasę `AIConfig` tuż przed klasą `Config`:

```python
class AIConfig(BaseModel):
    enabled: bool = False
    provider: Literal["ollama"] = "ollama"
    endpoint: str = "http://localhost:11434"
    model: str = "llama3.2"
    extensions: list[str] = Field(
        default_factory=lambda: ["pdf", "txt", "md", "docx"]
    )
    max_chars: int = 4000
    confidence_threshold: float = 0.7
    on_error: Literal["fallback", "abort"] = "fallback"
    allow_suggestions: bool = True
    taxonomy: dict[str, str] = Field(default_factory=dict)
```

Następnie w klasie `Config`, zaraz po polu `duplicates_dir: str = "duplikaty"`, dodaj:

```python
    review_dir: str = "do_przejrzenia"
```

oraz po polu `cache: CacheConfig = Field(default_factory=CacheConfig)` dodaj:

```python
    ai: AIConfig = Field(default_factory=AIConfig)
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/config.py tests/test_config.py
git commit -m "feat: konfiguracja AI (AIConfig, review_dir)"
```

---

### Task 3: Ekstrakcja tekstu

**Files:**
- Create: `local_file_organizer/classify/extractors.py`
- Test: `tests/test_extractors.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_extractors.py`:

```python
from local_file_organizer.classify.extractors import extract_text


def test_txt_extraction_truncates(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("ABCDEFGHIJ", encoding="utf-8")
    assert extract_text(f, "txt", max_chars=4) == "ABCD"


def test_md_and_csv_supported(tmp_path):
    md = tmp_path / "a.md"; md.write_text("# tytul", encoding="utf-8")
    csv = tmp_path / "a.csv"; csv.write_text("a,b,c", encoding="utf-8")
    assert extract_text(md, "md", 100) == "# tytul"
    assert extract_text(csv, "csv", 100) == "a,b,c"


def test_unsupported_extension_returns_none(tmp_path):
    f = tmp_path / "a.bin"; f.write_bytes(b"\x00\x01")
    assert extract_text(f, "bin", 100) is None


def test_broken_pdf_returns_none(tmp_path):
    f = tmp_path / "broken.pdf"; f.write_text("to nie jest pdf", encoding="utf-8")
    assert extract_text(f, "pdf", 100) is None
```

- [ ] **Step 2: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_extractors.py -v`
Expected: FAIL (ModuleNotFoundError: extractors)

- [ ] **Step 3: Zaimplementuj `classify/extractors.py`**

```python
from __future__ import annotations

from pathlib import Path

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
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `.venv/bin/python -m pytest tests/test_extractors.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/classify/extractors.py tests/test_extractors.py
git commit -m "feat: ekstrakcja tekstu (txt/md/csv/pdf/docx)"
```

---

### Task 4: Cache klasyfikacji AI (SQLite)

**Files:**
- Create: `local_file_organizer/cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_cache.py`:

```python
from local_file_organizer.cache import AICache


def test_put_get_roundtrip(tmp_path):
    cache = AICache(tmp_path / "c.sqlite")
    cache.put("k1", {"category": "faktury", "confidence": 0.9, "suggested_name": None})
    got = cache.get("k1")
    assert got["category"] == "faktury"
    assert got["confidence"] == 0.9


def test_get_missing_returns_none(tmp_path):
    cache = AICache(tmp_path / "c.sqlite")
    assert cache.get("niema") is None


def test_make_key_changes_with_taxonomy(tmp_path):
    k1 = AICache.make_key("HASH", "llama3.2", {"faktury": "a"})
    k2 = AICache.make_key("HASH", "llama3.2", {"faktury": "b"})
    k3 = AICache.make_key("HASH", "llama3.2", {"faktury": "a"})
    assert k1 != k2
    assert k1 == k3
    assert k1.startswith("HASH:llama3.2:")
```

- [ ] **Step 2: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_cache.py -v`
Expected: FAIL (ModuleNotFoundError: cache)

- [ ] **Step 3: Zaimplementuj `cache.py`**

```python
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


class AICache:
    def __init__(self, db_path: Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS ai_cache ("
            "key TEXT PRIMARY KEY, category TEXT, confidence REAL, suggestion TEXT)"
        )
        self.conn.commit()

    @staticmethod
    def make_key(file_hash: str, model: str, taxonomy: dict[str, str]) -> str:
        tax = hashlib.sha256(
            json.dumps(taxonomy, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        return f"{file_hash}:{model}:{tax}"

    def get(self, key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT category, confidence, suggestion FROM ai_cache WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return {"category": row[0], "confidence": row[1], "suggested_name": row[2]}

    def put(self, key: str, result: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO ai_cache (key, category, confidence, suggestion) "
            "VALUES (?, ?, ?, ?)",
            (
                key,
                result.get("category"),
                float(result.get("confidence") or 0.0),
                result.get("suggested_name"),
            ),
        )
        self.conn.commit()
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `.venv/bin/python -m pytest tests/test_cache.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/cache.py tests/test_cache.py
git commit -m "feat: cache klasyfikacji AI w SQLite (klucz hash+model+taksonomia)"
```

---

### Task 5: Klient Ollamy i logika klasyfikacji

**Files:**
- Create: `local_file_organizer/classify/ai.py`
- Test: `tests/test_ai.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_ai.py`:

```python
import httpx
import pytest
from local_file_organizer.config import Config
from local_file_organizer.models import FileEntry
from local_file_organizer.classify import ai as ai_mod
from local_file_organizer.classify.ai import (
    OllamaClient,
    build_prompt,
    interpret,
    classify_entries,
)


def test_build_prompt_contains_taxonomy_and_json():
    prompt = build_prompt("faktura.pdf", "tresc", {"faktury": "NIP"}, allow_suggestions=True)
    assert "faktury" in prompt
    assert "JSON" in prompt
    assert "faktura.pdf" in prompt


def test_interpret_accepts_high_confidence():
    cat, review, sug = interpret(
        {"category": "faktury", "confidence": 0.9}, {"faktury"}, 0.7, True
    )
    assert cat == "faktury" and review is False and sug is None


def test_interpret_low_confidence_goes_to_review():
    cat, review, sug = interpret(
        {"category": "faktury", "confidence": 0.3}, {"faktury"}, 0.7, True
    )
    assert cat is None and review is True


def test_interpret_suggestion_goes_to_review():
    cat, review, sug = interpret(
        {"category": "nieznane", "confidence": 0.9, "suggested_name": "paragony"},
        {"faktury"}, 0.7, True,
    )
    assert cat is None and review is True and sug == "paragony"


def test_interpret_unknown_no_suggestion_review():
    cat, review, sug = interpret(
        {"category": "nieznane", "confidence": 0.9}, {"faktury"}, 0.7, True
    )
    assert cat is None and review is True and sug is None


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_ollama_client_parses_response(monkeypatch):
    def fake_post(url, json, timeout):
        return _Resp({"response": '{"category": "faktury", "confidence": 0.8}'})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = OllamaClient("http://localhost:11434", "llama3.2")
    result = client.classify("prompt")
    assert result["category"] == "faktury"


def _cfg(tmp_path, **ai_kw):
    src = tmp_path / "src"; src.mkdir(exist_ok=True)
    ai = {"enabled": True, "extensions": ["txt"], "taxonomy": {"faktury": "NIP"}}
    ai.update(ai_kw)
    return Config(source_dir=src, dest_dir=tmp_path / "out", ai=ai)


def _txt_entry(tmp_path, name, content):
    p = tmp_path / "src" / name
    p.parent.mkdir(exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return FileEntry(path=p, size=len(content), ext="txt")


def test_classify_sets_category(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        OllamaClient, "classify",
        lambda self, prompt: {"category": "faktury", "confidence": 0.95},
    )
    e = _txt_entry(tmp_path, "f.txt", "tresc faktury")
    classify_entries([e], cfg, cache=None)
    assert e.ai_category == "faktury"
    assert e.ai_review is False


def test_classify_skips_non_ai_extension(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, extensions=["pdf"])  # txt nie jest na liscie
    called = []
    monkeypatch.setattr(
        OllamaClient, "classify",
        lambda self, prompt: called.append(1) or {"category": "faktury", "confidence": 1.0},
    )
    e = _txt_entry(tmp_path, "f.txt", "x")
    classify_entries([e], cfg, cache=None)
    assert e.ai_category is None
    assert called == []


def test_classify_skips_duplicate_and_encrypted(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        OllamaClient, "classify",
        lambda self, prompt: {"category": "faktury", "confidence": 1.0},
    )
    dup = _txt_entry(tmp_path, "d.txt", "x"); dup.duplicate_of = tmp_path / "orig"
    enc = _txt_entry(tmp_path, "e.txt", "y"); enc.is_encrypted = True
    classify_entries([dup, enc], cfg, cache=None)
    assert dup.ai_category is None
    assert enc.ai_category is None


def test_classify_uses_cache_on_second_run(tmp_path, monkeypatch):
    from local_file_organizer.cache import AICache
    cfg = _cfg(tmp_path)
    cache = AICache(tmp_path / "c.sqlite")
    calls = []
    monkeypatch.setattr(
        OllamaClient, "classify",
        lambda self, prompt: calls.append(1) or {"category": "faktury", "confidence": 0.95},
    )
    e1 = _txt_entry(tmp_path, "f.txt", "identyczna tresc")
    classify_entries([e1], cfg, cache=cache)
    e2 = FileEntry(path=e1.path, size=e1.size, ext="txt")
    classify_entries([e2], cfg, cache=cache)
    assert len(calls) == 1            # drugi raz z cache
    assert e2.ai_from_cache is True
    assert e2.ai_category == "faktury"


def test_classify_on_error_fallback(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, on_error="fallback")

    def boom(self, prompt):
        raise httpx.ConnectError("brak polaczenia")

    monkeypatch.setattr(OllamaClient, "classify", boom)
    e = _txt_entry(tmp_path, "f.txt", "x")
    classify_entries([e], cfg, cache=None)  # nie podnosi wyjatku
    assert e.ai_category is None


def test_classify_on_error_abort(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, on_error="abort")

    def boom(self, prompt):
        raise httpx.ConnectError("brak polaczenia")

    monkeypatch.setattr(OllamaClient, "classify", boom)
    e = _txt_entry(tmp_path, "f.txt", "x")
    with pytest.raises(httpx.ConnectError):
        classify_entries([e], cfg, cache=None)
```

- [ ] **Step 2: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_ai.py -v`
Expected: FAIL (ModuleNotFoundError: classify.ai)

- [ ] **Step 3: Zaimplementuj `classify/ai.py`**

```python
from __future__ import annotations

import json

import httpx

from ..cache import AICache
from ..config import Config
from ..hashing import compute_hash
from ..models import FileEntry
from .extractors import extract_text


class OllamaClient:
    def __init__(self, endpoint: str, model: str, timeout: float = 60.0):
        self.url = endpoint.rstrip("/") + "/api/generate"
        self.model = model
        self.timeout = timeout

    def classify(self, prompt: str) -> dict:
        resp = httpx.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "format": "json",
                "stream": False,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        return json.loads(payload["response"])


def build_prompt(
    filename: str, text: str, taxonomy: dict[str, str], allow_suggestions: bool
) -> str:
    lines = ["Sklasyfikuj plik do JEDNEJ z ponizszych kategorii.", "", "Kategorie:"]
    for name, hint in taxonomy.items():
        lines.append(f"- {name}: {hint}")
    lines += ["", f"Nazwa pliku: {filename}", "Fragment tresci:", text, ""]
    if allow_suggestions:
        lines.append(
            "Jesli nic nie pasuje, ustaw category='nieznane' i zaproponuj "
            "nowa nazwe w 'suggested_name'."
        )
    lines.append(
        'Zwroc TYLKO JSON: {"category": "<klucz|nieznane>", '
        '"confidence": <0.0-1.0>, "suggested_name": "<nazwa|null>"}'
    )
    return "\n".join(lines)


def interpret(
    result: dict,
    taxonomy_keys: set[str],
    threshold: float,
    allow_suggestions: bool,
) -> tuple[str | None, bool, str | None]:
    """Zwraca (ai_category, review, suggestion)."""
    category = result.get("category")
    try:
        confidence = float(result.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    suggestion = result.get("suggested_name") or None
    if category in taxonomy_keys and confidence >= threshold:
        return category, False, None
    if allow_suggestions and suggestion:
        return None, True, suggestion
    return None, True, None


def classify_entries(
    entries: list[FileEntry], config: Config, cache: AICache | None
) -> None:
    """Ustawia pola ai_* in-place. AI tylko dla nie-duplikatow, plikow
    czytelnych i rozszerzen z ai.extensions."""
    ai = config.ai
    if not ai.enabled:
        return
    client = OllamaClient(ai.endpoint, ai.model)
    tax_keys = set(ai.taxonomy)

    for entry in entries:
        if entry.duplicate_of is not None or entry.is_encrypted:
            continue
        if entry.ext not in ai.extensions:
            continue
        text = extract_text(entry.path, entry.ext, ai.max_chars)
        if not text:
            continue

        if entry.content_hash is None:
            entry.content_hash = compute_hash(entry.path)

        result = None
        if cache is not None:
            key = AICache.make_key(entry.content_hash, ai.model, ai.taxonomy)
            result = cache.get(key)
            if result is not None:
                entry.ai_from_cache = True

        if result is None:
            try:
                prompt = build_prompt(
                    entry.path.name, text, ai.taxonomy, ai.allow_suggestions
                )
                result = client.classify(prompt)
            except Exception:
                if ai.on_error == "abort":
                    raise
                return  # fallback: przerwij AI, reszta poleci trybem bazowym
            if cache is not None:
                cache.put(
                    AICache.make_key(entry.content_hash, ai.model, ai.taxonomy),
                    result,
                )

        cat, review, suggestion = interpret(
            result, tax_keys, ai.confidence_threshold, ai.allow_suggestions
        )
        entry.ai_category = cat
        entry.ai_review = review
        entry.ai_suggestion = suggestion
```

- [ ] **Step 4: Uruchom testy — mają przejść**

Run: `.venv/bin/python -m pytest tests/test_ai.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/classify/ai.py tests/test_ai.py
git commit -m "feat: klient Ollamy, prompt z taksonomia, interpretacja, classify_entries z cache i on_error"
```

---

### Task 6: Integracja nakładki AI w planerze

**Files:**
- Modify: `local_file_organizer/planner.py`
- Test: `tests/test_planner_ai.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_planner_ai.py`:

```python
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


def test_ai_category_creates_subfolder(tmp_path):
    cfg = _cfg(tmp_path, mode="category", categories={"dokumenty": ["pdf"]})
    e = _entry(tmp_path, "faktura.pdf", ai_category="faktury")
    plan = build_plan([e], cfg)
    m = plan.moves[0]
    assert m.reason == Reason.AI
    assert m.subcategory == "faktury"
    assert m.dest == cfg.dest_dir / "dokumenty" / "faktury" / "faktura.pdf"


def test_ai_review_goes_to_review_dir(tmp_path):
    cfg = _cfg(tmp_path, mode="category", categories={"dokumenty": ["pdf"]})
    e = _entry(tmp_path, "cos.pdf", ai_review=True, ai_suggestion="paragony")
    plan = build_plan([e], cfg)
    m = plan.moves[0]
    assert m.reason == Reason.REVIEW
    assert m.dest == cfg.dest_dir / "do_przejrzenia" / "cos.pdf"
    assert "paragony" in m.note


def test_no_ai_fields_behaves_like_base(tmp_path):
    cfg = _cfg(tmp_path, mode="category", categories={"dokumenty": ["pdf"]})
    e = _entry(tmp_path, "zwykly.pdf")
    plan = build_plan([e], cfg)
    m = plan.moves[0]
    assert m.reason == Reason.BASE
    assert m.dest == cfg.dest_dir / "dokumenty" / "zwykly.pdf"
```

- [ ] **Step 2: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_planner_ai.py -v`
Expected: FAIL (np. AssertionError: reason != AI, brak podfolderu)

- [ ] **Step 3: Zastąp `local_file_organizer/planner.py` pełną wersją**

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


def _note(entry: FileEntry) -> str | None:
    parts: list[str] = []
    if entry.is_encrypted:
        parts.append(f"zabezpieczony haslem ({entry.encrypted_format})")
    if entry.ai_suggestion:
        parts.append(f"sugestia AI: {entry.ai_suggestion}")
    return "; ".join(parts) if parts else None


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

        # 2. Folder docelowy: review > podkategoria AI > baza/unsorted
        subcategory: str | None = None
        category = resolve_base(entry.ext, config)

        if entry.ai_review:
            target_dir = dest_root / config.review_dir
            reason = Reason.REVIEW
        else:
            if category is None:
                base_dir = dest_root / config.unknown_dir
                reason = Reason.UNSORTED
            else:
                base_dir = dest_root / category
                reason = Reason.BASE
            if entry.ai_category:
                subcategory = entry.ai_category
                target_dir = base_dir / subcategory
                reason = Reason.AI
            else:
                target_dir = base_dir

        desired = target_dir / entry.path.name
        collision = desired in taken or desired.exists()
        if collision and config.conflict == "skip":
            plan.skipped.append((entry.path, "konflikt nazwy (skip)"))
            continue
        dest = _unique_dest(desired, taken)
        taken.add(dest)

        plan.moves.append(
            PlannedMove(
                source=entry.path,
                dest=dest,
                reason=reason,
                category=category,
                subcategory=subcategory,
                note=_note(entry),
            )
        )

    return plan
```

- [ ] **Step 4: Uruchom testy — mają przejść (w tym Plan 1)**

Run: `.venv/bin/python -m pytest tests/test_planner.py tests/test_planner_ai.py -v`
Expected: PASS (test_planner.py 7 + test_planner_ai.py 3 = 10 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/planner.py tests/test_planner_ai.py
git commit -m "feat: planer uwzglednia nakladke AI (podkategoria, do_przejrzenia)"
```

---

### Task 7: Statystyki AI w raporcie

**Files:**
- Modify: `local_file_organizer/report.py`
- Test: `tests/test_report_ai.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_report_ai.py`:

```python
from pathlib import Path
from local_file_organizer.models import FileEntry, Plan, PlannedMove, Reason
from local_file_organizer.report import build_summary


def test_summary_counts_ai_and_review_and_cache():
    src1 = Path("/src/faktura.pdf")
    src2 = Path("/src/cos.pdf")
    entries = [
        FileEntry(path=src1, size=10, ext="pdf", ai_category="faktury", ai_from_cache=True),
        FileEntry(path=src2, size=20, ext="pdf", ai_review=True, ai_suggestion="paragony"),
    ]
    plan = Plan(moves=[
        PlannedMove(source=src1, dest=Path("/out/dokumenty/faktury/faktura.pdf"),
                    reason=Reason.AI, category="dokumenty", subcategory="faktury"),
        PlannedMove(source=src2, dest=Path("/out/do_przejrzenia/cos.pdf"),
                    reason=Reason.REVIEW),
    ])
    summary = build_summary(plan, entries, applied=False)
    assert summary["ai_count"] == 1
    assert summary["review_count"] == 1
    assert summary["ai_from_cache"] == 1
    assert ("/src/cos.pdf", "paragony") in summary["suggestions"]
```

- [ ] **Step 2: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_report_ai.py -v`
Expected: FAIL (KeyError: 'ai_count')

- [ ] **Step 3: Zaktualizuj `build_summary` i `render_console` w `report.py`**

Zastąp funkcję `build_summary` pełną wersją:

```python
def build_summary(plan: Plan, entries: list[FileEntry], applied: bool) -> dict:
    size_by_source = {e.path: e.size for e in entries}
    moved_bytes = sum(size_by_source.get(m.source, 0) for m in plan.moves)
    duplicates = sum(1 for m in plan.moves if m.reason == Reason.DUPLICATE)
    unsorted = sum(1 for m in plan.moves if m.reason == Reason.UNSORTED)
    ai_count = sum(1 for m in plan.moves if m.reason == Reason.AI)
    review_count = sum(1 for m in plan.moves if m.reason == Reason.REVIEW)
    from_cache = sum(1 for e in entries if e.ai_from_cache)
    suggestions = [
        (str(e.path), e.ai_suggestion) for e in entries if e.ai_suggestion
    ]
    encrypted = [e for e in entries if e.is_encrypted]
    per_folder = Counter(str(m.dest.parent) for m in plan.moves)
    return {
        "applied": applied,
        "moved_count": len(plan.moves),
        "moved_bytes": moved_bytes,
        "moved_human": human_size(moved_bytes),
        "duplicates": duplicates,
        "unsorted": unsorted,
        "ai_count": ai_count,
        "review_count": review_count,
        "ai_from_cache": from_cache,
        "suggestions": suggestions,
        "encrypted": [(str(e.path), e.encrypted_format) for e in encrypted],
        "skipped": len(plan.skipped),
        "errors": len(plan.errors),
        "per_folder": dict(per_folder),
    }
```

Następnie w `render_console`, po wierszu `table.add_row("Unsorted", str(summary["unsorted"]))`, dodaj:

```python
    table.add_row("Sklasyfikowane przez AI", str(summary["ai_count"]))
    table.add_row("Do przejrzenia", str(summary["review_count"]))
    table.add_row("Z cache AI", str(summary["ai_from_cache"]))
```

oraz na końcu funkcji `render_console` (po bloku z plikami zabezpieczonymi) dodaj:

```python
    if summary["suggestions"]:
        console.print("\n[bold]Sugestie nowych kategorii (do_przejrzenia):[/bold]")
        for path, name in summary["suggestions"]:
            console.print(f"  - {path} -> {name}")
```

- [ ] **Step 4: Uruchom testy — mają przejść (w tym Plan 1)**

Run: `.venv/bin/python -m pytest tests/test_report.py tests/test_report_ai.py -v`
Expected: PASS (test_report.py 3 + test_report_ai.py 1 = 4 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/report.py tests/test_report_ai.py
git commit -m "feat: statystyki AI w raporcie (ai_count, review, cache, sugestie)"
```

---

### Task 8: Wpięcie etapu AI w CLI

**Files:**
- Modify: `local_file_organizer/cli.py`
- Test: `tests/test_cli_ai.py`

- [ ] **Step 1: Napisz failing test**

`tests/test_cli_ai.py`:

```python
import yaml
from typer.testing import CliRunner
from local_file_organizer.cli import app
from local_file_organizer.classify.ai import OllamaClient

runner = CliRunner()


def test_run_with_ai_routes_to_subcategory(tmp_path, monkeypatch):
    src = tmp_path / "src"; src.mkdir()
    (src / "faktura.txt").write_text("tresc z NIP 123", encoding="utf-8")
    out = tmp_path / "out"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"dokumenty": ["txt"]},
        "password_detection": {"enabled": False},
        "cache": {"path": str(tmp_path / "c.sqlite")},
        "ai": {
            "enabled": True,
            "extensions": ["txt"],
            "taxonomy": {"faktury": "zawiera NIP"},
        },
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    monkeypatch.setattr(
        OllamaClient, "classify",
        lambda self, prompt: {"category": "faktury", "confidence": 0.95},
    )

    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 0
    assert (out / "dokumenty" / "faktury" / "faktura.txt").exists()


def test_run_ai_disabled_ignores_taxonomy(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "faktura.txt").write_text("x", encoding="utf-8")
    out = tmp_path / "out"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"dokumenty": ["txt"]},
        "password_detection": {"enabled": False},
        "ai": {"enabled": False, "taxonomy": {"faktury": "x"}},
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 0
    assert (out / "dokumenty" / "faktura.txt").exists()  # bez podkategorii
```

- [ ] **Step 2: Uruchom — ma się nie powieść**

Run: `.venv/bin/python -m pytest tests/test_cli_ai.py -v`
Expected: FAIL (plik trafia do dokumenty/ bez podkategorii — etap AI jeszcze nie wpięty)

- [ ] **Step 3: Wepnij etap AI w `cli.py`**

W `local_file_organizer/cli.py`, w bloku importów (po `from .scanner import scan`) dodaj:

```python
from .cache import AICache
from .classify.ai import classify_entries
```

Następnie w funkcji `run`, **pomiędzy** blokiem detekcji haseł a `plan = build_plan(entries, cfg)`, wstaw:

```python
    if cfg.ai.enabled:
        cache = AICache(cfg.cache.path) if cfg.cache.enabled else None
        classify_entries(entries, cfg, cache)
```

Po zmianie fragment `run` wygląda tak:

```python
    entries = scan(cfg)
    group_duplicates(entries)
    if cfg.password_detection.enabled:
        for e in entries:
            if detect_password(e.path, e.ext, cfg.password_detection.formats):
                e.is_encrypted = True
                e.encrypted_format = e.ext
    if cfg.ai.enabled:
        cache = AICache(cfg.cache.path) if cfg.cache.enabled else None
        classify_entries(entries, cfg, cache)
    plan = build_plan(entries, cfg)
```

- [ ] **Step 4: Uruchom testy — mają przejść (w tym Plan 1 CLI)**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_cli_ai.py -v`
Expected: PASS (test_cli.py 4 + test_cli_ai.py 2 = 6 passed)

- [ ] **Step 5: Commit**

```bash
git add local_file_organizer/cli.py tests/test_cli_ai.py
git commit -m "feat: wpiecie etapu klasyfikacji AI w potok run"
```

---

### Task 9: Pełna suita + aktualizacja dokumentacji

**Files:**
- Modify: `README.md`
- Modify: `examples/lfo.yaml`
- Test: cała suita

- [ ] **Step 1: Uruchom całą suitę**

Run: `.venv/bin/python -m pytest -v`
Expected: PASS (wszystkie testy Planu 1 i Planu 2 zielone)

- [ ] **Step 2: Dodaj sekcję `ai:` do `examples/lfo.yaml`**

Dopisz na końcu pliku `examples/lfo.yaml`:

```yaml
review_dir: do_przejrzenia

ai:
  enabled: true
  provider: ollama
  endpoint: http://localhost:11434
  model: llama3.2
  extensions: [pdf, txt, md, docx]
  max_chars: 4000
  confidence_threshold: 0.7
  on_error: fallback
  allow_suggestions: true
  taxonomy:
    faktury: "zawiera NIP, slowo 'faktura', kwoty, dane firmy"
    umowy:   "zawiera 'umowa', strony, paragrafy"
```

- [ ] **Step 3: Zaktualizuj `README.md`**

Zastąp w `README.md` linię:

```markdown
> Klasyfikacja AI (Ollama) jest dostarczana w osobnym planie (Plan 2).
```

sekcją:

```markdown
## Klasyfikacja AI (Ollama)

Gdy `ai.enabled: true`, dla rozszerzen z `ai.extensions` aplikacja czyta tresc,
wysyla fragment do Ollamy i przypisuje podkategorie z `ai.taxonomy`
(np. `dokumenty/faktury/`). Niepewne wyniki i sugestie nowych kategorii trafiaja
do `do_przejrzenia/`. Wyniki sa cache'owane po hashu pliku — duplikaty i ponowne
uruchomienia nie wolaja modelu. Przy niedostepnej Ollamie `on_error: fallback`
schodzi do trybu bazowego.

Wymaga uruchomionej Ollamy (`ollama serve`) i pobranego modelu (`ollama pull llama3.2`).
```

- [ ] **Step 4: (Opcjonalny) E2E z prawdziwą Ollamą**

Jeśli lokalnie działa Ollama, ręczny smoke:

```bash
ollama pull llama3.2
mkdir -p /tmp/lfo_ai/src
printf "Faktura VAT\nNIP 123-456-78-90\nKwota: 1230 zl" > /tmp/lfo_ai/src/dok.txt
.venv/bin/lfo run --config examples/lfo.yaml --source /tmp/lfo_ai/src --dest /tmp/lfo_ai/out --apply
```
Expected: `dok.txt` w `out/dokumenty/faktury/` (lub `out/do_przejrzenia/` jeśli model niepewny).

- [ ] **Step 5: Commit**

```bash
git add README.md examples/lfo.yaml
git commit -m "docs: dokumentacja klasyfikacji AI i przyklad konfiguracji"
```

---

## Self-Review (pokrycie spec → plan)

- Sekcja 8 spec (klasyfikacja AI): zamknięta taksonomia + prompt (Task 5 `build_prompt`), próg pewności i decyzja review/sugestia (Task 5 `interpret`), cache po hashu+model+taksonomia (Task 4, użycie w Task 5), `on_error fallback/abort` (Task 5). ✔
- Sekcja 7 spec (ekstrakcja tekstu txt/pdf/docx, limit `max_chars`): Task 3. ✔
- Sekcja 3 spec (cache po hashu, duplikaty nie wołają Ollamy): Task 5 — duplikaty pomijane, cache współdzielony po hashu treści. ✔
- Sekcja 9 spec (raport: ile przez AI, ile z cache, sugestie, do_przejrzenia): Task 7. ✔
- Sekcja 5 spec (config `ai:`, `review_dir`): Task 2. ✔
- Routing do `dokumenty/faktury/` i `do_przejrzenia/`: Task 6. ✔

Brak placeholderów — cały kod podany dosłownie. Spójność typów: `classify_entries` ustawia pola `FileEntry.ai_*` zdefiniowane w Task 1; planer (Task 6) i raport (Task 7) czytają dokładnie te pola; `AICache.make_key/get/put` (Task 4) używane identycznie w Task 5; `OllamaClient.classify` mockowane w testach Task 5 i Task 8 tą samą sygnaturą. Zachowanie Planu 1 niezmienione, gdy `ai.enabled=false` (pola AI mają wartości domyślne) — potwierdzone testami `test_no_ai_fields_behaves_like_base` i `test_run_ai_disabled_ignores_taxonomy`.
