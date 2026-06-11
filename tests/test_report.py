import json
from pathlib import Path
from local_file_organizer.models import FileEntry, Plan, PlannedMove, Reason
from local_file_organizer.report import build_summary, human_size, write_json


def test_human_size_formats_units():
    assert human_size(0) == "0.0 B"
    assert human_size(1536) == "1.5 KB"


def test_build_summary_counts_and_bytes():
    src = Path("/src/a.zip")
    entries = [
        FileEntry(path=src, size=2048, ext="zip"),
        FileEntry(path=Path("/src/secret.pdf"), size=10, ext="pdf",
                  is_encrypted=True, encrypted_format="pdf"),
    ]
    plan = Plan(moves=[
        PlannedMove(source=src, dest=Path("/out/apps/a.zip"),
                    reason=Reason.BASE, category="apps"),
    ])
    summary = build_summary(plan, entries, applied=True)
    assert summary["moved_count"] == 1
    assert summary["moved_bytes"] == 2048
    assert summary["moved_human"] == "2.0 KB"
    assert len(summary["encrypted"]) == 1
    assert summary["applied"] is True


def test_write_json_roundtrip(tmp_path):
    summary = {"moved_count": 3, "moved_human": "1.0 KB"}
    out = tmp_path / "r.json"
    write_json(summary, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["moved_count"] == 3


def test_summary_lists_unsorted_files():
    src1 = Path("/src/mystery.xyz")
    src2 = Path("/src/setup.zip")
    entries = [
        FileEntry(path=src1, size=1, ext="xyz"),
        FileEntry(path=src2, size=1, ext="zip"),
    ]
    plan = Plan(moves=[
        PlannedMove(source=src1, dest=Path("/out/unsorted/mystery.xyz"),
                    reason=Reason.UNSORTED),
        PlannedMove(source=src2, dest=Path("/out/apps/setup.zip"),
                    reason=Reason.BASE, category="apps"),
    ])
    summary = build_summary(plan, entries, applied=False)
    assert summary["unsorted"] == 1
    assert summary["unsorted_files"] == ["/src/mystery.xyz"]


def test_render_console_shows_unsorted_files(capsys):
    from local_file_organizer.report import render_console
    src = Path("/src/mystery.xyz")
    plan = Plan(moves=[
        PlannedMove(source=src, dest=Path("/out/unsorted/mystery.xyz"),
                    reason=Reason.UNSORTED),
    ])
    summary = build_summary(plan, [FileEntry(path=src, size=1, ext="xyz")], applied=False)
    render_console(summary)
    out = capsys.readouterr().out
    assert "unsorted" in out.lower()
    assert "mystery.xyz" in out
