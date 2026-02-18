"""Tests for bootstrap CLI commands (init and doctor)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from stratus.bootstrap.commands import cmd_doctor, cmd_init


class TestCmdInit:
    def test_init_detects_services(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        (tmp_path / "apps" / "api").mkdir(parents=True)
        _ = (tmp_path / "apps" / "api" / "package.json").write_text(
            json.dumps({"name": "api", "dependencies": {"@nestjs/core": "^10"}})
        )
        _ = (tmp_path / "apps" / "api" / "nest-cli.json").write_text("{}")
        ns = argparse.Namespace(dry_run=False, force=False, scope="local")
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        captured = capsys.readouterr()
        assert "api" in captured.out
        assert "nestjs" in captured.out

    def test_init_writes_project_graph(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(dry_run=False, force=False, scope="local")
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        pg = tmp_path / "project-graph.json"
        assert pg.exists()
        data = cast(dict[str, object], json.loads(pg.read_text()))
        assert data["version"] == 1

    def test_init_writes_ai_framework_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(dry_run=False, force=False, scope="local")
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        ai = tmp_path / ".ai-framework.json"
        assert ai.exists()
        data = cast(dict[str, object], json.loads(ai.read_text()))
        assert isinstance(data, dict)

    def test_init_dry_run_writes_nothing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(dry_run=True, force=False, scope="local")
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        assert not (tmp_path / "project-graph.json").exists()
        assert not (tmp_path / ".ai-framework.json").exists()
        captured = capsys.readouterr()
        assert "dry-run" in captured.out.lower()

    def test_init_force_overwrites_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        _ = (tmp_path / ".ai-framework.json").write_text('{"old": true}')
        ns = argparse.Namespace(dry_run=False, force=True, scope="local")
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        data = cast(dict[str, object], json.loads((tmp_path / ".ai-framework.json").read_text()))
        assert "old" not in data

    def test_init_no_overwrite_without_force(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        _ = (tmp_path / ".ai-framework.json").write_text('{"old": true}')
        ns = argparse.Namespace(dry_run=False, force=False, scope="local")
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        data = cast(dict[str, object], json.loads((tmp_path / ".ai-framework.json").read_text()))
        assert data.get("old") is True
        captured = capsys.readouterr()
        assert "already exists" in captured.out

    def test_init_not_in_repo_exits(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(dry_run=False, force=False, scope="local")
        with patch("stratus.hooks._common.get_git_root", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                cmd_init(ns)
            assert exc_info.value.code == 1

    def test_init_registers_hooks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False, force=False, skip_hooks=False, skip_mcp=False, scope="local",
        )
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        settings = tmp_path / ".claude" / "settings.json"
        assert settings.exists()
        data = cast(dict[str, object], json.loads(settings.read_text()))
        assert "hooks" in data

    def test_init_registers_mcp(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False, force=False, skip_hooks=False, skip_mcp=False, scope="local",
        )
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        mcp = tmp_path / ".mcp.json"
        assert mcp.exists()
        data = cast(dict[str, object], json.loads(mcp.read_text()))
        assert "mcpServers" in data
        servers = cast(dict[str, object], data["mcpServers"])
        assert "stratus-memory" in servers

    def test_init_skip_hooks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False, force=False, skip_hooks=True, skip_mcp=False, scope="local",
        )
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        assert not (tmp_path / ".claude" / "settings.json").exists()

    def test_init_skip_mcp(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False, force=False, skip_hooks=False, skip_mcp=True, scope="local",
        )
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        assert not (tmp_path / ".mcp.json").exists()

    def test_init_dry_run_skips_registration(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=True, force=False, skip_hooks=False, skip_mcp=False, scope="local",
        )
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        assert not (tmp_path / ".claude" / "settings.json").exists()
        assert not (tmp_path / ".mcp.json").exists()
        captured = capsys.readouterr()
        assert "dry-run" in captured.out.lower()

    def test_cmd_init_enable_delivery_installs_agents(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """With --enable-delivery, register_agents is called and count is printed."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            enable_delivery=True,
            skip_agents=False,
            scope="local",
        )
        mock_register = MagicMock(return_value=["a.md", "b.md", "c.md", "d.md", "e.md"])
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.registration.register_agents",
                mock_register,
            ),
        ):
            cmd_init(ns)
        mock_register.assert_called_once()
        captured = capsys.readouterr()
        assert "5" in captured.out
        assert "agent" in captured.out.lower()

    def test_cmd_init_skip_agents(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With --skip-agents, register_agents is NOT called even if delivery enabled."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            enable_delivery=True,
            skip_agents=True,
            scope="local",
        )
        mock_register = MagicMock(return_value=["a.md", "b.md"])
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.registration.register_agents",
                mock_register,
            ),
        ):
            cmd_init(ns)
        mock_register.assert_not_called()

    def test_cmd_init_default_no_agents(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without any delivery flags, register_agents is NOT called."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            scope="local",
        )
        mock_register = MagicMock(return_value=["a.md", "b.md", "c.md"])
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.registration.register_agents",
                mock_register,
            ),
        ):
            cmd_init(ns)
        mock_register.assert_not_called()

    def test_cmd_init_delivery_enabled_via_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When .ai-framework.json has delivery_framework.enabled=true, agents are installed."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ai_config = tmp_path / ".ai-framework.json"
        _ = ai_config.write_text('{"delivery_framework": {"enabled": true}}')
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            enable_delivery=False,
            skip_agents=False,
            scope="local",
        )
        mock_register = MagicMock(
            return_value=["a.md", "b.md", "c.md", "d.md", "e.md", "f.md", "g.md"]
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.registration.register_agents",
                mock_register,
            ),
        ):
            cmd_init(ns)
        mock_register.assert_called_once()
        captured = capsys.readouterr()
        assert "7" in captured.out
        assert "agent" in captured.out.lower()

    def test_cmd_init_global_scope_no_git_required(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Global scope should NOT require git root."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            scope="global",
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=None),
            patch("stratus.bootstrap.registration.Path.home", return_value=fake_home),
        ):
            cmd_init(ns)  # Should NOT raise SystemExit
        captured = capsys.readouterr()
        assert "global" in captured.out.lower()

    def test_cmd_init_global_scope_registers_hooks_globally(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Global scope writes hooks and MCP to ~/.claude/."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            scope="global",
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=None),
            patch("stratus.bootstrap.registration.Path.home", return_value=fake_home),
        ):
            cmd_init(ns)
        # Verify files written to fake home
        settings = fake_home / ".claude" / "settings.json"
        assert settings.exists()
        data = cast(dict[str, object], json.loads(settings.read_text()))
        assert "hooks" in data
        mcp = fake_home / ".claude" / ".mcp.json"
        assert mcp.exists()
        mcp_data = cast(dict[str, object], json.loads(mcp.read_text()))
        servers = cast(dict[str, object], mcp_data["mcpServers"])
        assert "stratus-memory" in servers


    def test_cmd_init_interactive_when_no_scope(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When scope=None, interactive prompts run and set scope."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            scope=None,
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.commands._interactive_init",
                return_value=("local", False),
            ) as mock_interactive,
        ):
            cmd_init(ns)
        mock_interactive.assert_called_once()

    def test_cmd_init_no_interactive_when_scope_given(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When scope is explicitly set, no interactive prompts."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            scope="local",
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.commands._interactive_init",
                return_value=("local", False),
            ) as mock_interactive,
        ):
            cmd_init(ns)
        mock_interactive.assert_not_called()

    def test_cmd_init_dry_run_skips_interactive(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dry-run with no scope defaults to local, no interactive."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=True,
            force=False,
            skip_hooks=False,
            skip_mcp=False,
            scope=None,
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.commands._interactive_init",
                return_value=("local", False),
            ) as mock_interactive,
        ):
            cmd_init(ns)
        mock_interactive.assert_not_called()


