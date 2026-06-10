from local_file_organizer.classify.extractors import extract_text


def test_txt_extraction_truncates(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("ABCDEFGHIJ", encoding="utf-8")
    assert extract_text(f, "txt", max_chars=4) == "ABCD"


def test_md_and_csv_supported(tmp_path):
    md = tmp_path / "a.md"; md.write_text("# tytul", encoding="utf-8")
    csv = tmp_path / "a.csv"; csv.write_text("a,b,c", encoding="utf-8")
    assert extract_text(md, "md", 100) == "# tytul"
    assert extract_text(csv, "csv", 100) == "a,b,c"


def test_unsupported_extension_returns_none(tmp_path):
    f = tmp_path / "a.bin"; f.write_bytes(b"\x00\x01")
    assert extract_text(f, "bin", 100) is None


def test_broken_pdf_returns_none(tmp_path):
    f = tmp_path / "broken.pdf"; f.write_text("to nie jest pdf", encoding="utf-8")
    assert extract_text(f, "pdf", 100) is None
