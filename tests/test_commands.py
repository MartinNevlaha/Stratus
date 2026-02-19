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
        # With retrieval auto-detection, existing configs get merged (not "already exists")
        assert "updated retrieval" in captured.out or "already exists" in captured.out

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
        settings = tmp_path / ".claude" / "settings.json"
        if settings.exists():
            data = json.loads(settings.read_text())
            assert "hooks" not in data
        # settings.json may exist (statusline writes it) but must not have hooks

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

    def test_init_registers_statusline(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """cmd_init registers statusLine in settings.json."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False, force=False, skip_hooks=False, skip_mcp=False, scope="local",
        )
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        settings = tmp_path / ".claude" / "settings.json"
        assert settings.exists()
        data = json.loads(settings.read_text())
        assert "statusLine" in data
        assert data["statusLine"]["command"] == "uv run python -m stratus statusline"

    def test_init_dry_run_skips_statusline(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dry-run does not write statusLine."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=True, force=False, skip_hooks=False, skip_mcp=False, scope="local",
        )
        with patch("stratus.hooks._common.get_git_root", return_value=tmp_path):
            cmd_init(ns)
        settings = tmp_path / ".claude" / "settings.json"
        assert not settings.exists()


    def test_cmd_init_interactive_when_no_scope(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When scope=None, interactive prompts run and set scope."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

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
            patch(
                "stratus.bootstrap.retrieval_setup.detect_backends",
                return_value=BackendStatus(),
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.prompt_retrieval_setup",
                return_value=(False, False, False),
            ),
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


class TestCmdInitRetrieval:
    """Tests for retrieval backend detection in cmd_init."""

    def test_init_detects_vexor_and_enables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When vexor is detected, it's enabled in .ai-framework.json."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        status = BackendStatus(vexor_available=True, vexor_version="vexor 1.0")
        ns = argparse.Namespace(dry_run=False, force=False, scope="local", skip_retrieval=False)
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.retrieval_setup.detect_backends",
                return_value=status,
            ),
        ):
            cmd_init(ns)
        ai = tmp_path / ".ai-framework.json"
        assert ai.exists()
        data = json.loads(ai.read_text())
        assert data["retrieval"]["vexor"]["enabled"] is True

    def test_init_vexor_unavailable_disables(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When vexor not detected, it's disabled in .ai-framework.json."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        status = BackendStatus(vexor_available=False)
        ns = argparse.Namespace(dry_run=False, force=False, scope="local", skip_retrieval=False)
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.retrieval_setup.detect_backends",
                return_value=status,
            ),
        ):
            cmd_init(ns)
        ai = tmp_path / ".ai-framework.json"
        data = json.loads(ai.read_text())
        assert data["retrieval"]["vexor"]["enabled"] is False

    def test_init_existing_project_merges_retrieval(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When .ai-framework.json exists, retrieval config is merged (not overwritten)."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        # Pre-existing config with learning settings
        existing = {
            "version": 1,
            "learning": {"global_enabled": True},
            "retrieval": {"vexor": {"enabled": False}},
        }
        (tmp_path / ".ai-framework.json").write_text(json.dumps(existing))

        status = BackendStatus(vexor_available=True, vexor_version="vexor 1.0")
        ns = argparse.Namespace(dry_run=False, force=False, scope="local", skip_retrieval=False)
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.retrieval_setup.detect_backends",
                return_value=status,
            ),
        ):
            cmd_init(ns)
        data = json.loads((tmp_path / ".ai-framework.json").read_text())
        # Retrieval upgraded
        assert data["retrieval"]["vexor"]["enabled"] is True
        # Other config preserved
        assert data["learning"]["global_enabled"] is True

    def test_init_skip_retrieval_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With --skip-retrieval, detect_backends is not called."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(dry_run=False, force=False, scope="local", skip_retrieval=True)
        mock_detect = MagicMock()
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.retrieval_setup.detect_backends",
                mock_detect,
            ),
        ):
            cmd_init(ns)
        mock_detect.assert_not_called()

    def test_init_runs_indexing_when_approved(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When interactive mode approves indexing, run_initial_index_background is called."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        status = BackendStatus(vexor_available=True, vexor_version="vexor 1.0")
        ns = argparse.Namespace(dry_run=False, force=False, scope=None, skip_retrieval=False)
        mock_index = MagicMock(return_value=True)
        mock_setup = MagicMock(return_value=(True, False))
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.retrieval_setup.detect_backends",
                return_value=status,
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.prompt_retrieval_setup",
                return_value=(True, False, True),
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.run_initial_index_background",
                mock_index,
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.setup_vexor_local",
                mock_setup,
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.detect_cuda",
                return_value=False,
            ),
            patch(
                "stratus.bootstrap.commands._interactive_init",
                return_value=("local", False),
            ),
        ):
            cmd_init(ns)
        mock_setup.assert_called_once_with(cuda=False)
        mock_index.assert_called_once()
        captured = capsys.readouterr()
        assert "index" in captured.out.lower()


    def test_init_falls_back_to_cpu_when_cuda_runtime_unavailable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When GPU detected but CUDA runtime verification fails, falls back to CPU with message."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        status = BackendStatus(vexor_available=True, vexor_version="vexor 1.0")
        ns = argparse.Namespace(dry_run=False, force=False, scope=None, skip_retrieval=False)
        mock_setup = MagicMock(return_value=(True, False))
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch("stratus.bootstrap.retrieval_setup.detect_backends", return_value=status),
            patch(
                "stratus.bootstrap.retrieval_setup.prompt_retrieval_setup",
                return_value=(True, False, True),
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.run_initial_index_background",
                return_value=True,
            ),
            patch("stratus.bootstrap.retrieval_setup.setup_vexor_local", mock_setup),
            patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=True),
            patch("stratus.bootstrap.retrieval_setup.verify_cuda_runtime", return_value=False),
            patch(
                "stratus.bootstrap.retrieval_setup.install_vexor_local_package",
                return_value=True,
            ),
            patch("stratus.bootstrap.commands._interactive_init", return_value=("local", False)),
        ):
            cmd_init(ns)
        # setup_vexor_local must be called with cuda=False (fallen back to CPU)
        mock_setup.assert_called_once_with(cuda=False)
        captured = capsys.readouterr()
        assert "cuda runtime" in captured.out.lower() or "cpu" in captured.out.lower()


    def test_init_calls_governance_index_when_devrag_enabled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When interactive mode enables devrag, run_governance_index is called (Bug 1)."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        status = BackendStatus(vexor_available=False)
        ns = argparse.Namespace(dry_run=False, force=False, scope=None, skip_retrieval=False)
        mock_gov_index = MagicMock(return_value={"status": "ok", "docs": 5})
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch("stratus.bootstrap.retrieval_setup.detect_backends", return_value=status),
            patch(
                "stratus.bootstrap.retrieval_setup.prompt_retrieval_setup",
                return_value=(False, True, False),
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.run_governance_index",
                mock_gov_index,
            ),
            patch("stratus.bootstrap.commands._interactive_init", return_value=("local", False)),
        ):
            cmd_init(ns)
        mock_gov_index.assert_called_once()
        captured = capsys.readouterr()
        assert "governance" in captured.out.lower()

    def test_init_governance_index_failure_prints_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When governance indexing fails, a warning is printed (Bug 1)."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        status = BackendStatus(vexor_available=False)
        ns = argparse.Namespace(dry_run=False, force=False, scope=None, skip_retrieval=False)
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch("stratus.bootstrap.retrieval_setup.detect_backends", return_value=status),
            patch(
                "stratus.bootstrap.retrieval_setup.prompt_retrieval_setup",
                return_value=(False, True, False),
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.run_governance_index",
                return_value={"status": "error", "message": "no docs found"},
            ),
            patch("stratus.bootstrap.commands._interactive_init", return_value=("local", False)),
        ):
            cmd_init(ns)
        captured = capsys.readouterr()
        assert "warning" in captured.out.lower()

    def test_init_reinit_offers_reindex_when_ai_framework_exists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Re-init (ai-framework.json exists) in interactive mode offers reindexing (Bug 2)."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        existing = {"version": 1, "retrieval": {"vexor": {"enabled": True}}}
        (tmp_path / ".ai-framework.json").write_text(json.dumps(existing))

        status = BackendStatus(vexor_available=True, vexor_version="vexor 1.0")
        ns = argparse.Namespace(dry_run=False, force=False, scope=None, skip_retrieval=False)
        mock_gov_index = MagicMock(return_value={"status": "ok"})
        mock_index = MagicMock(return_value=True)
        mock_setup = MagicMock(return_value=(True, False))
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch("stratus.bootstrap.retrieval_setup.detect_backends", return_value=status),
            patch(
                "stratus.bootstrap.retrieval_setup.run_governance_index",
                mock_gov_index,
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.run_initial_index_background",
                mock_index,
            ),
            patch("stratus.bootstrap.retrieval_setup.setup_vexor_local", mock_setup),
            patch("stratus.bootstrap.retrieval_setup.detect_cuda", return_value=False),
            patch("stratus.bootstrap.commands._interactive_init", return_value=("local", False)),
            # User answers "y" to both reindex prompts
            patch("builtins.input", side_effect=["y", "y"]),
        ):
            cmd_init(ns)
        mock_index.assert_called_once()
        mock_gov_index.assert_called_once()

    def test_init_reinit_skips_reindex_on_no_answer(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Re-init in interactive mode skips indexing when user answers N (Bug 2)."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        from stratus.bootstrap.retrieval_setup import BackendStatus

        existing = {"version": 1, "retrieval": {"vexor": {"enabled": True}}}
        (tmp_path / ".ai-framework.json").write_text(json.dumps(existing))

        status = BackendStatus(vexor_available=True, vexor_version="vexor 1.0")
        ns = argparse.Namespace(dry_run=False, force=False, scope=None, skip_retrieval=False)
        mock_gov_index = MagicMock(return_value={"status": "ok"})
        mock_index = MagicMock(return_value=True)
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch("stratus.bootstrap.retrieval_setup.detect_backends", return_value=status),
            patch(
                "stratus.bootstrap.retrieval_setup.run_governance_index",
                mock_gov_index,
            ),
            patch(
                "stratus.bootstrap.retrieval_setup.run_initial_index_background",
                mock_index,
            ),
            patch("stratus.bootstrap.commands._interactive_init", return_value=("local", False)),
            # User answers "n" to both
            patch("builtins.input", side_effect=["n", "n"]),
        ):
            cmd_init(ns)
        mock_index.assert_not_called()
        mock_gov_index.assert_not_called()


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


class TestEnsureServer:
    def test_ensure_server_skips_when_already_running(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """If health check passes, don't start a new server."""
        from stratus.bootstrap.commands import _ensure_server

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("stratus.bootstrap.commands.httpx.get", return_value=mock_resp):
            _ensure_server()
        captured = capsys.readouterr()
        assert "already running" in captured.out.lower()

    def test_ensure_server_starts_when_not_running(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """If health check fails, spawn server process."""
        from stratus.bootstrap.commands import _ensure_server

        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        (tmp_path / "data").mkdir(parents=True)

        mock_popen = MagicMock()
        mock_popen.pid = 12345
        # First health check fails, second (after spawn) succeeds
        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        with (
            patch(
                "stratus.bootstrap.commands.httpx.get",
                side_effect=[Exception("no server"), mock_resp_ok],
            ),
            patch(
                "stratus.bootstrap.commands.subprocess.Popen",
                return_value=mock_popen,
            ) as mock_spawn,
        ):
            _ensure_server()
        mock_spawn.assert_called_once()
        captured = capsys.readouterr()
        assert "server" in captured.out.lower()

    def test_ensure_server_warns_on_startup_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """If server doesn't become healthy after spawn, print warning."""
        from stratus.bootstrap.commands import _ensure_server

        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        (tmp_path / "data").mkdir(parents=True)

        mock_popen = MagicMock()
        mock_popen.pid = 99999
        with (
            patch(
                "stratus.bootstrap.commands.httpx.get",
                side_effect=Exception("no server"),
            ),
            patch(
                "stratus.bootstrap.commands.subprocess.Popen",
                return_value=mock_popen,
            ),
            patch("stratus.bootstrap.commands.time.sleep"),
        ):
            _ensure_server()
        captured = capsys.readouterr()
        assert "not respond" in captured.out.lower() or "warning" in captured.out.lower()

    def test_init_calls_ensure_server(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """cmd_init calls _ensure_server at the end (not in dry-run)."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=False, force=False, skip_hooks=True, skip_mcp=True, scope="local",
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.commands._ensure_server",
            ) as mock_ensure,
        ):
            cmd_init(ns)
        mock_ensure.assert_called_once()

    def test_init_dry_run_skips_ensure_server(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """cmd_init does NOT call _ensure_server in dry-run mode."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        ns = argparse.Namespace(
            dry_run=True, force=False, skip_hooks=True, skip_mcp=True, scope="local",
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.commands._ensure_server",
            ) as mock_ensure,
        ):
            cmd_init(ns)
        mock_ensure.assert_not_called()

    def test_init_global_scope_calls_ensure_server(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Global scope init also starts the server."""
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(tmp_path / "data"))
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        ns = argparse.Namespace(
            dry_run=False, force=False, skip_hooks=False, skip_mcp=False, scope="global",
        )
        with (
            patch("stratus.hooks._common.get_git_root", return_value=None),
            patch("stratus.bootstrap.registration.Path.home", return_value=fake_home),
            patch(
                "stratus.bootstrap.commands._ensure_server",
            ) as mock_ensure,
        ):
            cmd_init(ns)
        mock_ensure.assert_called_once()


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
