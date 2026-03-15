# Pancake Mobile Plan

**Goal:** Full Pancake features on iPhone, synced with the Mac.

**Date:** 2026-03-14

---

## Current Architecture (What We're Working With)

| Component | Detail |
|-----------|--------|
| Server | Python stdlib `http.server`, threaded, binds `127.0.0.1:5790` |
| Data store | Single file: `~/Obsidian/main/PRIORITIES.md` |
| User context | `~/Obsidian/main/About Me.md` |
| Undo/redo | JSON files in `data/undo_stack.json`, `data/redo_stack.json` |
| Chat sessions | JSON files in `data/chat_sessions/` |
| Chat backend | Anthropic SDK, SSE streaming, tool use loop |
| File locking | `fcntl.flock()` (POSIX-only) |
| macOS-specific | `/api/claude` uses `osascript` to open Terminal |
| Dependencies | `anthropic>=0.40`, Python 3.10+ |
| Tests | 200 pytest tests |

### What Breaks If We Move Off Localhost

1. **`fcntl.flock()`** -- Works on Linux/macOS. Won't work on Windows or serverless (no filesystem).
2. **`osascript` in `/api/claude`** -- Opens Terminal on the Mac. Irrelevant on mobile; the in-app Think chat is the real feature.
3. **SSE streaming for chat** -- Requires persistent HTTP connections. Problematic for serverless with 10-second timeouts. Fine for any always-on server.
4. **File-based storage** -- PRIORITIES.md, undo stacks, chat sessions are all flat files. Need a database or synced filesystem for cloud deployment.
5. **`ANTHROPIC_API_KEY`** -- Currently read from env. Must be securely provided in any remote deployment.

---

## Option 1: Tailscale (Tunnel to Your Mac)

**Concept:** Install Tailscale on Mac and iPhone. Access `http://100.x.x.x:5790` from the phone over an encrypted WireGuard mesh. Zero code changes.

### Setup

1. Install Tailscale on Mac and iPhone (both free)
2. Change server bind from `127.0.0.1` to `0.0.0.0` (one line in `server.py`)
3. Optionally enable Tailscale MagicDNS so you can access `http://macbook:5790` by name
4. Bookmark on iPhone home screen

### Evaluation

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Setup complexity | **Very low** | ~15 min. One line of code + two app installs |
| Cost | **$0/month** | Free for personal use (up to 100 devices) |
| Sync reliability | **Excellent** | No sync needed -- single source of truth on Mac |
| Feature completeness | **99%** | Everything works except `/api/claude` (Terminal launcher). Think chat works fine. |
| Security | **Excellent** | WireGuard encryption, no public exposure, no auth needed |
| Latency | **Low** | Direct peer-to-peer when on same network; relay through DERP servers otherwise (~50-100ms) |
| Offline support | **None** | Phone must reach Mac. If Mac is asleep/off, nothing works |
| Maintenance | **Near zero** | Tailscale auto-updates, auto-reconnects |

### Pros
- Zero architecture changes. The app stays local-first.
- No database migration, no API key exposure, no auth to build.
- Mac stays the single source of truth -- no sync conflicts ever.
- Can also access from any device on your tailnet.

### Cons
- **Mac must be on and awake.** If your MacBook sleeps, Pancake is unreachable.
  - Mitigation: Energy Saver settings to prevent sleep on power adapter.
  - Mitigation: Power Nap keeps network connections alive on newer Macs.
- No offline mobile access. Can't check priorities on a plane.
- Slight latency when off home network (routed through Tailscale relay).

### Implementation: ~30 minutes

---

## Option 2: Cloudflare Tunnel

**Concept:** Run `cloudflared` on your Mac, which creates an outbound-only tunnel to Cloudflare's network. Get a public URL (custom domain or `*.trycloudflare.com`) that routes to your local server. Add Cloudflare Access for auth.

### Setup

1. Sign up for Cloudflare (free), optionally add a custom domain
2. Install `cloudflared` on Mac
3. Create a tunnel: `cloudflared tunnel create pancake`
4. Route to `localhost:5790`
5. Set up Cloudflare Access (Zero Trust) for authentication -- email OTP or Google SSO
6. Change server bind to `0.0.0.0`

