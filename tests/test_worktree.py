"""Tests for the git worktree handler module.

All subprocess calls are mocked via _run_git. shutil.copytree is mocked for
file copy operations.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from stratus.orchestration.worktree import (
    WorktreeError,
    _worktree_dir,
    cleanup,
    create,
    derive_slug,
    detect,
    diff,
    status,
    sync,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(
    stdout: str = "", stderr: str = "", returncode: int = 0
) -> subprocess.CompletedProcess:
    result: subprocess.CompletedProcess[str] = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


GIT_ROOT = "/repo"
SLUG = "add-auth"
PLAN_PATH = "2026-02-15-add-auth.md"

# Porcelain worktree list output for a matched worktree
_WORKTREE_PATH = str(_worktree_dir(GIT_ROOT, SLUG, PLAN_PATH))

WORKTREE_LIST_WITH_MATCH = f"""\
worktree /repo
HEAD abc123
branch refs/heads/main

worktree {_WORKTREE_PATH}
HEAD def456
branch refs/heads/spec/{SLUG}

"""

WORKTREE_LIST_NO_MATCH = """\
worktree /repo
HEAD abc123
branch refs/heads/main

"""


# ---------------------------------------------------------------------------
# 1. derive_slug
# ---------------------------------------------------------------------------


class TestDeriveSlug:
    def test_derive_slug_strips_date_prefix_and_md_extension(self):
        assert derive_slug("2026-02-15-my-feature.md") == "my-feature"

    def test_derive_slug_no_date_prefix_strips_md_extension(self):
        assert derive_slug("my-feature.md") == "my-feature"

    def test_derive_slug_full_path_with_date_prefix(self):
        assert derive_slug("/path/to/2026-02-15-add-auth.md") == "add-auth"

    def test_derive_slug_no_md_extension(self):
        assert derive_slug("simple") == "simple"

    def test_derive_slug_date_prefix_only_no_extension(self):
        assert derive_slug("2026-02-15-feature-name") == "feature-name"

    def test_derive_slug_nested_path_no_date(self):
        assert derive_slug("/some/path/my-feature.md") == "my-feature"


# ---------------------------------------------------------------------------
# 2. detect
# ---------------------------------------------------------------------------


class TestDetect:
    @patch("stratus.orchestration.worktree._run_git")
    def test_detect_found_returns_worktree_info(self, mock_run):
        mock_run.return_value = _completed(WORKTREE_LIST_WITH_MATCH)

        result = detect(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["found"] is True
        assert result["path"] == _WORKTREE_PATH
        assert result["branch"] == f"refs/heads/spec/{SLUG}"
        assert "base_branch" in result

    @patch("stratus.orchestration.worktree._run_git")
    def test_detect_not_found_returns_false(self, mock_run):
        mock_run.return_value = _completed(WORKTREE_LIST_NO_MATCH)

        result = detect(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["found"] is False
        assert result["path"] is None
        assert result["branch"] is None

    @patch("stratus.orchestration.worktree._run_git")
    def test_detect_calls_worktree_list_porcelain(self, mock_run):
        mock_run.return_value = _completed(WORKTREE_LIST_NO_MATCH)

        detect(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        mock_run.assert_called_once_with(["worktree", "list", "--porcelain"], cwd=GIT_ROOT)


# ---------------------------------------------------------------------------
# 3. create
# ---------------------------------------------------------------------------


class TestCreate:
    @patch("stratus.orchestration.worktree.shutil")
    @patch("stratus.orchestration.worktree._run_git")
    def test_create_happy_path_clean_tree(self, mock_run, mock_shutil, tmp_path):
        """Clean working tree: no stash, creates worktree, returns info."""
        worktree_path = str(_worktree_dir(GIT_ROOT, SLUG, PLAN_PATH))

        # status --porcelain → clean
        # worktree add → success
        mock_run.side_effect = [
            _completed(""),  # git status --porcelain
            _completed(""),  # git worktree add
        ]
        mock_shutil.copytree = MagicMock()

        result = create(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["path"] == worktree_path
        assert result["branch"] == f"spec/{SLUG}"
        assert result["base_branch"] == "main"
        assert result["stashed"] is False

    @patch("stratus.orchestration.worktree.shutil")
    @patch("stratus.orchestration.worktree._run_git")
    def test_create_auto_stash_dirty_tree(self, mock_run, mock_shutil):
        """Dirty working tree triggers stash before creating worktree."""
        mock_run.side_effect = [
            _completed(" M somefile.py"),  # git status --porcelain → dirty
            _completed(""),  # git stash push
            _completed(""),  # git worktree add
        ]
        mock_shutil.copytree = MagicMock()

        result = create(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["stashed"] is True
        stash_call = mock_run.call_args_list[1]
        assert stash_call == call(
            ["stash", "push", "-m", "ai-framework: pre-worktree stash"],
            cwd=GIT_ROOT,
        )

    @patch("stratus.orchestration.worktree.shutil")
    @patch("stratus.orchestration.worktree._run_git")
    def test_create_raises_on_worktree_add_failure(self, mock_run, mock_shutil):
        """git worktree add failure raises WorktreeError."""
        mock_run.side_effect = [
            _completed(""),  # git status --porcelain
            _completed("fatal: error", returncode=128),  # git worktree add fails
        ]
        mock_shutil.copytree = MagicMock()

        with pytest.raises(WorktreeError, match="worktree add failed"):
            create(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

    @patch("stratus.orchestration.worktree.shutil")
    @patch("stratus.orchestration.worktree._run_git")
    def test_create_copies_claude_dir_if_exists(self, mock_run, mock_shutil, tmp_path):
        """Copies .claude/ into the new worktree when it exists."""
        git_root = str(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        worktree_path = _worktree_dir(git_root, SLUG, PLAN_PATH)
        worktree_path.mkdir(parents=True)

        mock_run.side_effect = [
            _completed(""),  # git status --porcelain
            _completed(""),  # git worktree add
        ]
        mock_shutil.copytree = MagicMock()

        create(SLUG, git_root, plan_path=PLAN_PATH)

        mock_shutil.copytree.assert_called_once_with(
            claude_dir, worktree_path / ".claude", dirs_exist_ok=True
        )

    @patch("stratus.orchestration.worktree.shutil")
    @patch("stratus.orchestration.worktree._run_git")
    def test_create_worktree_add_uses_base_branch(self, mock_run, mock_shutil):
        """git worktree add command targets the correct base branch."""
        mock_run.side_effect = [
            _completed(""),  # git status --porcelain
            _completed(""),  # git worktree add
        ]
        mock_shutil.copytree = MagicMock()

        create(SLUG, GIT_ROOT, plan_path=PLAN_PATH, base_branch="develop")

        worktree_call = mock_run.call_args_list[1]
        args_passed = worktree_call[0][0]
        assert "develop" in args_passed
        assert f"spec/{SLUG}" in args_passed


# ---------------------------------------------------------------------------
# 4. diff
# ---------------------------------------------------------------------------


class TestDiff:
    @patch("stratus.orchestration.worktree._run_git")
    def test_diff_returns_diff_string(self, mock_run):
        diff_output = "diff --git a/foo.py b/foo.py\n+new line\n"
        # merge-base call → SHA, then diff call → diff output
        mock_run.side_effect = [
            _completed("abc123\n"),  # git merge-base
            _completed(diff_output),  # git diff
        ]

        result = diff(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result == diff_output

    @patch("stratus.orchestration.worktree._run_git")
    def test_diff_calls_merge_base_then_diff(self, mock_run):
        mock_run.side_effect = [
            _completed("abc123\n"),
            _completed(""),
        ]

        diff(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        calls = mock_run.call_args_list
        assert calls[0][0][0] == ["merge-base", "main", f"spec/{SLUG}"]
        assert calls[1][0][0][:2] == ["diff", "abc123"]

    @patch("stratus.orchestration.worktree._run_git")
    def test_diff_returns_empty_string_on_error(self, mock_run):
        mock_run.side_effect = [
            _completed("", returncode=128),  # merge-base fails
        ]

        result = diff(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result == ""


# ---------------------------------------------------------------------------
# 5. sync
# ---------------------------------------------------------------------------


class TestSync:
    @patch("stratus.orchestration.worktree._run_git")
    def test_sync_happy_path_returns_stats(self, mock_run):
        stat_output = (
            " src/foo.py | 10 +++++\n"
            " src/bar.py |  5 ---\n"
            " 2 files changed, 10 insertions(+), 5 deletions(-)\n"
        )
        mock_run.side_effect = [
            _completed(stat_output),  # git merge --squash --stat
            _completed("abc123\n"),  # git rev-parse HEAD
        ]

        result = sync(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["merged"] is True
        assert result["files_changed"] == 2
        assert result["insertions"] == 10
        assert result["deletions"] == 5
        assert result["commit"] == "abc123"

    @patch("stratus.orchestration.worktree._run_git")
    def test_sync_raises_on_merge_failure(self, mock_run):
        mock_run.return_value = _completed("conflict", returncode=1)

        with pytest.raises(WorktreeError, match="merge failed"):
            sync(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

    @patch("stratus.orchestration.worktree._run_git")
    def test_sync_calls_merge_squash(self, mock_run):
        mock_run.side_effect = [
            _completed(" 1 file changed, 3 insertions(+)\n"),
            _completed("abc123\n"),
        ]

        sync(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        first_call_args = mock_run.call_args_list[0][0][0]
        assert "merge" in first_call_args
        assert "--squash" in first_call_args
        assert f"spec/{SLUG}" in first_call_args


# ---------------------------------------------------------------------------
# 6. cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    @patch("stratus.orchestration.worktree._run_git")
    def test_cleanup_happy_path(self, mock_run):
        mock_run.side_effect = [
            _completed(""),  # git worktree remove --force
            _completed(""),  # git branch -D
        ]
        worktree_path = str(_worktree_dir(GIT_ROOT, SLUG, PLAN_PATH))

        result = cleanup(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["removed"] is True
        assert result["path"] == worktree_path
        assert result["branch_deleted"] is True

    @patch("stratus.orchestration.worktree._run_git")
    def test_cleanup_calls_worktree_remove_then_branch_delete(self, mock_run):
        mock_run.side_effect = [
            _completed(""),
            _completed(""),
        ]
        worktree_path = str(_worktree_dir(GIT_ROOT, SLUG, PLAN_PATH))

        cleanup(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        calls = mock_run.call_args_list
        assert calls[0][0][0] == ["worktree", "remove", "--force", worktree_path]
        assert calls[1][0][0] == ["branch", "-D", f"spec/{SLUG}"]

    @patch("stratus.orchestration.worktree._run_git")
    def test_cleanup_handles_worktree_remove_error(self, mock_run):
        """When worktree remove fails, removed=False and branch_deleted=False."""
        mock_run.return_value = _completed("error", returncode=128)

        result = cleanup(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["removed"] is False
        assert result["branch_deleted"] is False

    @patch("stratus.orchestration.worktree._run_git")
    def test_cleanup_handles_branch_delete_error(self, mock_run):
        """When branch delete fails after successful remove, branch_deleted=False."""
        mock_run.side_effect = [
            _completed(""),  # worktree remove succeeds
            _completed("", returncode=1),  # branch -D fails
        ]

        result = cleanup(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["removed"] is True
        assert result["branch_deleted"] is False


# ---------------------------------------------------------------------------
# 7. status
# ---------------------------------------------------------------------------


class TestStatus:
    @patch("stratus.orchestration.worktree._run_git")
    def test_status_active_clean_worktree(self, mock_run):
        worktree_path = str(_worktree_dir(GIT_ROOT, SLUG, PLAN_PATH))
        mock_run.side_effect = [
            _completed(WORKTREE_LIST_WITH_MATCH),  # worktree list
            _completed(""),  # git status --porcelain (clean)
            _completed("3\n"),  # ahead count
            _completed("1\n"),  # behind count
            _completed("2\n"),  # files changed in worktree
        ]

        result = status(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["active"] is True
        assert result["dirty"] is False
        assert result["ahead"] == 3
        assert result["behind"] == 1
        assert result["branch"] == f"refs/heads/spec/{SLUG}"
        assert result["base_branch"] == "main"
        assert result["path"] == worktree_path

    @patch("stratus.orchestration.worktree._run_git")
    def test_status_active_dirty_worktree(self, mock_run):
        mock_run.side_effect = [
            _completed(WORKTREE_LIST_WITH_MATCH),
            _completed(" M modified.py\n"),  # dirty
            _completed("0\n"),
            _completed("0\n"),
            _completed("1\n"),
        ]

        result = status(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["active"] is True
        assert result["dirty"] is True

    @patch("stratus.orchestration.worktree._run_git")
    def test_status_inactive_worktree(self, mock_run):
        mock_run.return_value = _completed(WORKTREE_LIST_NO_MATCH)

        result = status(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["active"] is False
        assert result["dirty"] is False
        assert result["ahead"] == 0
        assert result["behind"] == 0
        assert result["path"] is None
        assert result["branch"] is None

    @patch("stratus.orchestration.worktree._run_git")
    def test_status_files_changed_count(self, mock_run):
        mock_run.side_effect = [
            _completed(WORKTREE_LIST_WITH_MATCH),
            _completed(""),
            _completed("5\n"),
            _completed("2\n"),
            _completed("4\n"),
        ]

        result = status(SLUG, GIT_ROOT, plan_path=PLAN_PATH)

        assert result["files_changed"] == 4


# ---------------------------------------------------------------------------
# _run_git error paths (unit tests)
# ---------------------------------------------------------------------------


class TestRunGit:
    def test_run_git_raises_on_file_not_found(self):
        """WorktreeError raised when git binary is missing."""
        from stratus.orchestration.worktree import _run_git

        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(WorktreeError, match="git binary not found"):
                _run_git(["status"])

    def test_run_git_raises_on_timeout(self):
        from stratus.orchestration.worktree import _run_git

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            with pytest.raises(WorktreeError, match="timed out"):
                _run_git(["status"])
