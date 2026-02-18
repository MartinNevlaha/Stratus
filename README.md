# stratus

Open-source framework providing persistent memory, retrieval, adaptive learning, and spec-driven
orchestration for Claude Code sessions. Python 3.12+.

This is not an agent runtime. It enhances Claude Code sessions via hooks, an MCP server, and an
HTTP API — all of which integrate with Claude Code's existing extension points.

## Features

- Persistent memory with SQLite+FTS5 full-text search, timeline, and session tracking
- Retrieval layer: Vexor for code search, GovernanceStore for governance docs (SQLite+FTS5), with unified auto-routing
- Claude Code hooks: context monitoring, compaction handling, file linting, TDD enforcement,
  tool redirect, learning triggers, spec guards, quality gates
- MCP stdio server with 6 tools proxying to the HTTP API (stateless MCP, stateful HTTP)
- HTTP API (Starlette/Uvicorn) for memory, sessions, retrieval, learning, analytics, orchestration
- Adaptive learning: pattern detection from git history, AST analysis, heuristic scoring, proposal
  generation — disabled by default, no LLM API calls required
- Spec-driven orchestration: git worktree isolation, reviewer verdicts, coordinator state machine
- Bootstrap: service detection, project-graph generation, automatic hook and MCP registration

## Installation

### 1. Install the package

```bash
pipx install stratus
```

