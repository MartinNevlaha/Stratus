---
name: differential-review
description: Security-focused review of code diffs. Use when auditing changes for vulnerabilities, trust boundary violations, secret exposure, or injection risks before merging.
context: fork
agent: delivery-security-reviewer
---

# Security Differential Review

Analyze code changes for security issues. Every diff is a potential attack surface change.

## Process

### 1. Get the Diff

```bash
git diff main...HEAD          # changes vs main
git diff HEAD~1               # last commit
git diff --stat HEAD~1        # summary of files changed
```

### 2. Categorize Changes

| Category | What to look for |
|----------|------------------|
| Auth/authz | Permission checks added/removed, token handling |
| Input handling | New user-controlled data, validation changes |
| Secrets | API keys, credentials, env vars in code |
| Deps | New packages (supply chain), version pins removed |
| Crypto | Hash algorithms, random generation, key sizes |
| File I/O | Path construction, user-supplied filenames |
| SQL | Query construction, ORM raw() calls |
| Serialization | Pickle, eval(), exec(), `__reduce__` |

### 3. High-Risk Patterns

```python
# Command injection
subprocess.run(f"git log {user_input}", shell=True)

# Path traversal
open(f"/data/{user_filename}")

# SQL injection
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# Hardcoded secret
API_KEY = "sk-proj-abc123..."

# Insecure deserialization
pickle.loads(user_data)
```

### 4. Trust Boundary Check

- Where does untrusted data enter? (HTTP params, env vars, files, IPC)
- Is it validated/sanitized before use?
- Does the diff add new entry points without validation?
- Does the diff bypass existing validation?

### 5. Dependency Changes

```bash
git diff HEAD~1 -- requirements.txt pyproject.toml package.json
```

- New packages: check reputation, last published, maintainer
- Version pins removed: floating versions = supply chain risk
- `*` or `latest` versions: flag immediately

## Output Format

```
## Security Review

**Verdict: PASS** | **Verdict: FAIL**

### Findings
1. **[CRITICAL]** `api.py:42` — command injection via shell=True with user input
   - Attack: `; rm -rf /`
   - Fix: remove shell=True, pass args as list

2. **[HIGH]** `config.py:8` — hardcoded API key
   - Fix: move to environment variable

3. **[LOW]** `utils.py:55` — MD5 used for checksums (not security-critical)
   - Note: acceptable for non-security checksums

### Trust Boundary Analysis
- New entry points: <list>
- Validation gaps: <list>
- Dependency changes: <summary>
```
