# Provider OpenAI-compatible (LM Studio i in.) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Buduje na Planie 2** (nakładka AI). Gałąź bazowa: `feat/ai-overlay`.

**Goal:** Umożliwić klasyfikację AI przez dowolny serwer zgodny z OpenAI API (LM Studio, llama.cpp server, vLLM, LocalAI, Ollama `/v1`), obok istniejącej natywnej Ollamy — przez `provider: openai` w konfiguracji.

**Architecture:** „Mózg" (`build_prompt`, `interpret`, cache, planer, raport) jest provider-agnostyczny i pozostaje bez zmian. Dochodzi drugi klient HTTP (`OpenAIClient`) mówiący w standardzie OpenAI (`/chat/completions`) oraz mała fabryka `build_client(ai)` wybierająca klienta wg `ai.provider`. `classify_entries` woła fabrykę zamiast twardego `OllamaClient`. Domyślny provider to nadal `ollama` (pełna wsteczna kompatybilność).

**Tech Stack:** httpx (już jest), pydantic, pytest. Bez nowych zależności.

---

## Struktura plików

```
local_file_organizer/
  config.py            # MOD: provider Literal["ollama","openai"], pole api_key
  classify/ai.py       # MOD: OpenAIClient, build_client; classify_entries uzywa build_client
examples/lfo.yaml      # MOD: zakomentowany wariant LM Studio
README.md              # MOD: notka o providerze openai
tests/
  test_config.py       # MOD: testy provider/api_key
  test_ai.py           # MOD: testy OpenAIClient + build_client + classify_entries(openai)
```

---

### Task 1: Konfiguracja providera openai + api_key

**Files:**
- Modify: `local_file_organizer/config.py` (AIConfig)
- Test: `tests/test_config.py`

- [ ] **Step 1: Dopisz failing testy** na końcu `tests/test_config.py`:
```python
def test_ai_provider_openai_and_api_key(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cfg = Config(
        source_dir=src, dest_dir=tmp_path / "out",
        ai={"provider": "openai", "api_key": "sk-x",
            "endpoint": "http://localhost:1234/v1"},
    )
    assert cfg.ai.provider == "openai"
    assert cfg.ai.api_key == "sk-x"


def test_ai_api_key_defaults_none(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cfg = Config(source_dir=src, dest_dir=tmp_path / "out")
    assert cfg.ai.provider == "ollama"
    assert cfg.ai.api_key is None


def test_ai_invalid_provider_rejected(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    with pytest.raises(ValueError):
        Config(source_dir=src, dest_dir=tmp_path / "out", ai={"provider": "bogus"})
```

- [ ] **Step 2: Uruchom — ma się nie powieść**
Run: `.venv/bin/python -m pytest tests/test_config.py::test_ai_provider_openai_and_api_key -v`
Expected: FAIL (validation: "openai" not allowed / no api_key field)

- [ ] **Step 3: Edytuj `AIConfig` w `config.py`**
Zmień linię:
```python
    provider: Literal["ollama"] = "ollama"
```
na:
```python
    provider: Literal["ollama", "openai"] = "ollama"
```
oraz dodaj zaraz po polu `model: str = "llama3.2"` nowe pole:
```python
    api_key: str | None = None
```

- [ ] **Step 4: Uruchom — ma przejść**
Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (wszystkie, w tym 3 nowe)
Potem pełna suita: `.venv/bin/python -m pytest -q` → zielona.

- [ ] **Step 5: Commit**
```bash
git add local_file_organizer/config.py tests/test_config.py
git commit -m "feat: config providera openai + api_key"
```

---

### Task 2: OpenAIClient + fabryka build_client

**Files:**
- Modify: `local_file_organizer/classify/ai.py`
- Test: `tests/test_ai.py`

