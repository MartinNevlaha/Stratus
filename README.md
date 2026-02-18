# stratus

Open-source framework for Claude Code sessions.

Stratus adds persistent memory, retrieval, adaptive learning, and spec-driven orchestration through Claude Code integration points (hooks, MCP, HTTP API). It is not a separate agent runtime.

- Python: 3.12+
- License: Apache-2.0
- Package: `stratus`

## What You Get

- Persistent memory with SQLite + FTS5 (events, sessions, timeline, observations)
- Unified retrieval:
  - code search via Vexor (if installed)
  - governance/docs search via built-in SQLite index
- Claude Code hooks for context monitoring, lint checks, TDD nudges, lifecycle guards
- MCP stdio server that proxies tools to the local Stratus HTTP API
- Spec-driven orchestration with git worktree isolation and reviewer verdict loops
- Optional adaptive learning pipeline that proposes rules/ADRs/templates/skills

## Architecture (High Level)

- `bootstrap`: project detection, config generation, hook/MCP registration
- `memory`: durable event/session store
- `retrieval`: Vexor + governance retrieval with auto-routing
- `learning`: pattern detection, scoring, and proposal generation
- `orchestration`: spec state machine and worktree lifecycle
- `hooks`: Claude Code event handlers
- `mcp_server`: MCP tool surface for agents
- `server`: Starlette API + dashboard

## Installation

### Option A: pipx (recommended)

```bash
pipx install stratus
```

### Option B: installer script

```bash
curl -fsSL https://raw.githubusercontent.com/MartinNevlaha/stratus/main/scripts/install.sh | sh
```

### Option C: from source

```bash
git clone https://github.com/MartinNevlaha/stratus.git
cd stratus
uv sync --dev
```

## Quick Start

### 1. Initialize integration in your project

```bash
cd /path/to/your/git/repo
stratus init
```

This writes/updates:

- `project-graph.json`
- `.ai-framework.json`
- `.claude/settings.json` (hooks)
- `.mcp.json` (MCP registration)

### 2. Start API server

```bash
stratus serve
```

Default URL: `http://127.0.0.1:41777`

### 3. Health check

```bash
stratus doctor
```

### 4. Reconcile existing agents, skills and rules (recommended)

If your project already has agents, skills, rules, or slash-commands, run the reconciliation audit inside Claude Code:

```
/stratus:sync-stratus
```

This skill scans your entire environment — agents, skills, rules, commands, and `CLAUDE.md` at all levels (global, project, subdirectory) — and produces a conflict report against the Stratus delegation model. It is **plan-only** and does not modify any files.

You will receive:
- A classified conflict report (CRITICAL / MAJOR / MINOR)
- A consolidation strategy with explicit merge proposals
- Ordered migration steps from lowest to highest risk

Run this before your first `/stratus:spec` session to ensure clean orchestration.

### 5. Open dashboard (optional)

`http://127.0.0.1:41777/dashboard`

## `init` Modes

### Project scope (default)

Installs hooks/MCP in the current repository and runs service/retrieval setup.

```bash
stratus init
```

### Global scope

Installs hooks/MCP to `~/.claude/` for all projects.

```bash
stratus init --scope global
```

### Enable delivery agent set

```bash
stratus init --enable-delivery
```

### Useful flags

- `--dry-run`: show actions without writing files
- `--force`: overwrite existing `.ai-framework.json`
- `--skip-hooks`: do not register Claude hooks
- `--skip-mcp`: do not register MCP server
- `--skip-retrieval`: skip retrieval backend detection/setup
- `--skip-agents`: skip runtime agent installation

## CLI Reference

```bash
stratus analyze <file.jsonl> [--context-window N]
stratus init [--dry-run] [--force] [--scope local|global]
stratus doctor
stratus serve
stratus mcp-serve
stratus reindex [--full]
stratus retrieval-status
stratus statusline
stratus hook <module>

stratus worktree detect <slug> [--plan-path PATH] [--base-branch BRANCH]
stratus worktree create <slug> [--plan-path PATH] [--base-branch BRANCH]
stratus worktree diff <slug> [--plan-path PATH]
stratus worktree sync <slug> [--plan-path PATH]
stratus worktree cleanup <slug> [--plan-path PATH]
stratus worktree status <slug> [--plan-path PATH] [--base-branch BRANCH]

stratus learning analyze [--since COMMIT] [--scope SCOPE]
stratus learning proposals [--max-count N] [--min-confidence X]
stratus learning decide <proposal_id> <accept|reject|ignore|snooze>
stratus learning config
stratus learning status
```

## Claude Code Plugin

The `plugin/` directory contains a self-contained Claude Code plugin bundle.

It includes:

- plugin manifest
- namespaced slash commands (`/stratus:*`)
- hooks
- agents and skills
- `.mcp.json` for `stratus mcp-serve`

Run Claude Code with local plugin directory:

```bash
claude --plugin-dir ./plugin
```

Available plugin commands:

- `/stratus:init`
- `/stratus:doctor`
- `/stratus:status`
- `/stratus:analyze`
- `/stratus:reindex`
- `/stratus:proposals`
- `/stratus:decide`
- `/stratus:worktree`

## Configuration

Environment variables:

- `AI_FRAMEWORK_DATA_DIR` (default `~/.ai-framework/data`)
- `AI_FRAMEWORK_PORT` (default `41777`)
- `CLAUDE_CODE_TASK_LIST_ID` (default `default`)

Primary project config:

- `.ai-framework.json`

## Development

```bash
uv run pytest -q
uv run pytest --cov=stratus --cov-fail-under=80
uv run ruff check src/ tests/
uv run basedpyright src/
```

## Docker

```bash
docker build -t stratus .
docker run -p 41777:41777 -v ~/.ai-framework:/root/.ai-framework stratus
```

## Uninstall

```bash
./scripts/uninstall.sh
```

With project cleanup:

```bash
./scripts/uninstall.sh --project
```

## Repository Layout

- `src/stratus/`: framework source code
- `tests/`: test suite
- `plugin/`: Claude Code plugin assets
- `scripts/`: install/uninstall helpers
- `docs/`: design and delivery docs

## License

Apache License 2.0. See `LICENSE`.
