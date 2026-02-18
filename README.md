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

## Claude Code Plugin

Stratus is also available as a Claude Code plugin, which bundles commands, hooks, agents,
skills, and the MCP server into a self-contained directory. This eliminates the need to run
`stratus init` — Claude Code discovers everything from the plugin manifest.

**Prerequisite:** `stratus` must be installed via `pipx install stratus` (or from source).

### Installation

Development (local directory):

```bash
claude --plugin-dir ./plugin
```

### Plugin Commands

All commands are namespaced under `/stratus:`:

| Command | Description |
|---|---|
| `/stratus:init` | Initialize project (detect services, register hooks, configure MCP) |
| `/stratus:doctor` | Run health checks on all components |
| `/stratus:status` | Show retrieval and learning engine status |
| `/stratus:analyze` | Analyze a JSONL transcript |
| `/stratus:reindex` | Trigger code reindexing |
| `/stratus:proposals` | List pending learning proposals |
| `/stratus:decide` | Accept/reject a learning proposal |
| `/stratus:worktree` | Manage git worktrees for spec-driven development |

### Plugin Hooks

Hooks run automatically on Claude Code events:

| Event | Hook | Behavior | Blocking? |
|---|---|---|---|
| PreToolUse (WebSearch/WebFetch) | tool_redirect | Suggests `retrieve` MCP tool for codebase queries | No |
| PostToolUse (*) | context_monitor | Monitors transcript size, warns on threshold | No |
| PostToolUse (Write/Edit) | file_checker | Runs language-specific linter (ruff, eslint, gofmt) | No |
| PostToolUse (Write/Edit) | tdd_enforcer | Warns when editing code without tests | No |
| PostToolUse (Bash) | learning_trigger | Detects git commit/merge, triggers learning analysis | No |
| PreCompact (*) | pre_compact | Captures session state before compaction | No |
| SessionStart (compact) | post_compact_restore | Restores state after compaction | No |
| SessionEnd (*) | session_end | Persists session state, performs cleanup | No |
| Stop (*) | spec_stop_guard | Blocks exit during active spec verify phase | Yes (conditional) |
| TeammateIdle (*) | teammate_idle | Validates reviewer verdict format in Agent Teams | Yes (exit 2) |
| TaskCompleted (*) | task_completed | Validates task output completeness in Agent Teams | Yes (exit 2) |

### Plugin Architecture

- **Commands** — user-triggered via `/stratus:<name>`, delegate to the `stratus` CLI
- **Hooks** — autonomous, fire on Claude Code events via `stratus hook <module>`
- **MCP** — agent-facing tools via `stratus mcp-serve` (stdio transport)
- **Agents** — 7 core + 19 delivery agent definitions for spec-driven workflows
- **Skills** — 3 core + 7 delivery skills for common operations

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

## Web UI

Start the server and open the dashboard in a browser:

```bash
stratus serve
# Open http://localhost:41777/dashboard
```

The dashboard provides a read-only swarm monitor with:

- **Canvas visualization** — orbital animation of active agents, colored by category
- **Phase progress** — current spec/delivery phase, task completion, review iteration
- **Agent list** — active agents with role indicators (lead/worker)
- **Learning stats** — proposal counts, sensitivity, candidate pipeline
- **Memory stats** — event and session totals

Data refreshes every 3 seconds via a single aggregated endpoint (`/api/dashboard/state`).
No build step or external dependencies — vanilla HTML/CSS/JS served by the existing Starlette app.

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

## Adaptive Learning

The learning subsystem detects recurring patterns in your development workflow and proposes
reusable rules, ADRs, templates, and skills. Ships disabled by default.

### How It Works

```
git commit (x5)  -->  learning_trigger hook  -->  POST /api/learning/analyze
                                                        |
                      +--------------------------------+
                      |
                      v
              Git Analysis              AST Analysis
        (structural changes,      (function signatures,
         import patterns)          class hierarchies,
                                   error handlers)
                      |                    |
                      +--------+-----------+
                               |
                               v
                    Heuristic Scoring (H1-H7)
              confidence = base * consistency
                         * recency * scope
                         * prior_decision_factor
                               |
                               v
                    Decision Tree Filter
              (min count, single-file, cooldown,
               existing rule dedup)
                               |
                               v
                    Proposal Generation
              (max 3/session, LLM prompt templates)
                               |
                               v
                  User decides: accept / reject / ignore
                               |
               +---------------+----------------+
               |                                |
            ACCEPT                        REJECT/IGNORE
               |                                |
         Create artifact                  7-day cooldown
         Save memory event               Lower prior_factor
         Snapshot baseline               Save memory event
```

**Trigger**: The `learning_trigger` hook fires on `PostToolUse` for `git commit`, `git merge`,
and `git pull`. After every 5 commits (configurable), it sends an analysis request to the HTTP
API. The hook always exits 0 — it never blocks the developer.

**Analysis**: `GitAnalyzer` runs `git diff` to find structural changes and import patterns.
`AstAnalyzer` parses Python via stdlib `ast` (TypeScript via regex) to extract function
signatures, class hierarchies, and error handling patterns. Cross-file repetition produces
`Detection` objects.

**Scoring**: Seven heuristics compute confidence scores. The `prior_decision_factor` creates a
reinforcement loop: past accepts boost confidence for similar patterns, past rejects lower it.
A decision tree discards low-count, single-file, and recently-rejected patterns.

