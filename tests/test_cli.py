import yaml
from typer.testing import CliRunner
from local_file_organizer.cli import app

runner = CliRunner()


def _make_yaml(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "setup.zip").write_text("aplikacja instalacyjna")
    (src / "model.stl").write_text("model 3d ascii")
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(tmp_path / "out"),
        "mode": "category",
        "categories": {"apps": ["zip"], "3dprint": ["stl"]},
        "password_detection": {"enabled": False},
    }
    p = tmp_path / "lfo.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p, src, tmp_path / "out"


def test_run_dry_run_does_not_move(tmp_path):
    yaml_path, src, out = _make_yaml(tmp_path)
    result = runner.invoke(app, ["run", "--config", str(yaml_path)])
    assert result.exit_code == 0
    assert (src / "setup.zip").exists()       # nic nie ruszone
    assert not out.exists()


def test_run_apply_moves_files(tmp_path):
    yaml_path, src, out = _make_yaml(tmp_path)
    result = runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert result.exit_code == 0
    assert (out / "apps" / "setup.zip").exists()
    assert (out / "3dprint" / "model.stl").exists()
    assert not (src / "setup.zip").exists()


def test_undo_last_restores(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "setup.zip").write_text("x")
    out = tmp_path / "out"
    db = tmp_path / "cache.sqlite"
    cfg = {
        "source_dir": str(src),
        "dest_dir": str(out),
        "mode": "category",
        "categories": {"apps": ["zip"]},
        "password_detection": {"enabled": False},
        "cache": {"path": str(db)},
    }
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    runner.invoke(app, ["run", "--config", str(yaml_path), "--apply"])
    assert (out / "apps" / "setup.zip").exists()

    result = runner.invoke(app, ["undo", "last", "--db", str(db)])
    assert result.exit_code == 0
    assert (src / "setup.zip").exists()
    assert not (out / "apps" / "setup.zip").exists()


def test_cli_source_dest_override(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    (src / "a.txt").write_text("x")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["run", "--source", str(src), "--dest", str(out), "--mode", "type", "--apply"],
    )
    assert result.exit_code == 0
    assert (out / "txt" / "a.txt").exists()
