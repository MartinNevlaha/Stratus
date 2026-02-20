#!/bin/sh
# stratus installer
# Installs stratus from GitHub. No sudo, no binary downloads.
# Re-running upgrades an existing installation.
set -e

MIN_MAJOR=3
MIN_MINOR=12
REPO="MartinNevlaha/Stratus"
PACKAGE="stratus @ git+https://github.com/${REPO}.git"
VENV_DIR="${HOME}/.local/share/stratus/venv"
BIN_DIR="${HOME}/.local/bin"

log() { printf '%s\n' "$1"; }
err() { printf 'Error: %s\n' "$1" >&2; exit 1; }

# --- Find a suitable Python >= 3.12 ---
find_python() {
    for candidate in python3.14 python3.13 python3.12 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            py_version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || continue
            py_major=$(echo "$py_version" | cut -d. -f1)
            py_minor=$(echo "$py_version" | cut -d. -f2)
            if [ "$py_major" -ge "$MIN_MAJOR" ] && [ "$py_minor" -ge "$MIN_MINOR" ]; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python) || err "Python >= ${MIN_MAJOR}.${MIN_MINOR} not found. Install it first."
log "Found Python: $PYTHON ($($PYTHON --version 2>&1))"

# --- Try pipx first (preferred) ---
if command -v pipx >/dev/null 2>&1; then
    log "Using pipx..."
    if pipx list 2>/dev/null | grep -q "stratus"; then
        pipx upgrade stratus --python "$PYTHON"
    else
        pipx install "git+https://github.com/${REPO}.git" --python "$PYTHON"
    fi
    log ""
    log "Installed via pipx. Run 'pipx upgrade stratus' to update later."
    stratus --version
else
    # --- Fallback: venv + pip ---
    log "pipx not found, using venv at $VENV_DIR"

    if [ -d "$VENV_DIR" ]; then
        log "Upgrading existing installation..."
        "$VENV_DIR/bin/pip" install --upgrade "$PACKAGE"
    else
        log "Creating virtual environment..."
        "$PYTHON" -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1
        "$VENV_DIR/bin/pip" install "$PACKAGE"
    fi

    # --- Create wrapper script ---
    mkdir -p "$BIN_DIR"
    wrapper="$BIN_DIR/stratus"
    cat > "$wrapper" <<WRAPPER
#!/bin/sh
exec "$VENV_DIR/bin/stratus" "\$@"
WRAPPER
    chmod +x "$wrapper"

    # --- PATH check ---
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *)
            log ""
            log "WARNING: $BIN_DIR is not in your PATH."
            log "Add this to your shell profile:"
            log "  export PATH=\"$BIN_DIR:\$PATH\""
            ;;
    esac

    log ""
    "$wrapper" --version
fi

# --- Resolve stratus binary path ---
STRATUS_BIN="stratus"
if ! command -v "$STRATUS_BIN" >/dev/null 2>&1; then
    if [ -f "$BIN_DIR/stratus" ]; then
        STRATUS_BIN="$BIN_DIR/stratus"
    elif [ -f "$VENV_DIR/bin/stratus" ]; then
        STRATUS_BIN="$VENV_DIR/bin/stratus"
    fi
fi

# --- Init: register hooks, MCP server, start HTTP server ---
# When piped (curl | sh), stdin is the pipe — reconnect to /dev/tty
# so stratus init interactive prompts work. If /dev/tty is unavailable
# (e.g. CI), fall back to non-interactive auto-detect.
log ""
if [ -t 0 ]; then
    # Already interactive (script run directly)
    log "Running stratus init..."
    if "$STRATUS_BIN" init; then
        log ""
        log "Installation complete. Hooks and MCP are ready."
        log "Start the HTTP server with: stratus serve"
    else
        log ""
        log "Installation complete. Run 'stratus init' to finish setup."
    fi
elif [ -e /dev/tty ]; then
    # Piped (curl | sh) but terminal available — reconnect stdin
    log "Running stratus init..."
    if "$STRATUS_BIN" init </dev/tty; then
        log ""
        log "Installation complete. Hooks and MCP are ready."
        log "Start the HTTP server with: stratus serve"
    else
        log ""
        log "Installation complete. Run 'stratus init' to finish setup."
    fi
else
    # No terminal (CI/Docker) — auto-detect scope
    if git rev-parse --show-toplevel >/dev/null 2>&1; then
        log "Git repository detected — running project-local init..."
        INIT_SCOPE="local"
    else
        log "No git repository — running global init..."
        INIT_SCOPE="global"
    fi
    if "$STRATUS_BIN" init --scope "$INIT_SCOPE"; then
        log ""
        log "Installation complete. Hooks and MCP are ready."
        log "Start the HTTP server with: stratus serve"
    else
        log ""
        log "Installation complete. Run 'stratus init' to finish setup."
    fi
fi
