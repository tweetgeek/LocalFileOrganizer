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
