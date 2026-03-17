#!/bin/bash
set -euo pipefail

# Pancake installer -- interactive, guides you through everything.
# Usage: curl -fsSL https://raw.githubusercontent.com/vishnya/pancake/main/install.sh | bash

PANCAKE_DIR="${PANCAKE_DIR:-$HOME/pancake}"
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
    echo -e "Found existing install at ${GREEN}$PANCAKE_DIR${RESET}"
    cd "$PANCAKE_DIR"
else
    echo -e "Installing to ${GREEN}$PANCAKE_DIR${RESET}"
    git clone -q https://github.com/vishnya/pancake.git "$PANCAKE_DIR"
    cd "$PANCAKE_DIR"
fi

# ── Step 2: Python environment ──────────────────────────────────────────────

echo "Setting up Python..."
if command -v uv &>/dev/null; then
    uv venv "$PANCAKE_DIR/.venv" -q 2>/dev/null || true
    uv pip install -q -e "$PANCAKE_DIR" -p "$PANCAKE_DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    python3 -m venv "$PANCAKE_DIR/.venv"
    "$PANCAKE_DIR/.venv/bin/pip" install -q -e "$PANCAKE_DIR"
else
    echo -e "${RED}Python 3.10+ is required but not found.${RESET}"
    echo "Install it first: https://www.python.org/downloads/"
    exit 1
fi
echo -e "${GREEN}Done.${RESET}"

# ── Step 3: pk CLI ──────────────────────────────────────────────────────────

LOCAL_BIN="${HOME}/.local/bin"
mkdir -p "$LOCAL_BIN" 2>/dev/null || true
if [ -d "$LOCAL_BIN" ]; then
    ln -sf "$PANCAKE_DIR/.venv/bin/pk" "$LOCAL_BIN/pk"
fi

# ── Step 4: Ask about setup mode ────────────────────────────────────────────

echo ""
echo -e "${BOLD}How will you use Pancake?${RESET}"
echo ""
echo "  1) On a server  (recommended)"
echo "     Access from your phone or any device. Share with your"
echo "     household. Always on, even when your laptop is closed."
echo ""
echo "  2) On this computer only"
echo "     Just for you, on this machine. No phone access, no sharing."
echo "     Only works while this computer is on and awake."
echo ""
read -p "Choose [1/2]: " MODE
echo ""

# ── Step 5: Set password ────────────────────────────────────────────────────

echo -e "${BOLD}Set a password.${RESET}"
echo -e "${DIM}You'll use this to log in from your browser.${RESET}"
echo ""
while true; do
    read -s -p "Password (min 6 characters): " PASSWORD
    echo ""
    if [ ${#PASSWORD} -lt 6 ]; then
        echo -e "${RED}Too short. Try again.${RESET}"
        continue
    fi
    read -s -p "Confirm: " PASSWORD2
    echo ""
    if [ "$PASSWORD" != "$PASSWORD2" ]; then
        echo -e "${RED}Passwords don't match. Try again.${RESET}"
        continue
    fi
    break
done

# ── Step 6: Create data directories ─────────────────────────────────────────

DATA_DIR="$PANCAKE_DIR"
mkdir -p "$DATA_DIR/vault" "$DATA_DIR/data" "$DATA_DIR/config"

# ── Step 7: Write env config ────────────────────────────────────────────────

ENV_FILE="$PANCAKE_DIR/.env"
cat > "$ENV_FILE" << EOF
PANCAKE_PASSWORD=$PASSWORD
PANCAKE_DATA_ROOT=$DATA_DIR
EOF
chmod 600 "$ENV_FILE"

# ── Step 8: Mode-specific setup ─────────────────────────────────────────────

if [ "$MODE" = "1" ]; then
    # ── Server mode ──
    echo ""
    HOST_BIND="0.0.0.0"

    # Add host binding to env
    echo "PANCAKE_HOST=$HOST_BIND" >> "$ENV_FILE"

    # systemd service
    if command -v systemctl &>/dev/null; then
        echo "Setting up background service..."
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
    else
        echo -e "${YELLOW}systemd not found. Start Pancake manually:${RESET}"
        echo "  source $ENV_FILE && $PANCAKE_DIR/.venv/bin/python -m web.server"
    fi

    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "your-server-ip")

    echo ""
    echo -e "${GREEN}${BOLD}Pancake is running!${RESET}"
    echo ""
    echo -e "  Open in your browser: ${BOLD}http://${SERVER_IP}:5790${RESET}"
    echo ""
    echo "  Create your account on first visit (username, email, password)."
    echo "  Then share the URL with your household -- they sign up the same way."
    echo ""
    echo -e "${BOLD}What's next:${RESET}"
    echo "  1. Set up HTTPS so you can access it from your phone securely."
    echo "     The simplest way: install Caddy (https://caddyserver.com)"
    echo "     and point a domain at this server."
    echo "  2. For email notifications when assigning tasks:"
    echo "     Add SMTP settings to $ENV_FILE"
    echo "     (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM)"
    echo ""

else
    # ── Local mode (Mac or Linux desktop) ──

    if [[ "$(uname)" == "Darwin" ]]; then
        # Mac: launchd agent (auto-start on login)
        PLIST_DIR="$HOME/Library/LaunchAgents"
        PLIST_PATH="$PLIST_DIR/com.pancake.plist"
        mkdir -p "$PLIST_DIR"
        cat > "$PLIST_PATH" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.pancake</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PANCAKE_DIR/.venv/bin/python</string>
    <string>-m</string>
    <string>web.server</string>
  </array>
  <key>WorkingDirectory</key><string>$PANCAKE_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PANCAKE_PASSWORD</key><string>$PASSWORD</string>
    <key>PANCAKE_DATA_ROOT</key><string>$DATA_DIR</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/pancake.log</string>
  <key>StandardErrorPath</key><string>/tmp/pancake.log</string>
</dict>
</plist>
PLISTEOF
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        launchctl load "$PLIST_PATH"
        echo -e "${GREEN}Pancake starts automatically when you log in.${RESET}"
    else
        echo -e "${YELLOW}Start Pancake manually:${RESET}"
        echo "  source $ENV_FILE && $PANCAKE_DIR/.venv/bin/python -m web.server"
    fi

    echo ""
    echo -e "${GREEN}${BOLD}Pancake is running!${RESET}"
    echo ""
    echo -e "  Open in your browser: ${BOLD}http://localhost:5790${RESET}"
    echo ""
    echo "  Create your account on first visit."
    echo ""
    echo -e "  ${YELLOW}Local mode limitations:${RESET}"
    echo "  - Only works while this computer is on and awake"
    echo "  - Can't access from your phone"
    echo "  - Can't share with household members"
    echo "  - To get those features, re-run this installer on a server"
    echo ""
fi

# ── Step 9: Claude Code commands (optional, silent) ─────────────────────────

if [ -d "${HOME}/.claude" ] || command -v claude &>/dev/null; then
    CLAUDE_COMMANDS="${HOME}/.claude/commands"
    mkdir -p "$CLAUDE_COMMANDS" 2>/dev/null || true
    for cmd in morning think; do
        if [ -f "$PANCAKE_DIR/claude/${cmd}.md" ]; then
            cp "$PANCAKE_DIR/claude/${cmd}.md" "$CLAUDE_COMMANDS/${cmd}.md"
        fi
    done
fi

echo -e "${DIM}Data:   $DATA_DIR/vault/${RESET}"
echo -e "${DIM}Logs:   /tmp/pancake.log${RESET}"
echo -e "${DIM}CLI:    pk status${RESET}"
echo -e "${DIM}Config: $ENV_FILE${RESET}"
echo ""
