---
name: performance-benchmark
description: "Run performance benchmarks and identify optimization opportunities"
agent: delivery-performance-engineer
context: fork
---

Run a performance analysis for: "$ARGUMENTS"

1. Identify hot paths in the codebase — entry points that handle the most requests or process the largest data volumes.
2. Use `Grep` to find N+1 query patterns: loops containing database calls or repeated identical queries.
3. Review all async/await usage for blocking calls on the event loop (e.g., `time.sleep`, synchronous file I/O inside async functions).
4. Inspect SQLite queries in `src/stratus/memory/database.py` and retrieval modules for missing indexes.
5. Check FTS5 query construction for unnecessary full-table scans.
6. Review any HTTP client usage for missing connection pooling or excessive round-trips.
7. Identify large in-memory data structures that could be streamed or paginated instead.
8. Produce a ranked list of optimization opportunities ordered by estimated impact.

Output format:
- Section "Hot Paths Identified" — list of entry points with estimated call frequency
- Section "Findings" — table with columns: Area, Issue, Estimated Impact (High/Medium/Low), Recommended Fix
- Section "Quick Wins" — fixes achievable in under 30 minutes
- Section "Structural Changes" — optimizations requiring design changes
