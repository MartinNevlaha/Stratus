"""Tests for rule_engine/config.py — RulesConfig loading with env var overrides."""

from __future__ import annotations

import json


class TestRulesConfigDefaults:
    def test_immutability_check_default_true(self):
        from stratus.rule_engine.config import RulesConfig

        cfg = RulesConfig()
        assert cfg.immutability_check is True

    def test_enforce_in_classic_default_false(self):
        from stratus.rule_engine.config import RulesConfig

        cfg = RulesConfig()
        assert cfg.enforce_in_classic is False

    def test_is_dataclass(self):
        import dataclasses

        from stratus.rule_engine.config import RulesConfig

        assert dataclasses.is_dataclass(RulesConfig)


class TestLoadRulesConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        from stratus.rule_engine.config import load_rules_config

        cfg = load_rules_config(tmp_path / "nonexistent.json")
        assert cfg.immutability_check is True
        assert cfg.enforce_in_classic is False

    def test_returns_defaults_for_none_path(self):
        from stratus.rule_engine.config import load_rules_config

        cfg = load_rules_config(None)
        assert cfg.immutability_check is True
        assert cfg.enforce_in_classic is False

    def test_loads_from_rules_section(self, tmp_path):
        from stratus.rule_engine.config import load_rules_config

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps(
                {
                    "rules": {
                        "immutability_check": False,
                        "enforce_in_classic": True,
                    }
                }
            )
        )
        cfg = load_rules_config(config_file)
        assert cfg.immutability_check is False
        assert cfg.enforce_in_classic is True

    def test_partial_config_uses_defaults(self, tmp_path):
        from stratus.rule_engine.config import load_rules_config

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps(
                {
                    "rules": {
                        "immutability_check": False,
                    }
                }
            )
        )
        cfg = load_rules_config(config_file)
        assert cfg.immutability_check is False
        assert cfg.enforce_in_classic is False  # default

    def test_missing_rules_key_uses_defaults(self, tmp_path):
        from stratus.rule_engine.config import load_rules_config

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"learning": {}}))
        cfg = load_rules_config(config_file)
        assert cfg.immutability_check is True
        assert cfg.enforce_in_classic is False

    def test_invalid_json_uses_defaults(self, tmp_path):
        from stratus.rule_engine.config import load_rules_config

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("not valid json")
        cfg = load_rules_config(config_file)
        assert cfg.immutability_check is True

    def test_empty_file_uses_defaults(self, tmp_path):
        from stratus.rule_engine.config import load_rules_config

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("")
        cfg = load_rules_config(config_file)
        assert cfg.immutability_check is True


class TestEnvVarOverrides:
    def test_env_disables_immutability_check(self, monkeypatch):
        from stratus.rule_engine.config import load_rules_config

        monkeypatch.setenv("AI_FRAMEWORK_RULES_IMMUTABILITY", "false")
        cfg = load_rules_config(None)
        assert cfg.immutability_check is False

    def test_env_enables_immutability_check(self, tmp_path, monkeypatch):
        from stratus.rule_engine.config import load_rules_config

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"rules": {"immutability_check": False}}))
        monkeypatch.setenv("AI_FRAMEWORK_RULES_IMMUTABILITY", "true")
        cfg = load_rules_config(config_file)
        assert cfg.immutability_check is True

    def test_env_true_value(self, monkeypatch):
        from stratus.rule_engine.config import load_rules_config

        monkeypatch.setenv("AI_FRAMEWORK_RULES_IMMUTABILITY", "true")
        cfg = load_rules_config(None)
        assert cfg.immutability_check is True

    def test_env_1_value(self, monkeypatch):
        from stratus.rule_engine.config import load_rules_config

        monkeypatch.setenv("AI_FRAMEWORK_RULES_IMMUTABILITY", "1")
        cfg = load_rules_config(None)
        assert cfg.immutability_check is True

    def test_env_yes_value(self, monkeypatch):
        from stratus.rule_engine.config import load_rules_config

        monkeypatch.setenv("AI_FRAMEWORK_RULES_IMMUTABILITY", "yes")
        cfg = load_rules_config(None)
        assert cfg.immutability_check is True

    def test_env_0_disables(self, monkeypatch):
        from stratus.rule_engine.config import load_rules_config

        monkeypatch.setenv("AI_FRAMEWORK_RULES_IMMUTABILITY", "0")
        cfg = load_rules_config(None)
        assert cfg.immutability_check is False

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        from stratus.rule_engine.config import load_rules_config

        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"rules": {"immutability_check": True}}))
        monkeypatch.setenv("AI_FRAMEWORK_RULES_IMMUTABILITY", "false")
        cfg = load_rules_config(config_file)
        assert cfg.immutability_check is False
