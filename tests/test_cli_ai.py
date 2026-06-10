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
