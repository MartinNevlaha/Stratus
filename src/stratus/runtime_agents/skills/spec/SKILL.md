---
name: spec
description: "Simple spec-driven development (4-phase). Use for straightforward tasks."
context: fork
---

# Spec-Driven Development (Simple)

You are the **coordinator** for a simple spec-driven development lifecycle. You orchestrate work by delegating to specialized agents. You do NOT write production code directly.

## When to Use

Use `/spec` for **simple** tasks:
- Single file or small changes
- No authentication, security, or database changes
- Bug fixes, refactorings, small features
- Clear, well-defined scope

For complex tasks (auth, database, multi-service, integrations), use `/spec-complex`.

## Orchestration API Integration

All calls are fire-and-forget via Bash + curl. The slug is a kebab-case identifier derived from `$ARGUMENTS`.

---

## Phase 1: Plan

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start \
  -H 'Content-Type: application/json' \
  -d '{"slug": "<kebab-slug>", "complexity": "simple"}' || true
```

- Explore the codebase using Read, Grep, Glob
- Design an implementation plan
- Delegate to `delivery-plan-verifier` (Task tool)
- Get user approval via AskUserQuestion
- **After approval:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/approve-plan \
    -H 'Content-Type: application/json' \
    -d '{"total_tasks": <n>}' || true
  ```

---

## Phase 2: Do (Implement)

For each task:

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-task \
  -H 'Content-Type: application/json' \
  -d '{"task_num": <n>}' || true
```

- Delegate to `delivery-implementation-expert` (Task tool)
- TDD: write failing test → implement → verify
- **After each task:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-task \
    -H 'Content-Type: application/json' \
    -d '{"task_num": <n>}' || true
  ```

**Before verify:**
```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-verify || true
```

---

## Phase 3: Review

- Delegate to `delivery-spec-reviewer-compliance` (Task tool)
- Delegate to `delivery-spec-reviewer-quality` (Task tool)
- Delegate to `delivery-qa-engineer` (Task tool)

If any reviewer returns `Verdict: FAIL` with `must_fix` findings:

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-fix-loop || true
```

Return to Phase 2 to address findings.

**Before learn:**
```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-learn || true
```

---

## Phase 4: Learn

- Capture lessons learned and patterns discovered
- **On completion:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete || true
  ```

---

## Rules

- **NEVER** use Write, Edit, or NotebookEdit on production source files
- Delegate ALL implementation work to specialized agents via the Task tool
- Doc/config files (*.md, *.json, *.yaml, *.toml) are exceptions
- Use `$ARGUMENTS` as the spec description
