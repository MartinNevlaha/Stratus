# stratus

Open-source framework for Claude Code sessions. Python 3.12+.

## Project Structure

```
src/stratus/
  transcript.py       # JSONL transcript parser (TokenUsage, CompactionEvent, TranscriptStats)
  cli.py              # CLI entry point (subcommands: analyze, init, doctor, serve, mcp-serve, reindex, retrieval-status, worktree, hook, learning)
  __main__.py         # Module runner: python -m stratus

  bootstrap/
    __init__.py       # Package init
    models.py         # Pydantic models: ServiceType, ServiceInfo, SharedComponent, InfraInfo, ProjectGraph
    detector.py       # Service detection heuristics (NestJS, Next.js, Python, Go, Rust, shared, proto)
    writer.py         # Config file generators: project-graph.json, .ai-framework.json
    commands.py       # CLI command handlers: cmd_init (enhanced), cmd_doctor (health checks)
    registration.py   # Hook + MCP server registration (local or global scope)

  memory/
    models.py         # Pydantic models: MemoryEvent, Session, enums
    schema.py         # SQLite DDL, FTS5 virtual table, migration runner
    database.py       # Database class: CRUD, FTS5 search, timeline, sessions

  retrieval/
    __init__.py         # Public exports for retrieval layer
    models.py           # Pydantic models: SearchResult, RetrievalResponse, IndexStatus, CorpusType
    config.py           # VexorConfig, DevRagConfig, RetrievalConfig, .ai-framework.json loader
    index_state.py      # index-state.json read/write, staleness detection via git diff
    embed_cache.py      # SQLite cache keyed by SHA256(content+model), WAL mode, migrations
    vexor.py            # VexorClient: subprocess calls to vexor binary, porcelain parsing
    devrag.py           # DevRagClient: governance document search via GovernanceStore
    governance_store.py  # GovernanceStore: SQLite+FTS5 indexer for governance docs
    unified.py          # UnifiedRetriever: routes code→Vexor, governance→GovernanceStore, hybrid→both

  server/
    app.py              # Starlette app factory with lifespan (DB + retriever + embed cache + coordinator)
    routes_system.py    # /health, /api/version, /api/stats
    routes_memory.py    # /api/memory/save, /api/search, /api/timeline, /api/observations
    routes_session.py   # /api/sessions/init, /api/sessions, /api/context/inject
    routes_retrieval.py # /api/retrieval/search, /status, /index, /index-state, /embed-cache/stats
    routes_learning.py  # /api/learning/analyze, /proposals, /decide, /config, /stats
    routes_analytics.py # /api/learning/analytics/* — failure recording, summary, trends, effectiveness
    routes_orchestration.py # /api/orchestration/state, /start, /approve-plan, /verdicts, /team
    routes_dashboard.py # /api/dashboard/state, /dashboard — aggregated monitor + HTML page
    runner.py           # Uvicorn launcher, port.lock management
    static/             # Web UI assets (index.html, dashboard.css, dashboard.js)

  mcp_server/
    server.py         # MCP stdio server with 6 tool handlers
    client.py         # Async httpx client for memory HTTP API

  learning/
    __init__.py       # Public exports for learning layer
    models.py         # Enums + Pydantic models: Detection, PatternCandidate, Proposal, etc.
    config.py         # LearningConfig dataclass, .ai-framework.json loader, sensitivity mapping
    schema.py         # SQLite DDL: pattern_candidates, proposals, analysis_state
    database.py       # LearningDatabase: CRUD, cooldown, prior_decision_factor, db_creation_time
    git_analyzer.py   # Git diff/log analysis via subprocess (_run_git pattern)
    ast_analyzer.py   # Python AST + TypeScript regex pattern extraction
    heuristics.py     # H1-H7 heuristics, confidence scoring, decision tree filtering
    proposals.py      # Proposal generation, LLM prompt templates, deduplication, existing-rule check
    artifacts.py      # Artifact content generators + file writer (rules, ADRs, templates, skills, project-graph)
    watcher.py        # ProjectWatcher facade: orchestrates full pipeline + artifact creation on accept
    analytics_db.py   # AnalyticsDB: failure events + rule baselines CRUD (shares LearningDatabase connection)
    analytics.py      # Pure computation: failure summary, trends, hotspots, rule effectiveness scoring

  hooks/
    _common.py        # Shared: stdin JSON reader, session dir, API URL, get_git_root
    context_monitor.py  # PostToolUse: transcript analysis + threshold warnings
    pre_compact.py    # PreCompact: capture session state before compaction
    post_compact_restore.py  # SessionStart[compact]: restore state after compaction
    file_checker.py   # PostToolUse: language-specific linting on Write/Edit
    tdd_enforcer.py   # PostToolUse: warns when editing code without tests
    tool_redirect.py  # PreToolUse: suggests retrieve MCP tool over web search
    learning_trigger.py # PostToolUse: detect git commit/merge, trigger learning analysis
    spec_stop_guard.py  # Stop: blocks exit during active /spec verify phase
    session_end.py    # SessionEnd: cleanup / persist session state on session end
    teammate_idle.py  # TeammateIdle: quality gate — validates reviewer verdict format
    task_completed.py # TaskCompleted: quality gate — validates task output completeness

  orchestration/
    models.py         # Pydantic models: SpecState, ReviewResult, WorktreeInfo, TeamConfig, enums
    worktree.py       # Git worktree CRUD: detect, create, diff, sync, cleanup, status
    spec_state.py     # Spec lifecycle state machine: load, transition, persist
    review.py         # Review orchestration: invoke reviewer agents, aggregate verdicts
    coordinator.py    # SpecCoordinator: plan→implement→verify→learn control loop
    teams.py          # TeamManager: Agent Teams config, prompts, validation

  session/
    config.py         # Constants, config loading, env var overrides
    state.py          # Session state JSON read/write, session ID resolution

tests/
  conftest.py         # JSONL fixtures
  test_transcript.py  # Parser tests
  test_cli.py         # CLI tests
  test_commands.py    # Bootstrap CLI command tests (init and doctor)
  test_bootstrap_models.py   # Bootstrap Pydantic model tests
  test_bootstrap_detector.py # Service detection heuristic tests
  test_bootstrap_writer.py   # Config file writer tests
  test_registration.py  # Hook + MCP registration tests
  test_models.py      # Pydantic model tests
  test_schema.py      # SQLite schema/migration tests
  test_database.py    # Database CRUD/search tests
  test_config.py      # Config loading tests
  test_state.py       # Session state tests
  test_server.py      # HTTP API server tests (Starlette TestClient)
  test_mcp_server.py  # MCP server + client tests
  test_hooks.py       # Hook script tests (context_monitor, pre_compact, post_compact)
  test_file_checker.py  # File checker hook tests
  test_tdd_enforcer.py  # TDD enforcer hook tests
  test_tool_redirect.py   # Tool redirect hook tests
  test_retrieval_models.py # Retrieval Pydantic model tests
  test_retrieval_config.py # Retrieval config loading tests
  test_index_state.py      # Index state + git staleness tests
  test_embed_cache.py      # Embed cache SQLite tests
  test_vexor.py            # Vexor client tests (mock subprocess)
  test_devrag.py           # DevRag client tests (GovernanceStore-backed)
  test_governance_store.py  # GovernanceStore indexer tests
  test_unified.py          # Unified retriever tests (mock clients)
  test_retrieval_routes.py # Retrieval HTTP route tests
  test_orchestration_models.py # Orchestration Pydantic model tests
  test_spec_state.py       # Spec state lifecycle tests
  test_worktree.py         # Worktree handler tests (mock subprocess)
  test_review.py           # Review verdict parsing tests
  test_spec_stop_guard.py  # Stop hook tests
  test_session_end.py      # SessionEnd hook tests
  test_learning_models.py  # Learning Pydantic model tests
  test_learning_config.py  # Learning config loading tests
  test_learning_schema.py  # Learning SQLite schema tests
  test_learning_database.py # Learning database CRUD tests
  test_git_analyzer.py     # Git change detection tests (mock subprocess)
  test_ast_analyzer.py     # Python AST + TS regex extraction tests
  test_heuristics.py       # Heuristic engine + confidence scoring tests
  test_proposals.py        # Proposal generator + prompt template tests
  test_watcher.py          # ProjectWatcher facade tests (mock components)
  test_artifacts.py        # Artifact content generation + file writing tests
  test_analytics_models.py  # Analytics Pydantic model tests (FailureEvent, RuleBaseline, etc.)
  test_analytics_db.py      # Analytics CRUD tests (dedup, trends, hotspots, baselines)
  test_analytics.py         # Analytics computation tests (summary, effectiveness scoring)
  test_analytics_routes.py  # Analytics HTTP route tests
  test_learning_routes.py  # Learning HTTP route tests
  test_learning_trigger.py # Learning trigger hook tests
  test_learning_commands.py # Learning CLI command handler tests
  test_coordinator.py      # SpecCoordinator lifecycle tests
  test_teams.py            # TeamManager config/prompt/validation tests
  test_teammate_idle.py    # TeammateIdle hook tests
  test_task_completed.py   # TaskCompleted hook tests
  test_orchestration_routes.py # Orchestration HTTP route tests
  test_dashboard_routes.py # Dashboard aggregated endpoint + static serving tests

.claude/
  agents/
    framework-expert.md      # Implementation agent (sonnet)
    architecture-guide.md    # Architecture Q&A agent (opus, read-only)
    qa-engineer.md           # Test/lint agent (haiku)
    plan-verifier.md         # Plan validation against architecture (opus, read-only)
    plan-challenger.md       # Adversarial plan review (opus, read-only)
    spec-reviewer-compliance.md  # Implementation vs spec check (opus, read-only)
    spec-reviewer-quality.md     # Code quality review (opus, read-only)
  skills/
    run-tests/               # Delegates to qa-engineer
    explain-architecture/    # Delegates to architecture-guide
    implement-mcp/           # Delegates to framework-expert

plugin/
  .claude-plugin/
    plugin.json             # Plugin manifest (name, version, description)
  .mcp.json                 # MCP server config (stratus mcp-serve, stdio)
  commands/                 # 8 command files (init, doctor, status, analyze, reindex, proposals, decide, worktree)
  agents/                   # 26 agent definitions (7 core + 19 delivery)
  skills/                   # 10 skill definitions (3 core + 7 delivery)
  hooks/
    hooks.json              # Hook configuration (11 hooks using `stratus hook <module>`)

scripts/
  install.sh          # POSIX installer (pipx or venv fallback, no sudo)
  uninstall.sh        # POSIX uninstaller (pipx and venv)

docs/
  architecture/       # Full framework architecture doc
  phase0/             # Phase 0 deliverables

Dockerfile            # Minimal container for HTTP API server (python:3.12-slim + uv)
```

