# Pancake: Brainstorming

Non-finalized ideas and directions. Nothing here is committed to -- just thinking out loud.

---

## 1. Multi-Profile Support

Separate, independent priority boards per profile. Tab-style switching in the UI -- never merged.

### Access Model (Asymmetric)

- **Work laptop**: sees both work AND personal profiles (tab switch)
- **Personal laptop**: sees only personal (no switcher needed)
- Personal data synced to work laptop via git or cloud sync (read-write)
- Work data never leaves work laptop

### Config

```json
// ~/.config/pancake/config.json
{
  "profiles": {
    "work": {
      "vault": "~/Obsidian/work/PRIORITIES.md",
      "projects_dir": "~/Obsidian/work/Projects/",
      "performance": true
    },
    "personal": {
      "vault": "~/Drive/personal/PRIORITIES.md",
      "projects_dir": "~/Drive/personal/Projects/",
      "performance": false
    }
  },
  "default_profile": "work"
}
```

Single-profile installs (personal laptop) just have one entry -- UI skips the switcher.

### UI

- Header: "Pancake: Work" with tab/dropdown when multiple profiles exist
- Switching loads a completely independent board (different PRIORITIES.md)
- Each profile has its own projects, tasks, done list
- Color theme could optionally differ per profile (visual cue)

### CLI

- `lc status` uses default profile
- `lc --profile personal status` to target a specific profile
- `PANCAKE_PROFILE=work lc status` env var override

### Server

- Single server process, serves all profiles
- `GET /api/profiles` returns available profiles
- All endpoints gain optional `?profile=name` param
- Profile selection sticky via cookie

### Sync (Personal → Work)

- TBD based on what sync tools are available at Meta
- Options: git repo, Google Drive, iCloud, manual `lc sync` commands

### Implementation Order

1. Add config file support (`~/.config/pancake/config.json`)
2. Update `vault_path()` to read from config based on active profile
3. Add `/api/profiles` endpoint
4. Add profile tabs to UI header
5. Update CLI with `--profile` flag
6. Set up sync between machines

---

## 2. Performance Tracking (Work Profile Only)

### Core Insight

The unit of performance impact is the **project**, not individual tasks. Tasks are evidence that accumulates toward a project-level story. Don't add friction to task completion.

### When to Capture

- **Project completion**: When all tasks done or project archived, prompt for impact summary
- **Manual highlight**: "Log Impact" button on project card for mid-project milestones
- **NOT on every task done** -- tasks flow to Done silently, building evidence

### Data Model

```
PERFORMANCE.md (in work Obsidian vault, continuously updated)

## Q1 2026

### [Project Name] -- Impact Title
_Date: 2026-04-15_
_Competency: technical execution_

**Summary**: 1-2 sentence impact bullet in PSC format
**Evidence**: auto-collected from completed tasks
- Built X (done 2026-04-01)
- Fixed Y (done 2026-04-05)
- Shipped Z (done 2026-04-12)
**Artifacts**: linked docs, designs, PRs -- wikilinked to enriched resource notes
- [[Design Doc - New Auth Flow]] (design)
- [[PR #1234 - Auth Migration]] (code)
- [[Q1 OKR Dashboard]] (metrics)
**Notes**: additional context
```

PERFORMANCE.md is a **living document** -- updated continuously as tasks complete and impact is logged, not just at PSC time. It should always reflect the current state of work done this cycle.

### Artifact Linking

When notes/links are added to tasks, they become potential performance artifacts:
- Links added to project tasks (design docs, PRs, dashboards, metrics pages) are auto-collected as evidence
- The enrichment pipeline (section 3) creates `[[wikilinked]]` resource notes for each -- those same notes appear as artifacts in PERFORMANCE.md
- At "Log Impact" time, all links from the project's completed tasks are pre-populated as artifacts
- User can tag artifact type (design, code, metrics, presentation) or let LLM infer it

This means: drop a link to your design doc on a task, and it automatically shows up as a citable artifact in your performance review.

### Flow

1. Work through tasks normally -- zero friction, just check done
2. Done tasks stay associated with their project (tracked via project tag)
3. Links/notes on tasks are enriched in background and become referenceable artifacts
4. When ready to capture impact (project done OR manual trigger):
   - Project card shows "Log Impact" action
   - Opens view pre-filled with all completed tasks + all linked artifacts for that project
   - One text field: "What was the impact?"
   - Claude generates draft PSC bullet using:
     - Impact note + completed task list as evidence
     - Linked artifacts (design docs, PRs, dashboards)
     - Project description
     - Growth plan axes (Rachel will provide)
   - Save to PERFORMANCE.md

### Growth Plan Integration