**Proposals**: Scored candidates are deduplicated, checked against existing `.claude/rules/`
files, and converted to proposals with LLM prompt templates. Stratus never calls an LLM API
itself — interpretation happens through agents or manual review.

### Artifacts

Accepted proposals create files that Claude Code discovers automatically:

| Proposal Type | Artifact Path | How Claude Code Uses It |
|---|---|---|
| RULE | `.claude/rules/learning-<slug>.md` | Loaded into system prompt of every session |
| ADR | `docs/decisions/<slug>.md` | Indexed by GovernanceStore, searchable via retrieval |
| TEMPLATE | `.claude/templates/<slug>.md` | Available for project scaffolding |
| SKILL | `.claude/skills/<slug>/prompt.md` | Invocable by name in Claude Code |
| PROJECT_GRAPH | `.ai-framework/project-graph.json` | Informs service detection and agent prompts |

Rules are the primary output. Once `.claude/rules/learning-<slug>.md` is on disk, Claude Code
includes it in the system prompt for all future sessions in that project — no configuration needed.

### Effectiveness Feedback Loop

Hooks (`file_checker`, `tdd_enforcer`) record failures to the analytics system. When a rule is
accepted, the current failure rate is baselined. Over time, effectiveness is scored:

```
score = 1.0 - (current_failure_rate / baseline_failure_rate) / 2.0
```

- Score > 0.6: **effective** (failures decreased)
- 0.4 - 0.6: **neutral**
- < 0.4: **ineffective**

Low-impact rules are surfaced via `GET /api/learning/analytics/rules/low-impact`.

### Anti-Annoyance Controls

- Disabled by default (`global_enabled: false`)
- Max 3 proposals per session
- 7-day cooldown after reject/ignore
- 24-hour warmup before first analysis
- Conservative confidence threshold (0.7)

## Agent Orchestration

Spec-driven development uses the `/spec` workflow: plan → implement → verify → learn. Two
orchestration backends share the same state machine, review logic, and worktree isolation.

### Task Tool (Default)

Main Claude (Opus) spawns disposable subagents via the `Task` tool. Each agent gets a fresh
context, executes its assignment, and terminates. All state flows through the coordinator.

```
/spec <slug>
  |
  PLAN -----> Main Claude writes plan, user approves
  |
  IMPLEMENT -> worktree.create() -> git worktree on spec/<slug>
  |            For each task:
  |              Task(implementer, "Implement task N...")
  |              -> Agent runs TDD, hooks check linting + tests
  |
  VERIFY ----> Task(spec-reviewer-compliance, run_in_background=true)
  |            Task(spec-reviewer-quality, run_in_background=true)
  |            -> parse_verdict() extracts PASS/FAIL + findings
  |            -> aggregate_verdicts()
  |            |
  |            +-- All PASS? -> LEARN
  |            +-- FAIL? -> fix loop (max 3 iterations)
  |                         build_fix_instructions(findings)
  |                         -> back to IMPLEMENT -> VERIFY
  |
  LEARN -----> sync_worktree() -> squash-merge to main
               cleanup_worktree() -> remove worktree + branch
               Save memory events
```

### Agent Teams (Opt-In, Experimental)

Instead of disposable agents, creates persistent teammates that share a task list and
communicate directly. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and configuration
in `.ai-framework.json`:

```json
{
  "agent_teams": {
    "enabled": true,
    "mode": "agent-teams",
    "teammate_mode": "auto",
    "max_teammates": 5
  }
}
```

The lifecycle is the same (PLAN → IMPLEMENT → VERIFY → LEARN), but dispatch differs:

- **Implementation**: `TeamManager` creates a team with N teammates, each owning non-overlapping
  files. Teammates auto-claim tasks from a shared task list.
- **Review**: `TeamManager` creates a review team. `TeammateIdle` hook enforces verdict format
  (exit 2 = keep working). `TaskCompleted` hook validates output completeness.
- **Quality gates**: `teammate_idle` and `task_completed` hooks are active only in this mode.
  They never crash — all errors swallowed with exit 0.

### Comparison

| Aspect | Task Tool | Agent Teams |
|---|---|---|
| Agent lifecycle | Disposable (spawn, execute, terminate) | Persistent (live across tasks) |
| Communication | Through coordinator only | Direct inter-agent messaging |
| Parallelism | `run_in_background` + polling | Shared task list, auto-claiming |
| Quality gates | Coordinator validates output | `TeammateIdle` + `TaskCompleted` hooks |
| Token cost | Lower (results summarized) | Higher (each teammate = full instance) |
| Stability | Production | Experimental |

### Shared Components

Both modes use the same:
- **SpecCoordinator** (`orchestration/coordinator.py`) — pure state machine, manages phase
  transitions. Does not generate prompts or call Claude APIs.
- **TeamManager** (`orchestration/teams.py`) — generates prompts for Agent Teams, validates
  outputs. Does not call Claude APIs directly.
- **Reviewer agents** (`.claude/agents/spec-reviewer-*.md`) — read-only Opus agents producing
  `Verdict: PASS/FAIL` with structured findings. Same definitions in both modes.
- **Review logic** (`orchestration/review.py`) — `parse_verdict()`, `aggregate_verdicts()`,
  `needs_fix_loop()`. Operates on `ReviewVerdict` objects, never string matching.
- **Worktree isolation** (`orchestration/worktree.py`) — git worktree create/sync/cleanup.

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
