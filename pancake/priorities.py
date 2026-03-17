"""Parse and write PRIORITIES.md -- the single source of truth for Pancake.

Format: global priority stack with project-tagged tasks.
- ## Active: tasks currently being worked on (2-3 at a time)
- ## Up Next: ordered backlog, top is highest priority
- ## Projects: descriptions and links per project
- ## Done: completed tasks
- ## Notes: timestamped notes

Tasks carry [ProjectName] tags. Order in file = priority order.
Hand-editable in Obsidian (Alt+Up/Down to reorder lines).
"""

import fcntl
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_VAULT_PATH = os.path.expanduser("~/Obsidian/main/PRIORITIES.md")

# Thread-local profile context for multi-profile support
_ctx = threading.local()


def set_active_profile(profile_slug: str | None) -> None:
    """Set the active profile for the current thread/request."""
    _ctx.profile_slug = profile_slug


def get_active_profile() -> str | None:
    """Get the active profile slug for the current thread."""
    return getattr(_ctx, "profile_slug", None)


def vault_path() -> Path:
    """Return the PRIORITIES.md path for the active profile, or fallback to env var."""
    slug = get_active_profile()
    if slug:
        from pancake.accounts import vault_path_for_profile
        return vault_path_for_profile(slug)
    return Path(os.environ.get("PANCAKE_VAULT", DEFAULT_VAULT_PATH))


def user_context_path() -> Path:
    """User context file lives alongside PRIORITIES.md."""
    slug = get_active_profile()
    if slug:
        from pancake.accounts import user_context_path_for_profile
        return user_context_path_for_profile(slug)
    return vault_path().parent / "About Me.md"


@dataclass
class Task:
    text: str
    project: str = ""
    done: bool = False
    notes: list[str] = field(default_factory=list)
    deadline: str = ""  # ISO date string, e.g. "2026-03-20"
    priority: int = 0  # 0=normal, 1=important (!), 2=critical (!!)
    recurrence: str = ""  # e.g. "daily", "2d", "weekly", "weekdays", "monthly"
    assignee: str = ""  # username of assigned person
    manual: bool = False  # user manually placed this task; auto_sort should skip it

    def to_lines(self) -> list[str]:
        check = "x" if self.done else " "
        tag = f"[{self.project}] " if self.project else ""
        dl = f" @due({self.deadline})" if self.deadline else ""
        rec = f" @every({self.recurrence})" if self.recurrence else ""
        pri = f" @p({self.priority})" if self.priority else ""
        asg = f" @assigned({self.assignee})" if self.assignee else ""
        man = " @manual" if self.manual else ""
        lines = [f"- [{check}] {tag}{self.text}{dl}{rec}{pri}{asg}{man}"]
        for note in self.notes:
            lines.append(f"  - note: {note}")
        return lines

    def to_line(self) -> str:
        return self.to_lines()[0]


@dataclass
class ProjectInfo:
    name: str
    description: str = ""
    tasks: list = field(default_factory=list)  # list[Task]
    archived: bool = False

    def to_lines(self) -> list[str]:
        header = f"### {self.name}"
        if self.archived:
            header += " [archived]"
        lines = [header]
        if self.description:
            lines.append(self.description)
        for task in self.tasks:
            lines.extend(task.to_lines())
        return lines


@dataclass
class Priorities:
    active: list[Task] = field(default_factory=list)
    up_next: list[Task] = field(default_factory=list)
    inbox: list[Task] = field(default_factory=list)
    projects: list[ProjectInfo] = field(default_factory=list)
    done: list[Task] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def get_project(self, name: str) -> ProjectInfo | None:
        for p in self.projects:
            if p.name.lower() == name.lower():
                return p
        return None

    def find_project(self, name: str) -> ProjectInfo | None:
        """Fuzzy match project by substring."""
        proj = self.get_project(name)
        if proj:
            return proj
        for p in self.projects:
            if name.lower() in p.name.lower():
                return p
        return None

    def all_tasks(self) -> list[Task]:
        return self.active + self.up_next + self.inbox

    def project_names(self) -> list[str]:
        return [p.name for p in self.projects]


