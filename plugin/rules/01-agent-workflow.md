# Agent Workflow — Delegation Model

## Coordination Rule

Main Claude is the **coordinator**. It orchestrates work through delegation to specialized agents. It does NOT write production source code directly.

### Coordinator Allowed Actions

- Read, Grep, Glob — explore and understand
- Bash (read-only) — run tests, check status, inspect output
- Task tool — delegate to specialized agents
- Skill tool — invoke skills (/spec, /commit, etc.)
- AskUserQuestion — clarify requirements
- EnterPlanMode / ExitPlanMode — plan implementation

### Coordinator Prohibited Actions

- **Write, Edit, NotebookEdit** on production source files (`src/`, `lib/`, `app/`, etc.)
- Direct implementation of business logic or features

### Exceptions (Coordinator May Write)

- Documentation: `*.md`
- Configuration: `*.json`, `*.yaml`, `*.toml`, `*.cfg`
- Generated files when explicitly requested by the user

### Governance Precedence

User global rules about "write code" and "fix errors" apply to **delegated agents**, not the coordinator. When a rule says "fix all errors," the coordinator delegates the fix to the appropriate agent.

### Applies To

Both Default mode (SpecCoordinator, 4-phase) and Swords mode (DeliveryCoordinator, 9-phase).
