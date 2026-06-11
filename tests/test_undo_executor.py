import pytest
from pathlib import Path
from local_file_organizer.models import Plan, PlannedMove, Reason
from local_file_organizer.undo import UndoStore
from local_file_organizer.executor import apply_plan


def test_apply_moves_files_and_records_run(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    f = src / "a.txt"; f.write_text("dane")
    dest = tmp_path / "out" / "txt" / "a.txt"
    plan = Plan(moves=[PlannedMove(source=f, dest=dest, reason=Reason.BASE)])
    store = UndoStore(tmp_path / "db.sqlite")

    result = apply_plan(plan, store)

    assert dest.exists()
    assert not f.exists()
    assert result["moved"] == 1
    assert isinstance(result["run_id"], int)


def test_undo_restores_files_and_removes_empty_dirs(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    f = src / "a.txt"; f.write_text("dane")
    dest = tmp_path / "out" / "txt" / "a.txt"
    plan = Plan(moves=[PlannedMove(source=f, dest=dest, reason=Reason.BASE)])
    store = UndoStore(tmp_path / "db.sqlite")
    result = apply_plan(plan, store)

    undo_result = store.undo_run(result["run_id"])

    assert f.exists()
    assert f.read_text() == "dane"
    assert not dest.exists()
    assert not dest.parent.exists()  # pusty utworzony folder usuniety
    assert undo_result["restored"] == 1


def test_undo_last_resolves_latest_run(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    f = src / "a.txt"; f.write_text("dane")
    dest = tmp_path / "out" / "a.txt"
    plan = Plan(moves=[PlannedMove(source=f, dest=dest, reason=Reason.BASE)])
    store = UndoStore(tmp_path / "db.sqlite")
    apply_plan(plan, store)
    assert store.last_run_id() is not None


def test_apply_never_overwrites_existing_dest(tmp_path):
    # straznik bezpieczenstwa: jesli cel juz istnieje, NIE nadpisujemy
    src = tmp_path / "src"; src.mkdir()
    f = src / "a.txt"; f.write_text("nowe")
    dest_dir = tmp_path / "out" / "txt"; dest_dir.mkdir(parents=True)
    dest = dest_dir / "a.txt"; dest.write_text("istniejace")
    plan = Plan(moves=[PlannedMove(source=f, dest=dest, reason=Reason.BASE)])
    store = UndoStore(tmp_path / "db.sqlite")

    result = apply_plan(plan, store)

    assert result["moved"] == 0
    assert dest.read_text() == "istniejace"   # nie nadpisane
    assert f.exists()                          # zrodlo nietkniete
    assert len(plan.errors) == 1


def test_undo_invalid_run_id_raises(tmp_path):
    store = UndoStore(tmp_path / "db.sqlite")
    with pytest.raises(ValueError):
        store.undo_run(99999)


def test_undo_store_context_manager_closes(tmp_path):
    import sqlite3
    with UndoStore(tmp_path / "db.sqlite") as store:
        rid = store.start_run()
        store.finish_run(rid)
    with pytest.raises(sqlite3.ProgrammingError):
        store.conn.execute("SELECT 1")  # polaczenie zamkniete po wyjsciu z with
