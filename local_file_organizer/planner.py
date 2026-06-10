from __future__ import annotations

from pathlib import Path

from .classify.base import resolve_base
from .config import Config
from .models import FileEntry, Plan, PlannedMove, Reason


def _unique_dest(desired: Path, taken: set[Path]) -> Path:
    if desired not in taken and not desired.exists():
        return desired
    stem, suffix = desired.stem, desired.suffix
    i = 1
    while True:
        candidate = desired.with_name(f"{stem} ({i}){suffix}")
        if candidate not in taken and not candidate.exists():
            return candidate
        i += 1


def _note(entry: FileEntry) -> str | None:
    parts: list[str] = []
    if entry.is_encrypted:
        parts.append(f"zabezpieczony haslem ({entry.encrypted_format})")
    if entry.ai_suggestion:
        parts.append(f"sugestia AI: {entry.ai_suggestion}")
    return "; ".join(parts) if parts else None


def build_plan(entries: list[FileEntry], config: Config) -> Plan:
    plan = Plan()
    dest_root = config.dest_dir
    taken: set[Path] = set()

    for entry in entries:
        # 1. Duplikat -> kwarantanna albo tylko raport
        if entry.duplicate_of is not None:
            if config.dedup.action == "report_only":
                plan.skipped.append((entry.path, f"duplikat: {entry.duplicate_of}"))
                continue
            desired = dest_root / config.duplicates_dir / entry.path.name
            dest = _unique_dest(desired, taken)
            taken.add(dest)
            plan.moves.append(
                PlannedMove(
                    source=entry.path,
                    dest=dest,
                    reason=Reason.DUPLICATE,
                    note=f"duplikat: {entry.duplicate_of}",
                )
            )
            continue

        # 2. Folder docelowy: review > podkategoria AI > baza/unsorted
        subcategory: str | None = None
        category = resolve_base(entry.ext, config)

        if entry.ai_review:
            target_dir = dest_root / config.review_dir
            reason = Reason.REVIEW
        else:
            if category is None:
                base_dir = dest_root / config.unknown_dir
                reason = Reason.UNSORTED
            else:
                base_dir = dest_root / category
                reason = Reason.BASE
            if entry.ai_category:
                subcategory = entry.ai_category
                target_dir = base_dir / subcategory
                reason = Reason.AI
            else:
                target_dir = base_dir

        desired = target_dir / entry.path.name
        collision = desired in taken or desired.exists()
        if collision and config.conflict == "skip":
            plan.skipped.append((entry.path, "konflikt nazwy (skip)"))
            continue
        dest = _unique_dest(desired, taken)
        taken.add(dest)

        plan.moves.append(
            PlannedMove(
                source=entry.path,
                dest=dest,
                reason=reason,
                category=category,
                subcategory=subcategory,
                note=_note(entry),
            )
        )

    return plan
