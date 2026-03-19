#!/bin/bash
set -euo pipefail

# Pancake installer -- works on locked-down servers and personal machines alike.
# Usage: bash install.sh (from the pancake directory)

PANCAKE_DIR="${PANCAKE_DIR:-$HOME/pancake}"
ENV_FILE="$PANCAKE_DIR/.env"
BOLD="\033[1m"
DIM="\033[2m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}Pancake Installer${RESET}"
echo ""

# ── Step 1: Clone or find the repo ──────────────────────────────────────────

if [ -d "$PANCAKE_DIR/.git" ]; then
    echo -e "Found existing install at ${GREEN}$PANCAKE_DIR${RESET}"
    cd "$PANCAKE_DIR"
    git pull -q origin main 2>/dev/null || true
elif [ -d "$PANCAKE_DIR" ] && [ -f "$PANCAKE_DIR/pyproject.toml" ]; then
    echo -e "Found existing install at ${GREEN}$PANCAKE_DIR${RESET} (no git)"
    cd "$PANCAKE_DIR"
else
    echo "Cloning Pancake..."
    if git clone -q https://github.com/vishnya/pancake.git "$PANCAKE_DIR" 2>/dev/null; then
        cd "$PANCAKE_DIR"
    else
        echo ""
        echo -e "${RED}Could not reach github.com.${RESET}"
        echo "Copy the repo to $PANCAKE_DIR manually, then re-run this script."
        echo ""
        echo "  From a machine with access:"
        echo "    git clone https://github.com/vishnya/pancake.git"
        echo "    scp -r pancake $(whoami)@$(hostname):~/pancake"
        echo ""
        exit 1
    fi
fi

# ── Step 2: Check if installing inside an existing source repository ────────

INSIDE_REPO=false
REPO_ROOT=""

if git -C "$PANCAKE_DIR" rev-parse --show-toplevel &>/dev/null; then
    REPO_ROOT=$(git -C "$PANCAKE_DIR" rev-parse --show-toplevel 2>/dev/null)
    [ "$REPO_ROOT" != "$PANCAKE_DIR" ] && INSIDE_REPO=true
elif command -v sl &>/dev/null && sl -R "$PANCAKE_DIR" root &>/dev/null 2>&1; then
    REPO_ROOT=$(sl -R "$PANCAKE_DIR" root 2>/dev/null)
    [ "$REPO_ROOT" != "$PANCAKE_DIR" ] && INSIDE_REPO=true
elif command -v hg &>/dev/null && hg -R "$PANCAKE_DIR" root &>/dev/null 2>&1; then
    REPO_ROOT=$(hg -R "$PANCAKE_DIR" root 2>/dev/null)
    [ "$REPO_ROOT" != "$PANCAKE_DIR" ] && INSIDE_REPO=true
fi

if [ "$INSIDE_REPO" = true ]; then
    echo ""
    echo -e "${YELLOW}WARNING: $PANCAKE_DIR is inside a source repository ($REPO_ROOT).${RESET}"
    echo "Pancake should be installed outside of any source repo"
    echo "to avoid accidentally committing personal data."
    echo ""
    read -p "Continue anyway? [y/N]: " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy] ]]; then
        echo "Aborted. Move the pancake directory outside of $REPO_ROOT and try again."
        exit 1
    fi
fi

# ── Step 3: Add Pancake to global ignore files for all VCS tools ────────────

# Global git ignore
GLOBAL_GITIGNORE="${HOME}/.config/git/ignore"
mkdir -p "$(dirname "$GLOBAL_GITIGNORE")"
touch "$GLOBAL_GITIGNORE"
if ! grep -q "pancake" "$GLOBAL_GITIGNORE"; then
    echo "" >> "$GLOBAL_GITIGNORE"
    echo "# Pancake (personal tool, not production code)" >> "$GLOBAL_GITIGNORE"
    echo "pancake/" >> "$GLOBAL_GITIGNORE"
