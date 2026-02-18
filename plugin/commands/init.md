---
description: Initialize stratus for the current project (detect services, register hooks, configure MCP)
---

Run project initialization:

```bash
stratus init $ARGUMENTS
```

This detects services in the project, generates `project-graph.json` and `.ai-framework.json`, registers hooks in `.claude/settings.json`, and configures the MCP server in `.mcp.json`.

Common flags:
- `--dry-run` — preview changes without writing files
- `--force` — overwrite existing config
- `--scope global` — install to `~/.claude/` instead of the project
- `--enable-delivery` — install delivery agents and skills
- `--skip-hooks` / `--skip-mcp` / `--skip-retrieval` / `--skip-agents` — skip specific steps
