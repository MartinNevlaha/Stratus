"""Tests for bootstrap writer."""

from __future__ import annotations

import json
from pathlib import Path

from stratus.bootstrap.models import ProjectGraph, ServiceInfo, ServiceType
from stratus.bootstrap.writer import (
    _build_default_config,
    update_ai_framework_config,
    write_ai_framework_config,
    write_project_graph,
)


def _make_graph(root: Path) -> ProjectGraph:
    svc = ServiceInfo(
        name="api",
        type=ServiceType.NESTJS,
        path="apps/api",
        language="typescript",
    )
    return ProjectGraph(
        root=str(root),
        detected_at="2026-01-01T00:00:00Z",
        services=[svc],
    )


class TestWriteProjectGraph:
    def test_writes_file(self, tmp_path):
        graph = _make_graph(tmp_path)
        out = write_project_graph(graph, tmp_path)
        assert out == tmp_path / "project-graph.json"
        assert out.exists()

    def test_content_is_valid_json(self, tmp_path):
        graph = _make_graph(tmp_path)
        write_project_graph(graph, tmp_path)
        data = json.loads((tmp_path / "project-graph.json").read_text())
        assert data["version"] == 1
        assert data["root"] == str(tmp_path)
        assert len(data["services"]) == 1
        assert data["services"][0]["name"] == "api"

    def test_overwrites_existing(self, tmp_path):
        graph = _make_graph(tmp_path)
        write_project_graph(graph, tmp_path)
        # Second write with different content
        graph2 = ProjectGraph(root=str(tmp_path), detected_at="2026-02-01T00:00:00Z")
        write_project_graph(graph2, tmp_path)
        data = json.loads((tmp_path / "project-graph.json").read_text())
        assert len(data["services"]) == 0


class TestWriteAiFrameworkConfig:
    def test_writes_file_when_not_exists(self, tmp_path):
        graph = _make_graph(tmp_path)
        out = write_ai_framework_config(tmp_path, graph)
        assert out == tmp_path / ".ai-framework.json"
        assert out.exists()

    def test_returns_none_when_exists_no_force(self, tmp_path):
        graph = _make_graph(tmp_path)
        (tmp_path / ".ai-framework.json").write_text("{}")
        result = write_ai_framework_config(tmp_path, graph)
        assert result is None

    def test_force_overwrites(self, tmp_path):
        graph = _make_graph(tmp_path)
        (tmp_path / ".ai-framework.json").write_text("{}")
        result = write_ai_framework_config(tmp_path, graph, force=True)
        assert result == tmp_path / ".ai-framework.json"
        data = json.loads((tmp_path / ".ai-framework.json").read_text())
        assert "retrieval" in data or "learning" in data or "vexor" in data or len(data) > 0

    def test_content_is_valid_json(self, tmp_path):
        graph = _make_graph(tmp_path)
        write_ai_framework_config(tmp_path, graph)
        data = json.loads((tmp_path / ".ai-framework.json").read_text())
        assert isinstance(data, dict)


class TestBuildDefaultConfig:
    def test_returns_dict(self, tmp_path):
        graph = _make_graph(tmp_path)
        config = _build_default_config(tmp_path, graph)
        assert isinstance(config, dict)

    def test_has_expected_keys(self, tmp_path):
        graph = _make_graph(tmp_path)
        config = _build_default_config(tmp_path, graph)
        # Should have at least some configuration sections
        assert len(config) > 0

    def test_retrieval_override_used(self, tmp_path):
        """When retrieval_config provided, it overrides default retrieval section."""
        graph = _make_graph(tmp_path)
        custom_retrieval = {
            "vexor": {"enabled": False, "project_root": str(tmp_path)},
            "devrag": {"enabled": True},
        }
        config = _build_default_config(tmp_path, graph, retrieval_config=custom_retrieval)
        assert config["retrieval"]["vexor"]["enabled"] is False
        assert config["retrieval"]["devrag"]["enabled"] is True

    def test_retrieval_override_none_uses_default(self, tmp_path):
        """When retrieval_config is None, hardcoded defaults are used."""
        graph = _make_graph(tmp_path)
        config = _build_default_config(tmp_path, graph, retrieval_config=None)
        assert config["retrieval"]["vexor"]["enabled"] is True
        assert config["retrieval"]["devrag"]["enabled"] is False


class TestUpdateAiFrameworkConfig:
    def test_merges_into_existing(self, tmp_path):
        """Updates are merged into existing config."""
        path = tmp_path / ".ai-framework.json"
        path.write_text(json.dumps({"version": 1, "learning": {"global_enabled": False}}))
        updates = {"retrieval": {"vexor": {"enabled": True}}}
        result = update_ai_framework_config(tmp_path, updates)
        assert result == path
        data = json.loads(path.read_text())
        assert data["retrieval"]["vexor"]["enabled"] is True
        assert data["learning"]["global_enabled"] is False

    def test_returns_none_when_no_file(self, tmp_path):
        """Returns None when .ai-framework.json doesn't exist."""
        result = update_ai_framework_config(tmp_path, {"retrieval": {}})
        assert result is None

    def test_preserves_existing_keys(self, tmp_path):
        """Non-updated keys are preserved."""
        path = tmp_path / ".ai-framework.json"
        path.write_text(json.dumps({"version": 1, "project": {"name": "test"}}))
        update_ai_framework_config(tmp_path, {"retrieval": {"vexor": {"enabled": True}}})
        data = json.loads(path.read_text())
        assert data["project"]["name"] == "test"
        assert data["version"] == 1


class TestAtomicWrites:
    def test_write_project_graph_no_tmp_files_left_behind(self, tmp_path):
        """Atomic write leaves no .tmp files after write_project_graph success."""
        graph = _make_graph(tmp_path)
        write_project_graph(graph, tmp_path)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"

    def test_write_ai_framework_config_no_tmp_files_left_behind(self, tmp_path):
        """Atomic write leaves no .tmp files after write_ai_framework_config success."""
        graph = _make_graph(tmp_path)
        write_ai_framework_config(tmp_path, graph)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"

    def test_update_ai_framework_config_no_tmp_files_left_behind(self, tmp_path):
        """Atomic write leaves no .tmp files after update_ai_framework_config success."""
        path = tmp_path / ".ai-framework.json"
        path.write_text(json.dumps({"version": 1}))
        update_ai_framework_config(tmp_path, {"learning": {"global_enabled": True}})
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"

    def test_write_project_graph_file_readable_after_write(self, tmp_path):
        """File written atomically is valid JSON."""
        graph = _make_graph(tmp_path)
        out = write_project_graph(graph, tmp_path)
        data = json.loads(out.read_text())
        assert data["version"] == 1

    def test_write_ai_framework_config_file_readable_after_write(self, tmp_path):
        """File written atomically is valid JSON."""
        graph = _make_graph(tmp_path)
        out = write_ai_framework_config(tmp_path, graph)
        assert out is not None
        data = json.loads(out.read_text())
        assert isinstance(data, dict)
        assert len(data) > 0
