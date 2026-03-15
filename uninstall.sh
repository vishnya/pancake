#!/bin/bash
set -euo pipefail

LOCAL_BIN="$HOME/.local/bin"
INIT_LUA="$HOME/code/anki_fox/hammerspoon/init.lua"
CLAUDE_COMMANDS="$HOME/.claude/commands"
VAULT_DIR="$HOME/Obsidian/main"
PANCAKE_DIR="$HOME/code/pancake"
OBSIDIAN_HOTKEYS="$VAULT_DIR/.obsidian/hotkeys.json"
PLIST_DST="$HOME/Library/LaunchAgents/com.pancake.plist"

echo "Uninstalling Pancake..."

# 1. Unload and remove launchd agent
if [ -f "$PLIST_DST" ]; then
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    rm "$PLIST_DST"
    echo "Removed launchd agent"
fi

# 2. Kill any running server
lsof -ti:5790 2>/dev/null | xargs kill -9 2>/dev/null || true

# 3. Remove CLI symlink
if [ -L "$LOCAL_BIN/pk" ]; then
    rm "$LOCAL_BIN/pk"
    echo "Removed: $LOCAL_BIN/pk"
fi

# 4. Remove Hammerspoon hotkey lines
if [ -f "$INIT_LUA" ] && grep -q "pancake_hotkey.lua" "$INIT_LUA"; then
    sed -i '' '/-- Pancake hotkeys/d' "$INIT_LUA"
    sed -i '' '/-- Pancake quick capture/d' "$INIT_LUA"
    sed -i '' '/pancake_hotkey\.lua/d' "$INIT_LUA"
    sed -i '' -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$INIT_LUA"
    echo "Removed Hammerspoon hotkey"
fi

# 5. Remove Claude commands
for cmd in morning.md think.md; do
    if [ -f "$CLAUDE_COMMANDS/$cmd" ]; then
        rm "$CLAUDE_COMMANDS/$cmd"
        echo "Removed Claude command: $cmd"
    fi
done

# 6. Remove Obsidian hotkeys added by Pancake
if [ -f "$OBSIDIAN_HOTKEYS" ] && grep -q "swap-line-up" "$OBSIDIAN_HOTKEYS"; then
    python3 -c "
import json
with open('$OBSIDIAN_HOTKEYS') as f:
    hotkeys = json.load(f)
hotkeys.pop('editor:swap-line-up', None)
hotkeys.pop('editor:swap-line-down', None)
with open('$OBSIDIAN_HOTKEYS', 'w') as f:
    json.dump(hotkeys, f, indent=2)
    f.write('\n')
"
    echo "Removed Obsidian line-swap hotkeys"
fi

# 7. Remove /etc/hosts alias
if grep -q "^127.0.0.1.*pancake$" /etc/hosts 2>/dev/null; then
    echo ""
    echo "To remove the 'pancake' host alias, run:"
    echo "  sudo sed -i '' '/^127.0.0.1.*pancake$/d' /etc/hosts"
    echo ""
fi

# 8. Prompt for PRIORITIES.md
if [ -f "$VAULT_DIR/PRIORITIES.md" ]; then
    read -p "Delete $VAULT_DIR/PRIORITIES.md? This removes all your priorities. [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm "$VAULT_DIR/PRIORITIES.md"
        echo "Removed: PRIORITIES.md"
    else
        echo "Kept: PRIORITIES.md"
    fi
fi

# 9. Prompt for Projects directory
if [ -d "$VAULT_DIR/Projects" ]; then
    read -p "Delete $VAULT_DIR/Projects/ directory? [y/N] " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VAULT_DIR/Projects"
        echo "Removed: Projects/"
    else
        echo "Kept: Projects/"
    fi
fi

# 10. Prompt for project directory
read -p "Delete $PANCAKE_DIR/ project directory? [y/N] " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$PANCAKE_DIR"
    echo "Removed: $PANCAKE_DIR"
else
    echo "Kept: $PANCAKE_DIR"
fi

# 11. Reload Hammerspoon if running
if pgrep -x Hammerspoon > /dev/null 2>&1; then
    hs -c "hs.reload()" 2>/dev/null && echo "Hammerspoon reloaded" || true
fi

echo "Pancake uninstalled."
