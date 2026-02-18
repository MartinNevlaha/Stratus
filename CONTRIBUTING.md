# Contributing to stratus

Licensed under Apache 2.0. Contributions welcome.

## Development Setup

```bash
git clone https://github.com/your-fork/stratus.git
cd stratus
uv sync --dev
```

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

## Running Tests

```bash
uv run pytest -q                                          # all tests
uv run pytest --cov=stratus --cov-fail-under=80    # with coverage
uv run pytest -m "not integration" -q                    # unit tests only
```

## Linting and Type Checking

```bash
uv run ruff check src/ tests/    # lint
uv run basedpyright src/         # type check (informational, not blocking)
```

## Code Style

ruff handles formatting and import sorting. Follow the patterns in existing modules. Do not introduce new runtime dependencies without discussion — the core framework uses stdlib where possible.

## TDD Requirement

Write the test before the implementation.

1. Write a failing test that describes the behavior.
2. Run it and confirm it fails (not due to syntax errors).
3. Write the minimal code to make it pass.
4. Run all tests and confirm they pass.
5. Refactor if needed — tests must stay green.

Test naming: `test_<function>_<scenario>_<expected>`.

## File Size Limit

Production files: 300 lines target, 500 lines hard limit — stop and refactor. Test files are exempt.

## PR Process

1. Fork the repo and create a branch from `main`.
2. Write tests for any new behavior.
3. Ensure `uv run pytest -q` passes and coverage stays above 80%.
4. Run `uv run ruff check src/ tests/` with no errors.
5. Open a pull request against `main` with a clear description of what and why.

One concern per PR. Keep diffs reviewable.

## Releasing

1. Bump the version in `pyproject.toml`.
2. Commit: `git commit -am "Bump version to X.Y.Z"`
3. Create a signed tag: `git tag -s vX.Y.Z -m "vX.Y.Z"`
4. Push: `git push origin main --tags`
5. CI verifies the tag matches `pyproject.toml`, runs tests + lint, builds, and publishes to PyPI.
6. A GitHub Release is created automatically with the dist artifacts.
