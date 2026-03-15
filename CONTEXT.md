# Pancake -- Project Context

Local-first second brain and priority tracker. All data lives in plain Markdown files
in the Obsidian vault. Zero external dependencies beyond Python stdlib.

## Key Files

| File | Purpose |
|------|---------|
| `pancake/priorities.py` | Parser/writer for PRIORITIES.md (Task, ProjectInfo, Priorities dataclasses) |
| `pancake/cli.py` | Argparse entrypoint (`lc` command) |
| `pancake/commands/focus.py` | Core workflow: activate, done, bump, park, progress |
| `pancake/commands/priority.py` | Task/project add commands |
| `pancake/session_status.py` | Cross-device session sync (git-tracked JSON) |
| `web/server.py` | HTTP server (port 5790): serves web UI, API endpoints |
| `web/templates/index.html` | Single-page app |
| `web/static/app.js` | Vanilla JS: drag-and-drop, collapsible tasks/projects, natural date parsing |
| `web/static/style.css` | Dark theme |
| `web/static/favicon.svg` | Pancake favicon (orbital rings) |
| `hammerspoon/pancake_hotkey.lua` | Cmd+Shift+L opens web UI |
| `claude/morning.md` | `/morning` Claude command |
| `claude/think.md` | `/think` Claude command |
| `launchd/com.pancake.plist` | Template; install.sh generates the live plist |

## Architecture

```
Cmd+Shift+L (Hammerspoon) -> opens https://5.161.182.15.nip.io

Hetzner VPS (5.161.182.15):
  Caddy (HTTPS via nip.io) -> web/server.py (systemd, port 5790)
  -> serves web UI at /
  -> GET /api/priorities returns full state
  -> POST endpoints for task/project CRUD
  -> reads/writes /home/pancake/vault/PRIORITIES.md

PRIORITIES.md (single source of truth)
  -> ## Active: 2-3 tasks being worked on
  -> ## Up Next: ordered backlog
  -> ## Projects: collapsible folders with task backlogs
  -> ## Done: completed tasks
  -> ## Notes: timestamped notes
  -> Tasks: - [ ] [ProjectName] task text @due(2026-03-20)
  -> Sub-items: indented   - note: lines under tasks (URLs auto-linked)
```

## Data Model

- **Task**: text, project, done, notes[], deadline
- **ProjectInfo**: name, description, tasks[]
- **Priorities**: active[], up_next[], projects[], done[], notes[]

Tasks carry `[ProjectName]` tags. Order in file = priority order.
Tasks have optional sub-items (links, notes) and deadlines (`@due(YYYY-MM-DD)`).
Projects are collapsible folders containing task backlogs.
Tasks are created inside projects, then dragged to Up Next / Active.

## Web UI (port 5790)

- **Active / Up Next**: drag-and-drop task lists
- **Projects**: collapsible cards with description + task backlog
  - Tasks created inside projects, dragged up when ready to work
  - Color-coded per project (10-color palette)
  - Project color matches task pills in Active/Up Next
- **Tasks expand on click**: shows notes (with inline URL auto-linking), deadline picker
  - Notes: single list for text and links; URLs auto-detected and rendered as hyperlinks
  - Deadline: natural language input (tomorrow, fri, 3d, next week, mar 20)
- **Done**: completed tasks (last 10)
- **Talk to Claude**: launches `claude --dangerously-skip-permissions` with priority context

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/priorities` | Full state |
| POST | `/api/task/add` | Add task |
| POST | `/api/task/done` | Mark task done |
| POST | `/api/task/edit` | Edit task text |
| POST | `/api/task/delete` | Delete task |
| POST | `/api/task/add_note` | Add note/link to task |
| POST | `/api/task/delete_note` | Delete task note/link |
| POST | `/api/task/deadline` | Set/clear task deadline |
| POST | `/api/reorder` | Drag-and-drop reorder (active, up_next, project tasks) |
| POST | `/api/project/add` | Create project |
| POST | `/api/project/edit` | Edit project description |
| POST | `/api/project/task/add` | Add task to project backlog |
| POST | `/api/project/task/delete` | Delete project task |
| POST | `/api/project/task/done` | Mark project task done |
| POST | `/api/note/add` | Add note |
| POST | `/api/note/delete` | Delete note |
| POST | `/api/claude` | Launch Claude Code with priority context |

## CLI (`lc`)

- `lc` / `lc status` -- show current priorities
- `lc add "task" -p "Project"` -- add task
- `lc active N` -- move task N to active
- `lc done [N]` -- mark done
- `lc note "text"` -- quick note
- `lc morning` -- morning review context
- `lc think` -- priority conversation context

## Install / Uninstall

```bash
bash install.sh    # venv, CLI, Hammerspoon, Obsidian, Claude commands, launchd
bash uninstall.sh  # reverses everything, prompts for destructive actions
```

Artifacts created by install:
- `~/.local/bin/lc` (symlink)
- `~/Library/LaunchAgents/com.pancake.plist`
- Hammerspoon dofile line in `init.lua`
- Obsidian hotkeys (Alt+Up/Down)
- `~/.claude/commands/morning.md`, `think.md`
- `~/Obsidian/main/PRIORITIES.md` (if not present)
- `~/Obsidian/main/Projects/` directory

## Known Gotchas

- Server logs: `tail -f /tmp/pancake.log`
- Check server: `launchctl list | grep pancake`
- Restart server: `launchctl kickstart -k gui/$UID/com.pancake`
- Port conflict: `lsof -ti:5790 | xargs kill -9`
- Host alias requires: `echo '127.0.0.1 pancake' | sudo tee -a /etc/hosts`
- Vault path overridable via `PANCAKE_VAULT` env var
- File locking via `fcntl.flock()` for concurrent writes

## Planned (not yet implemented)

- **Multi-profile support**: work/personal profiles, tab switching (see `PLAN_WORK.md`)
- **Performance tracking**: PSC bullet generation from project completions (see `PLAN_WORK.md`)

## Recent Changes

- 2026-03-13: Initial build -- CLI, PRIORITIES.md parser, Hammerspoon chord hotkeys
- 2026-03-13: Web UI -- drag-and-drop priority board, dark theme, vanilla JS
- 2026-03-13: Collapsible project cards with task backlogs (tasks created in projects, dragged up)
- 2026-03-13: Per-project color coding (10-color palette, matches task pills)
- 2026-03-13: Collapsible tasks with links, notes, deadline sub-content
- 2026-03-13: Natural language deadline input (tomorrow, fri, 3d, next week, mar 20)
- 2026-03-13: Talk to Claude button launches claude --dangerously-skip-permissions with context
- 2026-03-13: Custom delete confirmation modal (24h suppress), trash icon
- 2026-03-13: Favicon (orbital rings SVG)
- 2026-03-13: launchd agent for auto-start on login
- 2026-03-13: Obsidian project sync (individual .md files per project)
