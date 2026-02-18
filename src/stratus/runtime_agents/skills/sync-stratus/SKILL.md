---
name: sync-stratus
description: "Post-install reconciliation audit. Scans agents, skills, rules, and commands for conflicts with Stratus delegation model. Plan-only — does not modify files."
context: fork
---

# /sync-stratus — Post-Install Reconciliation

You are the **reconciliation coordinator**. Your job is to audit the current project environment after Stratus installation and produce a structured conflict report with a safe integration plan.

**CRITICAL: Do NOT modify any files. This is analysis and planning only.**

Use `$ARGUMENTS` to scope the audit (e.g. `--apply` flag for future apply mode — currently a no-op).

---

## Step 1: Environment Audit

Scan the following locations using Read, Glob, and Grep:

### A) Agents

Enumerate every `.md` file in:
- `.claude/agents/`
- `plugin/agents/` (if present)
- Any other agent directories mentioned in `.ai-framework.json`

For each agent extract:
- `name` and `description` from frontmatter
- `tools` field — derive `can_write` (has Write/Edit/NotebookEdit)
- `model` field
- Any `phase` or `mode` hints in the body

Detect:
- **Naming conflicts** — two agents with the same `name`
- **Responsibility overlap** — two agents claiming the same domain (implementation, QA, architecture, etc.)
- **Phase mismatch** — reviewer/QA agent that has Write/Edit tools
- **Missing tool restrictions** — implementation agents without tool allowlists

### B) Skills

Enumerate every `SKILL.md` in `.claude/skills/` and `plugin/skills/`.

For each skill check:
- Does frontmatter have `context: fork`? (required for coordinator skills)
- Does frontmatter specify `agent:`? (model-invoked delegation — check the agent exists)
- Does the skill body instruct direct implementation (bypasses Task tool)?
- Does the skill encourage the main instance to write code?

Detect **bypass patterns**: any skill that delegates implementation to `framework-expert` or similar via `agent:` field is fine; any skill that tells the coordinator to write code directly is a conflict.

### C) Rules

Enumerate every `.md` file in:
- `.claude/rules/`
- `plugin/rules/`
- `~/.claude/rules/` or `~/.claude/CLAUDE.md` (global rules — read if accessible)

For each rule check:
- Does it instruct the main instance to write/fix/implement code directly?
- Does it contradict Stratus delegation guardrails (`01-agent-workflow.md`)?
- Is it a stub or placeholder (empty body, trivial content)?

Note precedence: global rules → project rules → framework rules. Flag any global rule that overrides delegation.

### F) CLAUDE.md at All Levels

CLAUDE.md files are instruction layers that Claude Code reads at startup. Scan all levels:

- `~/.claude/CLAUDE.md` — **global user level** (highest precedence, applies to all projects)
- `<project>/CLAUDE.md` — **project level** (checked into repo, applies to all contributors)
- Any subdirectory `CLAUDE.md` files — **scoped level** (applies only in that directory subtree)

For each CLAUDE.md found:
- Read the full content
- Check for instructions that tell the main instance to write code directly (`Write`, `Edit`, "implement this", "fix this")
- Check for instructions that conflict with `01-agent-workflow.md` delegation rules
- Check for instructions that override enforcement hooks (e.g. "ignore hooks", "always write directly")
- Note whether it imports or references any rules/skills that could bypass delegation
- Check for stub or outdated content

**Precedence risk:** A global `~/.claude/CLAUDE.md` that instructs "always fix errors immediately" or "write code as requested" overrides the project delegation rule for the coordinator. This is a CRITICAL conflict if it enables direct implementation.

Add CLAUDE.md findings to the conflict report alongside rules findings.

### D) Slash-Commands

Enumerate every file in `.claude/commands/` and `plugin/commands/`.

For each command:
- Does it delegate via Task tool or skill fork?
- Does it execute implementation logic directly (instructs main instance to write code)?
- Does it conflict with Stratus entrypoints (`/spec`, `/sync-stratus`)?

### E) Orchestration Config

Read `.ai-framework.json` if present. Determine:
- Is Stratus initialized (`stratus init` was run)?
- Is Swords/delivery mode enabled, disabled, or opt-in?
- Which phases are active?

Read `.claude/settings.json` — are hooks registered?

---

## Step 2: Conflict Classification

For every issue found, classify with:
- **CRITICAL** — breaks delegation enforcement (coordinator can implement, bypass of Task tool, conflicting rules that override delegation)
- **MAJOR** — inconsistent routing, unclear ownership, ambiguous mode switching
- **MINOR** — cosmetic, naming, stub content, doc-only gaps

For each issue include: file path, exact description, why it matters.

---

## Step 3: Consolidation Strategy (Plan Only)

Propose a safe integration plan. Do NOT execute — describe what should change.

### Agent Layer
- Rename conflicting agents (proposal)
- Merge or split responsibilities
- Ensure single registry authority (`src/stratus/registry/agent-registry.json` is the source of truth)
- Verify compatibility with Default mode and Swords mode

### Skill Layer
- Identify skills that need refactoring to use `context: fork`
- Identify skills that bypass delegation (propose moving implementation to Task-spawned agent)
- Ensure all coordinator skills delegate rather than implement

### Rule Layer
- Propose precedence model: Stratus delegation rules override "write code" rules **for the coordinator**; coding rules apply to write-capable subagents only
- Propose merging without deleting user content

### Command Layer
- Identify commands that must be rewritten to delegate via Task/skill
- Ensure `/spec` is the primary orchestration entrypoint
- `/sync-stratus` should be the only reconciliation entrypoint

---

## Step 4: Orchestration Harmonization

Verify after proposed changes:
- Deterministic delegation — no ambiguous routing
- Single orchestration authority — no two skills claim to orchestrate the same workflow
- No circular delegation loops
- No skill or command can override enforcement
- All implementation flows through Task tool invocation

If gaps exist, propose:
- Routing matrix (task type → agent)
- Rule priority model
- Guard strategy for slash-commands

---

## Step 5: Output

Produce a structured report with these sections:

```
## /sync-stratus Report

### Environment Summary
[project name, stratus version, mode, hook registration status]

### 1. Conflict Report

#### CRITICAL
[each issue with file path, description, impact]

#### MAJOR
[each issue]

#### MINOR
[each issue]

### 2. Risk Assessment
[what breaks today vs what breaks later]

### 3. Consolidation Strategy
[agent / skill / rule / command layer proposals]

### 4. Orchestration Harmonization
[routing matrix if needed, guard strategy]

### 5. Recommended Migration Steps
[ordered list, lowest risk first]

### Bonus: /sync-stratus --apply (future)
[what apply mode would do — currently disabled]
```

---

## Rules

- **Do NOT modify any files** — this is plan-only
- All changes go into the report as proposals
- If `$ARGUMENTS` contains `--apply`: acknowledge it but note the flag is not yet implemented
- Treat stub rules (body under 10 meaningful words) as MAJOR issues
- Missing `.claude/settings.json` or `.ai-framework.json` = CRITICAL (hooks and config not active)
