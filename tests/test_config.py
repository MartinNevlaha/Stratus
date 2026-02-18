"""Tests for config loading and constants."""

import json
from pathlib import Path

from stratus.session.config import (
    COMPACTION_THRESHOLD_PCT,
    DEFAULT_PORT,
    LEARN_THRESHOLDS,
    THRESHOLD_AUTOCOMPACT,
    THRESHOLD_WARN,
    THROTTLE_MIN_INTERVAL_SEC,
    Config,
    get_data_dir,
    load_config,
)


class TestConstants:
    def test_default_port(self):
        assert DEFAULT_PORT == 41777

    def test_compaction_threshold(self):
        assert COMPACTION_THRESHOLD_PCT == 83.5

    def test_warn_threshold(self):
        assert THRESHOLD_WARN == 65

    def test_autocompact_threshold(self):
        assert THRESHOLD_AUTOCOMPACT == 75

    def test_learn_thresholds(self):
        assert LEARN_THRESHOLDS == [40, 55, 65]

    def test_throttle_interval(self):
        assert THROTTLE_MIN_INTERVAL_SEC == 30


class TestGetDataDir:
    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("AI_FRAMEWORK_DATA_DIR", raising=False)
        data_dir = get_data_dir()
        assert data_dir == Path.home() / ".ai-framework" / "data"

    def test_env_override(self, monkeypatch, tmp_path):
        custom_dir = tmp_path / "custom-data"
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(custom_dir))
        data_dir = get_data_dir()
        assert data_dir == custom_dir


class TestConfig:
    def test_default_config(self):
        config = Config()
        assert config.port == DEFAULT_PORT
        assert config.db_name == "memory.db"

    def test_config_db_path(self, monkeypatch):
        monkeypatch.delenv("AI_FRAMEWORK_DATA_DIR", raising=False)
        config = Config()
        expected = Path.home() / ".ai-framework" / "data" / "memory.db"
        assert config.db_path == expected

    def test_config_db_path_with_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        config = Config()
        assert config.db_path == tmp_path / "memory.db"


class TestLoadConfig:
    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        config = load_config(tmp_path / "nonexistent.json")
        assert config.port == DEFAULT_PORT

    def test_load_config_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"port": 9999}))
        config = load_config(config_path)
        assert config.port == 9999

    def test_load_config_partial(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"db_name": "custom.db"}))
        config = load_config(config_path)
        assert config.db_name == "custom.db"
        assert config.port == DEFAULT_PORT

    def test_port_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("AI_FRAMEWORK_PORT", "8888")
        config = load_config()
        assert config.port == 8888