fi
git config --global core.excludesFile "$GLOBAL_GITIGNORE"

# Global Mercurial/Sapling ignore
GLOBAL_HGIGNORE="${HOME}/.hgignore_global"
touch "$GLOBAL_HGIGNORE"
if ! grep -q "pancake" "$GLOBAL_HGIGNORE"; then
    echo "" >> "$GLOBAL_HGIGNORE"
    echo "# Pancake (personal tool, not production code)" >> "$GLOBAL_HGIGNORE"
    echo "syntax: glob" >> "$GLOBAL_HGIGNORE"
    echo "pancake/" >> "$GLOBAL_HGIGNORE"
fi

# ── Step 4: Python venv setup with proxy awareness ─────────────────────────

echo "Setting up Python..."

# Find best Python (prefer 3.12+ if available)
PYTHON=$(command -v python3.12 || command -v python3)

if [ -z "$PYTHON" ]; then
    echo -e "${RED}Python 3.10+ is required but not found.${RESET}"
    exit 1
fi

# Create venv
"$PYTHON" -m venv "$PANCAKE_DIR/.venv"

# Install with proxy if set in environment, otherwise without
PIP_PROXY=""
if [ -n "${https_proxy:-$HTTPS_PROXY}" ]; then
    PIP_PROXY="--proxy ${https_proxy:-$HTTPS_PROXY}"
fi

"$PANCAKE_DIR/.venv/bin/pip" install $PIP_PROXY -q -e "$PANCAKE_DIR"

echo -e "${GREEN}Done.${RESET}"

# ── Step 5: Chat backend selection ─────────────────────────────────────────

echo ""
echo -e "${BOLD}How should the chat panel connect to Claude?${RESET}"
echo ""
echo "  1) Local Claude CLI  (recommended if claude is installed)"
echo "     Uses the claude command installed on this machine."
echo "     No API key needed."
echo ""
echo "  2) Anthropic API"
echo "     Requires your own ANTHROPIC_API_KEY."
echo "     Installs the anthropic Python package."
echo ""
echo "  3) Disable chat"
echo "     Skip chat setup entirely."
echo ""
read -p "Choose [1/2/3]: " CHAT_CHOICE
echo ""

CHAT_BACKEND="disabled"
case "$CHAT_CHOICE" in
    1)
        CHAT_BACKEND="local"
        ;;
    2)
        CHAT_BACKEND="api"
        "$PANCAKE_DIR/.venv/bin/pip" install $PIP_PROXY -q -e "$PANCAKE_DIR[api]"
        echo ""
        read -p "ANTHROPIC_API_KEY: " API_KEY
        echo ""
        ;;
    3)
        CHAT_BACKEND="disabled"
        ;;
esac

# ── Step 6: Create data directories ────────────────────────────────────────

mkdir -p "$PANCAKE_DIR/vault" "$PANCAKE_DIR/data" "$PANCAKE_DIR/config"

# ── Step 7: Write env config ───────────────────────────────────────────────

cat > "$ENV_FILE" << EOF
PANCAKE_DIR=$PANCAKE_DIR
PANCAKE_HOST=0.0.0.0
PANCAKE_CHAT_BACKEND=$CHAT_BACKEND
EOF

if [ "$CHAT_BACKEND" = "api" ] && [ -n "${API_KEY:-}" ]; then
    echo "ANTHROPIC_API_KEY=$API_KEY" >> "$ENV_FILE"
fi

if [ "$CHAT_BACKEND" = "local" ]; then
    echo "PANCAKE_CHAT_MODEL=claude-opus-4-6[1m]" >> "$ENV_FILE"
fi

chmod 600 "$ENV_FILE"

# ── Step 8: pk CLI ─────────────────────────────────────────────────────────