## Commands

```bash
uv run pytest -q                              # Run tests
uv run pytest --cov=stratus --cov-fail-under=80  # Coverage
uv run ruff check src/ tests/                 # Lint

# CLI subcommands
uv run stratus --version                # Print version and exit
uv run stratus analyze <file.jsonl>     # Analyze transcript
uv run stratus init [--dry-run] [--force] [--skip-hooks] [--skip-mcp] [--scope local|global]  # Initialize project bootstrap
uv run stratus doctor                    # Run health checks on all components
uv run stratus serve                    # Start HTTP API server (port 41777)
uv run stratus mcp-serve                # Start MCP stdio server
uv run stratus reindex [--full]         # Trigger code reindexing
uv run stratus retrieval-status         # Show retrieval backend status
uv run stratus worktree detect <slug>   # Detect existing worktree for slug
uv run stratus worktree create <slug>   # Create worktree for slug
uv run stratus worktree diff <slug>     # Show diff vs base branch (plain text)
uv run stratus worktree sync <slug>     # Squash-merge worktree branch to main
uv run stratus worktree cleanup <slug>  # Remove worktree and delete branch
uv run stratus worktree status <slug>   # Show worktree status (JSON)
#   Options: --plan-path <path>  --base-branch <branch>

uv run stratus learning status           # Show learning engine status
uv run stratus learning analyze [--since COMMIT]  # Run learning analysis
uv run stratus learning proposals        # List pending proposals
uv run stratus learning decide ID accept # Decide on a proposal
uv run stratus learning config           # Show learning config

uv run stratus hook <module>             # Run a hook module (plugin entry point)

# Backward compat
uv run stratus <file.jsonl>             # Auto-dispatches to analyze
```