class TestInteractiveInit:
    def test_selects_local_scope(self) -> None:
        from stratus.bootstrap.commands import _interactive_init

        with patch("builtins.input", side_effect=["1", "n"]):
            scope, delivery = _interactive_init()
        assert scope == "local"
        assert delivery is False

    def test_selects_global_scope(self) -> None:
        from stratus.bootstrap.commands import _interactive_init

        with patch("builtins.input", side_effect=["2"]):
            scope, delivery = _interactive_init()
        assert scope == "global"

    def test_default_is_local(self) -> None:
        from stratus.bootstrap.commands import _interactive_init

        with patch("builtins.input", side_effect=["", "n"]):
            scope, delivery = _interactive_init()
        assert scope == "local"

    def test_enables_delivery(self) -> None:
        from stratus.bootstrap.commands import _interactive_init

        with patch("builtins.input", side_effect=["1", "y"]):
            scope, delivery = _interactive_init()
        assert scope == "local"
        assert delivery is True

    def test_global_skips_delivery_prompt(self) -> None:
        from stratus.bootstrap.commands import _interactive_init

        with patch("builtins.input", side_effect=["2"]) as mock_input:
            scope, delivery = _interactive_init()
        assert scope == "global"
        assert delivery is False
        # Only 1 call (scope), no delivery prompt
        assert mock_input.call_count == 1


class TestCmdDoctor:
    def test_doctor_prints_health_checks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.chdir(tmp_path)
        _ = (tmp_path / ".ai-framework.json").write_text("{}")
        _ = (tmp_path / "project-graph.json").write_text("{}")
        (tmp_path / "data").mkdir(parents=True)
        _ = (tmp_path / "data" / "memory.db").write_text("")

        ns = argparse.Namespace()
        with (
            patch("stratus.bootstrap.commands._check_cmd", return_value=True),
            patch("stratus.bootstrap.commands.httpx.get") as mock_get,
        ):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            cmd_doctor(ns)

        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "Memory DB" in captured.out

    def test_doctor_exits_1_on_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.chdir(tmp_path)
        ns = argparse.Namespace()
        with (
            patch(
                "stratus.bootstrap.commands._check_cmd",
                return_value=False,
            ),
            patch(
                "stratus.bootstrap.commands.httpx.get",
                side_effect=Exception("no server"),
            ),
        ):
            with pytest.raises(SystemExit) as exc_info:
                cmd_doctor(ns)
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.out
