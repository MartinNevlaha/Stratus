"""Git worktree handler for spec-branch isolation.

Follows the vexor.py subprocess-wrapping pattern: all git calls go through
_run_git(), which is the single mock target in tests.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import cast


class WorktreeError(Exception):
    """Raised when a git worktree operation fails."""


def _run_git(
    args: list[str],
    *,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a git command, raising WorktreeError on failure."""
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise WorktreeError("git binary not found")
    except subprocess.TimeoutExpired:
        raise WorktreeError(f"git {args[0]} timed out")


def _worktree_dir(git_root: str | Path, slug: str, plan_path: str = "") -> Path:
    """Convention: <git_root>/.worktrees/spec-<slug>-<short_hash>/"""
    short_hash = hashlib.sha256(plan_path.encode()).hexdigest()[:8]
    return Path(git_root) / ".worktrees" / f"spec-{slug}-{short_hash}"


def derive_slug(plan_path: str) -> str:
    """Strip date prefix (YYYY-MM-DD-) and .md extension from basename."""
    name = Path(plan_path).stem  # removes extension
    # strip leading YYYY-MM-DD- if present
    stripped = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
    return stripped


def detect(
    slug: str,
    git_root: str | Path,
    *,
    plan_path: str = "",
    base_branch: str = "main",
) -> dict[str, object]:
    """Check whether a worktree for slug exists. Returns: found, path, branch, base_branch."""
    result = _run_git(["worktree", "list", "--porcelain"], cwd=git_root)
    target_path = str(_worktree_dir(git_root, slug, plan_path))
    found_path = None
    found_branch = None
    current_path = None
    current_branch = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree ") :].strip()
            current_branch = None
        elif line.startswith("branch "):
            current_branch = line[len("branch ") :].strip()
        elif line == "":
            if current_path == target_path:
                found_path = current_path
                found_branch = current_branch
                break
            current_path = None
            current_branch = None

    # handle final block (no trailing blank line)
    if found_path is None and current_path == target_path:
        found_path = current_path
        found_branch = current_branch

    return {
        "found": found_path is not None,
        "path": found_path,
        "branch": found_branch,
        "base_branch": base_branch,
    }


def create(
    slug: str,
    git_root: str | Path,
    *,
    plan_path: str = "",
    base_branch: str = "main",
) -> dict[str, object]:
    """Create a worktree; auto-stash dirty tree; copy .claude/ and .mcp.json."""
    git_root_path = Path(git_root)
    worktree_path = _worktree_dir(git_root_path, slug, plan_path)
    branch = f"spec/{slug}"

    status_result = _run_git(["status", "--porcelain"], cwd=git_root)
    stashed = False
    if status_result.stdout.strip():
        _ = _run_git(
            ["stash", "push", "-m", "ai-framework: pre-worktree stash"],
            cwd=git_root,
        )
        stashed = True

    add_result = _run_git(
        ["worktree", "add", str(worktree_path), "-b", branch, base_branch],
        cwd=git_root,
    )
    if add_result.returncode != 0:
        raise WorktreeError(f"worktree add failed: {add_result.stderr.strip()}")

    claude_src = git_root_path / ".claude"
    if claude_src.exists():
        _ = shutil.copytree(claude_src, worktree_path / ".claude", dirs_exist_ok=True)

    mcp_src = git_root_path / ".mcp.json"
    if mcp_src.exists():
        _ = shutil.copy2(str(mcp_src), str(worktree_path / ".mcp.json"))

    return {
        "path": str(worktree_path),
        "branch": branch,
        "base_branch": base_branch,
        "stashed": stashed,
    }


def diff(
    slug: str,
    git_root: str | Path,
    *,
    plan_path: str = "",
    base_branch: str = "main",
) -> str:
    """Return diff between the worktree branch and the merge-base with base_branch."""
    branch = f"spec/{slug}"

    merge_base_result = _run_git(
        ["merge-base", base_branch, branch],
        cwd=git_root,
    )
    if merge_base_result.returncode != 0:
        return ""

    merge_base = merge_base_result.stdout.strip()
    worktree_path = str(_worktree_dir(git_root, slug, plan_path))

    diff_result = _run_git(
        ["diff", merge_base, branch, "--", worktree_path],
        cwd=git_root,
    )
    return diff_result.stdout


