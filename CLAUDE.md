# Pancake -- Claude Instructions

## Session Start -- Always Do This

1. Run `git pull origin <current-branch>` to get latest
2. Read `WORKLOG.md` -- this is your handoff from the last session (may have been on a different device). Mention key items to the user.
3. Read `data/session_status.json` -- if a long task is running/done/errored, tell the user.

## Session End -- Always Do This

Before your final commit, append a new entry to `WORKLOG.md`:
- Date, device (Mac/Server/Phone), 1-3 bullet points of what was done
- Trim old entries to keep only the last 10
- Commit and push so the next session (on any device) sees it

## Cross-Device Session Sync

This repo uses a git-tracked status file for monitoring long-running tasks across devices.

### Checking status (phone or any device)

If the user asks what their computer is doing, what's running, or wants a progress update:

1. Pull the latest: `git pull origin <current-branch>`
2. Read `data/session_status.json`
3. Display it in human-readable format (phase, progress %, detail, timing)

You can also run: `python -m pancake.status_cli --pull`

### Running long tasks (computer)

When running any long-running operation, use `SessionStatus`:

```python
from pancake.session_status import SessionStatus

status = SessionStatus(auto_push=True)
status.mark_phase("processing", "reindexing notes")
# ... do work ...
status.mark_done("reindexed 150 notes")
```

### Status JSON schema

```json
{
  "phase": "processing",
  "status": "running | done | error",
  "detail": "Human-readable description",
  "percent": 42.5,
  "items_done": 425,
  "items_total": 1000,
  "started_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "summary": "Final result (when done)",
  "error": "Error message (when failed)"
}
```

## Project Overview

Pancake is a local-first second brain and priority tracker. All data lives in a single `PRIORITIES.md` file in the Obsidian vault (`~/Obsidian/main/`).

### CLI (`pk`)

- `pk` / `pk status` -- show current focus + priorities
- `pk focus "task"` -- set current focus
- `pk done [N]` -- mark done
- `pk progress "note"` -- log progress
- `pk note "text"` -- quick note
- `pk drop [url]` -- drop link (clipboard if no arg)
- `pk priority add "task" [--level !!|!] [--queue]` -- add priority
- `pk morning` -- morning review context
- `pk think` -- priority conversation context

### Architecture

- Zero dependencies beyond Python stdlib
- Source of truth: Hetzner VPS (5.161.182.15), vault at `/home/pancake/vault/PRIORITIES.md`
- Web UI: https://5.161.182.15.nip.io (Caddy + systemd)
- Hammerspoon hotkey: Cmd+Shift+P opens web UI
- Claude commands: `/morning`, `/think`
- File locking via `fcntl.flock()` for concurrent writes
- Vault path overridable via `PANCAKE_VAULT` env var

### Key files

```
pancake/
    priorities.py         Parser/writer for PRIORITIES.md
    cli.py                Argparse entrypoint
    session_status.py     Cross-device session sync
    status_cli.py         CLI for session status
    commands/             One module per subcommand
data/
    session_status.json   Git-tracked session status (NOT gitignored)
hammerspoon/
    pancake_hotkey.lua      Cmd+Shift+P opens web UI
claude/
    morning.md            /morning Claude command
    think.md              /think Claude command
install.sh
uninstall.sh
tests/                    26 tests
```

### Git / Monorepo

This project lives at `~/code/pancake/` inside the monorepo. Push with:

```bash
git subtree push --prefix=pancake <remote> main
```

### Tests

```bash
cd ~/code/pancake && .venv/bin/python -m pytest tests/ -v
```

### Commit style

- No "Co-Authored-By: Claude" or LLM attribution
- No "Generated with Claude Code" footers
