---
name: code-review
description: Perform structured code review. Use when reviewing PRs, auditing code changes, or checking implementation quality before merging.
context: fork
agent: spec-reviewer-quality
---

# Code Review

Systematic review focused on correctness, maintainability, and project standards.

## Review Dimensions

### 1. Correctness
- Does it do what it claims?
- Edge cases: empty input, None, zero, max values
- Error handling: specific exceptions, not bare `except`
- Race conditions in async/concurrent code

### 2. Project Standards
- File size: production files < 300 lines (500 hard limit)
- Type hints on all public functions
- No unused imports
- Naming follows language conventions
- Run: `uv run ruff check src/ tests/` (Python) or `eslint` (TS)

### 3. Tests
- Every new function has a test
- Tests mock external dependencies
- Tests verify behavior, not implementation
- Coverage does not drop

### 4. Security
- No hardcoded secrets or credentials
- SQL parameters, not string interpolation
- Path operations validated against traversal
- User input sanitized at entry points

### 5. Maintainability
- No duplicate logic (DRY)
- Functions do one thing
- No deeply nested conditionals (max 3 levels)
- Comments explain WHY, not WHAT

## Output Format

```
## Code Review

**Verdict: PASS** | **Verdict: FAIL**

### Issues
1. **[must_fix]** `file.py:42` — bare `except` catches everything, use specific exception
2. **[should_fix]** `file.py:88` — duplicate logic, extract to helper
3. **[suggestion]** `file.py:120` — consider early return to reduce nesting

### Checks
- [ ] Correctness: PASS/FAIL
- [ ] Tests: PASS/FAIL
- [ ] Standards: PASS/FAIL
- [ ] Security: PASS/FAIL
- [ ] Maintainability: PASS/FAIL
```

`must_fix` → FAIL verdict. `should_fix` → warning. `suggestion` → optional.