## Runtime Dependencies

- `mcp>=1.20` — MCP stdio server (transitive: starlette, uvicorn, pydantic, httpx, anyio)
- `httpx>=0.27` — HTTP client for hooks calling the API

## Architecture Reference

See `docs/architecture/framework-architecture.md` for the full framework design (9 subsystems, 6 phases).

## Key Design Decisions

- Only count `type: "assistant"` messages for token usage (not `progress` sub-agent messages)
- Ground truth for compaction = `compactMetadata.preTokens` in `compact_boundary` system messages
- Compaction threshold: ~83.5% of 200K context window (~167K tokens)
- Starlette + Uvicorn come free via `mcp` transitive deps
- Pydantic for models (available via `mcp`)
- SQLite+FTS5 with porter stemmer for full-text search (stdlib)
- MCP server proxies to HTTP API (stateless MCP, stateful HTTP)
- Hooks are importable modules (installed as scripts but testable as imports)
- `stratus init` auto-registers hooks in `.claude/settings.json` and MCP server in `.mcp.json`
- `--scope local` (default): writes to project `.claude/settings.json` + `.mcp.json`, requires git repo
- `--scope global`: writes to `~/.claude/settings.json` + `~/.claude/.mcp.json`, no git repo required
- Global scope skips service detection, project-graph, .ai-framework.json, and agents — only hooks + MCP
- Global MCP config omits `cwd` field (local uses `cwd: "."`)
- Registration is idempotent: merges into existing config, preserves non-hook keys
- `--skip-hooks` and `--skip-mcp` flags to opt out of auto-registration
- Session ID resolution: `CLAUDE_CODE_TASK_LIST_ID` → `"default"`
- Data directory: `~/.ai-framework/data/` (override: `AI_FRAMEWORK_DATA_DIR`)
- Default API port: 41777 (override: `AI_FRAMEWORK_PORT`)
- Reviewer agents are read-only (opus) — they analyze and produce PASS/FAIL verdicts
- File checker hook runs ruff (Python), eslint (TS), gofmt (Go) on Write/Edit
- TDD enforcer warns when implementation files lack corresponding test files
- Tool redirect suggests `retrieve` MCP tool over WebSearch for codebase queries
- Vexor client wraps CLI binary via subprocess (search, index, porcelain parsing)
- GovernanceStore provides Python-native SQLite+FTS5 governance doc search (rules, ADRs, templates, skills, agents, architecture)
- DevRagClient delegates to GovernanceStore — no Docker dependency, no subprocess calls
- Governance docs chunked by `## ` headers, change detection via SHA256 file hashing
- UnifiedRetriever auto-routes queries using classify_query from tool_redirect hook
- EmbedCache follows memory/database.py pattern (SQLite WAL, migrations, :memory: for tests)
- Retrieval graceful degradation: if one backend fails, try the other

