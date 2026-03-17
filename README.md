<h1 align="center">Pancake</h1>

<p align="center"><em>A priority tracker that lives in a plain text file.</em></p>

**Keep track of what matters.** Pancake manages your tasks, projects, and priorities in a single Markdown file that you own. Use the web UI from your phone, the `pk` CLI from your terminal, or edit the file directly in Obsidian. All three stay in sync.

Works for individuals. Works for households — one person hosts it, everyone else just opens the URL.

### Who needs to install this?

- **If someone already set up Pancake for your household** — you don't install anything. Just open the URL they gave you, click "Create account", and you're in.
- **If you're starting fresh** — you're the host. Keep reading.

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

## Host setup

This section is for the person hosting Pancake — the one setting it up for the first time. If someone already hosts it for you, skip to [Joining a household](#household-use).

One command:

```bash
curl -fsSL https://raw.githubusercontent.com/vishnya/pancake/main/install.sh | bash
```

The installer walks you through everything:
1. **Server or laptop?** — pick how you'll host it
2. **Set a password** — for logging into the web UI
3. **Done** — it sets up Python, the background service, and tells you where to go

Open the URL it gives you and create your account. Then share the URL with anyone you want to invite.

### Server vs. laptop — which should I pick?

| | Server | Laptop |
|---|---|---|
| Access from phone | Yes | No |
| Share with household | Yes | No |
| Works when laptop is closed | Yes | No |
| Needs a VPS or always-on machine | Yes | No |
| Good for | Families, mobile use | Solo, desktop only |

**Server** means a computer that's always on — a $5/month VPS (DigitalOcean, Hetzner), a Raspberry Pi, or an old laptop you leave running. The installer sets up a systemd service that starts on boot.

**Laptop** means it runs on your Mac. It starts automatically when you log in and stops when you close the lid. You can only use it from that computer's browser — no phone, no sharing. Good for trying it out or personal desktop use.

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

Say you want to share a grocery list and household tasks with your partner. They don't need to install anything — they just need your server's URL.

1. **You** (the person who set up the server) create your account and log in. You already have a "Personal" profile.
2. **You** create a "Family" profile using the profile switcher in the top bar (click your profile name → "+ New profile").
3. **Your partner** opens the same URL on their phone, clicks "Create account", picks a username and password. Done — they now have their own account with a private "Personal" profile.
4. **You** add your partner to the Family profile: click your profile name → "Manage members" → enter their username.
5. **Your partner** logs in and switches to the Family profile using the profile switcher.

Now you both see the same Family tasks, can add items, mark things done, and it all stays in sync. Your Personal profiles remain private — you can't see theirs, they can't see yours.

**Only one person installs Pancake** (whoever sets up the server). Everyone else just visits the URL and creates an account. Think of it like a shared household whiteboard that lives on your server.

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
