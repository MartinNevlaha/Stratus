<p align="center">
  <img src="./stratus.png" alt="Stratus Logo" width="400">
</p>

<h1 align="center">Stratus</h1>

<p align="center">
  <strong>Open-source framework for Claude Code sessions</strong>
</p>

<p align="center">
  Persistent memory • Unified retrieval • Adaptive learning • Spec-driven orchestration
</p>

<p align="center">
  <a href="#installation">Install</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#cli-reference">CLI</a> •
  <a href="#uninstall">Uninstall</a>
</p>

---

## What is Stratus?

**Stratus** is an open-source framework that extends Claude Code with:

- **Persistent memory** — Claude remembers across sessions via SQLite + FTS5
- **Intelligent retrieval** — code via Vexor, governance docs via built-in index
- **Adaptive learning** — automatically proposes rules, ADRs, templates, and skills
- **Spec-driven orchestration** — isolated worktrees, reviewer verdict loops, agent coordination

Stratus is **not** a separate agent runtime. It integrates directly into Claude Code via:
- **Hooks** — event handlers for lifecycle events
- **MCP Server** — tools available to agents
- **HTTP API** — local server with dashboard

---

## Why Stratus?

| Problem | Solution |
|---------|----------|
| Claude forgets between sessions | SQLite + FTS5 persistent memory |
| Chaotic project rules | Automatic generation of rules/ADRs/templates |
| Manual context switching | Spec-driven worktree isolation |
| Inconsistent code quality | TDD enforcer, lint hooks, reviewer verdicts |
| Lost decisions and patterns | Learning pipeline proposes governance artifacts |

---

## Benefits

- **Zero vendor lock-in** — everything runs locally, SQLite databases, no cloud services
- **Non-intrusive** — hooks are best-effort, never block your workflow
- **Modular** — use only what you need (memory, retrieval, learning, orchestration)
- **CLI-first** — everything controllable from the terminal
- **Claude Code native** — integrates directly into the ecosystem (hooks, MCP, statusline)

---

## What's Included

```
stratus/
├── bootstrap/      # Project detection, config generation
├── memory/         # Durable event/session store (SQLite + FTS5)
├── retrieval/      # Vexor + governance search
├── learning/       # Pattern detection, scoring, proposals
├── orchestration/  # Spec state machine, worktree lifecycle
├── hooks/          # Claude Code event handlers (13 hooks)
├── mcp_server/     # MCP tool surface for agents
├── server/         # Starlette HTTP API + dashboard
├── self_debug/     # Static analysis + patch generation
└── registry/       # 26 agents (7 core + 19 delivery)
```

**Included hooks:**
- `context_monitor` — warns on high token usage
- `file_checker` — ruff/eslint/gofmt on Write/Edit
- `tdd_enforcer` — alerts on code without tests
- `tool_redirect` — suggests `retrieve` over web search
- `learning_trigger` — detects git commit/merge, triggers learning
- `spec_stop_guard` — blocks exit during verify phase
- `session_end` — cleanup at session end
- + 6 more

---

## Installation

### Option A: pipx (recommended)

```bash
pipx install stratus
```

### Option B: Installer script

```bash
curl -fsSL https://raw.githubusercontent.com/MartinNevlaha/stratus/main/scripts/install.sh | sh
```

### Option C: From source

```bash
git clone https://github.com/MartinNevlaha/stratus.git
cd stratus
uv sync --dev
```

### Requirements

