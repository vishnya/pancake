#!/bin/bash
set -euo pipefail

PANCAKE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing Pancake..."

# 1. Python environment (uv preferred, pip fallback)
echo "Setting up Python environment..."
if command -v uv &>/dev/null; then
    uv venv "$PANCAKE_DIR/.venv" -q 2>/dev/null || true
    uv pip install -q -e "$PANCAKE_DIR" -p "$PANCAKE_DIR/.venv/bin/python"
else
    python3 -m venv "$PANCAKE_DIR/.venv"
    "$PANCAKE_DIR/.venv/bin/pip" install -q -e "$PANCAKE_DIR"
fi

# 2. Symlink pk CLI (optional, if ~/.local/bin exists or user wants it)
LOCAL_BIN="${HOME}/.local/bin"
if [ -d "$LOCAL_BIN" ] || mkdir -p "$LOCAL_BIN" 2>/dev/null; then
    ln -sf "$PANCAKE_DIR/.venv/bin/pk" "$LOCAL_BIN/pk"
    echo "Installed: pk -> $LOCAL_BIN/pk"
fi

# 3. Create data directories
DATA_DIR="${PANCAKE_DATA_ROOT:-$PANCAKE_DIR}"
mkdir -p "$DATA_DIR/vault" "$DATA_DIR/data" "$DATA_DIR/config"
echo "Data directory: $DATA_DIR"

# 4. Create default PRIORITIES.md if not present
VAULT_PATH="${PANCAKE_VAULT:-}"
if [ -z "$VAULT_PATH" ]; then
    # Default: vault/personal/PRIORITIES.md
    mkdir -p "$DATA_DIR/vault/default"
    if [ ! -f "$DATA_DIR/vault/default/PRIORITIES.md" ]; then
        if [ -f "$PANCAKE_DIR/templates/PRIORITIES.md" ]; then
            cp "$PANCAKE_DIR/templates/PRIORITIES.md" "$DATA_DIR/vault/default/PRIORITIES.md"
            echo "Created: vault/default/PRIORITIES.md"
        fi
    fi
fi

# 5. Install Claude commands (if claude is installed)
CLAUDE_COMMANDS="${HOME}/.claude/commands"
if [ -d "${HOME}/.claude" ] || command -v claude &>/dev/null; then
    mkdir -p "$CLAUDE_COMMANDS"
    for cmd in morning think; do
        if [ -f "$PANCAKE_DIR/claude/${cmd}.md" ]; then
            cp "$PANCAKE_DIR/claude/${cmd}.md" "$CLAUDE_COMMANDS/${cmd}.md"
        fi
    done
    echo "Installed Claude commands: /morning, /think"
fi

# 6. Mac-specific: Hammerspoon + launchd (skip on Linux)
if [[ "$(uname)" == "Darwin" ]]; then
    # Hammerspoon hotkey
    INIT_LUA="${HOME}/code/anki_fox/hammerspoon/init.lua"
    DOFILE_LINE="dofile(os.getenv(\"HOME\") .. \"/code/pancake/hammerspoon/pancake_hotkey.lua\")"
    if [ -f "$INIT_LUA" ] && ! grep -q "pancake_hotkey.lua" "$INIT_LUA"; then
        echo "" >> "$INIT_LUA"
        echo "-- Pancake hotkeys" >> "$INIT_LUA"
        echo "$DOFILE_LINE" >> "$INIT_LUA"
        echo "Added Hammerspoon hotkey (Cmd+Shift+P)"
    fi

    # launchd agent
    PLIST_SRC="$PANCAKE_DIR/launchd/com.pancake.plist"
    PLIST_DST="$HOME/Library/LaunchAgents/com.pancake.plist"
    if [ -f "$PLIST_SRC" ]; then
        VENV_PYTHON="$PANCAKE_DIR/.venv/bin/python"
        sed -e "s|__VENV_PYTHON__|$VENV_PYTHON|g" \
            -e "s|__PANCAKE_DIR__|$PANCAKE_DIR|g" \
            "$PLIST_SRC" > "$PLIST_DST"
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        launchctl load "$PLIST_DST"
        echo "Installed launchd agent: web UI auto-starts on login"
    fi
fi

echo ""
echo "Pancake installed!"
echo ""
echo "  Start the web UI:"
echo "    $PANCAKE_DIR/.venv/bin/python -m web.server"
echo ""
echo "  Then open http://localhost:5790 in your browser."
echo "  You'll be prompted to create your first account."
echo ""
if [ -f "$LOCAL_BIN/pk" ]; then
    echo "  CLI: pk status"
fi
