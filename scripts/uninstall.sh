#!/bin/sh
# stratus uninstaller
# Removes stratus installed via pipx or the venv fallback.
set -e

PACKAGE="stratus"
VENV_DIR="${HOME}/.local/share/stratus/venv"
BIN_DIR="${HOME}/.local/bin"
removed=0

log() { printf '%s\n' "$1"; }

# --- pipx ---
if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "$PACKAGE"; then
    log "Removing pipx installation..."
    pipx uninstall "$PACKAGE"
    removed=1
fi

# --- venv fallback ---
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

if [ "$removed" -eq 0 ]; then
    log "No stratus installation found."
else
    log "Uninstall complete."
fi
