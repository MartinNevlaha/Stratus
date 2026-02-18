"""Tests for CLI entry point."""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratus.cli import main


class TestAnalyzeSubcommand:
    def test_analyze_with_valid_transcript(
        self, simple_transcript: Path, capsys: pytest.CaptureFixture[str]
    ):
        with patch("sys.argv", ["stratus", "analyze", str(simple_transcript)]):
            main()
        captured = capsys.readouterr()
        assert "Messages:" in captured.out
        assert "3" in captured.out
        assert "Peak tokens:" in captured.out

    def test_analyze_with_missing_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        missing = tmp_path / "nonexistent.jsonl"
        with patch("sys.argv", ["stratus", "analyze", str(missing)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "error" in captured.err.lower()

    def test_analyze_with_compaction(
        self, transcript_with_compaction: Path, capsys: pytest.CaptureFixture[str]
    ):
        with patch("sys.argv", ["stratus", "analyze", str(transcript_with_compaction)]):
            main()
        captured = capsys.readouterr()
        assert "Compaction" in captured.out or "compaction" in captured.out
        assert "167000" in captured.out or "167,000" in captured.out

    def test_analyze_with_custom_context_window(
        self, simple_transcript: Path, capsys: pytest.CaptureFixture[str]
    ):
        with patch(
            "sys.argv",
            ["stratus", "analyze", str(simple_transcript), "--context-window", "100000"],
        ):
            main()
        captured = capsys.readouterr()
        assert "Context window:" in captured.out
        assert "100,000" in captured.out or "100000" in captured.out


class TestBackwardCompat:
    def test_bare_jsonl_arg_dispatches_to_analyze(
        self, simple_transcript: Path, capsys: pytest.CaptureFixture[str]
    ):
        """stratus <file.jsonl> should still work (backward compat)."""
        with patch("sys.argv", ["stratus", str(simple_transcript)]):
            main()
        captured = capsys.readouterr()
        assert "Messages:" in captured.out


class TestInitSubcommand:
    def test_init_creates_data_dir(self, tmp_path, monkeypatch, capsys):
        data_dir = tmp_path / "ai-data"
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(data_dir))
        with (
            patch("sys.argv", ["stratus", "init", "--scope", "local"]),
            patch(
                "stratus.hooks._common.get_git_root",
                return_value=tmp_path,
            ),
        ):
            main()
        assert data_dir.exists()
        captured = capsys.readouterr()
        assert "data" in captured.out.lower() or "directory" in captured.out.lower()

    def test_init_creates_database(self, tmp_path, monkeypatch, capsys):
        data_dir = tmp_path / "ai-data"
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(data_dir))
        with (
            patch("sys.argv", ["stratus", "init", "--scope", "local"]),
            patch(
                "stratus.hooks._common.get_git_root",
                return_value=tmp_path,
            ),
        ):
            main()
        assert (data_dir / "memory.db").exists()


class TestServeSubcommand:
    def test_serve_calls_runner(self, monkeypatch):
        mock_run = MagicMock()
        with patch("sys.argv", ["stratus", "serve"]):
            with patch("stratus.cli.run_server", mock_run):
                main()
        mock_run.assert_called_once()


class TestMcpServeSubcommand:
    def test_mcp_serve_calls_mcp_main(self, monkeypatch):
        mock_mcp_main = MagicMock()
        with patch("sys.argv", ["stratus", "mcp-serve"]):
            with patch("stratus.cli.mcp_main", mock_mcp_main):
                main()
        mock_mcp_main.assert_called_once()


class TestReindexSubcommand:
    def test_reindex_subcommand_available(self):
        from stratus.cli import main as cli_main

        # The parser must recognise "reindex" without raising an error
        with patch("sys.argv", ["stratus", "reindex"]):
            with patch("stratus.cli._cmd_reindex"):
                try:
                    cli_main()
                except SystemExit as exc:
                    # exit 0 or exit 1 are both fine; what matters is no argparse error
                    assert exc.code in (0, 1, None)

    def test_cmd_reindex_when_vexor_unavailable(self, monkeypatch, capsys):
        from stratus.cli import _cmd_reindex

        mock_client = MagicMock()
        mock_client.is_available.return_value = False

        with (
            patch("stratus.retrieval.vexor.VexorClient", return_value=mock_client),
            patch(
                "stratus.retrieval.config.load_retrieval_config",
                return_value=MagicMock(vexor=MagicMock()),
            ),
        ):
            ns = argparse.Namespace(full=False)
            with pytest.raises(SystemExit) as exc_info:
                _cmd_reindex(ns)
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not available" in captured.err.lower() or "error" in captured.err.lower()

    def test_cmd_reindex_success(self, monkeypatch, capsys):
        from stratus.cli import _cmd_reindex

        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.index.return_value = {"status": "ok", "output": "indexed 42 files"}

        with (
            patch("stratus.retrieval.vexor.VexorClient", return_value=mock_client),
            patch(
                "stratus.retrieval.config.load_retrieval_config",
                return_value=MagicMock(vexor=MagicMock()),
            ),
        ):
            ns = argparse.Namespace(full=False)
            _cmd_reindex(ns)
        captured = capsys.readouterr()
        assert "complete" in captured.out.lower() or "reindex" in captured.out.lower()


