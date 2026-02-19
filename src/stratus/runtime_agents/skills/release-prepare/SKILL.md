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
4. Read the current version from the project's manifest (`pyproject.toml`, `package.json`, `Cargo.toml`, etc.) and compute the new version string.
5. Draft a changelog entry in Keep a Changelog format with sections: Added, Changed, Fixed, Removed, Security.
6. Verify that all tests pass by checking for a recent green CI run or by running the project's test suite (detect runner: `uv run pytest`, `poetry run pytest`, `pytest`, `npm test`, `cargo test`, etc.).
7. Confirm the version in the manifest matches the version source in the codebase (e.g. `__init__.py`, `version.py`, `mod.rs`, `index.ts`).
8. Produce the release notes text suitable for pasting into a GitHub Release.

Output format:
- Section "Version" — old → new with bump rationale
- Section "Changelog Entry" — formatted for CHANGELOG.md insertion
- Section "Release Notes" — user-facing summary for GitHub Release
- Section "Pre-release Checklist" — ordered steps to complete before tagging
