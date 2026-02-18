---
name: security-review
description: "Audit code for security vulnerabilities and compliance issues"
agent: delivery-security-reviewer
context: fork
---

Run a security review for: "$ARGUMENTS"

1. Use `Grep` to scan all files in scope for hardcoded secrets, tokens, and credentials (patterns: `secret`, `password`, `api_key`, `token` in assignments).
2. Check all HTTP endpoints for authentication and authorization guards — verify no route is accessible without identity verification.
3. Audit input validation on every user-controlled parameter (query strings, request bodies, file paths).
4. Check for path traversal risks on any `open()` or `Path` operations that accept external input.
5. Review dependency list in `pyproject.toml` for known vulnerable packages using known CVE patterns.
6. Verify that SQL queries use parameterized statements — scan for string-formatted queries via `Grep`.
7. Check OWASP Top 10 categories applicable to this codebase: injection, broken auth, SSRF, insecure deserialization.
8. Produce a PASS or FAIL verdict with a severity-ranked list of findings.

Output format:
- Verdict: PASS or FAIL
- Section "Critical Findings" — must fix before release (severity: critical/high)
- Section "Moderate Findings" — should fix (severity: medium)
- Section "Informational" — low severity or hardening suggestions
- Each finding: file path, line number, description, recommended remediation
