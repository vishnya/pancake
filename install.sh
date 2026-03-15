#!/bin/bash
set -euo pipefail

PANCAKE_DIR="$HOME/code/pancake"
VAULT_DIR="$HOME/Obsidian/main"
LOCAL_BIN="$HOME/.local/bin"
INIT_LUA="$HOME/code/anki_fox/hammerspoon/init.lua"
CLAUDE_COMMANDS="$HOME/.claude/commands"
OBSIDIAN_HOTKEYS="$VAULT_DIR/.obsidian/hotkeys.json"
PLIST_SRC="$PANCAKE_DIR/launchd/com.pancake.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.pancake.plist"
DOFILE_LINE='dofile(os.getenv("HOME") .. "/code/pancake/hammerspoon/pancake_hotkey.lua")'
DOFILE_COMMENT="-- Pancake hotkeys"

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

# 2. Symlink pk CLI
mkdir -p "$LOCAL_BIN"
ln -sf "$PANCAKE_DIR/.venv/bin/pk" "$LOCAL_BIN/pk"
echo "Installed: pk -> $LOCAL_BIN/pk"

# 3. Create PRIORITIES.md if not present
if [ ! -f "$VAULT_DIR/PRIORITIES.md" ]; then
    mkdir -p "$VAULT_DIR"
    cp "$PANCAKE_DIR/templates/PRIORITIES.md" "$VAULT_DIR/PRIORITIES.md"
    echo "Created: $VAULT_DIR/PRIORITIES.md"
else
    echo "Skipped: PRIORITIES.md already exists"
fi

# 4. Create Projects directory in Obsidian vault
mkdir -p "$VAULT_DIR/Projects"

# 5. Add Hammerspoon hotkey
if [ -f "$INIT_LUA" ]; then
    if ! grep -q "pancake_hotkey.lua" "$INIT_LUA"; then
        echo "" >> "$INIT_LUA"
        echo "$DOFILE_COMMENT" >> "$INIT_LUA"
        echo "$DOFILE_LINE" >> "$INIT_LUA"
        echo "Added Hammerspoon hotkey (Cmd+Shift+P opens web UI)"
    else
        echo "Skipped: Hammerspoon hotkey already configured"
    fi
else
    echo "Warning: $INIT_LUA not found. Hammerspoon hotkey not installed."
fi

# 6. Configure Obsidian hotkeys (Alt+Up/Down)
if [ -f "$OBSIDIAN_HOTKEYS" ]; then
    if ! grep -q "swap-line-up" "$OBSIDIAN_HOTKEYS"; then
        python3 -c "
import json
with open('$OBSIDIAN_HOTKEYS') as f:
    hotkeys = json.load(f)
hotkeys['editor:swap-line-up'] = [{'modifiers': ['Alt'], 'key': 'ArrowUp'}]
hotkeys['editor:swap-line-down'] = [{'modifiers': ['Alt'], 'key': 'ArrowDown'}]
with open('$OBSIDIAN_HOTKEYS', 'w') as f:
    json.dump(hotkeys, f, indent=2)
    f.write('\n')
"
        echo "Configured Obsidian hotkeys: Alt+Up/Down"
    else
        echo "Skipped: Obsidian hotkeys already configured"
    fi
else
    echo "Warning: Obsidian hotkeys.json not found. Skipping."
fi

# 7. Install Claude commands
mkdir -p "$CLAUDE_COMMANDS"
cp "$PANCAKE_DIR/claude/morning.md" "$CLAUDE_COMMANDS/morning.md"
cp "$PANCAKE_DIR/claude/think.md" "$CLAUDE_COMMANDS/think.md"
echo "Installed Claude commands: /morning, /think"

# 8. Install launchd agent (auto-start web UI on login)
VENV_PYTHON="$PANCAKE_DIR/.venv/bin/python"
sed -e "s|__VENV_PYTHON__|$VENV_PYTHON|g" \
    -e "s|__PANCAKE_DIR__|$PANCAKE_DIR|g" \
    "$PLIST_SRC" > "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "Installed launchd agent: web UI auto-starts on login (port 5790)"

# 9. Add /etc/hosts alias (requires sudo)
if ! grep -q "^127.0.0.1.*pancake$" /etc/hosts 2>/dev/null; then
    echo ""
    echo "To access the UI at http://pancake:5790 instead of http://localhost:5790, run:"
    echo "  echo '127.0.0.1 pancake' | sudo tee -a /etc/hosts"
    echo ""
fi

# 10. Reload Hammerspoon if running
if pgrep -x Hammerspoon > /dev/null 2>&1; then
    hs -c "hs.reload()" 2>/dev/null && echo "Hammerspoon reloaded" || echo "Note: reload Hammerspoon manually"
fi

echo ""
echo "Pancake installed!"
echo "  Web UI: https://5.161.182.15.nip.io"
echo "  CLI:    pk status"
echo "  Hotkey: Cmd+Shift+P opens web UI"
echo "  Logs:   tail -f /tmp/pancake.log"
