"""Tests for skills/config.py — SkillsConfig loading and env var overrides."""

from __future__ import annotations

import json

from stratus.skills.config import SkillsConfig, load_skills_config


class TestSkillsConfigDefaults:
    def test_enabled_true_by_default(self):
        cfg = SkillsConfig()
        assert cfg.enabled is True

    def test_auto_dispatch_true_by_default(self):
        cfg = SkillsConfig()
        assert cfg.auto_dispatch is True

    def test_skills_dir_default(self):
        cfg = SkillsConfig()
        assert cfg.skills_dir == ".claude/skills"


class TestLoadSkillsConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        cfg = load_skills_config(tmp_path / "nonexistent.json")
        assert cfg.enabled is True
        assert cfg.auto_dispatch is True
        assert cfg.skills_dir == ".claude/skills"

    def test_returns_defaults_when_none_path(self):
        cfg = load_skills_config(None)
        assert cfg.enabled is True

    def test_loads_from_json_skills_section(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(
            json.dumps(
                {
                    "skills": {
                        "enabled": False,
                        "auto_dispatch": False,
                        "skills_dir": "custom/skills",
                    }
                }
            )
        )
        cfg = load_skills_config(config_file)
        assert cfg.enabled is False
        assert cfg.auto_dispatch is False
        assert cfg.skills_dir == "custom/skills"

    def test_partial_config_keeps_other_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"skills": {"enabled": False}}))
        cfg = load_skills_config(config_file)
        assert cfg.enabled is False
        assert cfg.auto_dispatch is True
        assert cfg.skills_dir == ".claude/skills"

    def test_missing_skills_key_returns_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"learning": {}}))
        cfg = load_skills_config(config_file)
        assert cfg.enabled is True

    def test_invalid_json_returns_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("not json")
        cfg = load_skills_config(config_file)
        assert cfg.enabled is True

    def test_empty_file_returns_defaults(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("{}")
        cfg = load_skills_config(config_file)
        assert cfg.enabled is True


class TestEnvVarOverrides:
    def test_env_true_enables(self, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_SKILLS_ENABLED", "true")
        cfg = load_skills_config(None)
        assert cfg.enabled is True

    def test_env_false_disables(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"skills": {"enabled": True}}))
        monkeypatch.setenv("AI_FRAMEWORK_SKILLS_ENABLED", "false")
        cfg = load_skills_config(config_file)
        assert cfg.enabled is False

    def test_env_1_enables(self, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_SKILLS_ENABLED", "1")
        cfg = load_skills_config(None)
        assert cfg.enabled is True

    def test_env_yes_enables(self, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_SKILLS_ENABLED", "yes")
        cfg = load_skills_config(None)
        assert cfg.enabled is True

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"skills": {"enabled": True}}))
        monkeypatch.setenv("AI_FRAMEWORK_SKILLS_ENABLED", "false")
        cfg = load_skills_config(config_file)
        assert cfg.enabled is False
