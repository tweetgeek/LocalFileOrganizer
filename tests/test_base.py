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