- [ ] **Step 1: Dopisz failing testy** na końcu `tests/test_ai.py` (plik importuje już `httpx`, `OllamaClient`, `build_prompt`, `interpret`, `classify_entries`, oraz ma helper `_Resp`, `_cfg`, `_txt_entry`):
```python
def test_openai_client_parses_response_and_sends_auth(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _Resp({"choices": [{"message": {"content": '{"category": "umowy", "confidence": 0.8}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    from local_file_organizer.classify.ai import OpenAIClient
    client = OpenAIClient("http://localhost:1234/v1", "gemma", api_key="sk-x")
    result = client.classify("prompt")
    assert result["category"] == "umowy"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-x"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["messages"][0]["content"] == "prompt"


def test_openai_client_without_api_key_has_no_auth_header(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["headers"] = headers
        return _Resp({"choices": [{"message": {"content": '{"category": "nieznane", "confidence": 0.1}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    from local_file_organizer.classify.ai import OpenAIClient
    OpenAIClient("http://localhost:1234/v1", "gemma").classify("prompt")
    assert "Authorization" not in captured["headers"]


def test_build_client_selects_by_provider():
    from local_file_organizer.classify.ai import build_client, OpenAIClient
    from local_file_organizer.config import AIConfig
    assert isinstance(build_client(AIConfig(provider="ollama")), OllamaClient)
    assert isinstance(build_client(AIConfig(provider="openai")), OpenAIClient)


def test_classify_entries_uses_openai_provider(tmp_path, monkeypatch):
    from local_file_organizer.classify.ai import OpenAIClient
    cfg = _cfg(tmp_path, provider="openai", endpoint="http://localhost:1234/v1")
    monkeypatch.setattr(
        OpenAIClient, "classify",
        lambda self, prompt: {"category": "faktury", "confidence": 0.95},
    )
    e = _txt_entry(tmp_path, "f.txt", "tresc faktury")
    classify_entries([e], cfg, cache=None)
    assert e.ai_category == "faktury"
```

- [ ] **Step 2: Uruchom — ma się nie powieść**
Run: `.venv/bin/python -m pytest tests/test_ai.py -k "openai or build_client" -v`
Expected: FAIL (ImportError: OpenAIClient / build_client)

- [ ] **Step 3: Edytuj `classify/ai.py`**

(a) Rozszerz import configu. Zmień:
```python
from ..config import Config
```
na:
```python
from ..config import AIConfig, Config
```

(b) Dodaj `OpenAIClient` zaraz po klasie `OllamaClient`:
```python
class OpenAIClient:
    def __init__(
        self, endpoint: str, model: str, api_key: str | None = None, timeout: float = 60.0
    ):
        self.url = endpoint.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def classify(self, prompt: str) -> dict:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = httpx.post(
            self.url,
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "stream": False,
            },
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        return json.loads(payload["choices"][0]["message"]["content"])


def build_client(ai: AIConfig):
    """Zwraca klienta klasyfikacji wg ai.provider."""
    if ai.provider == "openai":
        return OpenAIClient(ai.endpoint, ai.model, ai.api_key)
    return OllamaClient(ai.endpoint, ai.model)
```

(c) W `classify_entries` zmień:
```python
    client = OllamaClient(ai.endpoint, ai.model)
```
na:
```python
    client = build_client(ai)
```

- [ ] **Step 4: Uruchom — ma przejść**
Run: `.venv/bin/python -m pytest tests/test_ai.py -v`
Expected: PASS (wszystkie istniejące + 4 nowe)
Potem pełna suita: `.venv/bin/python -m pytest -q` → zielona.

- [ ] **Step 5: Commit**
```bash
git add local_file_organizer/classify/ai.py tests/test_ai.py
git commit -m "feat: OpenAIClient + fabryka build_client (provider openai)"
```

---

### Task 3: Dokumentacja (LM Studio / Gemma) + pełna suita

**Files:**
- Modify: `examples/lfo.yaml`
- Modify: `README.md`
- Test: cała suita

