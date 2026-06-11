import httpx
import pytest
from local_file_organizer.config import Config
from local_file_organizer.models import FileEntry
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


def test_classify_parse_error_skips_only_that_entry(tmp_path, monkeypatch):
    # serwer zywy, ale jedna odpowiedz jest bledna -> pomijamy tylko ten plik
    cfg = _cfg(tmp_path, on_error="fallback")
    calls = []

    def flaky(self, prompt):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("zepsuty JSON")
        return {"category": "faktury", "confidence": 0.95}

    monkeypatch.setattr(OllamaClient, "classify", flaky)
    e1 = _txt_entry(tmp_path, "a.txt", "tresc a")
    e2 = _txt_entry(tmp_path, "b.txt", "tresc b zupelnie inna")
    classify_entries([e1, e2], cfg, cache=None)
    assert e1.ai_category is None        # pierwszy pominiety (parse error)
    assert e2.ai_category == "faktury"   # drugi sklasyfikowany (continue, nie return)
    assert len(calls) == 2


def test_classify_connection_error_stops_remaining(tmp_path, monkeypatch):
    # awaria polaczenia -> przerywamy AI dla calej reszty (brak N timeoutow)
    cfg = _cfg(tmp_path, on_error="fallback")
    calls = []

    def boom(self, prompt):
        calls.append(1)
        raise httpx.ConnectError("brak polaczenia")

    monkeypatch.setattr(OllamaClient, "classify", boom)
    e1 = _txt_entry(tmp_path, "a.txt", "tresc a")
    e2 = _txt_entry(tmp_path, "b.txt", "tresc b zupelnie inna")
    classify_entries([e1, e2], cfg, cache=None)
    assert e1.ai_category is None
    assert e2.ai_category is None
    assert len(calls) == 1               # po bledzie polaczenia nie wolamy drugi raz


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
    assert e.ai_review is False


def test_classify_http_status_error_stops_batch(tmp_path, monkeypatch):
    from local_file_organizer.classify.ai import OpenAIClient
    cfg = _cfg(tmp_path, provider="openai", endpoint="http://localhost:1234/v1")
    calls = []

    def boom(self, prompt):
        calls.append(1)
        req = httpx.Request("POST", "http://x/chat/completions")
        raise httpx.HTTPStatusError("401", request=req, response=httpx.Response(401, request=req))

    monkeypatch.setattr(OpenAIClient, "classify", boom)
    e1 = _txt_entry(tmp_path, "a.txt", "tresc a")
    e2 = _txt_entry(tmp_path, "b.txt", "tresc b zupelnie inna")
    classify_entries([e1, e2], cfg, cache=None)  # fallback -> nie rzuca
    assert e1.ai_category is None and e2.ai_category is None
    assert len(calls) == 1   # batch-stop: drugi plik juz nie wola serwera


def test_classify_http_status_error_abort_raises(tmp_path, monkeypatch):
    from local_file_organizer.classify.ai import OpenAIClient
    cfg = _cfg(tmp_path, provider="openai", on_error="abort")

    def boom(self, prompt):
        req = httpx.Request("POST", "http://x")
        raise httpx.HTTPStatusError("401", request=req, response=httpx.Response(401, request=req))

    monkeypatch.setattr(OpenAIClient, "classify", boom)
    e = _txt_entry(tmp_path, "f.txt", "tresc")
    with pytest.raises(httpx.HTTPStatusError):
        classify_entries([e], cfg, cache=None)


def test_extract_json_handles_fences_and_prose():
    from local_file_organizer.classify.ai import _extract_json
    assert _extract_json('{"a": 1}') == {"a": 1}
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Oto wynik:\n{"a": 1}\nGotowe.') == {"a": 1}


def test_openai_client_json_schema_mode(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["json"] = json
        return _Resp({"choices": [{"message": {"content": '{"category": "faktury", "confidence": 0.9, "suggested_name": null}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    from local_file_organizer.classify.ai import OpenAIClient
    result = OpenAIClient("http://x/v1", "gemma", json_mode="json_schema").classify("p")
    assert result["category"] == "faktury"
    assert captured["json"]["response_format"]["type"] == "json_schema"


def test_openai_client_off_mode_omits_response_format(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["json"] = json
        return _Resp({"choices": [{"message": {"content": '{"category": "nieznane", "confidence": 0.1}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    from local_file_organizer.classify.ai import OpenAIClient
    OpenAIClient("http://x/v1", "gemma", json_mode="off").classify("p")
    assert "response_format" not in captured["json"]


def test_openai_client_parses_fenced_content(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return _Resp({"choices": [{"message": {"content": "```json\n{\"category\": \"umowy\", \"confidence\": 0.8}\n```"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    from local_file_organizer.classify.ai import OpenAIClient
    result = OpenAIClient("http://x/v1", "gemma").classify("p")
    assert result["category"] == "umowy"


def test_build_client_openai_passes_json_mode():
    from local_file_organizer.classify.ai import build_client, OpenAIClient
    from local_file_organizer.config import AIConfig
    client = build_client(AIConfig(provider="openai", json_mode="json_schema"))
    assert isinstance(client, OpenAIClient)
    assert client.json_mode == "json_schema"
