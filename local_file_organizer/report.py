from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .models import FileEntry, Plan, Reason


def human_size(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def build_summary(plan: Plan, entries: list[FileEntry], applied: bool) -> dict:
    size_by_source = {e.path: e.size for e in entries}
    moved_bytes = sum(size_by_source.get(m.source, 0) for m in plan.moves)
    duplicates = sum(1 for m in plan.moves if m.reason == Reason.DUPLICATE)
    unsorted = sum(1 for m in plan.moves if m.reason == Reason.UNSORTED)
    unsorted_files = [str(m.source) for m in plan.moves if m.reason == Reason.UNSORTED]
    ai_count = sum(1 for m in plan.moves if m.reason == Reason.AI)
    review_count = sum(1 for m in plan.moves if m.reason == Reason.REVIEW)
    # ai_from_cache liczy wpisy (oszczednosci wywolan Ollamy), nie przeniesienia
    from_cache = sum(1 for e in entries if e.ai_from_cache)
    suggestions = [
        (str(e.path), e.ai_suggestion) for e in entries if e.ai_suggestion
    ]
    encrypted = [e for e in entries if e.is_encrypted]
    per_folder = Counter(str(m.dest.parent) for m in plan.moves)
    return {
        "applied": applied,
        "moved_count": len(plan.moves),
        "moved_bytes": moved_bytes,
        "moved_human": human_size(moved_bytes),
        "duplicates": duplicates,
        "unsorted": unsorted,
        "unsorted_files": unsorted_files,
        "ai_count": ai_count,
        "review_count": review_count,
        "ai_from_cache": from_cache,
        "suggestions": suggestions,
        "encrypted": [(str(e.path), e.encrypted_format) for e in encrypted],
        "skipped": len(plan.skipped),
        "errors": len(plan.errors),
        "per_folder": dict(per_folder),
    }


def render_console(summary: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    verb = "Przeniesiono" if summary["applied"] else "Zostaloby przeniesione"
    table = Table(title="Local File Organizer — podsumowanie")
    table.add_column("Metryka")
    table.add_column("Wartosc", justify="right")
    table.add_row(verb, str(summary["moved_count"]))
    table.add_row("Rozmiar", summary["moved_human"])
    table.add_row("Duplikaty", str(summary["duplicates"]))
    table.add_row("Zabezpieczone haslem", str(len(summary["encrypted"])))
    table.add_row("Unsorted", str(summary["unsorted"]))
    table.add_row("Sklasyfikowane przez AI", str(summary["ai_count"]))
    table.add_row("Do przejrzenia", str(summary["review_count"]))
    table.add_row("Z cache AI", str(summary["ai_from_cache"]))
    table.add_row("Pominiete", str(summary["skipped"]))
    table.add_row("Bledy", str(summary["errors"]))
    console.print(table)
    if summary["unsorted_files"]:
        console.print("\n[bold]Pliki bez dopasowania (unsorted):[/bold]")
        for path in summary["unsorted_files"]:
            console.print(f"  - {path}", markup=False)
    if summary["encrypted"]:
        console.print("\n[bold]Pliki zabezpieczone haslem:[/bold]")
        for path, fmt in summary["encrypted"]:
            console.print(f"  - {path} ({fmt})", markup=False)
    if summary["suggestions"]:
        console.print("\n[bold]Sugestie nowych kategorii (do_przejrzenia):[/bold]")
        for path, name in summary["suggestions"]:
            console.print(f"  - {path} -> {name}", markup=False)


def write_json(summary: dict, output: Path) -> None:
    Path(output).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