### Evaluation

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Setup complexity | **Low-medium** | ~1 hour. DNS config, tunnel setup, auth policy |
| Cost | **$0/month** | Free tier includes tunnels + Access for up to 50 users |
| Sync reliability | **Excellent** | Same as Tailscale -- single source of truth on Mac |
| Feature completeness | **99%** | Same as Tailscale. Chat SSE streaming works through CF tunnels |
| Security | **Good** | Cloudflare Access adds auth layer. Data traverses Cloudflare's network |
| Latency | **Low-medium** | Extra hop through Cloudflare edge (~20-50ms added) |
| Offline support | **None** | Mac must be on |
| Maintenance | **Low** | `cloudflared` runs as a service. Occasional token refresh |

### Pros
- Custom domain (e.g., `pancake.yourdomain.com`).
- Built-in auth via Cloudflare Access (email OTP, Google login).
- Works from any browser, any device, anywhere. No Tailscale app needed on the phone.
- Free.

### Cons
- **Mac must be on** -- same as Tailscale.
- Data passes through Cloudflare's infrastructure (not end-to-end encrypted like Tailscale).
- Slightly more setup than Tailscale.
- Quick tunnels change URL on restart; named tunnels need a domain.

### Implementation: ~1 hour

---

## Option 3: Vercel / Cloud Deployment (Serverless)

**Concept:** Rewrite the backend as serverless functions, replace PRIORITIES.md with a database, deploy to Vercel. Access from any device with a URL.

### What Needs to Change (Major Rewrite)

1. **Replace file I/O with a database.** PRIORITIES.md becomes rows in Postgres or a document in a KV store.
   - Option A: **Neon Postgres** (Vercel Marketplace) -- structured, ACID, free tier
   - Option B: **Upstash Redis** -- store as a single JSON blob
   - Option C: **Vercel Blob** -- store as a file, but no locking/transactions

2. **Remove `fcntl.flock()`** -- no filesystem on serverless.

3. **Rewrite server.py as serverless functions.** Each endpoint becomes a separate function. Vercel supports Flask or FastAPI.

4. **SSE streaming won't work on Hobby plan.** 10-second timeout kills Claude chat.
   - Pro plan ($20/month) gets 60-second timeout
   - Or rewrite chat to use polling instead of SSE

5. **Build authentication** from scratch.

6. **API key** stored as Vercel environment variable.

7. **Obsidian sync breaks.** PRIORITIES.md no longer exists as a file in your vault.

### Evaluation

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Setup complexity | **Very high** | Major rewrite: database, auth, serverless functions |
| Cost | **$0-20/month** | Hobby: free but chat broken. Pro: $20/month. Plus DB costs |
| Sync reliability | **N/A** | No sync -- database IS the source of truth. Obsidian editing lost |
| Feature completeness | **80-90%** | Chat streaming problematic. Undo/redo needs rework |
| Security | **Good** | HTTPS included, but must build auth. API key in Vercel env |
| Latency | **Excellent** | Vercel edge network. But cold starts add 1-3s on Hobby |
| Offline support | **None** | Cloud-dependent |
| Maintenance | **Medium** | Easy deploys (`git push`), but two codebases to maintain |

### Pros
- Works from any device, any network, without Mac running.
- Professional deployment with HTTPS, CDN, auto-scaling.
- Could share with others.

### Cons
- **Massive rewrite.** 2-4 weeks. Essentially building a new app with the same UI.
- **Loses local-first identity.** Data no longer lives in Obsidian vault.
- **Chat is problematic.** Serverless timeouts fight SSE streaming.
- **Obsidian integration breaks.** No more editing PRIORITIES.md, no wikilinks, no project file sync.
- **Vercel's Python support is Beta.** Less mature than JS/TS.

### Estimated effort: 2-4 weeks

---

## Option 4: Fly.io / Railway (Always-On Cloud VM)

**Concept:** Deploy Pancake as-is on a persistent VM. No serverless rewrite needed. Replace file storage with a persistent volume.

### What Needs to Change

1. **Persistent volume** for PRIORITIES.md and data files (Fly.io supports this)
2. **Remove macOS-specific code** (`osascript`, `pbpaste`)
3. **Add authentication** (basic auth or token)
4. **Dockerfile** for deployment
5. **Set API key as environment variable**