Or use the one-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/MartinNevlaha/stratus/main/scripts/install.sh | sh
```

### 2. Set up for your project (choose one)

**Project scope** — hooks and MCP registered in the project directory:

```bash
cd /path/to/your/project    # must be a git repository
stratus init
```

This detects services, probes retrieval backends (Vexor, governance index), generates
`project-graph.json` and `.ai-framework.json`, registers hooks in `.claude/settings.json`,
and the MCP server in `.mcp.json`. Re-running on an existing project upgrades the retrieval
config without downgrading previously enabled backends.

**Global scope** — hooks and MCP registered in `~/.claude/` (works across all projects):

```bash
stratus init --scope global
```

**With delivery agents and skills:**

```bash
stratus init --enable-delivery
```

### 3. Start the HTTP API server

```bash
stratus serve
```

### 4. Verify

```bash
stratus doctor
```

### Optional flags for `init`

| Flag | Description |
|---|---|
| `--dry-run` | Preview changes without writing files |
| `--force` | Overwrite existing `.ai-framework.json` |
| `--scope global` | Install hooks and MCP globally to `~/.claude/` (no git repo required) |
| `--enable-delivery` | Install delivery agents and skills |
| `--skip-hooks` | Skip hook registration |
| `--skip-mcp` | Skip MCP server registration |
| `--skip-retrieval` | Skip retrieval backend detection and setup |
| `--skip-agents` | Skip agent/skill installation |

## Quick Start

**Initialize in your project (registers hooks and MCP server):**

```bash
cd /path/to/your/project
stratus init
```

**Start the HTTP API server:**

```bash
stratus serve
# Listening on http://localhost:41777
```

Claude Code will connect to the MCP server automatically once `init` has registered it in
`.mcp.json`. Hooks are registered in `.claude/settings.json`.

## CLI Reference

| Command | Description |
|---|---|
| `stratus --version` | Print version and exit |
| `stratus analyze <file.jsonl>` | Parse and display transcript stats |
| `stratus init` | Detect services, generate config, register hooks and MCP server |
| `stratus init --dry-run` | Preview what init would do without writing files |
| `stratus init --force` | Overwrite existing config files |
| `stratus init --skip-hooks` | Skip hook registration |
| `stratus init --skip-mcp` | Skip MCP server registration |
| `stratus init --skip-retrieval` | Skip retrieval backend auto-detection |
| `stratus doctor` | Run health checks on all components |
| `stratus serve` | Start the HTTP API server (default port 41777) |
| `stratus mcp-serve` | Start the MCP stdio server |
| `stratus reindex` | Trigger incremental code reindex |
| `stratus reindex --full` | Trigger full code reindex |
| `stratus retrieval-status` | Show retrieval backend status |
| `stratus worktree detect <slug>` | Detect existing worktree for a spec slug |
| `stratus worktree create <slug>` | Create a git worktree for a spec slug |
| `stratus worktree diff <slug>` | Show diff vs base branch |
| `stratus worktree sync <slug>` | Squash-merge worktree branch to base branch |
| `stratus worktree cleanup <slug>` | Remove worktree and delete its branch |
| `stratus worktree status <slug>` | Show worktree status as JSON |
| `stratus learning status` | Show learning engine status |
| `stratus learning analyze` | Run learning analysis against recent git history |
| `stratus learning proposals` | List pending rule/ADR/template proposals |
| `stratus learning decide <id> <accept\|reject\|ignore>` | Act on a proposal |
| `stratus learning config` | Show current learning configuration |

Worktree commands accept `--plan-path <path>` and `--base-branch <branch>` options.

## Architecture

The framework is organized into eight subsystems:

**Memory** — SQLite+FTS5 database at `~/.ai-framework/data/`. Stores memory events, sessions,
observations, and a searchable timeline. The FTS5 virtual table uses the porter stemmer.

**Retrieval** — Two backends behind a unified interface. Vexor (external binary) handles code
semantic search; GovernanceStore (Python-native SQLite+FTS5) indexes governance documentation
(rules, ADRs, templates, skills, agents, architecture docs). `UnifiedRetriever` auto-routes
queries: code queries go to Vexor, governance queries to GovernanceStore, hybrid queries to both.
The embed cache is a SQLite database keyed by SHA256(content+model).

**Hooks** — Python modules installed as entry points and registered as Claude Code hooks. They
run on tool use events, session start/end, and stop signals. No hook ever raises an unhandled
exception that would block a Claude Code session.

**MCP Server** — Stdio MCP server exposing six tools: `save_memory`, `search`, `timeline`,
`observations`, `sessions_init`, `context_inject`. Each tool delegates to the HTTP API via httpx.

**HTTP API** — Starlette application with route groups for memory, sessions, retrieval, learning,
analytics, and orchestration. Launched by `stratus serve` via Uvicorn on port 41777.

**Learning** — Pattern detection pipeline: git diff/log analysis, Python AST and TypeScript regex
extraction, seven heuristics with confidence scoring, deduplication against existing rules, and
proposal generation. Accepted proposals write artifacts to `.claude/rules/`, `docs/decisions/`,
`.claude/templates/`, or `.claude/skills/`. Disabled by default.

**Orchestration** — Spec-driven development support. Worktrees are created under
`.worktrees/spec-<slug>-<sha8>/` on branch `spec/<slug>`. The `SpecCoordinator` is a pure state
machine (plan → implement → verify → learn). Reviewer agents produce PASS/FAIL verdicts.

**Bootstrap** — Detects service types (NestJS, Next.js, Python, Go, Rust, proto, shared),
generates `project-graph.json` and `.ai-framework.json`, and registers hooks and the MCP server
into `.claude/settings.json` and `.mcp.json`. Registration is idempotent.

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `AI_FRAMEWORK_DATA_DIR` | `~/.ai-framework/data/` | Directory for all SQLite databases and state files |
| `AI_FRAMEWORK_PORT` | `41777` | HTTP API server port |
| `CLAUDE_CODE_TASK_LIST_ID` | `"default"` | Session ID passed by Claude Code |

## Docker

Build and run the HTTP API server in a container:

```bash
docker build -t stratus .
docker run -p 41777:41777 -v ~/.ai-framework:/root/.ai-framework stratus
```

The container runs `stratus serve` on port 41777. Mount `~/.ai-framework` to persist data
across container restarts.

## Development

```bash
git clone https://github.com/MartinNevlaha/stratus.git
cd stratus
uv sync --dev

uv run pytest -q                                          # Run tests
uv run pytest --cov=stratus --cov-fail-under=80    # Tests with coverage
uv run ruff check src/ tests/                             # Lint
```

Runtime dependencies: `mcp>=1.20` (transitive: starlette, uvicorn, pydantic, httpx, anyio) and
`httpx>=0.27`. The core framework uses only stdlib beyond these two packages.

Optional external tools: Vexor binary (code search). Governance document search is built-in
via GovernanceStore (no external dependencies). The framework degrades gracefully when Vexor is
unavailable.

## Uninstall

Remove stratus binary, data, and global config:

```bash
curl -fsSL https://raw.githubusercontent.com/MartinNevlaha/stratus/main/scripts/uninstall.sh | sh
```

Or run locally:

```bash
./scripts/uninstall.sh
```

To also remove project-local artifacts (hooks, MCP entry, config files, managed agents/skills)
from the current git repo:

```bash
./scripts/uninstall.sh --project
```

| Flag | Description |
|---|---|
| `--project` | Also clean stratus artifacts from the current git repo |
| `--yes` | Skip confirmation prompts |

The uninstaller only removes managed agent/skill files (those with the `<!-- managed-by: stratus`
header). User-created files are never touched.

## License

Apache License 2.0. See [LICENSE](LICENSE) for the full text.
