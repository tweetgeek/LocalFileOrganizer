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


def test_scan_non_recursive_skips_subdirs(tmp_path):
    cfg = _cfg(tmp_path, recursive=False)
    sub = cfg.source_dir / "sub"
    sub.mkdir()
    (sub / "hidden.txt").write_text("x")
    (cfg.source_dir / "visible.txt").write_text("x")
    entries = scan(cfg)
    assert [e.path.name for e in entries] == ["visible.txt"]
