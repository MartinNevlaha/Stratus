"""Tests for self-debug CLI subcommand."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratus.cli import main


class TestSelfDebugCLIParser:
    """Test argument parsing for the self-debug subcommand."""

    def _get_args(self, argv: list[str]):
        """Build an argparse.Namespace by calling the real parser logic."""
        import argparse

        parser = argparse.ArgumentParser(prog="stratus")
        subparsers = parser.add_subparsers(dest="command")
        sd_parser = subparsers.add_parser("self-debug")
        _ = sd_parser.add_argument("-o", "--output", default=None)
        return parser.parse_args(argv)

    def test_self_debug_subcommand_exists(self) -> None:
        """Parsing ['self-debug'] sets args.command == 'self-debug'."""
        args = self._get_args(["self-debug"])
        assert args.command == "self-debug"

    def test_output_flag(self) -> None:
        """Parsing ['self-debug', '--output', '/tmp/report.md'] sets args.output."""
        args = self._get_args(["self-debug", "--output", "/tmp/report.md"])
        assert args.output == "/tmp/report.md"

    def test_output_short_flag(self) -> None:
        """Parsing ['self-debug', '-o', '/tmp/report.md'] works."""
        args = self._get_args(["self-debug", "-o", "/tmp/report.md"])
        assert args.output == "/tmp/report.md"

    def test_output_default_none(self) -> None:
        """Parsing ['self-debug'] without --output yields args.output == None."""
        args = self._get_args(["self-debug"])
        assert args.output is None

    def test_subcommand_registered_in_real_cli(self, capsys: pytest.CaptureFixture[str]) -> None:
        """self-debug appears in the real CLI's help output."""
        with pytest.raises(SystemExit):
            with patch.object(sys, "argv", ["stratus", "--help"]):
                main()
        captured = capsys.readouterr()
        assert "self-debug" in captured.out


class TestSelfDebugCLIHandler:
    """Test the self-debug command handler dispatch and behaviour."""

    def test_handler_in_dispatch(self) -> None:
        """The dispatch dict inside main() includes 'self-debug'."""

        # We call main with a mocked sandbox so the handler runs without I/O.
        mock_report = MagicMock()
        mock_sandbox = MagicMock()
        mock_sandbox.run.return_value = mock_report

        with (
            patch("stratus.cli.SelfDebugSandbox", return_value=mock_sandbox),
            patch("stratus.cli.load_self_debug_config", return_value=MagicMock()),
            patch("stratus.cli.format_report", return_value="report text"),
            patch.object(sys, "argv", ["stratus", "self-debug"]),
            patch("builtins.print"),
        ):
            # If "self-debug" is not in dispatch, main() will call parser.print_help
            # and exit(1). With the handler wired up it should exit cleanly (0).
            try:
                main()
            except SystemExit as exc:
                pytest.fail(f"main() exited with code {exc.code} — handler not dispatched")

    def test_runs_sandbox_and_prints_report(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Handler creates SelfDebugSandbox, calls run(), formats report, prints to stdout."""
        mock_report = MagicMock()
        mock_sandbox = MagicMock()
        mock_sandbox.run.return_value = mock_report
        mock_config = MagicMock()

        with (
            patch("stratus.cli.SelfDebugSandbox", return_value=mock_sandbox) as mock_cls,
            patch("stratus.cli.load_self_debug_config", return_value=mock_config) as mock_load,
            patch("stratus.cli.format_report", return_value="# Self-Debug Report") as mock_fmt,
            patch.object(sys, "argv", ["stratus", "self-debug"]),
        ):
            main()

        mock_load.assert_called_once()
        mock_cls.assert_called_once()
        mock_sandbox.run.assert_called_once()
        mock_fmt.assert_called_once_with(mock_report)

        captured = capsys.readouterr()
        assert "# Self-Debug Report" in captured.out

    def test_writes_to_output_file(self, tmp_path: Path) -> None:
        """When --output is given, report is written to file not stdout."""
        out_file = tmp_path / "report.md"
        mock_report = MagicMock()
        mock_sandbox = MagicMock()
        mock_sandbox.run.return_value = mock_report

        with (
            patch("stratus.cli.SelfDebugSandbox", return_value=mock_sandbox),
            patch("stratus.cli.load_self_debug_config", return_value=MagicMock()),
            patch("stratus.cli.format_report", return_value="file content"),
            patch.object(sys, "argv", ["stratus", "self-debug", "--output", str(out_file)]),
        ):
            main()

        assert out_file.read_text() == "file content"

    def test_prints_error_on_value_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """When sandbox.run() raises ValueError, prints error to stderr and exits 1."""
        mock_sandbox = MagicMock()
        mock_sandbox.run.side_effect = ValueError(
            "Self-debug refuses to run on main/master branch."
        )

        with (
            patch("stratus.cli.SelfDebugSandbox", return_value=mock_sandbox),
            patch("stratus.cli.load_self_debug_config", return_value=MagicMock()),
            patch.object(sys, "argv", ["stratus", "self-debug"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "main/master" in captured.err
