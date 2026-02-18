---
name: run-tests
description: Runs the project test suite. Use when the user asks to "test" or "verify" changes.
agent: qa-engineer
context: fork
---

Run the test suite for the project.

1.  Detect the project type from configuration files (pyproject.toml, package.json, go.mod, Cargo.toml).
2.  Run the appropriate test command:
    - **Python**: `pytest -v` (or `uv run pytest -v` if uv is used)
    - **Node.js**: `npm test` or `bun test`
    - **Go**: `go test ./...`
    - **Rust**: `cargo test`
3.  If specific files are provided in "$ARGUMENTS", run only those tests.
4.  If tests fail, analyze the failure and suggest a fix.
5.  If tests pass, run the project's linter to ensure code quality.
