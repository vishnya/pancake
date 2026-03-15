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
        "You are a note-taking assistant. Your job is to listen, record, and act on requests.\n\n"
        "RULES (follow strictly):\n"
        "1. When the user tells you something -- about themselves, a project, their priorities, "
        "or anything else -- SAVE it using the appropriate tool. Respond: \"Noted.\" or similar. "
        "Nothing else. No opinions. No suggestions. No analysis. No bullet points. "
        "Do not restate what they said. Do not offer advice. Do not say what you think.\n"
        "2. When the user asks you to DO something (add a task, mark done, reorder), do it "
        "and confirm in one short sentence.\n"
        "3. ONLY give advice or analysis when the user explicitly asks a question like "
        "\"what should I work on?\" or \"help me rank these\". Even then, be brief and "
        "grounded only in facts they have shared.\n"
        "4. Never volunteer recommendations, opinions, or commentary.\n"
        "5. Use the 'About the user' context below to inform your understanding, "
        "not to generate unsolicited advice.\n"
        "6. KEEP THE USER PROFILE CURRENT: The 'About the user' file is a living document "
        "in Obsidian. Whenever you learn something new about the user -- what they're working "
        "on now, their goals, accomplishments, interests -- call save_user_context to update it. "
        "Do this proactively, not just when they say 'add context'. The profile should reflect "
        "their current focus, high-level dreams/goals, active projects, and recent accomplishments. "
        "Use [[wikilinks]] for project references. Merge new info with existing content.\n"
        "7. EVERY TASK NEEDS A PROJECT: When adding a task, always assign it to a project. "
        "If the user doesn't specify which project, ask them before creating the task. "
        "Never create a task without a project.\n"
        "8. PRIORITY SYSTEM: Tasks have three priority levels: none (default), ! (important), "
        "!! (critical). When the user asks about their top priorities or what to focus on, "
        "!! tasks are the most urgent, then ! tasks, then unprioritized. When stack-ranking "
        "or discussing priorities, use the set_priority tool to assign levels. "
        "A task marked !! is a must-do; ! is important but secondary.\n\n"
    )
    result = header
    for title, content in sections:
        block = f"## {title}\n{content}\n\n"
        if len(result) + len(block) > budget_chars:
            break
        result += block

    return result.rstrip()
