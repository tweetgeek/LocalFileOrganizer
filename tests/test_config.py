import pytest
import yaml
from local_file_organizer.config import Config, load_config


def test_minimal_config_defaults(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    cfg = Config(source_dir=src, dest_dir=tmp_path / "out")
    assert cfg.mode == "category"
    assert cfg.recursive is True
    assert cfg.conflict == "rename"
    assert cfg.dedup.action == "quarantine"
    assert "pdf" in cfg.password_detection.formats


def test_source_dir_must_exist(tmp_path):
    with pytest.raises(ValueError):
        Config(source_dir=tmp_path / "nie_ma", dest_dir=tmp_path / "out")


def test_source_and_dest_must_differ(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    with pytest.raises(ValueError):
        Config(source_dir=src, dest_dir=src)


def test_extra_keys_ignored(tmp_path):
    # sekcja ai: jest ignorowana w Planie 1
    src = tmp_path / "src"
    src.mkdir()
    cfg = Config(source_dir=src, dest_dir=tmp_path / "out", ai={"enabled": True})
    assert cfg.source_dir == src


def test_load_config_from_yaml(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    yaml_path = tmp_path / "lfo.yaml"
    yaml_path.write_text(
        yaml.safe_dump({
            "source_dir": str(src),
            "dest_dir": str(tmp_path / "out"),
            "mode": "type",
        }),
        encoding="utf-8",
    )
    cfg = load_config(yaml_path)
    assert cfg.mode == "type"


def test_ai_defaults(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cfg = Config(source_dir=src, dest_dir=tmp_path / "out")
    assert cfg.ai.enabled is False
    assert cfg.ai.model == "llama3.2"
    assert cfg.ai.confidence_threshold == 0.7
    assert cfg.ai.on_error == "fallback"
    assert cfg.review_dir == "do_przejrzenia"


def test_ai_taxonomy_parsed(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cfg = Config(
        source_dir=src, dest_dir=tmp_path / "out",
        ai={"enabled": True, "taxonomy": {"faktury": "zawiera NIP"}},
    )
    assert cfg.ai.enabled is True
    assert cfg.ai.taxonomy["faktury"] == "zawiera NIP"