- [ ] **Step 1: Pełna suita**
Run: `.venv/bin/python -m pytest -q`
Expected: wszystko zielone. Jeśli coś pada — STOP, raport BLOCKED.

- [ ] **Step 2: Dopisz zakomentowany wariant LM Studio do `examples/lfo.yaml`** (na końcu pliku, NIE zmieniając istniejącej sekcji `ai:`):
```yaml

# --- Wariant: serwer zgodny z OpenAI (LM Studio, llama.cpp, vLLM, Ollama /v1) ---
# Zakomentuj sekcje `ai:` powyzej i odkomentuj ponizsza, aby uzyc LM Studio:
#
# ai:
#   enabled: true
#   provider: openai
#   endpoint: http://localhost:1234/v1   # baza z /v1; klient dokleja /chat/completions
#   model: google/gemma-4-e4b            # identyfikator modelu zaladowanego w LM Studio
#   api_key: null                        # LM Studio nie wymaga; ustaw dla zdalnych serwerow
#   extensions: [pdf, txt, md, docx]
#   max_chars: 4000
#   confidence_threshold: 0.7
#   on_error: fallback
#   allow_suggestions: true
#   taxonomy:
#     faktury: "zawiera NIP, slowo 'faktura', kwoty, dane firmy"
#     umowy:   "zawiera 'umowa', strony, paragrafy"
```

- [ ] **Step 3: Dopisz akapit do sekcji „Klasyfikacja AI (Ollama)" w `README.md`** (po istniejącym opisie, przed wzmianką o `ollama pull`):
```markdown

### Inne backendy (OpenAI-compatible)

Zamiast Ollamy mozna uzyc dowolnego serwera zgodnego z OpenAI API
(LM Studio, llama.cpp server, vLLM, LocalAI, a takze Ollama przez `/v1`).
Ustaw w konfiguracji:

    ai:
      provider: openai
      endpoint: http://localhost:1234/v1   # LM Studio: baza z /v1
      model: google/gemma-4-e4b            # nazwa modelu zaladowanego w serwerze
      api_key: null                        # opcjonalnie, dla serwerow wymagajacych klucza

Klient wysyla `POST /chat/completions` z `response_format: json_object` i
`temperature: 0`. Male modele (np. Gemma 4B) bywaja mniej karne w formacie
JSON — pojedyncza wadliwa odpowiedz jest pomijana (plik leci dalej), a tryb
JSON serwera (LM Studio) znaczaco poprawia skutecznosc.
```

- [ ] **Step 4: Walidacja przykładu**
Run: `.venv/bin/python -c "import yaml; yaml.safe_load(open('examples/lfo.yaml')); print('yaml OK')"`
Expected: `yaml OK` (zakomentowany blok nie psuje parsowania).

- [ ] **Step 5: Commit**
```bash
git add examples/lfo.yaml README.md
git commit -m "docs: provider OpenAI-compatible (LM Studio, Gemma)"
```

---

## Self-Review (spec → plan)

- Provider `openai` + `api_key` w configu: Task 1. ✔
- `OpenAIClient` (poprawny endpoint `/chat/completions`, `messages`, `response_format json_object`, parsowanie `choices[0].message.content`, opcjonalny `Authorization`): Task 2. ✔
- Fabryka `build_client` + użycie w `classify_entries`: Task 2. ✔
- Wsteczna kompatybilność (domyślnie `ollama`, „mózg" i obsługa błędów bez zmian): zachowana — `classify_entries` zmienia tylko sposób tworzenia klienta; `interpret`/cache/planer/raport nietknięte; istniejące testy Ollamy muszą przechodzić. ✔
- Docs LM Studio/Gemma: Task 3. ✔
- Typy spójne: `build_client(ai: AIConfig)`; oba klienty mają `classify(prompt) -> dict` o tym samym kształcie; `response_format` i parsowanie zgodne z OpenAI API.

Brak placeholderów — cały kod podany dosłownie.
