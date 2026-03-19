"""Build a system prompt from priorities, projects, and Obsidian notes."""

import re
from pathlib import Path

from pancake.priorities import Priorities, vault_path


def _obsidian_projects_dir() -> Path:
    return vault_path().parent / "Projects"


def _obsidian_vault_dir() -> Path:
    return vault_path().parent


def _first_paragraph(path: Path) -> str:
    """Return the first non-heading, non-empty paragraph from a markdown file."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return ""
    lines = []
    past_heading = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            if past_heading and lines:
                break
            past_heading = True
            continue
        if not stripped:
            if lines:
                break
            continue
        lines.append(stripped)
    return " ".join(lines)[:200]


def _resolve_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] targets from text."""
    return re.findall(r"\[\[(.+?)(?:\|.+?)?\]\]", text)


def _obsidian_summaries(p: Priorities) -> str:
    """Read Obsidian project files and resolve wikilinks to one-line summaries."""
    proj_dir = _obsidian_projects_dir()
    vault_dir = _obsidian_vault_dir()
    if not proj_dir.exists():
        return ""

    lines = []
    for proj in p.projects:
        proj_file = proj_dir / f"{proj.name}.md"
        if not proj_file.exists():
            continue
        try:
            content = proj_file.read_text()
        except (OSError, UnicodeDecodeError):
            continue

        # Resolve wikilinks in project file
        links = _resolve_wikilinks(content)
        for link_name in links:
            link_path = vault_dir / f"{link_name}.md"
            if link_path.exists():
                summary = _first_paragraph(link_path)
                if summary:
                    lines.append(f"  - {link_name}: {summary}")

    return "\n".join(lines)


def build_context(p: Priorities, user_context_path: Path, budget_chars: int = 16000) -> str:
    """Assemble a system prompt from multiple sources, truncating if over budget."""
    sections = []

    # 1. User context
    if user_context_path.exists():
        try:
            user_ctx = user_context_path.read_text().strip()
            if user_ctx:
                sections.append(("About the user", user_ctx))
        except (OSError, UnicodeDecodeError):
            pass

    # 2. Active tasks
    if p.active:
        lines = []
        for t in p.active:
            tag = f"[{t.project}] " if t.project else ""
            dl = f" (due {t.deadline})" if t.deadline else ""
            pri = " !!" if t.priority == 2 else " !" if t.priority == 1 else ""
            lines.append(f"- {tag}{t.text}{dl}{pri}")
            for note in t.notes:
                lines.append(f"  - {note}")
        sections.append(("Active tasks", "\n".join(lines)))

    # 3. Up Next (top 10)
    if p.up_next:
        lines = []
        for t in p.up_next[:10]:
            tag = f"[{t.project}] " if t.project else ""
            dl = f" (due {t.deadline})" if t.deadline else ""
            pri = " !!" if t.priority == 2 else " !" if t.priority == 1 else ""
            lines.append(f"- {tag}{t.text}{dl}{pri}")
        sections.append(("Up Next", "\n".join(lines)))

    # 3b. Inbox
    if p.inbox:
        lines = []
        for t in p.inbox:
            dl = f" (due {t.deadline})" if t.deadline else ""
            pri = " !!" if t.priority == 2 else " !" if t.priority == 1 else ""
            lines.append(f"- {t.text}{dl}{pri}")
        sections.append(("Inbox (unsorted)", "\n".join(lines)))

    # 4. Project summaries
    if p.projects:
        lines = []
        for proj in p.projects:
            if proj.archived:
                continue
            task_count = len(proj.tasks)
            desc = f" -- {proj.description}" if proj.description else ""
            lines.append(f"### {proj.name}{desc} ({task_count} tasks)")
            for t in proj.tasks[:5]:
                pri = " !!" if t.priority == 2 else " !" if t.priority == 1 else ""
                lines.append(f"- {t.text}{pri}")
        sections.append(("Projects", "\n".join(lines)))

    # 5. Last 15 done tasks
    if p.done:
        lines = []
        for t in p.done[:15]:
            tag = f"[{t.project}] " if t.project else ""
            lines.append(f"- {tag}{t.text}")
        sections.append(("Recently completed", "\n".join(lines)))

    # 6. Notes from PRIORITIES.md
    if p.notes:
        lines = [f"- {n}" for n in p.notes[:10]]
        sections.append(("Notes", "\n".join(lines)))

    # 7. Obsidian wikilink summaries
    obsidian = _obsidian_summaries(p)
    if obsidian:
        sections.append(("Obsidian linked notes", obsidian))

    # Assemble with budget
    header = (
        "You are an accountability coach and mentor. Your job is to help the user define their "
        "goals, break them into concrete tasks, and hold them accountable to follow through.\n\n"
        "RULES (follow strictly):\n"
        "1. UNDERSTAND GOALS: When the user shares what they want to accomplish, ask clarifying "
        "questions to turn vague intentions into specific, actionable tasks. Help them define "
        "what 'done' looks like. Save what you learn using the appropriate tool.\n"
        "2. HOLD ACCOUNTABLE: When you see overdue tasks, stale priorities, or tasks that have "
        "been sitting untouched, call it out. Ask what's blocking them. Don't nag -- be direct "
        "and curious. \"I notice X has been in Active for a while -- what's the holdup?\"\n"
        "3. CELEBRATE WINS: When the user completes tasks, acknowledge it. Briefly. Not over "
        "the top. \"Nice, that's done. What's next?\"\n"
        "4. CHALLENGE GENTLY: If the user is adding more tasks without finishing existing ones, "
        "or avoiding high-priority work, point it out. \"You've got 3 !! items untouched -- "
        "want to talk about what's in the way before adding more?\"\n"
        "5. STAY GROUNDED: Base everything on the facts they've shared and the tasks you can see. "
        "Don't project or assume. Ask rather than lecture.\n"
        "6. ACT ON REQUESTS: When the user asks you to add a task, mark done, reorder, etc., "
        "do it and confirm in one short sentence.\n"
        "7. KEEP THE USER PROFILE CURRENT: The 'About the user' file is a living document "
        "in Obsidian. Whenever you learn something new about the user -- what they're working "
        "on now, their goals, accomplishments, interests -- call save_user_context to update it. "
        "Do this proactively. The profile should reflect their current focus, high-level "
        "dreams/goals, active projects, and recent accomplishments. "
        "Use [[wikilinks]] for project references. Merge new info with existing content.\n"
        "8. INBOX FOR UNASSIGNED TASKS: When adding a task, if the user specifies a project, "
        "assign it there. If they don't specify a project, put it in the inbox (the default). "
        "Never ask which project a task belongs to -- just add it to inbox and move on.\n"
        "9. PRIORITY SYSTEM: Tasks have three priority levels: none (default), ! (important), "
        "!! (critical). !! tasks are must-dos; ! tasks are important but secondary. "
        "When reviewing priorities, push the user toward their !! items first. Use set_priority "
        "to assign levels when stack-ranking.\n"
        "10. BE CONCISE: Keep responses short and direct. You're a coach, not a therapist. "
        "One or two sentences is usually enough. Ask one question at a time.\n\n"
    )
    result = header
    for title, content in sections:
        block = f"## {title}\n{content}\n\n"
        if len(result) + len(block) > budget_chars:
            break
        result += block

    return result.rstrip()