- Python 3.12+
- Git (for worktree features)
- Optional: [Vexor](https://github.com/MartinNevlaha/vexor) for code retrieval

---

## Quick Start

### 1. Initialize your project

```bash
cd /path/to/your/git/repo
stratus init
```

This creates/updates:
- `.ai-framework.json` — main config
- `.claude/settings.json` — hooks registration
- `.mcp.json` — MCP server
- `project-graph.json` — project metadata

### 2. Start the API server

```bash
stratus serve
```

Default: `http://127.0.0.1:41777`

### 3. Health check

```bash
stratus doctor
```

### 4. Open dashboard (optional)

```
http://127.0.0.1:41777/dashboard
```

### 5. Reconcile existing agents/skills/rules (recommended)

In Claude Code:

```
/stratus:sync-stratus
```

This skill scans your environment and produces a conflict report against the Stratus delegation model.

---

## Spec-Driven Development Modes

Stratus provides two spec modes based on task complexity:

| Command | Phases | Flow |
|---------|--------|------|
| `/spec` | 4 | Plan → Do → Review → Learn |
| `/spec-complex` | 8 | Discovery → Design → Governance → Plan → Accept → Implement → Review → Learn |

### When to Use Which?

| Use `/spec` (Simple) | Use `/spec-complex` (Complex) |
|----------------------|-------------------------------|
| Single file changes | Authentication, authorization |
| Bug fixes | Database migrations, schema changes |
| Small refactorings | API design, new endpoints |
| Clear, well-defined scope | Third-party integrations |
| < 3 files affected | Multi-service changes |
| No security impact | Infrastructure, CI/CD changes |
| No database changes | Unclear or evolving requirements |

### Flow Comparison

```
SIMPLE (4-phase)              COMPLEX (8-phase)
─────────────────             ─────────────────────
Plan ─────────────┐           Discovery ────┐
                  │                          │
Do ───────────────┤           Design ───────┤
                  │                          │
Review ───────────┤           Governance ───┤ (skip if no risk)
                  │                          │
Learn ────────────┘           Plan ─────────┤
                              │              │
                              Accept ────────┤ (user gate)
                              │              │
                              Implement ─────┤
                              │              │
                              Review ────────┤
                              │              │
                              Learn ─────────┘
```

---

## CLI Reference

### Basic commands

```bash
stratus --version                    # Version
stratus init                         # Initialize project
stratus init --scope global          # Global installation
stratus init --enable-delivery       # With delivery agents
stratus doctor                       # Health check
stratus serve                        # HTTP API server
stratus mcp-serve                    # MCP stdio server
stratus statusline                   # Status line for Claude Code
```

### Worktree orchestration

```bash
stratus worktree detect <slug>       # Detect existing worktree
stratus worktree create <slug>       # Create worktree
stratus worktree diff <slug>         # Diff vs base branch
stratus worktree sync <slug>         # Squash-merge to main
stratus worktree cleanup <slug>      # Delete worktree + branch
stratus worktree status <slug>       # Worktree status
```

### Learning pipeline

```bash
stratus learning status              # Learning engine status
stratus learning analyze             # Run analysis
stratus learning proposals           # List proposals
stratus learning decide ID accept    # Accept proposal
stratus learning decide ID reject    # Reject proposal
stratus learning config              # Show config
```

### Other

```bash
stratus analyze <file.jsonl>         # Analyze transcript
stratus reindex [--full]             # Reindex retrieval
stratus retrieval-status             # Retrieval backend status
stratus hook <module>                # Run hook module
stratus self-debug                   # Self-debug analysis
```

---

## Init Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Show actions without writing |
| `--force` | Overwrite existing `.ai-framework.json` |
| `--scope local\|global` | Project vs global installation |
| `--skip-hooks` | Don't register hooks |
| `--skip-mcp` | Don't register MCP server |
| `--skip-retrieval` | Skip retrieval setup |
| `--skip-agents` | Skip runtime agents |
| `--enable-delivery` | Install delivery agent set |

---

## Claude Code Plugin

```bash
claude --plugin-dir ./plugin
```

Available commands:

| Command | Description |
|---------|-------------|
| `/stratus:spec` | Simple spec (4-phase): Plan → Do → Review → Learn |
| `/stratus:spec-complex` | Complex spec (8-phase): Discovery → Design → Governance → ... |
| `/stratus:init` | Initialize project |
| `/stratus:doctor` | Health check |
| `/stratus:status` | Show status |
| `/stratus:analyze` | Analyze transcript |
| `/stratus:reindex` | Reindex retrieval |
| `/stratus:proposals` | List learning proposals |
| `/stratus:decide` | Decide on proposal |
| `/stratus:worktree` | Worktree operations |

---

## Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_FRAMEWORK_DATA_DIR` | `~/.ai-framework/data` | Data directory |
| `AI_FRAMEWORK_PORT` | `41777` | API port |
| `CLAUDE_CODE_TASK_LIST_ID` | `default` | Session ID |

### Config file

`.ai-framework.json` — main project config

```json
{
  "learning": {
    "global_enabled": true,
    "sensitivity": "moderate"
  },
  "self_debug": {
    "enabled": false
  },
  "retrieval": {
    "vexor_enabled": true
  }
}
```

---

## Uninstall

```bash
# Uninstall without project cleanup
./scripts/uninstall.sh

# Uninstall with project cleanup
./scripts/uninstall.sh --project

# If installed via pipx
pipx uninstall stratus
```

---

## Development

```bash
# Tests
uv run pytest -q
uv run pytest --cov=stratus --cov-fail-under=80

# Lint
uv run ruff check src/ tests/
uv run basedpyright src/
```

---

## Docker

```bash
docker build -t stratus .
docker run -p 41777:41777 -v ~/.ai-framework:/root/.ai-framework stratus
```

---

## Architecture (High Level)

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Hooks   │  │   MCP    │  │ Statusline│  │  Plugin  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    HTTP API (port 41777)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Memory  │  │ Retrieval│  │ Learning │  │Orchestr. │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                     SQLite Storage                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Memory  │  │  Embed   │  │ Learning │  │Governance│   │
│  │    DB    │  │  Cache   │  │    DB    │  │  Store   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Repository Layout

```
src/stratus/       # Framework source
tests/             # Test suite (100+ test files)
scripts/           # Install/uninstall helpers
docs/              # Architecture & design docs
```

---

## License

Apache License 2.0 — see `LICENSE`

---

## Links

- **Repository:** https://github.com/MartinNevlaha/stratus
- **Issues:** https://github.com/MartinNevlaha/stratus/issues
- **PyPI:** https://pypi.org/project/stratus/
