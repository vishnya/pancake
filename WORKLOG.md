# Worklog

Recent session handoff notes. Read on session start, append before committing.
Keep only the last 10 entries. Each entry: date, device, what was done.

---

### 2026-03-17 | Server
- Recurring tasks due tomorrow now auto-sort to Active (was only today/overdue before)
- Completing a recurring task sets manual=True so it stays in Up Next until deadline arrives
- Due today/overdue overrides manual flag (clears it and moves to Active)
- Mobile: assignee pills now visible (were hidden), project action buttons tightened
- 197 tests pass (added 4 new auto_sort tests)

### 2026-03-17 | Server
- Added `@manual` override for recurring task auto-sort: when user drags a recurring task to a different section, it stays put instead of being auto-sorted back
- Manual flag cleared on task completion (deadline advances), so auto-sort resumes for next cycle
- 7 new tests for manual override behavior

### 2026-03-17 | Server
- Auto-sort recurring tasks by deadline: due today/overdue → Active, due within week → Up Next
- Checking off recurring task in Active moves it to Up Next (done for today, comes back when due)
- 13 new tests for recurring task auto-sorting

### 2026-03-17 | Server
- Registration with email required, auto-login, auto-creates personal profile
- First-run: fresh install shows registration page (no blank app)
- Profile creation UI ("+ New profile"), member management UI ("Manage members" modal)
- Email field on accounts (stored in accounts.json), install script rewritten for GitHub users
- Fixed: post-login redirect, Think inbox routing, drag-to-project tags, archive icon, GET /login route
- Tests updated for profile-scoped auth (120 server tests pass)

### 2026-03-17 | Server
- Fix 501 POST login error: login form used absolute `/login` action which broke behind Caddy's `/pancake/` path prefix (POST hit wrong backend). Changed to relative `login` action.
- Removed shared_auth from Pancake in Caddy (Pancake has its own auth, double-login was bad UX)
- Added 12 comprehensive auth/routing tests: HTTP method coverage for all routes, login form action validation, cookie flags, protected route checks

### 2026-03-17 | Server
- Multi-account/multi-profile system: accounts (username+password login), profiles (isolated PRIORITIES.md per profile), memberships (admin/member roles)
- Thread-local vault_path() for profile-scoped data isolation
- Profile switcher UI in header, profile API endpoints (list/switch/create/invite/members)
- Profile-scoped undo/redo stacks and chat sessions
- Login page with username field, backward-compatible with legacy single-password mode
- Added Inbox section (below Up Next) for unsorted tasks, Think routes projectless tasks there
- Mobile: delete button moved to expanded view, projects/history collapsed by default
- Fixed deadline pill alignment (fixed-width controls container)
- Migration script: scripts/migrate_to_profiles.py
- 192 tests (34 accounts + 57 priorities + 101 server)

### 2026-03-16 | Server
- Added recurring tasks: `@every(daily|weekly|2d|weekdays|monthly)` in PRIORITIES.md
- Recurring tasks reset in-place when checked off (new deadline, stays in section)
- Combined pill UI: shows recurrence label colored by deadline urgency, accepts both dates and recurrence
- Fixed chat panel bleed-through (display:none when not expanded), nuked service worker, no-cache headers
- Fixed mobile spacing: tighter task rows, auto-collapse empty sections, smaller controls
- Fixed static file serving with query params (cache busting), server sends no-cache headers
- 246 tests pass (57 priorities + 101 server + rest)

### 2026-03-16 | Server
- Fix chat panel header hidden behind status bar on mobile (close button was untappable)

### 2026-03-16 | Server
- Fixed inline mic (Web Speech API) for web Think panel, then replaced with Whisper-based voice (from phone session)
- Set up system watchdog (/root/repos/watchdog.sh, cron every 5min): checks services, HTTP health, restarts, escalates to Claude for complex issues
- Changed claude-web and pancake systemd to Restart=always (were on-failure, missed clean exits)
- Added no-cache headers for /code/ route in Caddy

### 2026-03-15 | Server
- Replaced broken Web Speech API voice input with MediaRecorder + server-side Whisper (faster-whisper tiny model)
- New `/api/transcribe` endpoint accepts audio blobs and returns transcribed text
- Silence detection via Web Audio API analyser node (auto-stops after 2s silence)
- Installed faster-whisper + ffmpeg on server



