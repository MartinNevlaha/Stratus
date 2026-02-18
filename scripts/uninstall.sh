#!/bin/sh
# stratus complete uninstaller
# Removes binary, data, hooks, MCP config, and project artifacts.
# Usage: uninstall.sh [--project] [--yes]
#   --project  Also clean stratus artifacts from the current git repo
#   --yes      Skip confirmation prompts
set -e

PACKAGE="stratus"
VENV_DIR="${HOME}/.local/share/stratus/venv"
BIN_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.ai-framework"
MANAGED_MARKER="<!-- managed-by: stratus"

clean_project=0
skip_confirm=0
for arg in "$@"; do
    case "$arg" in
        --project) clean_project=1 ;;
        --yes) skip_confirm=1 ;;
        -h|--help)
            printf 'Usage: %s [--project] [--yes]\n' "$0"
            printf '  --project  Also clean stratus artifacts from current git repo\n'
            printf '  --yes      Skip confirmation prompts\n'
            exit 0
            ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; exit 1 ;;
    esac
done

log() { printf '%s\n' "$1"; }
warn() { printf 'WARNING: %s\n' "$1" >&2; }

confirm() {
    if [ "$skip_confirm" -eq 1 ]; then return 0; fi
    printf '%s [y/N] ' "$1"
    if [ -t 0 ]; then
        read -r answer
    elif [ -e /dev/tty ]; then
        read -r answer </dev/tty
    else
        answer="n"
    fi
    case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

removed=0

# =========================================================================
# 1. Remove binary (pipx or venv)
# =========================================================================
if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "$PACKAGE"; then
    log "Removing pipx installation..."
    pipx uninstall "$PACKAGE"
    removed=1
fi

if [ -d "$VENV_DIR" ]; then
    log "Removing venv at $VENV_DIR..."
    rm -rf "$VENV_DIR"
    removed=1
fi

wrapper="$BIN_DIR/stratus"
if [ -f "$wrapper" ]; then
    log "Removing wrapper at $wrapper..."
    rm -f "$wrapper"
    removed=1
fi

# =========================================================================
# 2. Remove data directory (~/.ai-framework/)
# =========================================================================
if [ -d "$DATA_DIR" ]; then
    log "Found data directory: $DATA_DIR"
    if confirm "Remove data directory (memory DB, learning DB, indexes)?"; then
        rm -rf "$DATA_DIR"
        log "Removed $DATA_DIR"
        removed=1
    else
        log "Skipped data directory"
    fi
fi

# =========================================================================
# 3. Clean global hooks from ~/.claude/settings.json
# =========================================================================
global_settings="${HOME}/.claude/settings.json"
if [ -f "$global_settings" ]; then
    if grep -q "stratus.hooks" "$global_settings" 2>/dev/null; then
        log "Removing stratus hooks from $global_settings..."
        python3 -c "
import json, sys
p = '$global_settings'
with open(p) as f: d = json.load(f)
hooks = d.get('hooks', {})
changed = False
for event in list(hooks.keys()):
    groups = hooks[event]
    filtered = []
    for g in groups:
        cmds = [h for h in g.get('hooks', []) if 'stratus.hooks.' not in h.get('command', '')]
        if cmds:
            g['hooks'] = cmds
            filtered.append(g)
    if len(filtered) != len(groups):
        changed = True
    hooks[event] = filtered
# Remove empty event keys
for event in list(hooks.keys()):
    if not hooks[event]:
        del hooks[event]
if not hooks:
    del d['hooks']
elif changed:
    d['hooks'] = hooks
if changed:
    with open(p, 'w') as f: json.dump(d, f, indent=2)
    print('Cleaned hooks from global settings')
else:
    print('No stratus hooks in global settings')
" 2>/dev/null || warn "Could not clean global settings (python3 needed)"
        removed=1
    fi
fi

# =========================================================================
# 4. Clean global MCP from ~/.claude/.mcp.json
# =========================================================================
global_mcp="${HOME}/.claude/.mcp.json"
if [ -f "$global_mcp" ]; then
    if grep -q "stratus-memory" "$global_mcp" 2>/dev/null; then
        log "Removing stratus-memory from $global_mcp..."
        python3 -c "
import json
p = '$global_mcp'
with open(p) as f: d = json.load(f)
servers = d.get('mcpServers', {})
if 'stratus-memory' in servers:
    del servers['stratus-memory']
    if servers:
        d['mcpServers'] = servers
        with open(p, 'w') as f: json.dump(d, f, indent=2)
    else:
        import os; os.remove(p)
    print('Removed stratus-memory from global MCP config')
" 2>/dev/null || warn "Could not clean global MCP config (python3 needed)"
        removed=1
    fi
fi

# =========================================================================
# 5. Clean project-local files (only with --project)
# =========================================================================
if [ "$clean_project" -eq 1 ]; then
    git_root=$(git rev-parse --show-toplevel 2>/dev/null) || true
    if [ -z "$git_root" ]; then
        warn "Not in a git repo, skipping project cleanup"
    else
        log "Cleaning stratus artifacts from $git_root..."

        # 5a. Project hooks in .claude/settings.json
        proj_settings="$git_root/.claude/settings.json"
        if [ -f "$proj_settings" ] && grep -q "stratus.hooks" "$proj_settings" 2>/dev/null; then
            log "  Removing hooks from $proj_settings..."
            python3 -c "
import json
p = '$proj_settings'
with open(p) as f: d = json.load(f)
hooks = d.get('hooks', {})
for event in list(hooks.keys()):
    groups = hooks[event]
    filtered = []
    for g in groups:
        cmds = [h for h in g.get('hooks', []) if 'stratus.hooks.' not in h.get('command', '')]
        if cmds:
            g['hooks'] = cmds
            filtered.append(g)
        hooks[event] = filtered
    for event in list(hooks.keys()):
        if not hooks[event]:
            del hooks[event]
if not hooks and len(d) == 1:
    import os; os.remove(p)
else:
    if not hooks and 'hooks' in d:
        del d['hooks']
    with open(p, 'w') as f: json.dump(d, f, indent=2)
print('Cleaned project hooks')
" 2>/dev/null || warn "Could not clean project settings"
            removed=1
        fi

        # 5b. Project MCP (.mcp.json)
        proj_mcp="$git_root/.mcp.json"
        if [ -f "$proj_mcp" ] && grep -q "stratus-memory" "$proj_mcp" 2>/dev/null; then
            log "  Removing stratus-memory from $proj_mcp..."
            python3 -c "
import json, os
p = '$proj_mcp'
with open(p) as f: d = json.load(f)
servers = d.get('mcpServers', {})
if 'stratus-memory' in servers:
    del servers['stratus-memory']
if not servers:
    os.remove(p)
else:
    d['mcpServers'] = servers
    with open(p, 'w') as f: json.dump(d, f, indent=2)
print('Cleaned project MCP config')
" 2>/dev/null || warn "Could not clean project MCP config"
            removed=1
        fi

        # 5c. Clear Vexor index for this project (if binary available)
        if command -v vexor >/dev/null 2>&1; then
            log "  Clearing Vexor index for $git_root..."
            vexor index --clear --path "$git_root" 2>/dev/null && log "  Vexor index cleared" \
                || warn "Could not clear Vexor index"
        fi

        # 5d. Remove worktrees (.worktrees/spec-*)
        worktrees_dir="$git_root/.worktrees"
        if [ -d "$worktrees_dir" ]; then
            log "  Removing worktrees at $worktrees_dir..."
            for wt in "$worktrees_dir"/spec-*; do
                [ -d "$wt" ] || continue
                git -C "$git_root" worktree remove --force "$wt" 2>/dev/null \
                    || rm -rf "$wt"
                removed=1
            done
            # Remove empty .worktrees dir
            rmdir "$worktrees_dir" 2>/dev/null || true
            # Clean up spec/* branches
            for branch in $(git -C "$git_root" branch --list 'spec/*' 2>/dev/null); do
                log "  Deleting branch $branch"
                git -C "$git_root" branch -D "$branch" 2>/dev/null || true
                removed=1
            done
        fi

        # 5e. Config files
        for f in ".ai-framework.json" "project-graph.json"; do
            target="$git_root/$f"
            if [ -f "$target" ]; then
                log "  Removing $f"
                rm -f "$target"
                removed=1
            fi
        done

        # 5f. Managed agent files (.claude/agents/delivery-*.md)
        agents_dir="$git_root/.claude/agents"
        if [ -d "$agents_dir" ]; then
            for f in "$agents_dir"/delivery-*.md; do
                [ -f "$f" ] || continue
                if head -1 "$f" 2>/dev/null | grep -q "$MANAGED_MARKER"; then
                    log "  Removing managed agent: $(basename "$f")"
                    rm -f "$f"
                    removed=1
                fi
            done
        fi

        # 5g. Managed skill files (.claude/skills/*/SKILL.md)
        skills_dir="$git_root/.claude/skills"
        if [ -d "$skills_dir" ]; then
            for f in "$skills_dir"/*/SKILL.md; do
                [ -f "$f" ] || continue
                if head -1 "$f" 2>/dev/null | grep -q "$MANAGED_MARKER"; then
                    skill_dir=$(dirname "$f")
                    log "  Removing managed skill: $(basename "$skill_dir")"
                    rm -rf "$skill_dir"
                    removed=1
                fi
            done
        fi

        log "Project cleanup complete"
    fi
fi

# =========================================================================
# Summary
# =========================================================================
if [ "$removed" -eq 0 ]; then
    log "No stratus installation found."
else
    log ""
    log "Uninstall complete."
    if [ "$clean_project" -eq 0 ]; then
        log "Tip: run with --project to also remove artifacts from the current repo."
    fi
fi
