---
name: learn
description: "Learning proposal lifecycle. Use when asked to /learn."
context: fork
---

# Learning Coordinator

You are the coordinator for the learning proposal lifecycle. You orchestrate work by delegating to specialized agents. You do NOT create proposals directly.

## Prerequisites

Learning must be enabled in `.ai-framework.json`:
```json
{
  "learning": {
    "global_enabled": true
  }
}
```

Or via environment variable: `AI_FRAMEWORK_LEARNING_ENABLED=true`

## Workflow

### Phase 1: Analyze

Delegate to `delivery-learning-analyst` to trigger analysis and fetch proposals:

```
Use Task tool with subagent_type: delivery-learning-analyst
```

The analyst will:
1. Call `POST /api/learning/analyze` to trigger pattern detection
2. Fetch pending proposals via `GET /api/learning/proposals`
3. Return a structured report with all proposals

**If analyst returns 0 proposals:** Inform user "No learning proposals found. Run `/learn analyze` after more commits to detect patterns."

### Phase 2: Review

Present each proposal from the analyst report to the user:

For each proposal display:
- **ID**: proposal_id
- **Title**: what pattern was detected
- **Type**: rule / adr / template / skill / project_graph
- **Confidence**: 0.0 - 1.0 (higher = more certain)
- **Rationale**: why this proposal was generated
- **Files affected**: which files triggered this
- **Content Preview**: first few lines of proposed content

Ask the user for each proposal:
- `accept` - Create the artifact (rule, ADR, etc.)
- `reject` - Discard the proposal
- `edit` - Accept with modified content
- `skip` - Leave pending for later

### Phase 3: Decide

Record each decision via API:

```bash
curl -s -X POST http://127.0.0.1:41777/api/learning/decide \
  -H 'Content-Type: application/json' \
  -d '{"proposal_id": "<ID>", "decision": "accept"}' 2>/dev/null | jq .
```

For `edit`:
```bash
curl -s -X POST http://127.0.0.1:41777/api/learning/decide \
  -H 'Content-Type: application/json' \
  -d '{"proposal_id": "<ID>", "decision": "accept", "edited_content": "..."}' 2>/dev/null | jq .
```

### Phase 4: Summary

After all decisions, show updated stats:

```bash
curl -s http://127.0.0.1:41777/api/learning/stats 2>/dev/null | jq .
```

## Subcommands (via $ARGUMENTS)

- `/learn` or `/learn review` - Full workflow: analyze + review + decide
- `/learn analyze` - Only trigger analysis (no review)
- `/learn stats` - Show statistics only
- `/learn config` - Show current config

## Artifact Locations

When proposals are accepted, artifacts are created automatically at:

| Type | Location |
|------|----------|
| rule | `.claude/rules/<slug>.md` |
| adr | `docs/decisions/<slug>.md` |
| template | `.claude/templates/<slug>.md` |
| skill | `.claude/skills/<slug>/prompt.md` |
| project_graph | `.ai-framework/project-graph.json` |

## Rules

- **NEVER** create proposals directly — delegate to `delivery-learning-analyst`
- **NEVER** write artifacts directly — created automatically on accept
- Present proposals one at a time for user decision
- All API calls are fire-and-forget via Bash + curl

## Dashboard

For a visual interface, open: http://localhost:41777/dashboard

## Error Handling

If the server is not running:
```bash
stratus serve &
```

If learning is disabled, explain how to enable it (see Prerequisites).
