from __future__ import annotations

import json

import httpx

from ..cache import AICache
from ..config import AIConfig, Config
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
            },
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        return json.loads(payload["choices"][0]["message"]["content"])


def build_client(ai: AIConfig) -> OllamaClient | OpenAIClient:
    """Zwraca klienta klasyfikacji wg ai.provider."""
    if ai.provider == "openai":
        return OpenAIClient(ai.endpoint, ai.model, ai.api_key)
    return OllamaClient(ai.endpoint, ai.model)


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
    client = build_client(ai)
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
            prompt = build_prompt(
                entry.path.name, text, ai.taxonomy, ai.allow_suggestions
            )
            try:
                result = client.classify(prompt)
            except (httpx.TransportError, httpx.HTTPStatusError):
                # serwer niedostepny/timeout albo trwaly blad HTTP (np. 401 zly
                # api_key, 404 zly model) -> przerwij AI dla calej reszty,
                # bo ten blad powtorzy sie dla kazdego pliku
                if ai.on_error == "abort":
                    raise
                return
            except Exception:
                # bledna odpowiedz dla tego pliku -> pomijamy go, probujemy nastepny
                if ai.on_error == "abort":
                    raise
                continue
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
