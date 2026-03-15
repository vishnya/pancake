# Worklog

Recent session handoff notes. Read on session start, append before committing.
Keep only the last 10 entries. Each entry: date, device, what was done.

---

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
