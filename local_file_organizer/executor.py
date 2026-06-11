from __future__ import annotations

import shutil

from .models import Plan
from .undo import UndoStore


def apply_plan(plan: Plan, undo_store: UndoStore) -> dict:
    run_id = undo_store.start_run()
    moved = 0
    created_dirs: set = set()
    for move in plan.moves:
        try:
            if move.dest.exists():
                # twardy straznik: nigdy nie nadpisujemy
                plan.errors.append(
                    (move.source, f"cel juz istnieje, pomijam: {move.dest}")
                )
                continue
            parent = move.dest.parent
            if not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
                if parent not in created_dirs:
                    created_dirs.add(parent)
                    undo_store.record_dir(run_id, parent)
            # dest.exists() guard powyzej wyklucza tez katalog o tej nazwie;
            # planner emituje wylacznie sciezki plikow, wiec move nie przekieruje do katalogu
            shutil.move(str(move.source), str(move.dest))
            undo_store.record_move(run_id, move.source, move.dest)
            moved += 1
        except Exception as exc:  # blad per plik -> log i kontynuuj
            plan.errors.append((move.source, str(exc)))
    undo_store.finish_run(run_id)
    return {"run_id": run_id, "moved": moved}
