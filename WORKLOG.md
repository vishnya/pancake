# Worklog

Recent session handoff notes. Read on session start, append before committing.
Keep only the last 10 entries. Each entry: date, device, what was done.

---

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

### 2026-03-15 | Mac + Server
- Added cookie-based auth system (login page, sessions, HttpOnly cookies with SameSite=Lax)
- New endpoints: project rename/delete/archive, task undone, redo
- Touch drag-and-drop for mobile task reordering
- Chat panel improvements (close button, voice input)
- User context save/load API, PWA manifest + service worker
- Merged voice FAB (floating action button for mobile voice) from server session
- 35 new server tests (236 total across all test files)
- Fixed Pancake web auth: was using Caddy basicauth which broke on mobile Chrome
- Pushed to GitHub via subtree, synced server repo

### 2026-03-15 | Server
- Fixed white page bug: static assets (style.css, app.js) were behind Pancake's own auth, returning login HTML instead of actual files. Made them auth-exempt since Caddy shared auth already protects the site.

### 2026-03-15 | Server
- Added apple-touch-icon.png and PNG icons (192, 512) for mobile favicon support across all web projects
- Updated manifest.json with PNG icon entries

### 2026-03-15 | Mac
- Fixed CSS strikethrough bug: `.done-section .task-text` selector had been broken, applying line-through to ALL tasks
- Added task move up/down buttons + `/api/task/move` server endpoint (workaround for broken HTML5 drag-and-drop)
- Added `.task-move` CSS styles with mobile overrides
- Added `setData()` call in dragstart handler
- Removed debug "DRAG TEST" div and duplicate CSS blocks from server deploy
- Deployed clean local copies of style.css, app.js, server.py to server
