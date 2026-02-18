---
name: release-prepare
description: "Prepare release artifacts including changelog and version bump"
agent: delivery-release-manager
context: fork
---

Prepare a release for: "$ARGUMENTS"

1. Run `git log --oneline $(git describe --tags --abbrev=0)..HEAD` to list commits since the last tag.
2. Categorize each commit as: feat (new feature), fix (bug fix), perf (performance), docs, chore, or breaking.
3. Determine the version bump using semver rules: breaking change → major, feat → minor, fix/perf → patch.
4. Read the current version from `pyproject.toml` and compute the new version string.
5. Draft a changelog entry in Keep a Changelog format with sections: Added, Changed, Fixed, Removed, Security.
6. Verify that all tests pass by checking for a recent green CI run or noting that `uv run pytest -q` must be run.
7. Confirm that `pyproject.toml` version matches the `__version__` source in `src/stratus/__init__.py`.
8. Produce the release notes text suitable for pasting into a GitHub Release.

Output format:
- Section "Version" — old → new with bump rationale
- Section "Changelog Entry" — formatted for CHANGELOG.md insertion
- Section "Release Notes" — user-facing summary for GitHub Release
- Section "Pre-release Checklist" — ordered steps to complete before tagging
