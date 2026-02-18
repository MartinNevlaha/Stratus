"""Tests for learning/config.py — configuration with anti-annoyance controls."""

from __future__ import annotations

import json

from stratus.learning.config import LearningConfig, load_learning_config
from stratus.learning.models import Sensitivity


class TestLearningConfigDefaults:
    def test_disabled_by_default(self):
        cfg = LearningConfig()
        assert cfg.global_enabled is False

    def test_conservative_sensitivity(self):
        cfg = LearningConfig()
        assert cfg.sensitivity == Sensitivity.CONSERVATIVE

    def test_max_proposals_per_session(self):
        cfg = LearningConfig()
        assert cfg.max_proposals_per_session == 3

    def test_cooldown_days(self):
        cfg = LearningConfig()
        assert cfg.cooldown_days == 7

    def test_min_confidence_default(self):
        cfg = LearningConfig()
        assert cfg.min_confidence == 0.7

    def test_batch_frequency(self):
        cfg = LearningConfig()
        assert cfg.batch_frequency == "session_end"

    def test_commit_batch_threshold(self):
        cfg = LearningConfig()
        assert cfg.commit_batch_threshold == 5

    def test_min_age_hours(self):
        cfg = LearningConfig()
        assert cfg.min_age_hours == 24


class TestSensitivityMapping:
    def test_conservative_maps_to_0_7(self):
        cfg = LearningConfig(sensitivity=Sensitivity.CONSERVATIVE)
        assert cfg.min_confidence == 0.7

    def test_moderate_maps_to_0_5(self):
        cfg = LearningConfig(sensitivity=Sensitivity.MODERATE)
        assert cfg.min_confidence == 0.5

    def test_aggressive_maps_to_0_3(self):
        cfg = LearningConfig(sensitivity=Sensitivity.AGGRESSIVE)
        assert cfg.min_confidence == 0.3


class TestLoadLearningConfig:
    def test_returns_defaults_no_file(self, tmp_path):
        cfg = load_learning_config(tmp_path / "nonexistent.json")
        assert cfg.global_enabled is False
        assert cfg.sensitivity == Sensitivity.CONSERVATIVE

    def test_returns_defaults_none_path(self):
        cfg = load_learning_config(None)
        assert cfg.global_enabled is False

    def test_loads_from_json(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({
            "learning": {
                "global_enabled": True,
                "sensitivity": "moderate",
                "max_proposals_per_session": 5,
                "cooldown_days": 14,
                "commit_batch_threshold": 10,
                "min_age_hours": 48,
            }
        }))
        cfg = load_learning_config(config_file)
        assert cfg.global_enabled is True
        assert cfg.sensitivity == Sensitivity.MODERATE
        assert cfg.min_confidence == 0.5
        assert cfg.max_proposals_per_session == 5
        assert cfg.cooldown_days == 14
        assert cfg.commit_batch_threshold == 10
        assert cfg.min_age_hours == 48

    def test_partial_config(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({
            "learning": {
                "global_enabled": True,
            }
        }))
        cfg = load_learning_config(config_file)
        assert cfg.global_enabled is True
        assert cfg.sensitivity == Sensitivity.CONSERVATIVE
        assert cfg.cooldown_days == 7

    def test_missing_learning_key(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({"retrieval": {}}))
        cfg = load_learning_config(config_file)
        assert cfg.global_enabled is False

    def test_empty_file(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("")
        cfg = load_learning_config(config_file)
        assert cfg.global_enabled is False

    def test_invalid_json(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text("not json")
        cfg = load_learning_config(config_file)
        assert cfg.global_enabled is False

    def test_batch_frequency_from_file(self, tmp_path):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({
            "learning": {
                "batch_frequency": "on_commit",
            }
        }))
        cfg = load_learning_config(config_file)
        assert cfg.batch_frequency == "on_commit"


class TestEnvVarOverrides:
    def test_env_enables_learning(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_LEARNING_ENABLED", "true")
        cfg = load_learning_config(None)
        assert cfg.global_enabled is True

    def test_env_disables_learning(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({
            "learning": {"global_enabled": True}
        }))
        monkeypatch.setenv("AI_FRAMEWORK_LEARNING_ENABLED", "false")
        cfg = load_learning_config(config_file)
        assert cfg.global_enabled is False

    def test_env_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("AI_FRAMEWORK_LEARNING_ENABLED", "True")
        cfg = load_learning_config(None)
        assert cfg.global_enabled is True

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / ".ai-framework.json"
        config_file.write_text(json.dumps({
            "learning": {"global_enabled": False}
        }))
        monkeypatch.setenv("AI_FRAMEWORK_LEARNING_ENABLED", "true")
        cfg = load_learning_config(config_file)
        assert cfg.global_enabled is True