def sync(
    slug: str,
    git_root: str | Path,
    *,
    plan_path: str = "",
) -> dict[str, object]:
    """Squash-merge the worktree branch; parse stat output. Raises WorktreeError on failure."""
    _ = plan_path  # branch is derived from slug; plan_path accepted for API consistency
    branch = f"spec/{slug}"

    merge_result = _run_git(
        ["merge", "--squash", "--stat", branch],
        cwd=git_root,
    )
    if merge_result.returncode != 0:
        raise WorktreeError(f"merge failed: {merge_result.stderr.strip()}")

    files_changed = 0
    insertions = 0
    deletions = 0
    for line in merge_result.stdout.splitlines():
        m = re.search(r"(\d+) files? changed", line)
        if m:
            files_changed = int(m.group(1))
        m = re.search(r"(\d+) insertions?\(\+\)", line)
        if m:
            insertions = int(m.group(1))
        m = re.search(r"(\d+) deletions?\(-\)", line)
        if m:
            deletions = int(m.group(1))

    head_result = _run_git(["rev-parse", "HEAD"], cwd=git_root)
    commit = head_result.stdout.strip()

    return {
        "merged": True,
        "commit": commit,
        "files_changed": files_changed,
        "insertions": insertions,
        "deletions": deletions,
    }


def cleanup(
    slug: str,
    git_root: str | Path,
    *,
    plan_path: str = "",
) -> dict[str, object]:
    """Remove worktree and delete branch. Errors captured in return dict, not raised."""
    worktree_path = str(_worktree_dir(git_root, slug, plan_path))
    branch = f"spec/{slug}"

    remove_result = _run_git(
        ["worktree", "remove", "--force", worktree_path],
        cwd=git_root,
    )
    removed = remove_result.returncode == 0

    branch_deleted = False
    if removed:
        branch_result = _run_git(["branch", "-D", branch], cwd=git_root)
        branch_deleted = branch_result.returncode == 0

    return {
        "removed": removed,
        "path": worktree_path,
        "branch_deleted": branch_deleted,
    }


def status(
    slug: str,
    git_root: str | Path,
    *,
    plan_path: str = "",
    base_branch: str = "main",
) -> dict[str, object]:
    """Return status: active, dirty, ahead, behind, files_changed, branch, base_branch, path."""
    info = detect(slug, git_root, plan_path=plan_path, base_branch=base_branch)

    if not info["found"]:
        return {
            "active": False,
            "dirty": False,
            "ahead": 0,
            "behind": 0,
            "files_changed": 0,
            "branch": None,
            "base_branch": base_branch,
            "path": None,
        }

    worktree_path = cast(str | None, info["path"])
    branch = info["branch"]
    short_branch = f"spec/{slug}"

    status_result = _run_git(["status", "--porcelain"], cwd=worktree_path)
    dirty = bool(status_result.stdout.strip())

    ahead_result = _run_git(
        ["rev-list", "--count", f"{base_branch}..{short_branch}"],
        cwd=git_root,
    )
    ahead = int(ahead_result.stdout.strip()) if ahead_result.returncode == 0 else 0

    behind_result = _run_git(
        ["rev-list", "--count", f"{short_branch}..{base_branch}"],
        cwd=git_root,
    )
    behind = int(behind_result.stdout.strip()) if behind_result.returncode == 0 else 0

    files_result = _run_git(
        ["rev-list", "--count", f"{base_branch}..{short_branch}", "--"],
        cwd=git_root,
    )
    files_changed = int(files_result.stdout.strip()) if files_result.returncode == 0 else 0

    return {
        "active": True,
        "dirty": dirty,
        "ahead": ahead,
        "behind": behind,
        "files_changed": files_changed,
        "branch": branch,
        "base_branch": base_branch,
        "path": worktree_path,
    }
