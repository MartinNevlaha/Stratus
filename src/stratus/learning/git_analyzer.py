"""Git diff/log analysis for detecting patterns in project history."""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath

from stratus.learning.models import Detection, DetectionType


class AnalysisError(Exception):
    """Raised when git analysis operations fail."""


def _run_git(
    args: list[str],
    *,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a git command, raising AnalysisError on failure."""
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
    except FileNotFoundError:
        raise AnalysisError("git binary not found")
    except subprocess.TimeoutExpired:
        raise AnalysisError(f"git {args[0]} timed out")


class GitAnalyzer:
    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    def analyze_changes(
        self,
        since_commit: str | None = None,
        scope: str | None = None,
    ) -> list[Detection]:
        """Run full git analysis pipeline, returning raw detections."""
        added = self._get_added_files(since_commit)
        modified = self._get_modified_files(since_commit)

        if not added and not modified:
            return []

        detections: list[Detection] = []
        detections.extend(self._detect_structural_changes(added))
        detections.extend(self._detect_import_patterns(modified))
        return detections

    def _get_added_files(self, since_commit: str | None) -> list[str]:
        args = ["diff", "--name-only", "--diff-filter=A"]
        if since_commit:
            args.append(since_commit)
        else:
            args.append("HEAD~1")
        result = _run_git(args, cwd=self._root)
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.strip().split("\n") if line]

    def _get_modified_files(self, since_commit: str | None) -> list[str]:
        args = ["diff", "--name-only", "--diff-filter=M"]
        if since_commit:
            args.append(since_commit)
        else:
            args.append("HEAD~1")
        result = _run_git(args, cwd=self._root)
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.strip().split("\n") if line]

    def _get_commit_messages(
        self,
        since_commit: str | None,
        limit: int = 50,
    ) -> list[dict]:
        args = ["log", f"-{limit}", "--pretty=format:%H|%s"]
        if since_commit:
            args.append(f"{since_commit}..HEAD")
        result = _run_git(args, cwd=self._root)
        if result.returncode != 0:
            return []
        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            sha, msg = line.split("|", 1)
            commits.append({"hash": sha, "message": msg})
        return commits

    def _detect_structural_changes(self, added_files: list[str]) -> list[Detection]:
        """Detect new directory patterns (e.g., multiple new service dirs)."""
        if not added_files:
            return []
        # Group by parent directory
        dir_counter: Counter[str] = Counter()
        for f in added_files:
            parts = PurePosixPath(f).parts
            if len(parts) >= 2:
                dir_counter[parts[0] + "/" + parts[1]] += 1

        detections = []
        # Look for parent dirs with multiple new subdirs
        parent_counter: Counter[str] = Counter()
        for d in dir_counter:
            parent = PurePosixPath(d).parts[0]
            parent_counter[parent] += 1

        for parent, count in parent_counter.items():
            if count >= 2:
                matching_files = [
                    f for f in added_files if f.startswith(parent + "/")
                ]
                detections.append(
                    Detection(
                        type=DetectionType.STRUCTURAL_CHANGE,
                        count=count,
                        confidence_raw=min(0.4 + count * 0.1, 0.9),
                        files=matching_files,
                        description=f"New directory structure under {parent}/",
                        instances=[{"directory": parent, "subdirs": count}],
                    )
                )
        return detections

    def _detect_import_patterns(self, modified_files: list[str]) -> list[Detection]:
        """Find common import patterns across modified files."""
        if not modified_files:
            return []

        import_counter: Counter[str] = Counter()
        file_imports: dict[str, list[str]] = {}

        for f in modified_files:
            result = _run_git(["show", f"HEAD:{f}"], cwd=self._root)
            if result.returncode != 0:
                continue
            imports = []
            for line in result.stdout.split("\n"):
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    imports.append(stripped)
                    import_counter[stripped] += 1
            file_imports[f] = imports

        detections = []
        for imp, count in import_counter.items():
            if count >= 3:
                matching_files = [
                    f for f, imps in file_imports.items() if imp in imps
                ]
                detections.append(
                    Detection(
                        type=DetectionType.IMPORT_PATTERN,
                        count=count,
                        confidence_raw=min(0.3 + count * 0.1, 0.8),
                        files=matching_files,
                        description=f"Common import: {imp}",
                        instances=[{"import": imp, "count": count}],
                    )
                )
        return detections

    def _get_commits_since(self, since_commit: str | None) -> int:
        args = ["rev-list", "--count"]
        if since_commit:
            args.append(f"{since_commit}..HEAD")
        else:
            args.append("HEAD")
        result = _run_git(args, cwd=self._root)
        if result.returncode != 0:
            return 0
        try:
            return int(result.stdout.strip())
        except ValueError:
            return 0
