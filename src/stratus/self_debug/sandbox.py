"""SelfDebugSandbox facade: orchestrates the full self-debug pipeline."""

from __future__ import annotations

import subprocess
import time
import warnings
from pathlib import Path

from stratus.self_debug.analyzer import analyze_directory
from stratus.self_debug.config import SelfDebugConfig
from stratus.self_debug.models import DebugReport, PatchProposal
from stratus.self_debug.patcher import generate_patch

# Analyze broadly — all of src/stratus/
_ANALYZE_PREFIXES: frozenset[str] = frozenset({"src/stratus/"})

# Patch narrowly — deny governance/enforcement/self paths
_PATCH_DENY_PREFIXES: frozenset[str] = frozenset(
    {
        "src/stratus/hooks/",
        "src/stratus/orchestration/",
        "src/stratus/registry/",
        "src/stratus/self_debug/",
    }
)

_GOVERNANCE_DENYLIST: frozenset[str] = frozenset(
    {
        ".claude/",
        ".ai-framework.json",
        "plugin/hooks/",
        ".github/",
    }
)


class SelfDebugSandbox:
    _config: SelfDebugConfig
    _root: Path

    def __init__(self, config: SelfDebugConfig, project_root: Path) -> None:
        self._config = config
        self._root = project_root

    def run(self) -> DebugReport:
        """Full pipeline: validate branch → analyze → patch → report."""
        start_ms = time.monotonic_ns() // 1_000_000

        branch_known, is_safe = self._validate_branch()
        if branch_known and not is_safe:
            msg = "Self-debug refuses to run on main/master branch."
            raise ValueError(msg)

        if not branch_known:
            warnings.warn(
                "Could not determine git branch. Running analysis only (no patches).",
                stacklevel=2,
            )

        issues, analyzed, skipped = analyze_directory(
            self._root,
            allowed_prefixes=_ANALYZE_PREFIXES,
            denied_prefixes=frozenset(),
        )

        if len(issues) > self._config.max_issues:
            issues = issues[: self._config.max_issues]

        patches: list[PatchProposal] = []
        if branch_known:
            for issue in issues:
                if any(issue.file_path.startswith(p) for p in _PATCH_DENY_PREFIXES):
                    continue
                try:
                    source = (self._root / issue.file_path).read_text()
                except OSError:
                    continue
                patch = generate_patch(
                    issue,
                    source,
                    max_lines=self._config.max_patch_lines,
                    project_root=self._root,
                )
                if patch is not None:
                    patches.append(patch)

        elapsed_ms = (time.monotonic_ns() // 1_000_000) - start_ms

        return DebugReport(
            issues=issues,
            patches=patches,
            analyzed_files=analyzed,
            skipped_files=skipped,
            analysis_time_ms=elapsed_ms,
        )

    def _validate_branch(self) -> tuple[bool, bool]:
        """Check current git branch. Returns (branch_known, is_safe).

        - (True, True): branch known and not main/master
        - (True, False): on main/master
        - (False, True): git unavailable — fail-open for analysis
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=self._root,
            )
            if result.returncode != 0:
                return False, True
            branch = result.stdout.strip()
            if branch in ("main", "master"):
                return True, False
            return True, True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False, True
