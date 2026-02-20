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
3. Otherwise → use **Default mode** (simple or complex based on assessment)

## Complexity Assessment (Default Mode Only)

Before starting, assess complexity by calling:

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/assess-complexity \
  -H 'Content-Type: application/json' \
  -d '{"spec": "<the-user-spec>", "affected_files": ["<file1>", "<file2>"]}' || true
```

Response: `{"complexity": "simple"|"complex", "skip_governance": true|false}`

| Complexity | Flow | When |
|------------|------|------|
| **Simple** | 4-phase | Single file, no auth/security/data, < 3 files affected |
| **Complex** | 8-phase | Multi-file, auth, database, API, integration, or infrastructure |

## Orchestration API Integration

The coordinator MUST call these endpoints at each phase boundary. All calls are fire-and-forget via Bash + curl. The slug is a kebab-case identifier derived from `$ARGUMENTS`.

---

## SIMPLE FLOW (4-Phase)

Use when: `complexity: "simple"`

### Phase 1: Plan

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start \
  -H 'Content-Type: application/json' \
  -d '{"slug": "<kebab-slug>", "complexity": "simple"}' || true
```

- Explore the codebase using Read, Grep, Glob
- Design an implementation plan
- Delegate to `delivery-plan-verifier` (Task tool, subagent_type: delivery-plan-verifier)
- Get user approval via AskUserQuestion
- **After approval:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/approve-plan \
    -H 'Content-Type: application/json' \
    -d '{"total_tasks": <n>}' || true
  ```

### Phase 2: Do (Implement)

- For each implementation task:
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
- **Before verify:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-verify || true
  ```

### Phase 3: Review

- Delegate to `delivery-spec-reviewer-compliance` (Task tool)
- Delegate to `delivery-spec-reviewer-quality` (Task tool)
- Delegate to `delivery-qa-engineer` (Task tool)
- If any reviewer returns `Verdict: FAIL` with `must_fix` findings:
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-fix-loop || true
  ```
  - Return to Phase 2 to address findings
- **Before learn:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-learn || true
  ```

### Phase 4: Learn

- Capture lessons learned and patterns discovered
- **On completion:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete || true
  ```

---

## COMPLEX FLOW (8-Phase)

Use when: `complexity: "complex"`

### Phase 1: Discovery

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start \
  -H 'Content-Type: application/json' \
  -d '{"slug": "<kebab-slug>", "complexity": "complex"}' || true
```

- Delegate to `delivery-product-owner` (Task tool) — gather requirements
- Delegate to `delivery-tpm` (Task tool) — identify stakeholders
- **Complete discovery:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-discovery || true
  ```

### Phase 2: Design

- Delegate to `delivery-strategic-architect` (Task tool) — architecture decisions
- Delegate to `delivery-system-architect` (Task tool) — component design
- Produce ADRs if significant decisions made
- **Complete design:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-design || true
  ```

### Phase 3: Governance

**Check `skip_governance` from complexity assessment:**

- If `skip_governance: true` → skip this phase:
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/skip-governance \
    -H 'Content-Type: application/json' \
    -d '{"reason": "No security/data impact"}' || true
  ```

- If `skip_governance: false`:
  - Delegate to `delivery-risk-officer` (Task tool) — risk assessment
  - Delegate to `delivery-security-reviewer` (Task tool) — security audit
  - **Complete governance:**
    ```bash
    curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-governance || true
    ```

### Phase 4: Plan

- Delegate to `delivery-tpm` (Task tool) — task breakdown
- Delegate to `delivery-plan-verifier` (Task tool) — validate plan
- Delegate to `delivery-plan-challenger` (Task tool) — challenge assumptions
- **Start accept phase:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-accept \
    -H 'Content-Type: application/json' \
    -d '{"total_tasks": <n>}' || true
  ```

### Phase 5: Accept/Reject

- Present plan summary to user via AskUserQuestion
- **If accepted:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/approve-accept || true
  ```
- **If rejected:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/reject-accept \
    -H 'Content-Type: application/json' \
    -d '{"reason": "<user-feedback>"}' || true
  ```
  - Return to Phase 4 to revise plan

### Phase 6: Implement

- For each implementation task:
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-task \
    -H 'Content-Type: application/json' \
    -d '{"task_num": <n>}' || true
  ```
- Delegate to appropriate engineering agent based on task type:
  - `delivery-backend-engineer` — API, backend, services
  - `delivery-frontend-engineer` — UI, components, pages
  - `delivery-database-engineer` — migrations, schema
  - `delivery-devops-engineer` — infra, CI/CD
- TDD: write failing test → implement → verify
- **After each task:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-task \
    -H 'Content-Type: application/json' \
    -d '{"task_num": <n>}' || true
  ```
- **Before verify:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-verify || true
  ```

### Phase 7: Review

- Delegate to `delivery-spec-reviewer-compliance` (Task tool)
- Delegate to `delivery-spec-reviewer-quality` (Task tool)
- Delegate to `delivery-code-reviewer` (Task tool)
- Delegate to `delivery-qa-engineer` (Task tool)
- If any reviewer returns `Verdict: FAIL` with `must_fix` findings:
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-fix-loop || true
  ```
  - Return to Phase 6 to address findings
- **Before learn:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-learn || true
  ```

### Phase 8: Learn

- Capture lessons learned and patterns discovered
- Update rules/patterns if applicable
- **On completion:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete || true
  ```

---

## Sworm Mode (9-Phase DeliveryCoordinator)

Follow the delivery lifecycle via the delivery API:
1. **Discovery** → `delivery-product-owner`, `delivery-tpm`
2. **Architecture** → `delivery-strategic-architect`, `delivery-security-reviewer`
3. **Planning** → `delivery-tpm`, `delivery-cost-controller`
4. **Implementation** → engineering agents
5. **QA** → `delivery-qa-engineer`, `delivery-code-reviewer`
6. **Governance** → `delivery-risk-officer`, `delivery-security-reviewer`
7. **Performance** → `delivery-performance-engineer`
8. **Release** → `delivery-release-manager`, `delivery-documentation-engineer`
9. **Learning** → retrospective

---

## Rules

- **NEVER** use Write, Edit, or NotebookEdit on production source files
- Delegate ALL implementation work to specialized agents via the Task tool
- Doc/config files (*.md, *.json, *.yaml, *.toml) are exceptions — you may edit those
- Use `$ARGUMENTS` as the spec description if provided
