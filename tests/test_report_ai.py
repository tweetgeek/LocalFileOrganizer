from pathlib import Path
from local_file_organizer.models import FileEntry, Plan, PlannedMove, Reason
from local_file_organizer.report import build_summary


def test_summary_counts_ai_and_review_and_cache():
    src1 = Path("/src/faktura.pdf")
    src2 = Path("/src/cos.pdf")
    entries = [
        FileEntry(path=src1, size=10, ext="pdf", ai_category="faktury", ai_from_cache=True),
        FileEntry(path=src2, size=20, ext="pdf", ai_review=True, ai_suggestion="paragony"),
    ]
    plan = Plan(moves=[
        PlannedMove(source=src1, dest=Path("/out/dokumenty/faktury/faktura.pdf"),
                    reason=Reason.AI, category="dokumenty", subcategory="faktury"),
        PlannedMove(source=src2, dest=Path("/out/do_przejrzenia/cos.pdf"),
                    reason=Reason.REVIEW),
    ])
    summary = build_summary(plan, entries, applied=False)
    assert summary["ai_count"] == 1
    assert summary["review_count"] == 1
    assert summary["ai_from_cache"] == 1
    assert ("/src/cos.pdf", "paragony") in summary["suggestions"]
