"""Tests for learning/git_analyzer.py — git change detection."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stratus.learning.git_analyzer import AnalysisError, GitAnalyzer


def _mock_run(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


MOCK_TARGET = "stratus.learning.git_analyzer._run_git"


class TestRunGit:
    def test_raises_on_git_not_found(self):
        with patch(MOCK_TARGET, side_effect=AnalysisError("git binary not found")):
            analyzer = GitAnalyzer(Path("/repo"))
            with pytest.raises(AnalysisError, match="git binary not found"):
                analyzer.analyze_changes()


class TestGetAddedFiles:
    def test_parses_added_files(self):
        diff_output = "src/new_file.py\nlib/other.py\n"
        with patch(MOCK_TARGET, return_value=_mock_run(stdout=diff_output)):
            analyzer = GitAnalyzer(Path("/repo"))
            files = analyzer._get_added_files("abc123")
        assert files == ["src/new_file.py", "lib/other.py"]

    def test_empty_output(self):
        with patch(MOCK_TARGET, return_value=_mock_run(stdout="")):
            analyzer = GitAnalyzer(Path("/repo"))
            files = analyzer._get_added_files("abc123")
        assert files == []

    def test_handles_error(self):
        with patch(MOCK_TARGET, return_value=_mock_run(returncode=1, stderr="error")):
            analyzer = GitAnalyzer(Path("/repo"))
            files = analyzer._get_added_files("abc123")
        assert files == []


class TestGetModifiedFiles:
    def test_parses_modified_files(self):
        diff_output = "src/changed.py\nlib/updated.py\n"
        with patch(MOCK_TARGET, return_value=_mock_run(stdout=diff_output)):
            analyzer = GitAnalyzer(Path("/repo"))
            files = analyzer._get_modified_files("abc123")
        assert files == ["src/changed.py", "lib/updated.py"]


class TestGetCommitMessages:
    def test_parses_commit_messages(self):
        log_output = "abc123|fix: handle auth error\ndef456|feat: add user profile\n"
        with patch(MOCK_TARGET, return_value=_mock_run(stdout=log_output)):
            analyzer = GitAnalyzer(Path("/repo"))
            commits = analyzer._get_commit_messages("abc123")
        assert len(commits) == 2
        assert commits[0]["hash"] == "abc123"
        assert commits[0]["message"] == "fix: handle auth error"
        assert commits[1]["hash"] == "def456"

    def test_empty_log(self):
        with patch(MOCK_TARGET, return_value=_mock_run(stdout="")):
            analyzer = GitAnalyzer(Path("/repo"))
            commits = analyzer._get_commit_messages(None)
        assert commits == []


class TestDetectStructuralChanges:
    def test_detects_new_directory_pattern(self):
        added = [
            "services/auth/main.py",
            "services/auth/__init__.py",
            "services/billing/main.py",
            "services/billing/__init__.py",
        ]
        analyzer = GitAnalyzer(Path("/repo"))
        detections = analyzer._detect_structural_changes(added)
        assert len(detections) >= 1
        structural = [d for d in detections if d.type.value == "structural_change"]
        assert len(structural) >= 1

    def test_no_pattern_single_file(self):
        added = ["readme.md"]
        analyzer = GitAnalyzer(Path("/repo"))
        detections = analyzer._detect_structural_changes(added)
        structural = [d for d in detections if d.type.value == "structural_change"]
        assert len(structural) == 0


class TestDetectImportPatterns:
    def test_detects_common_imports(self):
        analyzer = GitAnalyzer(Path("/repo"))
        # Mock reading file content via _run_git for git show
        contents = {
            "a.py": "import logging\nfrom pathlib import Path\n",
            "b.py": "import logging\nfrom pathlib import Path\n",
            "c.py": "import logging\nfrom pathlib import Path\n",
        }

        def mock_run(args, *, cwd=None):
            if args[0] == "show":
                # args like ["show", "HEAD:a.py"]
                file_path = args[1].split(":")[-1]
                return _mock_run(stdout=contents.get(file_path, ""))
            return _mock_run(stdout="")

        with patch(MOCK_TARGET, side_effect=mock_run):
            detections = analyzer._detect_import_patterns(list(contents.keys()))
        import_detections = [d for d in detections if d.type.value == "import_pattern"]
        assert len(import_detections) >= 1


class TestGetCommitsSince:
    def test_counts_commits(self):
        with patch(MOCK_TARGET, return_value=_mock_run(stdout="15\n")):
            analyzer = GitAnalyzer(Path("/repo"))
            count = analyzer._get_commits_since("abc123")
        assert count == 15

    def test_counts_all_commits_no_since(self):
        with patch(MOCK_TARGET, return_value=_mock_run(stdout="42\n")):
            analyzer = GitAnalyzer(Path("/repo"))
            count = analyzer._get_commits_since(None)
        assert count == 42

    def test_returns_zero_on_error(self):
        with patch(MOCK_TARGET, return_value=_mock_run(returncode=1)):
            analyzer = GitAnalyzer(Path("/repo"))
            count = analyzer._get_commits_since("abc")
        assert count == 0


class TestAnalyzeChanges:
    def test_full_analysis(self):
        def mock_run(args, *, cwd=None):
            if "diff" in args and "--diff-filter=A" in args:
                return _mock_run(stdout="services/new/main.py\nservices/new/__init__.py\n")
            if "diff" in args and "--diff-filter=M" in args:
                return _mock_run(stdout="src/existing.py\n")
            if "log" in args:
                return _mock_run(stdout="abc|fix: handle error\n")
            if "rev-list" in args:
                return _mock_run(stdout="5\n")
            if "show" in args:
                return _mock_run(stdout="import os\n")
            return _mock_run()

        with patch(MOCK_TARGET, side_effect=mock_run):
            analyzer = GitAnalyzer(Path("/repo"))
            detections = analyzer.analyze_changes(since_commit="abc123")
        assert isinstance(detections, list)

    def test_analysis_with_no_changes(self):
        with patch(MOCK_TARGET, return_value=_mock_run(stdout="")):
            analyzer = GitAnalyzer(Path("/repo"))
            detections = analyzer.analyze_changes()
        assert detections == []

    def test_git_error_raises(self):
        with patch(MOCK_TARGET, side_effect=AnalysisError("git failed")):
            analyzer = GitAnalyzer(Path("/repo"))
            with pytest.raises(AnalysisError):
                analyzer.analyze_changes()
