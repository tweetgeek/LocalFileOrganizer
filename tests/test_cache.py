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
