from pathlib import Path
from local_file_organizer.hashing import compute_hash, group_duplicates
from local_file_organizer.models import FileEntry


def _entry(path: Path) -> FileEntry:
    return FileEntry(path=path, size=path.stat().st_size, ext=path.suffix.lstrip("."))


def test_compute_hash_matches_for_identical_content(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("identyczne")
    b = tmp_path / "b.txt"; b.write_text("identyczne")
    assert compute_hash(a) == compute_hash(b)


def test_group_duplicates_marks_later_copies(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("dup")
    b = tmp_path / "b.txt"; b.write_text("dup")
    c = tmp_path / "c.txt"; c.write_text("inny")
    entries = [_entry(a), _entry(b), _entry(c)]
    group_duplicates(entries)
    by_name = {e.path.name: e for e in entries}
    assert by_name["a.txt"].duplicate_of is None       # oryginal (pierwszy alfabetycznie)
    assert by_name["b.txt"].duplicate_of == a          # duplikat wskazuje na a
    assert by_name["c.txt"].duplicate_of is None        # unikalny


def test_group_duplicates_size_prefilter_skips_unique_sizes(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("krotki")
    b = tmp_path / "b.txt"; b.write_text("zdecydowanie dluzsza tresc")
    entries = [_entry(a), _entry(b)]
    group_duplicates(entries)
    # rozne rozmiary -> nie hashujemy, brak duplikatow
    assert all(e.duplicate_of is None for e in entries)
    assert all(e.content_hash is None for e in entries)


def test_group_duplicates_skips_unreadable_file(tmp_path, monkeypatch):
    import local_file_organizer.hashing as hashing
    a = tmp_path / "a.txt"; a.write_text("dup")
    b = tmp_path / "b.txt"; b.write_text("dup")
    entries = [_entry(a), _entry(b)]
    real = hashing.compute_hash

    def flaky(path):
        if path == a:
            raise PermissionError("brak dostepu")
        return real(path)

    monkeypatch.setattr(hashing, "compute_hash", flaky)
    hashing.group_duplicates(entries)  # nie podnosi wyjatku
    by_name = {e.path.name: e for e in entries}
    assert by_name["a.txt"].content_hash is None   # pominiety
    assert by_name["a.txt"].duplicate_of is None
    assert by_name["b.txt"].duplicate_of is None    # a pominiety, wiec b to oryginal
