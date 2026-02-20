---
name: sync-stratus
description: "Post-install reconciliation audit. Scans agents, skills, rules, and commands for conflicts with Stratus delegation model. Use --apply to execute the consolidation plan."
context: fork
---

# /sync-stratus — Post-Install Reconciliation

You are the **reconciliation coordinator**. Your job is to audit the current project environment after Stratus installation and produce a structured conflict report with a safe integration plan.

Check `$ARGUMENTS` for flags:
- **No flags** — audit and report only. Do NOT modify any files.
- **`--apply`** — audit, report, then execute the consolidation plan after user approval.
- **`--dry-run`** — audit, report, and show what `--apply` would change — but do NOT modify files.

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

Also check `agent-registry.json` (in `plugin/` or `src/stratus/registry/`) if present. Note each agent's `optional` field and `orchestration_modes`.

Detect:
- **Naming conflicts** — two agents with the same `name`
- **Responsibility overlap** — two agents claiming the same domain (implementation, QA, architecture, etc.)
- **Phase mismatch** — a `verify`/`governance`/`review`-phase agent that has Write/Edit tools. **Exception:** QA agents in `qa` or `implementation` phases legitimately need Write/Edit to create test files — do NOT flag these.
- **Missing tool restrictions** — implementation agents without tool allowlists
- **Missing optional agents** — agents marked `optional: true` in the registry that are absent from `.claude/agents/` are **expected** and should NOT be flagged. Only flag missing agents that are `optional: false`.

### B) Skills

Enumerate every `SKILL.md` in `.claude/skills/` and `plugin/skills/`.

For each skill check:
- Does frontmatter have `context: fork`? (required for coordinator skills)
- Does frontmatter specify `agent:`? (model-invoked delegation — check the agent exists)
- Does the skill body instruct direct implementation (bypasses Task tool)?
- Does the skill encourage the main instance to write code?

Detect **bypass patterns**: any skill that delegates implementation to `delivery-implementation-expert` or similar via `agent:` field is fine; any skill that tells the coordinator to write code directly is a conflict.

**Agent resolution:** When a skill references an agent via `agent:` field, resolve it across ALL agent sources: `.claude/agents/`, `plugin/agents/`, and the agent registry. Stratus delivery agents (`delivery-qa-engineer`, `delivery-spec-reviewer-quality`, `delivery-implementation-expert`, etc.) are provided by the framework and may only exist in `plugin/agents/` or the registry — they do not need a `.md` file in the project's `.claude/agents/` to be valid.

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
- Which phases are active?

Read the project name from `.ai-framework.json` field `project.name` (fallback: directory name). Use this in the Environment Summary.

**Config completeness:** A project needs `version`, `project`, `retrieval`, `learning`, and `agent_teams` in `.ai-framework.json`. Missing keys should be flagged as incomplete.

Read `.claude/settings.json` — are hooks registered?

---

## Step 2: Conflict Classification

For every issue found, classify with:
- **CRITICAL** — breaks delegation enforcement (coordinator can implement, bypass of Task tool, conflicting rules that override delegation)
- **MAJOR** — inconsistent routing, unclear ownership, ambiguous mode switching
- **MINOR** — cosmetic, naming, stub content, doc-only gaps

**Severity downgrade rule:** If the `delegation_guard` PreToolUse hook is registered and active (confirmed in Step 1E), then global rules or CLAUDE.md instructions that conflict with delegation but are **mechanically blocked by the hook** should be classified as **MINOR** (confusing but not dangerous), not MAJOR or CRITICAL. The hook provides hard enforcement regardless of what the rules say.

For each issue include: file path, exact description, why it matters.

---

## Step 3: Consolidation Strategy

Propose a safe integration plan. In report-only mode (no `--apply`), describe what should change. In `--apply` mode, these proposals become the execution plan for Step 6.

### Agent Layer
- Rename conflicting agents (proposal)
- Merge or split responsibilities
- Ensure single registry authority (`src/stratus/registry/agent-registry.json` is the source of truth)
- All agents use `orchestration_modes: ["default"]` — no mode-specific agents

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

### 6. Apply Summary
[if --apply: what will be applied; if --dry-run: what would be applied; if neither: omit]
```

If `$ARGUMENTS` does NOT contain `--apply`, stop here. The report is the final deliverable.

---

## Step 6: Apply (requires `--apply` flag)

**Skip this step entirely unless `$ARGUMENTS` contains `--apply`.**

This step takes the proposals from Steps 3-4 and executes them. The apply phase only modifies documentation and configuration files (`.md`, `.json`, `.yaml`, `.toml`) — never production source code.

### 6.1 — Pre-Apply Confirmation

Before modifying anything, present a numbered summary of all proposed changes:

```
## Apply Plan

