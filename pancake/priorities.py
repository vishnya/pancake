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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_VAULT_PATH = os.path.expanduser("~/Obsidian/main/PRIORITIES.md")


def vault_path() -> Path:
    return Path(os.environ.get("PANCAKE_VAULT", DEFAULT_VAULT_PATH))


def user_context_path() -> Path:
    """User context file lives in the Obsidian vault alongside PRIORITIES.md."""
    return vault_path().parent / "About Me.md"


@dataclass
class Task:
    text: str
    project: str = ""
    done: bool = False
    notes: list[str] = field(default_factory=list)
    deadline: str = ""  # ISO date string, e.g. "2026-03-20"
    priority: int = 0  # 0=normal, 1=important (!), 2=critical (!!)

    def to_lines(self) -> list[str]:
        check = "x" if self.done else " "
        tag = f"[{self.project}] " if self.project else ""
        dl = f" @due({self.deadline})" if self.deadline else ""
        pri = f" @p({self.priority})" if self.priority else ""
        lines = [f"- [{check}] {tag}{self.text}{dl}{pri}"]
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
        return self.active + self.up_next

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
    pri_match = re.search(r"\s*@p\(([12])\)", text)
    if pri_match:
        priority = int(pri_match.group(1))
        text = text[:pri_match.start()] + text[pri_match.end():]
    return Task(
        text=text.strip(),
        project=m.group(2) or "",
        done=m.group(1) == "x",
        deadline=deadline,
        priority=priority,
    )


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
            if section in ("active", "up_next"):
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
        if section in ("active", "up_next"):
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


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def time_str() -> str:
    return datetime.now().strftime("%H:%M")
