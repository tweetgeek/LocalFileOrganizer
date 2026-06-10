import sqlite3
import pytest
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


def test_suggested_name_roundtrip(tmp_path):
    cache = AICache(tmp_path / "c.sqlite")
    cache.put("k", {"category": "nieznane", "confidence": 0.4, "suggested_name": "paragony"})
    got = cache.get("k")
    assert got["suggested_name"] == "paragony"


def test_cache_context_manager_closes(tmp_path):
    with AICache(tmp_path / "c.sqlite") as cache:
        cache.put("k", {"category": "x", "confidence": 0.5, "suggested_name": None})
    with pytest.raises(sqlite3.ProgrammingError):
        cache.conn.execute("SELECT 1")  # polaczenie zamkniete po wyjsciu z with