class TestRetrievalStatusSubcommand:
    def test_retrieval_status_subcommand_available(self):
        with patch("sys.argv", ["stratus", "retrieval-status"]):
            with patch("stratus.cli._cmd_retrieval_status"):
                try:
                    main()
                except SystemExit as exc:
                    assert exc.code in (0, 1, None)

    def test_cmd_retrieval_status_output(self, monkeypatch, capsys):
        from stratus.cli import _cmd_retrieval_status

        mock_retriever = MagicMock()
        mock_retriever.status.return_value = {
            "vexor_available": True,
            "devrag_available": False,
        }

        with patch(
            "stratus.retrieval.unified.UnifiedRetriever",
            return_value=mock_retriever,
        ):
            ns = argparse.Namespace()
            _cmd_retrieval_status(ns)

        captured = capsys.readouterr()
        assert "vexor" in captured.out.lower()
        assert "devrag" in captured.out.lower()
        assert "available" in captured.out.lower()


class TestWorktreeSubcommand:
    def test_worktree_detect_subcommand(self, capsys):
        """worktree detect calls detect() and outputs JSON."""
        from stratus.cli import _cmd_worktree

        mock_result = {"found": False, "path": None, "branch": None, "base_branch": "main"}
        with (
            patch("stratus.hooks._common.get_git_root", return_value=Path("/repo")),
            patch("stratus.orchestration.worktree.detect", return_value=mock_result),
        ):
            ns = argparse.Namespace(
                action="detect", slug="my-feat", plan_path="", base_branch="main"
            )
            _cmd_worktree(ns)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["found"] is False

    def test_worktree_create_subcommand(self, capsys):
        """worktree create calls create() and outputs JSON."""
        from stratus.cli import _cmd_worktree

        mock_result = {
            "path": "/tmp/wt",
            "branch": "spec/my-feat",
            "base_branch": "main",
            "stashed": False,
        }
        with (
            patch("stratus.hooks._common.get_git_root", return_value=Path("/repo")),
            patch("stratus.orchestration.worktree.create", return_value=mock_result),
        ):
            ns = argparse.Namespace(
                action="create", slug="my-feat", plan_path="", base_branch="main"
            )
            _cmd_worktree(ns)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["path"] == "/tmp/wt"

    def test_worktree_diff_subcommand(self, capsys):
        """worktree diff calls diff() and prints plain text."""
        from stratus.cli import _cmd_worktree

        with (
            patch("stratus.hooks._common.get_git_root", return_value=Path("/repo")),
            patch("stratus.orchestration.worktree.diff", return_value="diff output"),
        ):
            ns = argparse.Namespace(action="diff", slug="my-feat", plan_path="", base_branch="main")
            _cmd_worktree(ns)
        captured = capsys.readouterr()
        assert "diff output" in captured.out

    def test_worktree_sync_subcommand(self, capsys):
        """worktree sync calls sync() and outputs JSON."""
        from stratus.cli import _cmd_worktree

        mock_result = {
            "merged": True,
            "commit": "abc123",
            "files_changed": 3,
            "insertions": 10,
            "deletions": 2,
        }
        with (
            patch("stratus.hooks._common.get_git_root", return_value=Path("/repo")),
            patch("stratus.orchestration.worktree.sync", return_value=mock_result),
        ):
            ns = argparse.Namespace(action="sync", slug="my-feat", plan_path="", base_branch="main")
            _cmd_worktree(ns)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["merged"] is True

    def test_worktree_cleanup_subcommand(self, capsys):
        """worktree cleanup calls cleanup() and outputs JSON."""
        from stratus.cli import _cmd_worktree

        mock_result = {"removed": True, "path": "/tmp/wt", "branch_deleted": True}
        with (
            patch("stratus.hooks._common.get_git_root", return_value=Path("/repo")),
            patch("stratus.orchestration.worktree.cleanup", return_value=mock_result),
        ):
            ns = argparse.Namespace(
                action="cleanup", slug="my-feat", plan_path="", base_branch="main"
            )
            _cmd_worktree(ns)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["removed"] is True

    def test_worktree_status_subcommand(self, capsys):
        """worktree status calls status() and outputs JSON."""
        from stratus.cli import _cmd_worktree

        mock_result = {
            "active": True,
            "dirty": False,
            "ahead": 2,
            "behind": 0,
            "files_changed": 3,
            "branch": "spec/feat",
            "base_branch": "main",
            "path": "/tmp/wt",
        }
        with (
            patch("stratus.hooks._common.get_git_root", return_value=Path("/repo")),
            patch("stratus.orchestration.worktree.status", return_value=mock_result),
        ):
            ns = argparse.Namespace(
                action="status", slug="my-feat", plan_path="", base_branch="main"
            )
            _cmd_worktree(ns)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["active"] is True

    def test_worktree_error_outputs_json(self, capsys):
        """WorktreeError should result in JSON error output and exit 1."""
        from stratus.cli import _cmd_worktree
        from stratus.orchestration.worktree import WorktreeError

        with (
            patch("stratus.hooks._common.get_git_root", return_value=Path("/repo")),
            patch(
                "stratus.orchestration.worktree.detect",
                side_effect=WorktreeError("git not found"),
            ),
        ):
            ns = argparse.Namespace(
                action="detect", slug="my-feat", plan_path="", base_branch="main"
            )
            with pytest.raises(SystemExit) as exc_info:
                _cmd_worktree(ns)
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "git not found" in captured.err

    def test_worktree_subcommand_registered(self):
        """The worktree subcommand must be recognized by argparse."""
        with patch("sys.argv", ["stratus", "worktree", "detect", "test-slug"]):
            with patch("stratus.cli._cmd_worktree"):
                try:
                    main()
                except SystemExit as exc:
                    assert exc.code in (0, 1, None)


