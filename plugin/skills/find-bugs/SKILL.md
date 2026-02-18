---
name: find-bugs
description: Systematically identify bugs in code. Use when debugging failures, investigating unexpected behavior, or auditing code for defects before production.
context: fork
agent: delivery-debugger
---

# Bug Finding

Systematically identify root causes — never guess without evidence.

## Process

### 1. Reproduce First
- Get the exact error message, stack trace, or unexpected output
- Identify the minimal steps to reproduce
- Confirm reproduction before investigating

### 2. Read the Error Completely
- Stack traces point to the ACTUAL failure site (often not the root cause)
- Check line numbers, not just the exception type
- Note what data was present when it failed

### 3. Trace Data Flow
```
Entry point → transformation → storage/output
              ↑ where does it go wrong?
```
- Read the input
- Follow the path through the code
- Find where expected ≠ actual

### 4. Check Recent Changes
```bash
git log --oneline -10
git diff HEAD~1
```
If a previously working feature broke, the bug is almost always in the diff.

### 5. Form a Falsifiable Hypothesis
"The bug is X because Y. If I change Z, the output will be W."

Never make multiple changes at once — one variable at a time.

### 6. Identify Fix + Regression Test

The fix is not complete without:
- A test that FAILS before the fix
- The same test PASSES after the fix

## Common Bug Patterns

| Pattern | Signal | Check |
|---------|--------|-------|
| Off-by-one | Wrong count, first/last item | Loop bounds, slice indices |
| None/null dereference | AttributeError, NullPointerException | Guard conditions |
| Race condition | Intermittent failures | Shared state, async code |
| Wrong type | TypeError, unexpected coercion | Input validation, type hints |
| State mutation | Works alone, fails in sequence | Shared objects, list.append |
| Encoding | UnicodeDecodeError | open(..., encoding="utf-8") |

## Output Format

```
## Bug Report

**Root Cause**: <one sentence>

**Evidence**:
- File: `path/to/file.py:42`
- Data at failure: <value>
- Expected: <value>

**Fix**:
<minimal code change>

**Regression Test**:
<test that catches this bug>
```
