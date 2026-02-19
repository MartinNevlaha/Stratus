"""Tests for self_debug/config.py — configuration for the self-debug sandbox."""

from __future__ import annotations

import json

from stratus.self_debug.config import SelfDebugConfig, load_self_debug_config


class TestSelfDebugConfigDefaults:
    def test_enabled_defaults_to_false(self):
        cfg = SelfDebugConfig()
        assert cfg.enabled is False

    def test_max_patch_lines_defaults_to_200(self):
        cfg = SelfDebugConfig()
        assert cfg.max_patch_lines == 200

    def test_max_issues_defaults_to_50(self):
        cfg = SelfDebugConfig()
        assert cfg.max_issues == 50

    def test_analyze_tests_defaults_to_false(self):
        cfg = SelfDebugConfig()
        assert cfg.analyze_tests is False


class TestLoadSelfDebugConfig:
    def test_returns_defaults_when_file_doesnt_exist(self, tmp_path):
        cfg = load_self_debug_config(tmp_path / "nonexistent.json")
        assert cfg.enabled is False
        assert cfg.max_patch_lines == 200
        assert cfg.max_issues == 50
        assert cfg.analyze_tests is False

    def test_returns_defaults_when_path_is_none(self):
        cfg = load_self_debug_config(None)
        assert cfg.enabled is False
        assert cfg.max_patch_lines == 200

    def test_loads_values_from_ai_framework_json(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps(
                {
                    "self_debug": {
                        "enabled": True,
                        "max_patch_lines": 500,
                        "max_issues": 100,
                        "analyze_tests": True,
                    }
                }
            )
        )
        cfg = load_self_debug_config(config_file)
        assert cfg.enabled is True
        assert cfg.max_patch_lines == 500
        assert cfg.max_issues == 100
        assert cfg.analyze_tests is True

    def test_partial_config_keeps_remaining_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps(
                {
                    "self_debug": {
                        "enabled": True,
                    }
                }
            )
        )
        cfg = load_self_debug_config(config_file)
        assert cfg.enabled is True
        assert cfg.max_patch_lines == 200
        assert cfg.max_issues == 50
        assert cfg.analyze_tests is False

    def test_missing_self_debug_key_returns_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"learning": {}}))
        cfg = load_self_debug_config(config_file)
        assert cfg.enabled is False

    def test_empty_file_returns_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("")
        cfg = load_self_debug_config(config_file)
        assert cfg.enabled is False

    def test_invalid_json_returns_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("not json")
        cfg = load_self_debug_config(config_file)
        assert cfg.enabled is False


class TestEnvVarOverrides:
    def test_env_true_enables_self_debug(self, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_SELF_DEBUG_ENABLED", "true")
        cfg = load_self_debug_config(None)
        assert cfg.enabled is True

    def test_env_false_overrides_file_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"self_debug": {"enabled": True}}))
        monkeypatch.setenv("AI_FRAMEWORK_SELF_DEBUG_ENABLED", "false")
        cfg = load_self_debug_config(config_file)
        assert cfg.enabled is False

    def test_env_case_insensitive_True(self, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_SELF_DEBUG_ENABLED", "True")
        cfg = load_self_debug_config(None)
        assert cfg.enabled is True

    def test_env_case_insensitive_TRUE(self, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_SELF_DEBUG_ENABLED", "TRUE")
        cfg = load_self_debug_config(None)
        assert cfg.enabled is True

    def test_env_overrides_file_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"self_debug": {"enabled": False}}))
        monkeypatch.setenv("AI_FRAMEWORK_SELF_DEBUG_ENABLED", "true")
        cfg = load_self_debug_config(config_file)
        assert cfg.enabled is True