class TestVersionFlag:
    def test_version_prints_semver(self, capsys: pytest.CaptureFixture[str]):
        """--version should print 'stratus <semver>'."""
        import re

        with patch("sys.argv", ["stratus", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert re.search(r"\d+\.\d+\.\d+", captured.out)

    def test_version_short_flag(self, capsys: pytest.CaptureFixture[str]):
        """-V should behave the same as --version."""
        with patch("sys.argv", ["stratus", "-V"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "stratus" in captured.out


class TestVersionImport:
    def test_init_exports_version(self):
        """stratus.__version__ should be importable."""
        from stratus import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_matches_routes(self):
        """__version__ must be the single source used in routes_system."""
        from stratus import __version__
        from stratus.server.routes_system import VERSION

        assert VERSION == __version__


class TestHookSubcommand:
    def test_hook_imports_and_calls_main(self):
        """stratus hook <module> should import stratus.hooks.<module> and call main()."""
        mock_main = MagicMock()
        mock_module = MagicMock()
        mock_module.main = mock_main

        with (
            patch("sys.argv", ["stratus", "hook", "context_monitor"]),
            patch("importlib.import_module", return_value=mock_module) as mock_import,
        ):
            main()

        mock_import.assert_called_once_with("stratus.hooks.context_monitor")
        mock_main.assert_called_once()

    def test_hook_with_different_module(self):
        """stratus hook <module> works for any hook module name."""
        mock_main = MagicMock()
        mock_module = MagicMock()
        mock_module.main = mock_main

        with (
            patch("sys.argv", ["stratus", "hook", "file_checker"]),
            patch("importlib.import_module", return_value=mock_module) as mock_import,
        ):
            main()

        mock_import.assert_called_once_with("stratus.hooks.file_checker")
        mock_main.assert_called_once()

    def test_hook_missing_module_arg_exits(self):
        """stratus hook without a module name should exit with error."""
        with patch("sys.argv", ["stratus", "hook"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse error

    def test_hook_import_error_propagates(self):
        """If the hook module doesn't exist, ImportError should propagate."""
        with (
            patch("sys.argv", ["stratus", "hook", "nonexistent_hook"]),
            patch("importlib.import_module", side_effect=ImportError("No module")),
        ):
            with pytest.raises(ImportError):
                main()


class TestInitDeliveryFlags:
    def test_init_enable_delivery_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--enable-delivery flag is accepted by the parser and passed to cmd_init."""
        data_dir = tmp_path / "ai-data"
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(data_dir))
        mock_register = MagicMock(return_value=["a.md", "b.md", "c.md"])
        with (
            patch("sys.argv", ["stratus", "init", "--scope", "local", "--enable-delivery"]),
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.registration.register_agents",
                mock_register,
            ),
        ):
            main()
        mock_register.assert_called_once()

    def test_init_skip_agents_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--skip-agents flag is accepted and suppresses agent installation."""
        data_dir = tmp_path / "ai-data"
        monkeypatch.setenv("AI_FRAMEWORK_DATA_DIR", str(data_dir))
        mock_register = MagicMock(return_value=["a.md", "b.md", "c.md"])
        with (
            patch(
                "sys.argv",
                ["stratus", "init", "--scope", "local", "--enable-delivery", "--skip-agents"],
            ),
            patch("stratus.hooks._common.get_git_root", return_value=tmp_path),
            patch(
                "stratus.bootstrap.registration.register_agents",
                mock_register,
            ),
        ):
            main()
        mock_register.assert_not_called()
