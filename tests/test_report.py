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
