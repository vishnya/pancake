<h1 align="center">Pancake</h1>

<p align="center"><em>A priority tracker that lives in a plain text file.</em></p>

**Keep track of what matters.** Pancake manages your tasks, projects, and priorities in a single Markdown file that you own. Use the web UI from your phone, the `pk` CLI from your terminal, or edit the file directly in Obsidian. All three stay in sync.

Works for individuals. Works for households — your partner can create their own account on the same server and share a family profile.

---

## How it works

Everything in Pancake lives in one file: `PRIORITIES.md`. It looks like this:

```markdown
## Active
- [Work] finish quarterly report !!
- [Home] fix kitchen faucet

## Up Next
- [Work] review pull requests
- [Home] schedule dentist appointment

## Projects
### Work
Lead backend team

### Home
Household maintenance

## Done
- [Work] deploy v2.1 (2026-03-15)
```

The file is plain Markdown. You can edit it by hand in any text editor, rearrange lines, add tasks — Pancake just reads and writes this format. If you use Obsidian, it lives in your vault and you get all of Obsidian's features (search, links, graph view) for free.

---

## Where does data live?

Pancake is **local-first**. Your data never leaves your machine or server.

```
~/pancake/                    (or wherever you install it)
├── vault/
│   ├── personal/             ← each profile gets its own vault
│   │   ├── PRIORITIES.md     ← the file — this IS your data
│   │   ├── About Me.md       ← optional context for Claude chat
│   │   └── Projects/         ← project detail pages
│   └── family/
│       ├── PRIORITIES.md
│       └── Projects/
├── config/
│   ├── accounts.json         ← user accounts (passwords hashed)
│   ├── profiles.json         ← profiles (Personal, Family, etc.)
│   └── memberships.json      ← who has access to which profile
└── data/
    └── profiles/
        ├── personal/         ← undo history, chat sessions
        └── family/
```

There's no cloud database. No API calls to external services (except Claude, if you use the chat feature). If you want a backup, just copy the `vault/` folder.

---

## Install

### On a server (recommended for households)

This is the best setup if multiple people will use it, or if you want to access it from your phone.

```bash
git clone https://github.com/vishnya/pancake.git
cd pancake
bash install.sh
```

The installer creates a Python virtual environment, installs the `pk` CLI, and sets up data directories.

To run the web UI:
```bash
PANCAKE_PASSWORD=your-secret .venv/bin/python -m web.server
```

The web server runs on port 5790. Put it behind a reverse proxy (Caddy, nginx) for HTTPS.

**As a systemd service** (starts on boot):
```bash
sudo tee /etc/systemd/system/pancake.service << EOF
[Unit]
Description=Pancake Priority Tracker
After=network.target

[Service]
Type=simple
User=pancake
WorkingDirectory=/home/pancake/pancake
ExecStart=/home/pancake/pancake/.venv/bin/python -m web.server
EnvironmentFile=/etc/pancake.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Put your password in the env file
echo "PANCAKE_PASSWORD=your-secret" | sudo tee /etc/pancake.env
sudo systemctl enable pancake && sudo systemctl start pancake
```

### On your Mac (personal use)

If it's just you, you can run it locally. Your data lives in your Obsidian vault.

```bash
git clone https://github.com/vishnya/pancake.git
cd pancake
bash install.sh
```

Set your vault path:
```bash
export PANCAKE_VAULT=~/Obsidian/main/PRIORITIES.md
```

Run the web UI:
```bash
.venv/bin/python -m web.server
```

Or just use the CLI:
```bash
pk status          # see what's on your plate
pk add "fix bug"   # add a task
pk done            # mark the top task done
```

---

## Accounts and profiles

Pancake supports multiple people sharing a server. Here's how it works:

### Concepts

- **Account** — a person. Has a username and password. (Example: `rachel`, `mike`)
- **Profile** — a collection of tasks and projects. Has its own `PRIORITIES.md`. (Example: `Personal`, `Family`)
- **Membership** — connects an account to a profile with a role (`admin` or `member`).

One person can belong to multiple profiles. One profile can have multiple members.

### Solo use

When you first log in, you create an account and a "Personal" profile is made for you automatically. That's it — you're set.

### Household use

Say you want to share a grocery list and household tasks with your partner:

1. **You** create your account and log in. You already have a "Personal" profile.
2. **You** create a "Family" profile using the profile switcher in the top bar (click your profile name → "+ New profile").
3. **Your partner** creates their own account by going to the site and clicking "Create account" on the login page.
4. **You** add your partner to the Family profile: click your profile name → "Manage members" → enter their username.
5. **Your partner** logs in and switches to the Family profile using the profile switcher.

Now you both see the same Family tasks, can add items, mark things done, and it all stays in sync. Your Personal profiles remain private.

**You don't need two servers.** Everyone uses the same server. Each person has their own account, and profiles control who sees what.

### Data isolation

- Each profile has its own `PRIORITIES.md` in a separate folder
- Switching profiles switches which file Pancake reads and writes
- Members can see and edit everything in a profile they belong to
- There are no per-task permissions — if you're in the profile, you can see all its tasks

---

## Web UI

The web UI is designed for phones. Open it in your browser:

| Section | What it does |
|---------|--------------|
| **Active** | Tasks you're working on right now (keep it to 2–3) |
| **Up Next** | Your backlog, ordered by priority |
| **Inbox** | New tasks that haven't been sorted into a project yet |
| **Projects** | Groups of related tasks with descriptions |
| **History** | Completed tasks, searchable |

Drag tasks between sections to reprioritize. Tap a task to expand it and add notes or deadlines.

**Profile switcher** — in the top bar, next to "Pancake". Click it to switch between Personal, Family, or any other profile you belong to.

**Think** — the chat panel (bottom-right on desktop, FAB button on mobile). Ask Claude questions about your priorities and it can add/edit tasks for you.

---

## CLI

The `pk` command works from your terminal:

```bash
pk                     # show active tasks and up next
pk add "buy groceries" # add to up next
pk done                # mark top active task as done
pk focus "write docs"  # move a task to active
pk note "called dentist, rescheduled to Friday"
pk morning             # morning review context for Claude
```

The CLI reads and writes the same `PRIORITIES.md` file as the web UI.

---

## Using with Obsidian

Pancake's data format is just Markdown. If you point your Obsidian vault at the same directory, you can:

- Edit `PRIORITIES.md` directly (changes show up in the web UI and CLI)
- Use Obsidian's search to find old tasks
- Link tasks to other notes in your vault
- Use Obsidian on mobile for quick edits

On a server, each profile's vault is at `vault/<profile-name>/`. On a Mac, set `PANCAKE_VAULT` to wherever your Obsidian vault keeps the file.

---

## Uninstall

```bash
bash uninstall.sh
```

This removes the virtual environment, CLI symlink, and systemd service. It asks before deleting your data.
