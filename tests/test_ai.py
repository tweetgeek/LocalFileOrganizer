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
