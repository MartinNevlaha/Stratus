---
name: sqlite-async-threading
description: |
  Fix for "SQLite objects created in a thread can only be used in that same
  thread" (sqlite3.ProgrammingError). Use when: (1) a Starlette/FastAPI/ASGI
  route uses asyncio.to_thread() to call a method on a class that holds a
  sqlite3.Connection, (2) the connection was created during app startup
  (lifespan or __init__), (3) the error appears only at runtime (request time),
  not at startup.
author: Claude Code
version: 1.0.0
---

# SQLite Threading in Async Python Servers

## Problem

`sqlite3.ProgrammingError: SQLite objects created in a thread can only be
used in that same thread. The object was created in thread id X and this
is thread id Y.`

## Context / Trigger Conditions

- ASGI server (Starlette, FastAPI) creates a `GovernanceStore`, `Database`,
  or similar class during app startup (lifespan, `__init__`, or `app.state`
  assignment).
- A route handler calls `await asyncio.to_thread(obj.method)` which runs the
  method in a `ThreadPoolExecutor` worker thread.
- The `sqlite3.Connection` inside the class was created in the main thread →
  SQLite's default `check_same_thread=True` rejects cross-thread access.

## Solution

Pass `check_same_thread=False` to `sqlite3.connect()`:

```python
# Before (crashes when used across threads)
self._conn = sqlite3.connect(path)

# After
self._conn = sqlite3.connect(path, check_same_thread=False)
```

**Is it safe?** Yes, provided:
- Writes are serialized (a single connection in WAL mode serializes writes
  automatically at the SQLite level).
- The connection is not shared between *processes*, only threads within one
  process.

SQLite WAL mode (set via `PRAGMA journal_mode=WAL`) makes concurrent reads
from multiple threads safe without extra locking.

## Diagnostic Pattern

Before changing anything, grep the codebase for existing database classes
that already work in the same server context:

```bash
grep -r "sqlite3.connect" src/
```

Any class that works correctly will show `check_same_thread=False`. Classes
missing it are the culprits.

## Verification

Run the route that was producing the 500:

```bash
curl http://localhost:PORT/api/retrieval/status
```

It should return 200 with JSON instead of a 500 traceback.

Run the test suite for the affected module:

```bash
uv run pytest tests/test_governance_store.py tests/test_retrieval_routes.py -q
```

## Example

**Error traceback (abbreviated):**

```
File ".../routes_retrieval.py", line 40, in retrieval_status
    data = await asyncio.to_thread(retriever.status)
File ".../governance_store.py", line 294, in stats
    total_files = self._conn.execute(...)
sqlite3.ProgrammingError: SQLite objects created in a thread can only be
used in that same thread. The object was created in thread id 127955371225216
and this is thread id 127955195918016.
```

**Fix applied to `governance_store.py`:**

```python
class GovernanceStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)  # ← added
        self._conn.row_factory = sqlite3.Row
        _run_migrations(self._conn)
```
