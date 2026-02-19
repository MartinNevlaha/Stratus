"""Tests for SelfDebugSandbox facade."""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratus.self_debug.config import SelfDebugConfig
from stratus.self_debug.models import DebugReport
from stratus.self_debug.sandbox import SelfDebugSandbox

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sandbox(tmp_path: Path, config: SelfDebugConfig | None = None) -> SelfDebugSandbox:
    cfg = config or SelfDebugConfig()
    return SelfDebugSandbox(config=cfg, project_root=tmp_path)


def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _safe_branch_mock(branch: str = "feature/test") -> MagicMock:
    """Return a mock subprocess.CompletedProcess for a git branch call."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = branch + "\n"
    return m


# ---------------------------------------------------------------------------
# TestSelfDebugSandbox
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSelfDebugSandbox:
    def test_run_returns_debug_report(self, tmp_path: Path) -> None:
        """Sandbox.run() returns a DebugReport when given a file with a bare except."""
        src = tmp_path / "src" / "stratus" / "example.py"
        _write_py(src, "try:\n    pass\nexcept:\n    pass\n")

        sandbox = _make_sandbox(tmp_path)
        with patch("stratus.self_debug.sandbox.subprocess.run", return_value=_safe_branch_mock()):
            report = sandbox.run()

        assert isinstance(report, DebugReport)
        assert len(report.issues) > 0
        assert any(i.type == "bare_except" for i in report.issues)

    def test_respects_max_issues(self, tmp_path: Path) -> None:
        """config.max_issues=1 caps the issues list to 1 entry."""
        # Create two files, each with a bare except → 2 issues minimum
        for name in ("a.py", "b.py"):
            src = tmp_path / "src" / "stratus" / name
            _write_py(src, "try:\n    pass\nexcept:\n    pass\n")

        cfg = SelfDebugConfig(max_issues=1)
        sandbox = _make_sandbox(tmp_path, cfg)

        with patch("stratus.self_debug.sandbox.subprocess.run", return_value=_safe_branch_mock()):
            report = sandbox.run()

        assert len(report.issues) <= 1

    def test_analysis_time_recorded(self, tmp_path: Path) -> None:
        """report.analysis_time_ms is a positive integer."""
        src = tmp_path / "src" / "stratus" / "example.py"
        _write_py(src, "x = 1\n")

        sandbox = _make_sandbox(tmp_path)
        with patch("stratus.self_debug.sandbox.subprocess.run", return_value=_safe_branch_mock()):
            report = sandbox.run()

        assert isinstance(report.analysis_time_ms, int)
        assert report.analysis_time_ms >= 0

    def test_analyzed_and_skipped_counts(self, tmp_path: Path) -> None:
        """analyzed_files and skipped_files are non-negative integers in the report."""
        allowed = tmp_path / "src" / "stratus" / "util.py"
        _write_py(allowed, "x = 1\n")
        outside = tmp_path / "other" / "stuff.py"
        _write_py(outside, "x = 1\n")

        sandbox = _make_sandbox(tmp_path)
        with patch("stratus.self_debug.sandbox.subprocess.run", return_value=_safe_branch_mock()):
            report = sandbox.run()

        assert report.analyzed_files >= 1  # util.py was analyzed
        assert report.skipped_files >= 1  # stuff.py was skipped


# ---------------------------------------------------------------------------
# TestBranchValidation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBranchValidation:
    def test_refuses_main_branch(self, tmp_path: Path) -> None:
        """Sandbox raises ValueError when on the main branch."""
        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock("main"),
        ):
            with pytest.raises(ValueError, match="main"):
                sandbox.run()

    def test_refuses_master_branch(self, tmp_path: Path) -> None:
        """Sandbox raises ValueError when on the master branch."""
        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock("master"),
        ):
            with pytest.raises(ValueError, match="[Mm]aster|main"):
                sandbox.run()

    def test_allows_feature_branch(self, tmp_path: Path) -> None:
        """Sandbox runs successfully on a feature branch."""
        src = tmp_path / "src" / "stratus" / "util.py"
        _write_py(src, "x = 1\n")

        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock("feature/foo"),
        ):
            report = sandbox.run()

        assert isinstance(report, DebugReport)

    def test_git_unavailable_analyze_only(self, tmp_path: Path) -> None:
        """When git is unavailable, analysis still runs but patches are empty."""
        src = tmp_path / "src" / "stratus" / "util.py"
        _write_py(src, "try:\n    pass\nexcept:\n    pass\n")

        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                report = sandbox.run()

        assert isinstance(report, DebugReport)
        assert len(report.patches) == 0
        assert len(report.issues) > 0
        assert any("branch" in str(w.message).lower() for w in caught)

    def test_git_error_analyze_only(self, tmp_path: Path) -> None:
        """When git returns non-zero exit code, patches list is empty but issues are present."""
        src = tmp_path / "src" / "stratus" / "util.py"
        _write_py(src, "try:\n    pass\nexcept:\n    pass\n")

        error_result = MagicMock()
        error_result.returncode = 128
        error_result.stdout = ""

        sandbox = _make_sandbox(tmp_path)
        with patch("stratus.self_debug.sandbox.subprocess.run", return_value=error_result):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                report = sandbox.run()

        assert isinstance(report, DebugReport)
        assert len(report.patches) == 0
        assert len(report.issues) > 0
        assert any("branch" in str(w.message).lower() for w in caught)


# ---------------------------------------------------------------------------
# TestPathConstraints
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPathConstraints:
    def test_analyzes_all_under_src_stratus(self, tmp_path: Path) -> None:
        """Files under src/stratus/ (including hooks/, orchestration/) are analyzed."""
        hooks_file = tmp_path / "src" / "stratus" / "hooks" / "myhook.py"
        orch_file = tmp_path / "src" / "stratus" / "orchestration" / "coord.py"
        _write_py(hooks_file, "try:\n    pass\nexcept:\n    pass\n")
        _write_py(orch_file, "try:\n    pass\nexcept:\n    pass\n")

        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock(),
        ):
            report = sandbox.run()

        analyzed_paths = {i.file_path for i in report.issues}
        assert any("hooks" in p for p in analyzed_paths)
        assert any("orchestration" in p for p in analyzed_paths)

    def test_skips_files_outside_allowed_prefix(self, tmp_path: Path) -> None:
        """Files NOT under src/stratus/ are skipped (not present in issues)."""
        outside = tmp_path / "scripts" / "helper.py"
        _write_py(outside, "try:\n    pass\nexcept:\n    pass\n")

        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock(),
        ):
            report = sandbox.run()

        analyzed_paths = {i.file_path for i in report.issues}
        assert not any("scripts" in p for p in analyzed_paths)

    def test_no_patches_for_denied_paths(self, tmp_path: Path) -> None:
        """Issues in hooks/ or orchestration/ paths produce no patches."""
        hooks_file = tmp_path / "src" / "stratus" / "hooks" / "myhook.py"
        orch_file = tmp_path / "src" / "stratus" / "orchestration" / "coord.py"
        _write_py(hooks_file, "try:\n    pass\nexcept:\n    pass\n")
        _write_py(orch_file, "try:\n    pass\nexcept:\n    pass\n")

        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock(),
        ):
            report = sandbox.run()

        # Patches for denied paths must not exist
        denied_prefixes = {"src/stratus/hooks/", "src/stratus/orchestration/"}
        for patch_proposal in report.patches:
            assert not any(patch_proposal.file_path.startswith(p) for p in denied_prefixes), (
                f"Unexpected patch for denied path: {patch_proposal.file_path}"
            )

    def test_patches_for_allowed_paths(self, tmp_path: Path) -> None:
        """Issues in non-denied paths (e.g. src/stratus/memory/) DO get patches."""
        allowed_file = tmp_path / "src" / "stratus" / "memory" / "util.py"
        _write_py(allowed_file, "try:\n    pass\nexcept:\n    pass\n")

        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock(),
        ):
            report = sandbox.run()

        patched_paths = {p.file_path for p in report.patches}
        assert any("memory" in p for p in patched_paths), (
            f"Expected a patch for memory/util.py, got patches for: {patched_paths}"
        )


# ---------------------------------------------------------------------------
# TestRecursionGuard
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecursionGuard:
    def test_self_debug_analyzable_but_not_patchable(self, tmp_path: Path) -> None:
        """Files in self_debug/ are analyzed (issues reported) but not patched."""
        sd_file = tmp_path / "src" / "stratus" / "self_debug" / "helper.py"
        _write_py(sd_file, "try:\n    pass\nexcept:\n    pass\n")

        sandbox = _make_sandbox(tmp_path)
        with patch(
            "stratus.self_debug.sandbox.subprocess.run",
            return_value=_safe_branch_mock(),
        ):
            report = sandbox.run()

        # Issue must exist for self_debug file
        sd_issues = [i for i in report.issues if "self_debug" in i.file_path]
        assert len(sd_issues) > 0, "Expected issues for self_debug/ file"

        # Patch must NOT exist for self_debug file
        sd_patches = [p for p in report.patches if "self_debug" in p.file_path]
        assert len(sd_patches) == 0, "Expected no patches for self_debug/ file"
