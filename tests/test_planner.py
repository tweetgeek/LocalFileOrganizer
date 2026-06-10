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
