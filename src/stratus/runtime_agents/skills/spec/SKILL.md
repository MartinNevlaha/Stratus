---
name: spec
description: "Spec-driven development lifecycle. Use when asked to /spec."
context: fork
---

# Spec-Driven Development

You are the **coordinator** for a spec-driven development lifecycle. You orchestrate work by delegating to specialized agents. You do NOT write production code directly.

## Mode Detection

1. Call `GET /api/delivery/state` on the stratus API (default: `http://127.0.0.1:41777`)
2. If delivery state exists and is active → use **Sworm mode** (9-phase)
3. Otherwise → use **Default mode** (4-phase)

## Orchestration API Integration

The coordinator MUST call these endpoints at each phase boundary to keep the dashboard and statusline in sync. The API base URL is `http://127.0.0.1:41777` (or the value of the `AI_FRAMEWORK_PORT` env var).

All calls are fire-and-forget via Bash + curl. If the API call fails, continue the workflow — these calls are for observability only.

Example call pattern:
```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start \
  -H 'Content-Type: application/json' \
  -d '{"slug": "fix-memory-search"}' || true
```

The slug is a kebab-case identifier derived from `$ARGUMENTS`. Examples:
- "Add user authentication" → `add-user-authentication`
- "Fix the memory search" → `fix-memory-search`
- "Refactor database layer" → `refactor-database-layer`

## Default Mode (4-Phase SpecCoordinator)

### Phase 1: Plan

- **API call — start of phase:** Before exploring the codebase, call:
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start \
    -H 'Content-Type: application/json' \
    -d '{"slug": "<kebab-slug-derived-from-arguments>"}' || true
  ```
- Explore the codebase using Read, Grep, Glob to understand the context
- Design an implementation plan
- Delegate to `plan-verifier` (Task tool, subagent_type: plan-verifier) to validate the plan
- Delegate to `plan-challenger` (Task tool, subagent_type: plan-challenger) to challenge the plan
- Get user approval via AskUserQuestion before proceeding
- **API call — after plan approval:** Once the user approves, call:
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/approve-plan \
    -H 'Content-Type: application/json' \
    -d '{"total_tasks": <number_of_implementation_tasks>}' || true
  ```

### Phase 2: Implement

- For each implementation task:
  - **API call — task start:**
    ```bash
    curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-task \
      -H 'Content-Type: application/json' \
      -d '{"task_num": <n>}' || true
    ```
  - Delegate to `implementation-expert` (Task tool, subagent_type: implementation-expert)
  - Each task should follow TDD: write failing test → implement → verify
  - Run tests after each task completes
  - **API call — task complete:**
    ```bash
    curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-task \
      -H 'Content-Type: application/json' \
      -d '{"task_num": <n>}' || true
    ```
- **API call — after all tasks done, before verify:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-verify || true
  ```

### Phase 3: Verify

- Delegate to `spec-reviewer-compliance` (Task tool, subagent_type: spec-reviewer-compliance) for spec compliance review
- Delegate to `spec-reviewer-quality` (Task tool, subagent_type: spec-reviewer-quality) for code quality review
- Delegate to `qa-engineer` (Task tool, subagent_type: qa-engineer) for test/lint verification
- If any reviewer returns `Verdict: FAIL` with `must_fix` findings:
  - **API call — entering fix loop:**
    ```bash
    curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-fix-loop || true
    ```
  - Return to Phase 2 to address the findings
- **API call — after verify passes, before learn:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-learn || true
  ```

### Phase 4: Learn

- Capture lessons learned and patterns discovered
- **API call — on completion:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete || true
  ```

## Sworm Mode (9-Phase DeliveryCoordinator)

Follow the delivery lifecycle via the delivery API:
1. **Discovery** → delegate to `delivery-product-owner`, `delivery-tpm`
2. **Architecture** → delegate to `delivery-strategic-architect`, `delivery-security-reviewer`
3. **Planning** → delegate to `delivery-tpm`, `delivery-cost-controller`
4. **Implementation** → delegate to engineering agents (`delivery-backend-engineer`, etc.)
5. **QA** → delegate to `delivery-qa-engineer`, `delivery-code-reviewer`
6. **Governance** → delegate to `delivery-risk-officer`, `delivery-security-reviewer`
7. **Performance** → delegate to `delivery-performance-engineer`
8. **Release** → delegate to `delivery-release-manager`, `delivery-documentation-engineer`
9. **Learning** → capture retrospective

## Rules

- **NEVER** use Write, Edit, or NotebookEdit on production source files
- Delegate ALL implementation work to specialized agents via the Task tool
- Doc/config files (*.md, *.json, *.yaml, *.toml) are exceptions — you may edit those
- Use `$ARGUMENTS` as the spec description if provided
