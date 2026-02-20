---
name: spec-complex
description: "Complex spec-driven development (8-phase). Use for auth, database, integrations, multi-service tasks."
context: fork
---

# Spec-Driven Development (Complex)

You are the **coordinator** for a complex spec-driven development lifecycle. You orchestrate work by delegating to specialized agents. You do NOT write production code directly.

## When to Use

Use `/spec-complex` for **complex** tasks:
- Authentication, authorization, security changes
- Database migrations, schema changes
- API design, new endpoints with business logic
- Third-party integrations, webhooks
- Infrastructure, CI/CD changes
- Multi-file or multi-service changes
- Unclear or evolving requirements

For simple tasks (bug fixes, small refactorings), use `/spec`.

## Phase Context

Use the **`delivery_dispatch`** MCP tool as an alternative to curl API calls:

```python
delivery_dispatch()
# Returns: {"phase": "planning", "lead_agent": "delivery-tpm", "agents": [...], "objectives": [...]}
```

This provides the current phase briefing without making HTTP calls directly.

## Orchestration API Integration

All calls are fire-and-forget via Bash + curl. The slug is a kebab-case identifier derived from `$ARGUMENTS`.

---

## Phase 1: Discovery

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

---

## Phase 2: Design

- Delegate to `delivery-strategic-architect` (Task tool) — architecture decisions
- Delegate to `delivery-system-architect` (Task tool) — component design
- Produce ADRs if significant decisions made
- **Complete design:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-design || true
  ```

---

## Phase 3: Governance

**Check if governance is needed:**
- Security changes (auth, encryption, permissions) → **REQUIRED**
- Database changes (migrations, schema) → **REQUIRED**
- No security/data impact → **SKIP**

**Skip governance:**
```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/skip-governance \
  -H 'Content-Type: application/json' \
  -d '{"reason": "No security/data impact"}' || true
```

**Or complete governance:**
- Delegate to `delivery-risk-officer` (Task tool) — risk assessment
- Delegate to `delivery-security-reviewer` (Task tool) — security audit
```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/complete-governance || true
```

---

## Phase 4: Plan

- Delegate to `delivery-tpm` (Task tool) — task breakdown
- Delegate to `delivery-plan-verifier` (Task tool) — validate plan
- Delegate to `delivery-plan-challenger` (Task tool) — challenge assumptions
- **Start accept phase:**
  ```bash
  curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-accept \
    -H 'Content-Type: application/json' \
    -d '{"total_tasks": <n>}' || true
  ```

---

## Phase 5: Accept/Reject

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
  Return to Phase 4 to revise plan.

---

## Phase 6: Implement

For each task:

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-task \
  -H 'Content-Type: application/json' \
  -d '{"task_num": <n>}' || true
```

Delegate to appropriate engineering agent:
| Task Type | Agent |
|-----------|-------|
| API, backend, services | `delivery-backend-engineer` |
| UI, components, pages | `delivery-frontend-engineer` |
| Migrations, schema | `delivery-database-engineer` |
| Infra, CI/CD | `delivery-devops-engineer` |

TDD: write failing test → implement → verify

**After each task:**
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

## Phase 7: Review

- Delegate to `delivery-spec-reviewer-compliance` (Task tool)
- Delegate to `delivery-spec-reviewer-quality` (Task tool)
- Delegate to `delivery-code-reviewer` (Task tool)
- Delegate to `delivery-qa-engineer` (Task tool)

If any reviewer returns `Verdict: FAIL` with `must_fix` findings:

```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-fix-loop || true
```

Return to Phase 6 to address findings.

**Before learn:**
```bash
curl -s -X POST http://127.0.0.1:41777/api/orchestration/start-learn || true
```

---

## Phase 8: Learn

- Capture lessons learned and patterns discovered
- Update rules/patterns if applicable
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