### Evaluation

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Setup complexity | **Medium** | Dockerfile, deploy config, auth, env vars. No major rewrite |
| Cost | **$5-11/month** | Fly.io: ~$5/mo smallest VM. Railway: ~$5-10/mo |
| Sync reliability | **Good** | Always available. Obsidian sync still breaks |
| Feature completeness | **95%** | Chat streaming works (persistent server). Only Terminal launcher gone |
| Security | **Needs work** | Must build auth. API key in env var |
| Latency | **Good** | Single region, ~50-100ms |
| Offline support | **None** | Cloud-dependent |
| Maintenance | **Medium** | Server uptime, updates, monitoring, backups |

### Pros
- Minimal code changes -- keep file-based architecture with persistent volume.
- SSE streaming works perfectly -- real server, not serverless.
- Mac can be off.

### Cons
- **Loses Obsidian integration** unless you build sync.
- Monthly cost.
- Need to manage a server.
- Persistent volumes on Fly.io are single-region, not auto-backed-up.

### Estimated effort: 1-2 days

---

## Option 5: Obsidian Sync + Obsidian Mobile

**Concept:** Buy Obsidian Sync ($4/month). Install Obsidian Mobile on iPhone. PRIORITIES.md syncs automatically.

### Sub-option 5A: Just Use Obsidian Mobile

View and edit PRIORITIES.md directly in Obsidian on your phone.

- Read access to all priorities immediately
- Editing is clunky (raw markdown, no drag-and-drop, no board view)
- No chat with Claude
- No task completion buttons, no colors, no priorities UI

### Sub-option 5B: Build an Obsidian Plugin

Build a Pancake plugin that renders the board UI inside Obsidian, parsing PRIORITIES.md.

- TypeScript plugin using Obsidian's API
- Rewrite board UI in Obsidian's framework
- Plugins work on mobile (Obsidian Mobile has full plugin support)
- Could include Claude chat if plugin makes API calls directly

### Evaluation

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Setup complexity | **Low (5A)** / **Very high (5B)** | 5A: buy sync, install app. 5B: build a whole plugin |
| Cost | **$4/month** | Obsidian Sync. Mobile app is free |
| Sync reliability | **Excellent** | End-to-end encrypted, mature, well-tested |
| Feature completeness | **30% (5A)** / **85% (5B)** | 5A: read-only at best. 5B: depends on plugin effort |
| Security | **Excellent** | E2E encrypted sync, API key stays on device |
| Latency | **Good** | Near-instant on wifi |
| Offline support | **Excellent** | Full offline access to PRIORITIES.md |
| Maintenance | **Low (5A)** / **High (5B)** | Plugin needs to track Obsidian API changes |

### Estimated effort: 5A = 15 minutes. 5B = 2-4 weeks.

---

## Option 6: PWA (Progressive Web App) -- Enhancement Layer

**Not standalone.** This is an enhancement TO another option (Tailscale, Cloudflare, etc.). Adds:

- Home screen icon with app-like launch (no Safari chrome)
- Cached assets for faster loading
- Limited offline read access (cached last-fetched state)

### What's Needed

1. `manifest.json` -- app name, icons, theme color, `display: standalone`
2. Service worker -- cache static assets, optionally cache last API response
3. Touch-friendly CSS adjustments for mobile
4. Apple-specific meta tags (`apple-mobile-web-app-capable`)

### iOS PWA Limitations (2026)

- No background sync
- 50MB cache limit (fine for Pancake)
- Push notifications work since iOS 16.4 but are unreliable
- Service worker cache can be evicted after ~7 days of non-use

### Estimated effort: 2-3 hours. **Recommended regardless of which main option you pick.**

---

## Option 7: Tailscale + PWA + Obsidian Sync (Hybrid) -- RECOMMENDED

**Concept:** Combine the best parts of multiple options.

### Architecture