def _parse_task(line: str) -> Task | None:
    """Parse '- [ ] [Project] text @due(date)' or '- [x] [Project] text'."""
    m = re.match(r"^- \[([ x])\]\s+(?:\[(.+?)\]\s+)?(.+)$", line.strip())
    if not m:
        return None
    text = m.group(3)
    deadline = ""
    priority = 0
    due_match = re.search(r"\s*@due\((\d{4}-\d{2}-\d{2})\)", text)
    if due_match:
        deadline = due_match.group(1)
        text = text[:due_match.start()] + text[due_match.end():]
    recurrence = ""
    rec_match = re.search(r"\s*@every\(([^)]+)\)", text)
    if rec_match:
        recurrence = rec_match.group(1)
        text = text[:rec_match.start()] + text[rec_match.end():]
    pri_match = re.search(r"\s*@p\(([12])\)", text)
    if pri_match:
        priority = int(pri_match.group(1))
        text = text[:pri_match.start()] + text[pri_match.end():]
    assignee = ""
    asg_match = re.search(r"\s*@assigned\(([^)]+)\)", text)
    if asg_match:
        assignee = asg_match.group(1)
        text = text[:asg_match.start()] + text[asg_match.end():]
    manual = False
    manual_match = re.search(r"\s*@manual\b", text)
    if manual_match:
        manual = True
        text = text[:manual_match.start()] + text[manual_match.end():]
    return Task(
        text=text.strip(),
        project=m.group(2) or "",
        done=m.group(1) == "x",
        deadline=deadline,
        priority=priority,
        recurrence=recurrence,
        assignee=assignee,
        manual=manual,
    )


def next_due_date(deadline: str, recurrence: str) -> str:
    """Compute the next due date for a recurring task.

    Base date is max(today, deadline) + interval, so missed days don't cascade.
    """
    today = datetime.now().date()
    if deadline:
        base = max(today, datetime.strptime(deadline, "%Y-%m-%d").date())
    else:
        base = today

    rec = recurrence.lower().strip()
    if rec in ("daily", "1d"):
        result = base + timedelta(days=1)
    elif rec == "weekdays":
        result = base + timedelta(days=1)
        while result.weekday() >= 5:  # skip Sat(5), Sun(6)
            result += timedelta(days=1)
    elif rec in ("weekly", "1w"):
        result = base + timedelta(weeks=1)
    elif rec in ("monthly", "1m"):
        month = base.month % 12 + 1
        year = base.year + (1 if base.month == 12 else 0)
        day = min(base.day, 28)  # safe for all months
        result = base.replace(year=year, month=month, day=day)
    elif m := re.match(r"(\d+)d", rec):
        result = base + timedelta(days=int(m.group(1)))
    elif m := re.match(r"(\d+)w", rec):
        result = base + timedelta(weeks=int(m.group(1)))
    elif m := re.match(r"(\d+)m", rec):
        months = int(m.group(1))
        month = (base.month - 1 + months) % 12 + 1
        year = base.year + (base.month - 1 + months) // 12
        day = min(base.day, 28)
        result = base.replace(year=year, month=month, day=day)
    else:
        result = base + timedelta(days=1)  # fallback: daily

    return result.strftime("%Y-%m-%d")


def parse(content: str) -> Priorities:
    p = Priorities()
    lines = content.split("\n")
    section = None
    current_project = None
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("# Priorities") or stripped.startswith("_"):
            i += 1
            continue

        # Section headers
        if stripped == "## Active":
            section = "active"
            current_project = None
            i += 1
            continue
        elif stripped == "## Up Next":
            section = "up_next"
            current_project = None
            i += 1
            continue
        elif stripped == "## Inbox":
            section = "inbox"
            current_project = None
            i += 1
            continue
        elif stripped == "## Projects":
            section = "projects"
            current_project = None
            i += 1
            continue
        elif stripped == "## Done":
            section = "done"
            current_project = None
            i += 1
            continue
        elif stripped == "## Notes":
            section = "notes"
            current_project = None
            i += 1
            continue
        elif stripped.startswith("## "):
            section = None
            current_project = None
            i += 1
            continue

        if stripped == "":
            i += 1
            continue

        # Parse indented sub-items (link:/note: under a task)
        if line.startswith("  - link: ") or line.startswith("  - note: "):
            # Find the last task added in the current section
            last_task = None
            if section in ("active", "up_next", "inbox"):
                tasks = getattr(p, section)
                if tasks:
                    last_task = tasks[-1]
            elif section == "projects" and current_project and current_project.tasks:
                last_task = current_project.tasks[-1]
            elif section == "done":
                if p.done:
                    last_task = p.done[-1]
            if last_task:
                if line.startswith("  - link: "):
                    last_task.notes.append(line[10:].strip())
                elif line.startswith("  - note: "):
                    last_task.notes.append(line[10:].strip())
            i += 1
            continue

        # Parse tasks in Active / Up Next
        if section in ("active", "up_next", "inbox"):
            task = _parse_task(stripped)
            if task:
                getattr(p, section).append(task)

        # Parse projects
        elif section == "projects":
            if stripped.startswith("### "):
                proj_name = stripped[4:].strip()
                archived = proj_name.endswith(" [archived]")
                if archived:
                    proj_name = proj_name[:-11].strip()
                current_project = ProjectInfo(name=proj_name, archived=archived)
                p.projects.append(current_project)
            elif current_project is not None:
                task = _parse_task(stripped)
                if task:
                    task.project = current_project.name
                    current_project.tasks.append(task)
                elif not current_project.description:
                    current_project.description = stripped

        # Parse done
        elif section == "done":
            task = _parse_task(stripped)
            if task:
                p.done.append(task)

        # Parse notes
        elif section == "notes":
            if stripped.startswith("- "):
                p.notes.append(stripped[2:])

        i += 1

    return p


