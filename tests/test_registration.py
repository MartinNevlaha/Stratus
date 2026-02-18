"""Tests for bootstrap registration: hook and MCP config generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from stratus.bootstrap.registration import (
    build_hooks_config,
    build_mcp_config,
    register_hooks,
    register_mcp,
)


class TestBuildHooksConfig:
    def test_returns_dict_with_hooks_key(self) -> None:
        result = build_hooks_config()
        assert isinstance(result, dict)
        assert "hooks" in result

    def test_all_event_types_present(self) -> None:
        hooks = build_hooks_config()["hooks"]
        assert isinstance(hooks, dict)
        expected = {
            "PreToolUse",
            "PostToolUse",
            "PreCompact",
            "SessionStart",
            "SessionEnd",
            "Stop",
            "TeammateIdle",
            "TaskCompleted",
        }
        assert expected == set(hooks.keys())

    def test_post_tool_use_has_three_matchers(self) -> None:
        hooks = build_hooks_config()["hooks"]
        assert isinstance(hooks, dict)
        post_tool_use = hooks["PostToolUse"]
        assert isinstance(post_tool_use, list)
        assert len(post_tool_use) == 3

    def test_write_edit_matcher_has_two_hooks(self) -> None:
        hooks = build_hooks_config()["hooks"]
        assert isinstance(hooks, dict)
        post_tool_use = hooks["PostToolUse"]
        assert isinstance(post_tool_use, list)
        write_edit_groups = [g for g in post_tool_use if g["matcher"] == "Write|Edit"]
        assert len(write_edit_groups) == 1
        hook_entries = write_edit_groups[0]["hooks"]
        assert isinstance(hook_entries, list)
        assert len(hook_entries) == 2

    def test_command_format_correct(self) -> None:
        hooks = build_hooks_config()["hooks"]
        assert isinstance(hooks, dict)
        pre_tool_use = hooks["PreToolUse"]
        assert isinstance(pre_tool_use, list)
        group = pre_tool_use[0]
        assert group["matcher"] == "WebSearch|WebFetch"
        hook_entries = group["hooks"]
        assert isinstance(hook_entries, list)
        assert len(hook_entries) == 1
        cmd = hook_entries[0]["command"]
        assert cmd == "uv run python -m stratus.hooks.tool_redirect"
        assert hook_entries[0]["type"] == "command"

    def test_stop_hook_correct(self) -> None:
        hooks = build_hooks_config()["hooks"]
        assert isinstance(hooks, dict)
        stop_groups = hooks["Stop"]
        assert isinstance(stop_groups, list)
        assert len(stop_groups) == 1
        group = stop_groups[0]
        assert group["matcher"] == ".*"
        hook_entries = group["hooks"]
        assert isinstance(hook_entries, list)
        assert hook_entries[0]["command"] == "uv run python -m stratus.hooks.spec_stop_guard"

    def test_session_start_matcher_is_compact(self) -> None:
        hooks = build_hooks_config()["hooks"]
        assert isinstance(hooks, dict)
        session_start = hooks["SessionStart"]
        assert isinstance(session_start, list)
        assert session_start[0]["matcher"] == "compact"

    def test_bash_matcher_has_learning_trigger(self) -> None:
        hooks = build_hooks_config()["hooks"]
        assert isinstance(hooks, dict)
        post_tool_use = hooks["PostToolUse"]
        assert isinstance(post_tool_use, list)
        bash_groups = [g for g in post_tool_use if g["matcher"] == "Bash"]
        assert len(bash_groups) == 1
        hook_entries = bash_groups[0]["hooks"]
        assert isinstance(hook_entries, list)
        assert hook_entries[0]["command"] == "uv run python -m stratus.hooks.learning_trigger"


class TestRegisterHooks:
    def test_creates_settings_json_in_dot_claude(self, tmp_path: Path) -> None:
        path = register_hooks(tmp_path)
        assert path == tmp_path / ".claude" / "settings.json"
        assert path.exists()

    def test_settings_json_has_hooks(self, tmp_path: Path) -> None:
        register_hooks(tmp_path)
        data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert "hooks" in data
        assert "PostToolUse" in data["hooks"]

    def test_idempotent_run_twice_same_result(self, tmp_path: Path) -> None:
        register_hooks(tmp_path)
        first = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        register_hooks(tmp_path)
        second = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert first == second

    def test_preserves_non_hook_settings(self, tmp_path: Path) -> None:
        dot_claude = tmp_path / ".claude"
        dot_claude.mkdir()
        existing = {"theme": "dark", "fontSize": 14, "hooks": {}}
        _ = (dot_claude / "settings.json").write_text(json.dumps(existing))
        register_hooks(tmp_path)
        data = json.loads((dot_claude / "settings.json").read_text())
        assert data["theme"] == "dark"
        assert data["fontSize"] == 14

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        register_hooks(tmp_path, dry_run=True)
        assert not (tmp_path / ".claude" / "settings.json").exists()

    def test_creates_dot_claude_dir_if_missing(self, tmp_path: Path) -> None:
        assert not (tmp_path / ".claude").exists()
        register_hooks(tmp_path)
        assert (tmp_path / ".claude").exists()
        assert (tmp_path / ".claude" / "settings.json").exists()

    def test_returns_path(self, tmp_path: Path) -> None:
        path = register_hooks(tmp_path)
        assert isinstance(path, Path)
        assert path.name == "settings.json"


class TestBuildMcpConfig:
    def test_returns_dict_with_mcp_servers(self) -> None:
        result = build_mcp_config()
        assert isinstance(result, dict)
        assert "mcpServers" in result

    def test_contains_stratus_memory_entry(self) -> None:
        result = build_mcp_config()
        servers = result["mcpServers"]
        assert isinstance(servers, dict)
        assert "stratus-memory" in servers

    def test_correct_command_and_args(self) -> None:
        result = build_mcp_config()
        servers = result["mcpServers"]
        assert isinstance(servers, dict)
        entry = servers["stratus-memory"]
        assert isinstance(entry, dict)
        assert entry["type"] == "stdio"
        assert entry["command"] == "uv"
        assert entry["args"] == ["run", "stratus", "mcp-serve"]
        assert entry["cwd"] == "."


class TestRegisterMcp:
    def test_creates_mcp_json(self, tmp_path: Path) -> None:
        path = register_mcp(tmp_path)
        assert path == tmp_path / ".mcp.json"
        assert path.exists()

    def test_mcp_json_has_stratus_memory(self, tmp_path: Path) -> None:
        register_mcp(tmp_path)
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert "mcpServers" in data
        assert "stratus-memory" in data["mcpServers"]

    def test_idempotent_run_twice_same_result(self, tmp_path: Path) -> None:
        register_mcp(tmp_path)
        first = json.loads((tmp_path / ".mcp.json").read_text())
        register_mcp(tmp_path)
        second = json.loads((tmp_path / ".mcp.json").read_text())
        assert first == second

    def test_preserves_other_mcp_servers(self, tmp_path: Path) -> None:
        existing = {
            "mcpServers": {"other-server": {"type": "stdio", "command": "other-cmd", "args": []}}
        }
        _ = (tmp_path / ".mcp.json").write_text(json.dumps(existing))
        register_mcp(tmp_path)
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert "other-server" in data["mcpServers"]
        assert "stratus-memory" in data["mcpServers"]

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        register_mcp(tmp_path, dry_run=True)
        assert not (tmp_path / ".mcp.json").exists()

    def test_returns_path(self, tmp_path: Path) -> None:
        path = register_mcp(tmp_path)
        assert isinstance(path, Path)
        assert path.name == ".mcp.json"


# ---------------------------------------------------------------------------
# New tests for agent registration helpers
# ---------------------------------------------------------------------------


class TestIsManaged:
    def test_is_managed_true(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import _is_managed

        f = tmp_path / "agent.md"
        f.write_text("<!-- managed-by: stratus sha256:abc123 -->\n# Agent")
        assert _is_managed(f) is True

    def test_is_managed_false(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import _is_managed

        f = tmp_path / "agent.md"
        f.write_text("# My custom agent\nI own this file.")
        assert _is_managed(f) is False

    def test_is_managed_missing_file(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import _is_managed

        f = tmp_path / "nonexistent.md"
        assert _is_managed(f) is False


class TestIsFrameworkRepo:
    def test_is_framework_repo_true(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import _is_framework_repo

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "stratus"\nversion = "0.1.0"\n'
        )
        assert _is_framework_repo(tmp_path) is True

    def test_is_framework_repo_false(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import _is_framework_repo

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-app"\nversion = "1.0.0"\n')
        assert _is_framework_repo(tmp_path) is False

    def test_is_framework_repo_no_pyproject(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import _is_framework_repo

        assert _is_framework_repo(tmp_path) is False


class TestRegisterAgents:
    def _make_config(
        self, *, enabled: bool = True, active_phases: list[str] | None = None
    ) -> object:
        from stratus.orchestration.delivery_config import DeliveryConfig

        return DeliveryConfig(enabled=enabled, active_phases=active_phases or [])

    def test_register_agents_disabled_config_returns_empty(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import register_agents

        config = self._make_config(enabled=False)
        result = register_agents(tmp_path, config, frozenset())  # type: ignore[arg-type]
        assert result == []

    def test_register_agents_framework_repo_returns_empty(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import register_agents

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "stratus"\n')
        config = self._make_config(enabled=True)
        result = register_agents(tmp_path, config, frozenset())  # type: ignore[arg-type]
        assert result == []

    def test_register_agents_writes_agent_files(self, tmp_path: Path) -> None:
        from stratus.bootstrap.models import ServiceType
        from stratus.bootstrap.registration import register_agents

        config = self._make_config(enabled=True)
        detected = frozenset({ServiceType.PYTHON})
        result = register_agents(tmp_path, config, detected)  # type: ignore[arg-type]

        # At minimum, universal non-optional agents should be written
        assert len(result) > 0
        # All written paths should exist under .claude/agents/
        for rel_path in result:
            full = tmp_path / rel_path
            assert full.exists(), f"Expected {full} to exist"

    def test_register_agents_no_double_prefix(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import register_agents

        config = self._make_config(enabled=True)
        result = register_agents(tmp_path, config, frozenset())  # type: ignore[arg-type]

        agent_paths = [p for p in result if ".claude/agents/" in p]
        for rel_path in agent_paths:
            filename = rel_path.split("/")[-1]
            assert not filename.startswith("delivery-delivery-"), f"Double prefix in {filename}"

    def test_register_agents_writes_skill_files(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import register_agents

        config = self._make_config(enabled=True)
        result = register_agents(tmp_path, config, frozenset())  # type: ignore[arg-type]

        # Non-optional skills should be written
        skill_paths = [p for p in result if ".claude/skills" in p or ".claude\\skills" in p]
        assert len(skill_paths) > 0
        for rel_path in skill_paths:
            full = tmp_path / rel_path
            assert full.exists(), f"Expected skill {full} to exist"

    def test_register_agents_managed_header_present(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import _is_managed, register_agents

        config = self._make_config(enabled=True)
        result = register_agents(tmp_path, config, frozenset())  # type: ignore[arg-type]

        assert len(result) > 0
        first_file = tmp_path / result[0]
        assert _is_managed(first_file), "Written file should have managed header"

    def test_register_agents_skips_user_owned_files(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import register_agents

        config = self._make_config(enabled=True)
        # Pre-create a file without the managed header for a universal agent
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        user_file = agents_dir / "delivery-tpm.md"
        user_content = "# My custom TPM agent\nThis is user-owned."
        user_file.write_text(user_content)

        register_agents(tmp_path, config, frozenset())  # type: ignore[arg-type]

        # User-owned file must be untouched
        assert user_file.read_text() == user_content

    def test_register_agents_overwrites_managed_files(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import register_agents

        config = self._make_config(enabled=True)
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        managed_file = agents_dir / "delivery-tpm.md"
        # Write an outdated managed file
        managed_file.write_text("<!-- managed-by: stratus sha256:old -->\n# Stale content")

        register_agents(tmp_path, config, frozenset())  # type: ignore[arg-type]

        # File should have been updated with fresh content
        new_content = managed_file.read_text()
        assert "sha256:old" not in new_content

    def test_register_hooks_local_unchanged(self, tmp_path: Path) -> None:
        """Regression: scope='local' behaves identically to the original (no scope arg)."""
        path = register_hooks(tmp_path, scope="local")
        assert path == tmp_path / ".claude" / "settings.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert "hooks" in data

    def test_register_hooks_global_writes_to_home_dir(self, tmp_path: Path) -> None:
        """scope='global' writes settings.json under ~/.claude/."""
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        with patch("stratus.bootstrap.registration.Path.home", return_value=fake_home):
            path = register_hooks(git_root=None, scope="global")
        expected = fake_home / ".claude" / "settings.json"
        assert path == expected
        assert expected.exists()
        data = json.loads(expected.read_text())
        assert "hooks" in data

    def test_register_mcp_global_writes_to_home_dir(self, tmp_path: Path) -> None:
        """scope='global' writes .mcp.json under ~/.claude/."""
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        with patch("stratus.bootstrap.registration.Path.home", return_value=fake_home):
            path = register_mcp(git_root=None, scope="global")
        expected = fake_home / ".claude" / ".mcp.json"
        assert path == expected
        assert expected.exists()
        data = json.loads(expected.read_text())
        assert "mcpServers" in data
        server = data["mcpServers"]["stratus-memory"]
        # Global scope should NOT have cwd="."
        assert "cwd" not in server

    def test_register_mcp_local_has_cwd_dot(self, tmp_path: Path) -> None:
        """Regression: scope='local' MCP config has cwd='.'."""
        register_mcp(tmp_path, scope="local")
        data = json.loads((tmp_path / ".mcp.json").read_text())
        server = data["mcpServers"]["stratus-memory"]
        assert server["cwd"] == "."

    def test_register_agents_force_overwrites_all(self, tmp_path: Path) -> None:
        from stratus.bootstrap.registration import register_agents

        config = self._make_config(enabled=True)
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        user_file = agents_dir / "delivery-tpm.md"
        user_content = "# My custom TPM agent\nThis is user-owned."
        user_file.write_text(user_content)

        register_agents(tmp_path, config, frozenset(), force=True)  # type: ignore[arg-type]

        # force=True should have overwritten even the user-owned file
        assert user_file.read_text() != user_content