```
Mac (always-on, power adapter):
  - Pancake server on 0.0.0.0:5790
  - Tailscale installed
  - Obsidian with Sync enabled

iPhone:
  - Tailscale installed
  - Pancake PWA on home screen (via Tailscale IP)
  - Obsidian Mobile with Sync (fallback read access)

When Mac is reachable:
  -> Use Pancake PWA over Tailscale (full features, chat, drag-and-drop)

When Mac is off/unreachable:
  -> Open Obsidian Mobile, read PRIORITIES.md directly (read-only fallback)
  -> PWA shows cached last-known state
```

### Evaluation

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Setup complexity | **Low** | Tailscale + PWA + Obsidian Sync |
| Cost | **$4/month** | Just Obsidian Sync |
| Sync reliability | **Excellent** | Tailscale for live access, Obsidian Sync for offline fallback |
| Feature completeness | **99% online, 30% offline** | Full over Tailscale; raw markdown view offline |
| Security | **Excellent** | Tailscale (WireGuard) + Obsidian (E2E encryption) |
| Latency | **Low** | Direct Tailscale connection |
| Offline support | **Partial** | Obsidian Mobile as fallback |
| Maintenance | **Low** | Three simple pieces, each low-maintenance |

### Estimated effort: ~3 hours total

---

## Comparison Matrix

| | Tailscale | CF Tunnel | Vercel | Fly.io | Obsidian | PWA | **Hybrid (7)** |
|---|---|---|---|---|---|---|---|
| **Setup time** | 30 min | 1 hr | 2-4 wk | 1-2 days | 15 min | 2-3 hrs | **3 hrs** |
| **Monthly cost** | $0 | $0 | $0-20 | $5-11 | $4 | $0 | **$4** |
| **Mac must be on?** | Yes | Yes | No | No | No | N/A | **Yes (degraded w/o)** |
| **Full features?** | Yes | Yes | Partial | Mostly | No | N/A | **Yes** |
| **Chat works?** | Yes | Yes | Problematic | Yes | No | N/A | **Yes** |
| **Offline?** | No | No | No | No | Yes | Limited | **Partial** |
| **Obsidian intact?** | Yes | Yes | No | No | Yes | N/A | **Yes** |
| **Code changes** | 1 line | 1 line | Major | Medium | None | Small | **Small** |
| **Auth needed?** | No | Yes | Yes | Yes | No | No | **No** |

---

## Recommendation

### Pick: Option 7 (Tailscale + PWA + Obsidian Sync)

**Why this wins:**

1. **Tailscale is the foundation.** Full Pancake features on your phone with one line of code change. WireGuard security, no auth to build, free. This alone gets you 95% of what you want.

2. **PWA polish is cheap.** 2-3 hours makes Pancake feel native on iOS -- full-screen, home screen icon, cached assets. Worth doing regardless.

3. **Obsidian Sync is the offline safety net.** For $4/month, read access to priorities even when Mac is off. You were already considering it.

**Why not Vercel?** It fights the architecture. Pancake is local-first -- a single markdown file in Obsidian. Serverless + database is a 2-4 week rewrite that destroys what makes Pancake elegant. You'd lose Obsidian editing, wikilinks, and simplicity. Chat streaming breaks on the Hobby plan ($0), and Pro is $20/month. Wrong tool for this job.

**Why not Fly.io?** Reasonable if Mac must be off, but for a personal tool on a desk Mac plugged in, it's unnecessary cost and complexity. If you outgrow Tailscale later, Fly.io is the natural upgrade path (~1-2 days, ~$5/month).

**Why not Cloudflare Tunnel?** Solid Tailscale alternative, especially with a custom domain. But for personal iPhone use, Tailscale is simpler (no auth config, no DNS). CF Tunnel is the upgrade if you want to share Pancake with others.

### Implementation Order

1. **Today (30 min):** Tailscale setup. Change bind address, install on Mac + iPhone, verify.
2. **This week (2-3 hrs):** PWA. Manifest, service worker, mobile CSS, Apple meta tags.
3. **When convenient ($4/mo):** Obsidian Sync. Install Obsidian Mobile, enable sync.
4. **Keep Mac awake:** Energy Saver to prevent sleep on power adapter.

### Future Upgrade Path

If "Mac must be on" becomes too limiting: **Fly.io with persistent volume**. Keep the file-based code, Dockerize, deploy. 1-2 days, ~$5/month. The smallest jump that removes the Mac dependency.