### Phase 4: Orchestration & Worktree Isolation

- Worktree path convention: `<git_root>/.worktrees/spec-<slug>-<sha256[:8]>/`
- Branch convention: `spec/<slug>` (created off base_branch, default: main)
- `worktree create` auto-stashes dirty working tree before adding worktree
- `worktree create` copies `.claude/` and `.mcp.json` into new worktree
- `worktree sync` squash-merges spec branch via `git merge --squash --stat`
- `worktree diff` computes merge-base diff between spec branch and base branch
- `worktree cleanup` runs `git worktree remove --force` + `git branch -D`
- All git calls go through `_run_git()` (single mock target for tests)
- `WorktreeError` raised on git failures; CLI catches it, prints to stderr, exits 1
- `Stop` hook (`spec_stop_guard`) blocks exit during active spec verify phase (stale check: >4h allows exit)
- `SessionEnd` hook (`session_end`) persists session state and performs cleanup on end
- `SpecCoordinator` is a pure state machine — manages transitions, delegates to spec_state/worktree/review
- `SpecCoordinator` does NOT generate prompts, contain Claude-specific logic, or invoke tools
- `TeamManager` generates prompts and validates outputs — does NOT call Claude Code APIs directly
- `needs_fix_loop()` is deterministic: operates on `ReviewVerdict` objects, never string matching
- Agent Teams default backend: Task Tool; Agent Teams is opt-in via `.ai-framework.json`
- `TeamConfig` loading follows `LearningConfig` pattern (dataclass + JSON loader + env overrides)
- `TeammateIdle` hook validates reviewer verdict format; exit 2 → keep working
- `TaskCompleted` hook validates task output; exit 2 → prevent completion
- Quality gate hooks NEVER crash: all errors swallowed with exit 0 (crash = blocked teammate)
- Memory events from coordinator are best-effort (HTTP POST, errors swallowed)

### Phase 5: Adaptive Learning