- Rachel will provide her promotion growth plan
- Store as `data/growth_plan.md`
- Claude maps each impact entry to relevant competency/dimension
- At PSC time: PERFORMANCE.md grouped by competency, bullets pre-written

### Claude Context Protocol (General Pattern)

When launching "Talk to Claude" from a project or the main board, Claude should receive rich context:

1. **Project context**: description, all notes/links, active tasks, completed tasks history
2. **Current priorities**: full Active + Up Next state across all projects
3. **Performance artifacts**: growth plan, logged impact entries, PERFORMANCE.md
4. **Memory**: project-specific memory file (e.g. `data/memory/<project>.md`) for persistent context across conversations

This should be a **general pattern** supported for any user, not a one-off:
- Each project can accumulate a memory file with key decisions, blockers, and context
- "Talk to Claude" from a project card sends that project's full context + performance docs
- "Talk to Claude" from the main board sends the full priority state + growth plan
- The system should make it easy to configure what documents feed into Claude context

### LLM Access at Work

- Meta may not provide Anthropic API keys
- Design the system to work with OR without LLM:
  - Without: stores impact note + evidence, user writes bullet
  - With: auto-drafts bullet, user approves/edits
- Check if Meta has internal LLM access that could be used

### UI Changes

- [ ] "Log Impact" button on project cards (visible when project has done tasks)
- [ ] Impact capture modal: shows completed tasks, one text field for impact
- [ ] Performance view: section showing all logged impact entries
- [ ] Optional: "Review bullets" batch mode for monthly cleanup

---

## 3. Obsidian Enrichment Pipeline

Background process that turns raw notes/links into best-practice Obsidian knowledge notes. Invisible to the user -- never blocks the frontend.

### Flow

1. User adds a note or link to a task in the UI -- saves instantly to PRIORITIES.md
2. An enrichment queue picks up new items containing URLs
3. For each URL:
   - Fetch the page content (title, meta, main text)
   - LLM summarizes into a proper Obsidian note: title, summary, key takeaways, tags
   - Creates/updates a note in the vault (e.g. `Resources/Two Sum - LeetCode.md`)
   - Adds `[[wikilinks]]` back into the project file to connect the graph
4. Non-URL notes get lighter treatment: LLM extracts any concepts worth linking as `[[wikilinks]]`

### Obsidian Output Quality

Project files (`Projects/ProjectName.md`) should look like hand-written notes:
- `## Notes` section with timestamped entries, wikilinked to related concepts
- `## Resources` section with fetched link summaries, not raw URLs
- Tags (e.g. `#project/active`, `#area/frontend`)
- `[[wikilinks]]` to other project notes, resource notes, concept notes

Resource notes (`Resources/PageTitle.md`) created from fetched URLs:
- Title, source URL, date added
- **1-3 sentence summary in plain English** -- no jargon, no bullet-point dumps, just "what is this and why does it matter"
- Tags and wikilinks to relevant projects/concepts
- Backlink to the project that referenced it

The default tone should read like a note you'd write to yourself: "This is a LeetCode problem about hash maps. Classic interview prep, O(n) solution." Not a formal abstract.

### Configuration

```json
// in ~/.config/pancake/config.json (or per-profile)
{
  "enrichment": {
    "enabled": true,         // toggle entire pipeline
    "fetch_urls": true,      // fetch page content for URLs
    "llm_enrich": true,      // use LLM for summaries/wikilinks
    "llm_provider": "anthropic",  // or "openai", "local", "none"
    "auto_wikilink": true,   // auto-create [[wikilinks]] in project files
    "resource_dir": "Resources"   // vault subdirectory for fetched pages
  }
}
```

Graceful degradation:
- `llm_enrich: false` -- still fetches page titles/meta, writes basic notes, no summarization
- `fetch_urls: false` -- just stores raw links in Obsidian, no fetching
- `enabled: false` -- current behavior, flat project file mirror

### Implementation

- Background thread or async queue in the server process (not blocking HTTP responses)
- Queue persisted to disk so enrichment survives server restarts
- Rate-limited fetching (respect robots.txt, don't hammer sites)
- Idempotent: re-enriching the same URL updates rather than duplicates
- LLM calls batched where possible to minimize API usage

### Priority

Low -- implement after multi-profile and performance tracking are working. The current flat sync is fine as a starting point. This is an enhancement layer.

---

## Open Questions

- What sync mechanism is available at Meta? (git, Drive, etc.)
- Should personal profile on work laptop be read-only or read-write?
- Different color themes per profile?
- Does the Hammerspoon hotkey need to be profile-aware?
- What does Rachel's growth plan look like? (axes, competencies, levels)
- Does Meta have internal LLM access?
- How to handle cross-project impact?
- Archive vs delete projects -- archived should preserve performance history
