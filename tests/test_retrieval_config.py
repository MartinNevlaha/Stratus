"""Tests for retrieval configuration loading."""

import json

from stratus.retrieval.config import (
    DevRagConfig,
    RetrievalConfig,
    VexorConfig,
    load_retrieval_config,
)


class TestVexorConfig:
    def test_defaults(self):
        cfg = VexorConfig()
        assert cfg.enabled is True
        assert cfg.binary_path == "vexor"
        assert cfg.model == "nomic-embed-text-v1.5"
        assert cfg.exclude_patterns == []

    def test_custom_values(self):
        cfg = VexorConfig(
            enabled=False,
            binary_path="/usr/local/bin/vexor",
            model="custom-model",
            exclude_patterns=["*.pyc", "node_modules"],
        )
        assert cfg.enabled is False
        assert cfg.binary_path == "/usr/local/bin/vexor"
        assert cfg.model == "custom-model"
        assert cfg.exclude_patterns == ["*.pyc", "node_modules"]


class TestDevRagConfig:
    def test_defaults(self):
        cfg = DevRagConfig()
        assert cfg.enabled is False
        assert cfg.db_path is None

    def test_custom_values(self):
        cfg = DevRagConfig(
            enabled=True,
            db_path="/tmp/governance.db",
        )
        assert cfg.enabled is True
        assert cfg.db_path == "/tmp/governance.db"


class TestRetrievalConfig:
    def test_defaults(self):
        cfg = RetrievalConfig()
        assert isinstance(cfg.vexor, VexorConfig)
        assert isinstance(cfg.devrag, DevRagConfig)
        assert cfg.project_root is None

    def test_nested_configs(self):
        cfg = RetrievalConfig(
            vexor=VexorConfig(enabled=False),
            devrag=DevRagConfig(db_path="/tmp/gov.db"),
            project_root="/my/project",
        )
        assert cfg.vexor.enabled is False
        assert cfg.devrag.db_path == "/tmp/gov.db"
        assert cfg.project_root == "/my/project"


class TestLoadRetrievalConfig:
    def test_load_from_nonexistent_file(self, tmp_path):
        cfg = load_retrieval_config(tmp_path / "nonexistent.json")
        assert cfg.vexor.enabled is True
        assert cfg.devrag.enabled is False

    def test_load_from_json_file(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps(
                {
                    "retrieval": {
                        "vexor": {"enabled": False, "model": "custom-model"},
                        "devrag": {"enabled": True, "db_path": "/tmp/gov.db"},
                        "project_root": "/some/path",
                    }
                }
            )
        )
        cfg = load_retrieval_config(config_file)
        assert cfg.vexor.enabled is False
        assert cfg.vexor.model == "custom-model"
        assert cfg.devrag.enabled is True
        assert cfg.devrag.db_path == "/tmp/gov.db"
        assert cfg.project_root == "/some/path"

    def test_load_with_partial_config(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"retrieval": {"vexor": {"enabled": False}}}))
        cfg = load_retrieval_config(config_file)
        assert cfg.vexor.enabled is False
        assert cfg.devrag.enabled is False  # default preserved

    def test_load_with_invalid_json(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("not valid json{{{")
        cfg = load_retrieval_config(config_file)
        assert cfg.vexor.enabled is True  # falls back to defaults

    def test_load_without_retrieval_key(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"other_key": "value"}))
        cfg = load_retrieval_config(config_file)
        assert cfg.vexor.enabled is True

    def test_env_override_vexor_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_VEXOR_PATH", "/custom/vexor")
        cfg = load_retrieval_config(tmp_path / "nonexistent.json")
        assert cfg.vexor.binary_path == "/custom/vexor"

    def test_env_override_devrag_db_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_DEVRAG_DB_PATH", "/custom/governance.db")
        cfg = load_retrieval_config(tmp_path / "nonexistent.json")
        assert cfg.devrag.db_path == "/custom/governance.db"

    def test_env_overrides_file_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps({"retrieval": {"vexor": {"binary_path": "/from/file"}}})
        )
        monkeypatch.setenv("AI_FRAMEWORK_VEXOR_PATH", "/from/env")
        cfg = load_retrieval_config(config_file)
        assert cfg.vexor.binary_path == "/from/env"

    def test_load_with_empty_file(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("")
        cfg = load_retrieval_config(config_file)
        assert cfg.vexor.enabled is True

    def test_load_exclude_patterns(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps(
                {"retrieval": {"vexor": {"exclude_patterns": ["*.pyc", "__pycache__"]}}}
            )
        )
        cfg = load_retrieval_config(config_file)
        assert cfg.vexor.exclude_patterns == ["*.pyc", "__pycache__"]

    def test_load_devrag_db_path_from_file(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps({"retrieval": {"devrag": {"db_path": "/data/governance.db"}}})
        )
        cfg = load_retrieval_config(config_file)
        assert cfg.devrag.db_path == "/data/governance.db"