- Ships **disabled by default** (`global_enabled: false`), conservative thresholds
- Sensitivity enum maps to min_confidence: conservative=0.7, moderate=0.5, aggressive=0.3
- Anti-annoyance controls: max 3 proposals/session, 7-day cooldown, 24h warmup
- No LLM API calls — generates prompt templates only; actual interpretation via agents/manual
- Dedicated SQLite DB (LearningDatabase) + MemoryEvent dual storage for decisions
- LearningDatabase follows embed_cache.py pattern (SQLite WAL, migrations, :memory: for tests)
- Git analysis via subprocess with `_run_git()` single mock target (follows worktree.py pattern)
- Python AST via stdlib `ast`; TypeScript uses regex fallback; malformed code → empty result
- H1-H7 heuristics with confidence scoring: base × consistency × recency × scope × prior_factor
- Decision tree: discard below count threshold, single-file, in cooldown, or existing rule
- Hook (`learning_trigger`) always exits 0 — never blocks user workflow
- Prior decision factor: acceptance ratio increases confidence, rejection decreases
- No new runtime dependencies — uses stdlib `ast`, `uuid`, `hashlib`, `re` + existing pydantic/httpx
- Accepted proposals create artifacts: RULE→`.claude/rules/`, ADR→`docs/decisions/`, TEMPLATE→`.claude/templates/`, SKILL→`.claude/skills/<slug>/prompt.md`, PROJECT_GRAPH→`.ai-framework/project-graph.json`
- `artifacts.py` generates content per ProposalType; `create_artifact()` never raises (returns None on error)
- PROJECT_GRAPH uses atomic write: read existing → merge in-memory → write temp file → `os.replace()`
- `_check_existing_rules()` deduplication wired into `generate_proposals()` via `rules_dir` parameter
- `min_age_hours` warmup guard: `analyze_changes()` returns empty result if DB younger than threshold
- `decide` route delegates to `watcher.decide_proposal()` (not `db.decide_proposal()` directly)
- Memory events enriched with proposal title, refs (artifact path), tags (proposal type), structured proposal_id
- Accept importance=0.7, reject/ignore importance=0.5 in memory events

### Phase 5.1: Learning Analytics — Failure Intelligence & Rule Effectiveness

- Failure events deduped via signature hash (category+file_path+detail[:200]+day) with INSERT OR IGNORE
- Record-failure endpoint is idempotent — same failure on same day silently ignored
- All timestamps UTC; trends bucket via `date(recorded_at)` in SQLite
- RuleBaseline uses UUID PK (not proposal_id) to allow re-baselining same rule
- Effectiveness formula (monotonic): `ratio = current/max(baseline, 0.01)`, `score = clamp(1.0 - ratio/2.0, 0, 1)`
- Verdict thresholds: effective > 0.6, neutral 0.4-0.6, ineffective < 0.4
- `category_source` field on RuleBaseline: "heuristic" (auto) or "manual" (user override)
- Hooks send 1 HTTP request per failure event with joined error details (not N requests)
- AnalyticsDB shares sqlite3.Connection with LearningDatabase via `db.analytics` lazy property
- Hook failure recording is best-effort (try/except: pass) — never blocks hooks
- No new runtime dependencies — uses stdlib + existing pydantic/httpx

### Plugin

- `plugin/` directory is the Claude Code plugin (separate from `.claude/` which is for framework development)
- `stratus hook <module>` CLI subcommand is the single entry point for all plugin hooks
- Plugin hooks use `stratus hook <module>` instead of `uv run python -m stratus.hooks.<module>`
- Plugin manifest at `plugin/.claude-plugin/plugin.json`
- Plugin MCP config at `plugin/.mcp.json` (uses `stratus mcp-serve` directly, no `uv run`)
- Core agents generalized: `framework-expert` → `implementation-expert`, stratus-specific refs removed
- Delivery agents copied verbatim from `src/stratus/runtime_agents/agents/`
- Core skills generalized: detect project type dynamically instead of hardcoding `uv run pytest`
- Delivery skills copied verbatim from `src/stratus/runtime_agents/skills/`

### Release & Distribution

- `__version__` sourced from `importlib.metadata` (single source of truth: pyproject.toml)
- `routes_system.VERSION` imports `__version__` — no hardcoded version strings
- `--version` / `-V` flag on CLI via argparse `action="version"`
- Installer scripts (`scripts/install.sh`, `scripts/uninstall.sh`) are POSIX sh, no sudo
- Installer prefers pipx, falls back to venv at `~/.local/share/stratus/venv`
- Release workflow triggers on `v*` tag push, verifies tag matches pyproject.toml version
- PyPI publish uses OIDC trusted publisher via `pypa/gh-action-pypi-publish` (no API tokens)
- GitHub Release created automatically with dist artifacts and auto-generated notes
