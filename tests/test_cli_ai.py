import httpx
import yaml
from typer.testing import CliRunner
from local_file_organizer.cli import app
from local_file_organizer.classify.ai import OllamaClient

runner = CliRunner()


def test_run_with_ai_routes_to_subcategory(tmp_path, monkeypatch):
    src = tmp_path / "src"; src.mkdir()
    (src / "faktura.txt").write_text("tresc z NIP 123", encoding="utf-8")
    out = tmp_path / "out"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"dokumenty": ["txt"]},
        "password_detection": {"enabled": False},
        "cache": {"path": str(tmp_path / "c.sqlite")},
        "ai": {
            "enabled": True,
            "extensions": ["txt"],
            "taxonomy": {"faktury": "zawiera NIP"},
        },
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    monkeypatch.setattr(
        OllamaClient, "classify",
        lambda self, prompt: {"category": "faktury", "confidence": 0.95},
    )

    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 0
    assert (out / "dokumenty" / "faktury" / "faktura.txt").exists()


def test_run_ai_disabled_ignores_taxonomy(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "faktura.txt").write_text("x", encoding="utf-8")
    out = tmp_path / "out"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"dokumenty": ["txt"]},
        "password_detection": {"enabled": False},
        "ai": {"enabled": False, "taxonomy": {"faktury": "x"}},
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 0
    assert (out / "dokumenty" / "faktura.txt").exists()  # bez podkategorii


def test_run_ai_abort_shows_clean_error(tmp_path, monkeypatch):
    src = tmp_path / "src"; src.mkdir()
    (src / "faktura.txt").write_text("tresc", encoding="utf-8")
    out = tmp_path / "out"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"dokumenty": ["txt"]},
        "password_detection": {"enabled": False},
        "cache": {"enabled": False},
        "ai": {
            "enabled": True,
            "extensions": ["txt"],
            "on_error": "abort",
            "taxonomy": {"faktury": "x"},
        },
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def boom(self, prompt):
        raise httpx.ConnectError("brak polaczenia")

    monkeypatch.setattr(OllamaClient, "classify", boom)

    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 1
    assert "AI" in result.output


def test_run_with_openai_provider_routes_to_subcategory(tmp_path, monkeypatch):
    from local_file_organizer.classify.ai import OpenAIClient

    src = tmp_path / "src"; src.mkdir()
    (src / "faktura.txt").write_text("tresc z NIP 123", encoding="utf-8")
    out = tmp_path / "out"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"dokumenty": ["txt"]},
        "password_detection": {"enabled": False},
        "cache": {"path": str(tmp_path / "c.sqlite")},
        "ai": {
            "enabled": True,
            "provider": "openai",
            "endpoint": "http://localhost:1234/v1",
            "model": "google/gemma-4-e4b",
            "extensions": ["txt"],
            "taxonomy": {"faktury": "zawiera NIP"},
        },
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    monkeypatch.setattr(
        OpenAIClient, "classify",
        lambda self, prompt: {"category": "faktury", "confidence": 0.95},
    )

    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 0
    assert (out / "dokumenty" / "faktury" / "faktura.txt").exists()
