from pathlib import Path
from local_file_organizer.models import FileEntry, PlannedMove, Plan, Reason


def test_file_entry_defaults():
    e = FileEntry(path=Path("/a/b.pdf"), size=10, ext="pdf")
    assert e.content_hash is None
    assert e.is_encrypted is False
    assert e.duplicate_of is None


def test_plan_starts_empty():
    plan = Plan()
    assert plan.moves == []
    assert plan.skipped == []
    assert plan.errors == []


def test_planned_move_reason_enum():
    m = PlannedMove(source=Path("/a"), dest=Path("/b"), reason=Reason.BASE)
    assert m.reason.value == "base"
