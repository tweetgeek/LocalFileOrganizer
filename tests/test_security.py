import zipfile
from local_file_organizer import security
from local_file_organizer.security import detect_password


def test_unlisted_extension_returns_false(tmp_path):
    f = tmp_path / "a.txt"; f.write_text("x")
    assert detect_password(f, "txt", ["pdf", "zip"]) is False


def test_plain_zip_not_encrypted(tmp_path):
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("inside.txt", "jawne dane")
    assert detect_password(z, "zip", ["zip"]) is False


def test_detection_error_is_swallowed(tmp_path):
    # uszkodzony "pdf" nie powinien wywalic programu, tylko zwrocic False
    bad = tmp_path / "broken.pdf"; bad.write_text("to nie jest pdf")
    assert detect_password(bad, "pdf", ["pdf"]) is False


def test_pdf_dispatch_uses_detector(tmp_path, monkeypatch):
    f = tmp_path / "secret.pdf"; f.write_text("x")
    monkeypatch.setattr(security, "_pdf_encrypted", lambda p: True)
    assert detect_password(f, "pdf", ["pdf"]) is True
