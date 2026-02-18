---
description: Manage git worktrees for spec-driven development
---

Manage git worktrees:

```bash
stratus worktree $ARGUMENTS
```

Actions:
- `detect <slug>` — check if a worktree exists for the given slug
- `create <slug>` — create a new worktree on branch `spec/<slug>`
- `diff <slug>` — show diff between the spec branch and base branch
- `sync <slug>` — squash-merge the spec branch back to the base branch
- `cleanup <slug>` — remove the worktree and delete the branch
- `status <slug>` — show worktree status as JSON

Options:
- `--plan-path <path>` — plan file path used for hash generation
- `--base-branch <branch>` — base branch (default: main)