LOCAL_BIN="${HOME}/.local/bin"
mkdir -p "$LOCAL_BIN" 2>/dev/null || true
if [ -d "$LOCAL_BIN" ]; then
    ln -sf "$PANCAKE_DIR/.venv/bin/pk" "$LOCAL_BIN/pk"
fi

# ── Step 9: Start the server ───────────────────────────────────────────────

if command -v systemctl &>/dev/null && systemctl --user status &>/dev/null 2>&1; then
    # systemd available
    echo "Setting up systemd service..."
    VENV_PYTHON="$PANCAKE_DIR/.venv/bin/python"
    SERVICE_USER=$(whoami)
    sudo tee /etc/systemd/system/pancake.service > /dev/null << SVCEOF
[Unit]
Description=Pancake Priority Tracker
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PANCAKE_DIR
ExecStart=$VENV_PYTHON -m web.server
EnvironmentFile=$PANCAKE_DIR/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF
    sudo systemctl daemon-reload
    sudo systemctl enable pancake -q
    sudo systemctl start pancake
    echo -e "${GREEN}Service installed and running.${RESET}"

elif command -v tmux &>/dev/null; then
    # tmux fallback
    tmux kill-session -t pancake 2>/dev/null || true
    tmux new-session -d -s pancake \
        "cd $PANCAKE_DIR && source .env && .venv/bin/python -m web.server"
    echo -e "${GREEN}Running in tmux session 'pancake'. Attach with: tmux attach -t pancake${RESET}"

else
    echo -e "${YELLOW}Start Pancake manually:${RESET}"
    echo "  source $ENV_FILE && $PANCAKE_DIR/.venv/bin/python -m web.server"
fi

# ── Step 10: Auto-start via .bashrc (optional, offered during install) ─────

if command -v tmux &>/dev/null && ! tmux has-session -t pancake 2>/dev/null; then
    # Add bashrc auto-start for tmux-based setups
    if ! grep -q "PANCAKE_DIR" ~/.bashrc 2>/dev/null; then
        cat >> ~/.bashrc << 'BASHEOF'

# Pancake
if command -v tmux &>/dev/null && ! tmux has-session -t pancake 2>/dev/null; then
    cd ~/pancake && tmux new-session -d -s pancake \
        "source .env && .venv/bin/python -m web.server"
fi
BASHEOF
    fi
fi

# Persist PANCAKE_DIR to .bashrc
if ! grep -q "PANCAKE_DIR" ~/.bashrc 2>/dev/null; then
    echo '' >> ~/.bashrc
    echo '# Pancake' >> ~/.bashrc
    echo "export PANCAKE_DIR=\"$PANCAKE_DIR\"" >> ~/.bashrc
fi

# Ensure ~/.local/bin is in PATH
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
fi

# ── Step 11: Claude Code commands (optional, silent) ───────────────────────

if [ -d "${HOME}/.claude" ] || command -v claude &>/dev/null; then
    CLAUDE_COMMANDS="${HOME}/.claude/commands"
    mkdir -p "$CLAUDE_COMMANDS" 2>/dev/null || true
    for cmd in morning think; do
        if [ -f "$PANCAKE_DIR/claude/${cmd}.md" ]; then
            cp "$PANCAKE_DIR/claude/${cmd}.md" "$CLAUDE_COMMANDS/${cmd}.md"
        fi
    done
fi

# ── Done ───────────────────────────────────────────────────────────────────

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "your-server-ip")

echo ""
echo -e "${GREEN}${BOLD}Pancake is running!${RESET}"
echo ""
echo -e "  Open in your browser: ${BOLD}http://${SERVER_IP}:5790${RESET}"
echo ""
echo "  Create your account on first visit (username, email, password)."
echo ""
echo -e "${DIM}Data:   $PANCAKE_DIR/vault/${RESET}"
echo -e "${DIM}CLI:    pk status${RESET}"
echo -e "${DIM}Config: $ENV_FILE${RESET}"
echo ""