def render(p: Priorities) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Priorities",
        f"_Last updated: {now}_",
        "",
    ]

    # Active
    lines.append("## Active")
    if p.active:
        for task in p.active:
            lines.extend(task.to_lines())
    else:
        lines.append("_Nothing active. Use `lc active N` to start a task._")
    lines.append("")

    # Up Next
    lines.append("## Up Next")
    if p.up_next:
        for task in p.up_next:
            lines.extend(task.to_lines())
    else:
        lines.append("_Backlog empty._")
    lines.append("")

    # Inbox
    lines.append("## Inbox")
    if p.inbox:
        for task in p.inbox:
            lines.extend(task.to_lines())
    else:
        lines.append("_No unsorted tasks._")
    lines.append("")

    # Projects
    if p.projects:
        lines.append("## Projects")
        for proj in p.projects:
            lines.extend(proj.to_lines())
            lines.append("")

    # Done
    if p.done:
        lines.append("## Done")
        for task in p.done:
            lines.extend(task.to_lines())
        lines.append("")

    # Notes
    if p.notes:
        lines.append("## Notes")
        for n in p.notes:
            lines.append(f"- {n}")
        lines.append("")

    return "\n".join(lines)


def load() -> Priorities:
    path = vault_path()
    if not path.exists():
        return Priorities()
    return parse(path.read_text())


def save(p: Priorities) -> None:
    path = vault_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render(p)
    with open(path, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(content)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    sync_all_projects_to_obsidian(p)


def projects_dir() -> Path:
    """Directory for individual project .md files in the Obsidian vault."""
    slug = get_active_profile()
    if slug:
        from pancake.accounts import projects_dir_for_profile
        return projects_dir_for_profile(slug)
    return vault_path().parent / "Projects"


def sync_project_to_obsidian(proj: ProjectInfo) -> None:
    """Write a project's data to its own Obsidian .md file for graph structure."""
    d = projects_dir()
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"# {proj.name}", ""]
    if proj.description:
        lines.extend([proj.description, ""])
    if proj.tasks:
        lines.append("## Tasks")
        for task in proj.tasks:
            lines.append(task.to_line())
        lines.append("")
    (d / f"{proj.name}.md").write_text("\n".join(lines))


def sync_all_projects_to_obsidian(p: Priorities) -> None:
    """Sync all projects to individual Obsidian files."""
    for proj in p.projects:
        sync_project_to_obsidian(proj)


def auto_sort_recurring(p: Priorities) -> bool:
    """Move recurring tasks between sections based on their deadline.

    - Due today or overdue → Active
    - Due tomorrow through 7 days → Up Next
    - Due 7+ days out → demote from Active to Up Next if needed

    Returns True if any tasks were moved.
    """
    today = datetime.now().date()
    week_out = today + timedelta(days=7)
    changed = False

    # Collect recurring tasks from all three sections with their source info
    moves: list[tuple[str, int, Task, str]] = []  # (from_section, idx, task, to_section)

    for section_name in ("active", "up_next", "inbox"):
        tasks = getattr(p, section_name)
        for i, task in enumerate(tasks):
            if not task.recurrence or not task.deadline:
                continue
            if task.manual:
                continue  # user manually placed this task, respect their choice
            try:
                due = datetime.strptime(task.deadline, "%Y-%m-%d").date()
            except ValueError:
                continue

            if due <= today:
                # Due today or overdue → should be Active
                if section_name != "active":
                    moves.append((section_name, i, task, "active"))
            elif due <= week_out:
                # Due within the next week → should be Up Next
                if section_name == "active":
                    moves.append((section_name, i, task, "up_next"))
                elif section_name == "inbox":
                    moves.append((section_name, i, task, "up_next"))
            else:
                # Due 7+ days out → shouldn't be Active
                if section_name == "active":
                    moves.append((section_name, i, task, "up_next"))

    # Apply moves in reverse index order to avoid index shifting
    for section_name in ("active", "up_next", "inbox"):
        section_moves = [(i, task, to) for (s, i, task, to) in moves if s == section_name]
        for i, task, to in sorted(section_moves, key=lambda x: x[0], reverse=True):
            getattr(p, section_name).pop(i)

    # Add tasks to their target sections
    for _, _, task, to_section in moves:
        if to_section == "active":
            p.active.append(task)
        elif to_section == "up_next":
            # Insert at top of up_next for visibility
            p.up_next.insert(0, task)
        changed = changed or bool(moves)

    return changed


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def time_str() -> str:
    return datetime.now().strftime("%H:%M")
