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


def test_reason_has_ai_and_review():
    assert Reason.AI.value == "ai"
    assert Reason.REVIEW.value == "review"


def test_file_entry_ai_defaults():
    from pathlib import Path as _P
    e = FileEntry(path=_P("/a/b.pdf"), size=1, ext="pdf")
    assert e.ai_category is None
    assert e.ai_review is False
    assert e.ai_suggestion is None
    assert e.ai_from_cache is False


def test_planned_move_has_subcategory():
    from pathlib import Path as _P
    m = PlannedMove(source=_P("/a"), dest=_P("/b"), reason=Reason.AI,
                    category="dokumenty", subcategory="faktury")
    assert m.subcategory == "faktury"
