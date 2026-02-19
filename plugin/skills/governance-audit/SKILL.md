---
name: governance-audit
description: "Audit project for compliance, risk, and governance issues"
agent: delivery-risk-officer
context: fork
---

Run a governance audit for: "$ARGUMENTS"

1. Detect the project's test runner and coverage tool, then run with coverage to capture current test coverage and identify untested modules (e.g. `pytest --cov=src --cov-report=term-missing -q`, `npm test -- --coverage`, `cargo tarpaulin`).
2. Use `Glob` to list all source files and verify each has a corresponding test file in `tests/`.
3. Check `docs/` completeness: confirm architecture doc, ADRs, and API reference are present and recently updated.
4. Review `pyproject.toml` for pinned dependency versions and flag any unpinned or overly broad version specifiers.
5. Use `Grep` to identify TODOs, FIXMEs, and HACKs in production source files and count them by module.
6. Verify that all public API endpoints have docstrings or OpenAPI descriptions.
7. Assess operational readiness: health check endpoint, structured logging, graceful shutdown, and error handling coverage.
8. Produce a compliance report with a risk score per category (1-5, where 5 is highest risk).

Output format:
- Section "Coverage Report" — per-module coverage table with pass/fail (threshold: 80%)
- Section "Documentation Gaps" — missing or stale docs
- Section "Dependency Risks" — unpinned or vulnerable packages
- Section "Technical Debt" — TODO/FIXME count per module
- Section "Risk Summary" — table with columns: Category, Risk Score, Finding, Recommendation
- Overall Risk Rating: LOW / MEDIUM / HIGH