The following changes will be made (CRITICAL first, then MAJOR, then MINOR):

1. [CRITICAL] Fix: <description> → <file path>
2. [CRITICAL] Fix: <description> → <file path>
3. [MAJOR] Fix: <description> → <file path>
...

Files that will be modified: [list]
Files that will be created: [list]
Items requiring manual review (not auto-applied): [list]

To revert all changes: git checkout -- .
```

Use **AskUserQuestion** to get explicit approval. Do NOT proceed without a "yes" / approval response.

### 6.2 — Apply Actions

Execute fixes in severity order (CRITICAL → MAJOR → MINOR). For each action, use the appropriate tool:

#### Auto-Applicable Fixes

| Issue Type | Fix Action | Tool |
|------------|-----------|------|
| **Reviewer agent in verify/governance phase has Write/Edit tools** | Remove Write/Edit/NotebookEdit from `tools:` frontmatter | Edit on `.md` |
| **Skill missing `context: fork`** | Add `context: fork` to frontmatter | Edit on `SKILL.md` |
| **Skill instructs coordinator to write code** | Add delegation warning comment at top of skill body | Edit on `SKILL.md` |
| **Rule stub (under 10 words)** | Append `<!-- STUB: needs content -->` marker | Edit on `.md` |
| **Missing `.ai-framework.json`** | Run `stratus init --skip-hooks --skip-mcp` | Bash |
| **Missing hooks in settings.json** | Run `stratus init --skip-mcp` | Bash |
| **Missing MCP server config** | Run `stratus init --skip-hooks` | Bash |
| **CLAUDE.md missing delegation clause** | Append governance precedence note at end of file | Edit on `.md` |

#### Manual-Review-Only (Never Auto-Applied)

These are reported but NOT automatically fixed — they require human judgment:

| Issue Type | Why Manual |
|------------|-----------|
| **Agent naming conflicts** | Renaming agents breaks Task tool references across skills and commands |
| **Agent responsibility overlap** | Merging/splitting agents is an architectural decision |
| **Command bypass patterns** | Rewriting commands requires understanding intent |
| **Rule conflicts with delegation** | User rules may be intentional overrides |
| **Global `~/.claude/` modifications** | Never modify global user config without explicit per-item approval |
| **Skill bypass via `agent:` field** | Removing delegation may break workflows |

### 6.3 — Apply Execution

For each auto-applicable fix:
1. Read the target file
2. Apply the specific Edit (smallest possible change)
3. Verify the file is still valid (frontmatter intact, no syntax errors)
4. Log the change: `[APPLIED] <severity> — <file path> — <description>`

For each manual-review item:
1. Log: `[SKIPPED — MANUAL REVIEW] <severity> — <file path> — <description>`

### 6.4 — Post-Apply Verification

After all fixes are applied:
1. Re-read every modified file to confirm changes took effect
2. Run `stratus doctor` (if available) to verify system health
3. Run a quick re-audit of the modified files to ensure no new conflicts were introduced

### 6.5 — Apply Report

Produce a final summary:

```
## Apply Results

### Applied
- [CRITICAL] <file path>: <what changed>
- [MAJOR] <file path>: <what changed>
...

### Skipped (Manual Review Required)
- [CRITICAL] <file path>: <why it needs manual review>
- [MAJOR] <file path>: <why it needs manual review>
...

### Verification
- Files modified: N
- Doctor check: PASS/FAIL
- New conflicts introduced: 0 / [list if any]

### Rollback
To revert all changes:
  git checkout -- .
```

---

## Rules

- **Without `--apply`**: Do NOT modify any files — this is plan-only
- **With `--apply`**: Only modify `.md`, `.json`, `.yaml`, `.toml` files — NEVER production source code (`.py`, `.ts`, `.js`, `.go`, etc.)
- **With `--dry-run`**: Show what `--apply` would change but do NOT modify files
- All changes require explicit user approval via AskUserQuestion before execution
- **Never delete user content** — only append, modify frontmatter metadata, or create new files
- **Never modify `~/.claude/` global files** without per-item user approval
- **Never auto-apply agent renames or responsibility changes** — these are manual-review-only
- Treat stub rules (body under 10 meaningful words) as MAJOR issues
- Missing `.claude/settings.json` or `.ai-framework.json` = CRITICAL (hooks and config not active)
- Apply is idempotent — re-running `--apply` on an already-fixed project produces no new changes
- Each fix is independent — a failure in one fix does not block others
