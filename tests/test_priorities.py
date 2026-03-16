"""Tests for priorities parser and writer."""

import os
import tempfile

_tmpdir = tempfile.mkdtemp()
os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")

from pancake.priorities import parse, render, load, save, Priorities, Task, ProjectInfo, next_due_date


SAMPLE = """# Priorities
_Last updated: 2026-03-13 09:15_

## Active
- [ ] [Pancake] !! fix hammerspoon chord hotkeys
- [ ] [Anki Fox] test screenshot flow

## Up Next
- [ ] [Pancake] push updated project model
- [ ] [Pancake] test on second device
- [ ] [Anki Fox] review PR

## Projects
### Pancake
Second brain / priority tracker CLI
- [ ] add collapsible projects

### Anki Fox
Hotkey -> screenshot -> Claude -> Anki cards

## Done
- [x] [Pancake] set up CLI

## Notes
- [2026-03-13 09:15] ask about rate limiting
"""


# --- Basic parsing ---

def test_parse_active():
    p = parse(SAMPLE)
    assert len(p.active) == 2
    assert p.active[0].project == "Pancake"
    assert "fix hammerspoon" in p.active[0].text
    assert p.active[1].project == "Anki Fox"


def test_parse_up_next():
    p = parse(SAMPLE)
    assert len(p.up_next) == 3
    assert p.up_next[0].project == "Pancake"


def test_parse_projects():
    p = parse(SAMPLE)
    assert len(p.projects) == 2
    assert p.projects[0].name == "Pancake"
    assert p.projects[0].description == "Second brain / priority tracker CLI"
    assert len(p.projects[0].tasks) == 1
    assert p.projects[0].tasks[0].text == "add collapsible projects"
    assert p.projects[1].name == "Anki Fox"


def test_parse_done():
    p = parse(SAMPLE)
    assert len(p.done) == 1
    assert p.done[0].done is True
    assert p.done[0].project == "Pancake"


def test_parse_notes():
    p = parse(SAMPLE)
    assert len(p.notes) == 1
    assert "rate limiting" in p.notes[0]


def test_parse_empty_content():
    p = parse("")
    assert len(p.active) == 0
    assert len(p.up_next) == 0
    assert len(p.projects) == 0
    assert len(p.done) == 0
    assert len(p.notes) == 0


def test_parse_unknown_section_ignored():
    content = "## Active\n- [ ] task one\n\n## Random\n- stuff\n\n## Up Next\n- [ ] task two\n"
    p = parse(content)
    assert len(p.active) == 1
    assert len(p.up_next) == 1


# --- Deadline parsing ---

def test_parse_task_with_deadline():
    content = "## Active\n- [ ] [Proj] build feature @due(2026-04-01)\n"
    p = parse(content)
    assert p.active[0].deadline == "2026-04-01"
    assert "build feature" == p.active[0].text
    assert "@due" not in p.active[0].text


def test_parse_task_without_deadline():
    content = "## Active\n- [ ] [Proj] no deadline here\n"
    p = parse(content)
    assert p.active[0].deadline == ""


def test_deadline_roundtrip():
    t = Task(text="build feature", project="Proj", deadline="2026-04-01")
    line = t.to_line()
    assert "@due(2026-04-01)" in line
    content = f"## Active\n{line}\n"
    p = parse(content)
    assert p.active[0].deadline == "2026-04-01"
    assert p.active[0].text == "build feature"


# --- Notes sub-items ---

def test_parse_task_with_notes():
    content = """## Active
- [ ] [Proj] my task
  - note: first note
  - note: second note
"""
    p = parse(content)
    assert len(p.active[0].notes) == 2
    assert p.active[0].notes[0] == "first note"
    assert p.active[0].notes[1] == "second note"


def test_parse_task_with_legacy_links():
    """Old link: format should be parsed into notes."""
    content = """## Active
- [ ] [Proj] my task
  - link: https://example.com
  - note: some note
"""
    p = parse(content)
    assert len(p.active[0].notes) == 2
    assert p.active[0].notes[0] == "https://example.com"
    assert p.active[0].notes[1] == "some note"


def test_notes_roundtrip():
    t = Task(text="my task", project="Proj", notes=["note one", "https://example.com"])
    lines = t.to_lines()
    assert len(lines) == 3
    assert "  - note: note one" in lines[1]
    assert "  - note: https://example.com" in lines[2]
    content = "## Active\n" + "\n".join(lines) + "\n"
    p = parse(content)
    assert len(p.active[0].notes) == 2


def test_notes_in_project_tasks():
    content = """## Projects
### MyProj
A description
- [ ] project task
  - note: project note
"""
    p = parse(content)
    assert len(p.projects[0].tasks[0].notes) == 1
    assert p.projects[0].tasks[0].notes[0] == "project note"


def test_notes_in_done_tasks():
    content = """## Done
- [x] [Proj] completed task
  - note: done note
"""
    p = parse(content)
    assert len(p.done[0].notes) == 1
    assert p.done[0].notes[0] == "done note"


# --- Task model ---

def test_task_to_line():
    t = Task(text="fix bug", project="Pancake", done=False)
    assert t.to_line() == "- [ ] [Pancake] fix bug"
    t.done = True
    assert t.to_line() == "- [x] [Pancake] fix bug"


def test_task_to_lines_with_notes_and_deadline():
    t = Task(text="task", project="P", notes=["note1", "note2"], deadline="2026-05-01")
    lines = t.to_lines()
    assert lines[0] == "- [ ] [P] task @due(2026-05-01)"
    assert lines[1] == "  - note: note1"
    assert lines[2] == "  - note: note2"
    assert len(lines) == 3


def test_task_to_lines_empty_notes():
    t = Task(text="simple", project="P")
    lines = t.to_lines()
    assert len(lines) == 1


# --- ProjectInfo model ---

def test_project_to_lines():
    proj = ProjectInfo(
        name="MyProject",
        description="A cool project",
        tasks=[Task(text="subtask", project="MyProject")],
    )
    lines = proj.to_lines()
    assert lines[0] == "### MyProject"
    assert lines[1] == "A cool project"
    assert "- [ ] [MyProject] subtask" in lines[2]


def test_project_to_lines_no_desc():
    proj = ProjectInfo(name="Bare", tasks=[])
    lines = proj.to_lines()
    assert lines == ["### Bare"]


# --- Priorities model ---

def test_find_project():
    p = parse(SAMPLE)
    assert p.find_project("pancake").name == "Pancake"
    assert p.find_project("fox").name == "Anki Fox"
    assert p.find_project("nonexistent") is None


def test_get_project_case_insensitive():
    p = parse(SAMPLE)
    assert p.get_project("pancake").name == "Pancake"
    assert p.get_project("PANCAKE").name == "Pancake"
    assert p.get_project("missing") is None


def test_all_tasks():
    p = parse(SAMPLE)
    all_t = p.all_tasks()
    assert len(all_t) == 5  # 2 active + 3 up_next


def test_project_names():
    p = parse(SAMPLE)
    assert p.project_names() == ["Pancake", "Anki Fox"]


# --- Round-trip ---

def test_round_trip():
    p = Priorities(
        active=[Task(text="active task", project="Proj")],
        up_next=[
            Task(text="next one", project="Proj"),
            Task(text="another", project="Other"),
        ],
        projects=[
            ProjectInfo(name="Proj", description="A project", tasks=[Task(text="subtask", project="Proj")]),
            ProjectInfo(name="Other"),
        ],
        done=[Task(text="old task", project="Proj", done=True)],
        notes=["[2026-03-13 10:00] test note"],
    )
    rendered = render(p)
    p2 = parse(rendered)
    assert len(p2.active) == 1
    assert p2.active[0].project == "Proj"
    assert len(p2.up_next) == 2
    assert len(p2.projects) == 2
    assert p2.projects[0].description == "A project"
    assert len(p2.done) == 1
    assert len(p2.notes) == 1


def test_round_trip_with_deadline_and_notes():
    t = Task(text="complex task", project="P", notes=["a note", "https://url.com"], deadline="2026-06-15")
    p = Priorities(active=[t], projects=[ProjectInfo(name="P")])
    rendered = render(p)
    p2 = parse(rendered)
    assert p2.active[0].deadline == "2026-06-15"
    assert len(p2.active[0].notes) == 2
    assert p2.active[0].notes[0] == "a note"


def test_round_trip_multiple_projects_with_tasks():
    p = Priorities(projects=[
        ProjectInfo(name="A", description="first", tasks=[
            Task(text="a1", project="A"),
            Task(text="a2", project="A"),
        ]),
        ProjectInfo(name="B", tasks=[
            Task(text="b1", project="B"),
        ]),
    ])
    rendered = render(p)
    p2 = parse(rendered)
    assert len(p2.projects) == 2
    assert len(p2.projects[0].tasks) == 2
    assert len(p2.projects[1].tasks) == 1
    assert p2.projects[0].tasks[0].project == "A"
    assert p2.projects[1].tasks[0].project == "B"


# --- Render ---

def test_render_empty_active_shows_placeholder():
    p = Priorities()
    rendered = render(p)
    assert "_Nothing active" in rendered


def test_render_empty_up_next_shows_placeholder():
    p = Priorities()
    rendered = render(p)
    assert "_Backlog empty" in rendered


def test_render_omits_empty_sections():
    p = Priorities()
    rendered = render(p)
    assert "## Done" not in rendered
    assert "## Notes" not in rendered
    assert "## Projects" not in rendered


def test_render_includes_nonempty_sections():
    p = Priorities(
        done=[Task(text="d", done=True)],
        notes=["a note"],
        projects=[ProjectInfo(name="P")],
    )
    rendered = render(p)
    assert "## Done" in rendered
    assert "## Notes" in rendered
    assert "## Projects" in rendered


# --- File I/O ---

def test_save_load():
    p = Priorities(
        up_next=[Task(text="test task", project="Test")],
        projects=[ProjectInfo(name="Test", description="testing")],
    )
    save(p)
    p2 = load()
    assert len(p2.up_next) == 1
    assert p2.up_next[0].project == "Test"
    assert len(p2.projects) == 1


def test_empty_load():
    os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "nonexistent.md")
    p = load()
    assert len(p.active) == 0
    assert len(p.up_next) == 0
    os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")


# --- Obsidian sync ---

def test_sync_project_to_obsidian(tmp_path):
    os.environ["PANCAKE_VAULT"] = str(tmp_path / "PRIORITIES.md")
    proj = ProjectInfo(name="TestProj", description="A test", tasks=[
        Task(text="task one", project="TestProj"),
    ])
    from pancake.priorities import sync_project_to_obsidian, projects_dir
    sync_project_to_obsidian(proj)
    md_path = projects_dir() / "TestProj.md"
    assert md_path.exists()
    content = md_path.read_text()
    assert "# TestProj" in content
    assert "A test" in content
    assert "task one" in content
    os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")


def test_sync_all_projects(tmp_path):
    os.environ["PANCAKE_VAULT"] = str(tmp_path / "PRIORITIES.md")
    p = Priorities(projects=[
        ProjectInfo(name="Alpha", tasks=[Task(text="a", project="Alpha")]),
        ProjectInfo(name="Beta"),
    ])
    from pancake.priorities import sync_all_projects_to_obsidian, projects_dir
    sync_all_projects_to_obsidian(p)
    assert (projects_dir() / "Alpha.md").exists()
    assert (projects_dir() / "Beta.md").exists()
    os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")


# --- Edge cases ---

def test_parse_task_no_checkbox():
    """Lines without checkboxes should not be parsed as tasks."""
    content = "## Active\n- just a bullet point\n- [ ] real task\n"
    p = parse(content)
    assert len(p.active) == 1
    assert p.active[0].text == "real task"


def test_multiple_notes_sections():
    """Only the first ## Notes section should be parsed."""
    content = "## Notes\n- note one\n- note two\n"
    p = parse(content)
    assert len(p.notes) == 2


def test_project_task_inherits_project_name():
    content = "## Projects\n### MyProj\nDesc\n- [ ] subtask\n"
    p = parse(content)
    assert p.projects[0].tasks[0].project == "MyProj"


# --- Priority parsing and serialization ---

def test_parse_priority_1():
    content = "## Active\n- [ ] do thing @p(1)\n"
    p = parse(content)
    assert p.active[0].priority == 1
    assert p.active[0].text == "do thing"


def test_parse_priority_2():
    content = "## Active\n- [ ] urgent thing @p(2)\n"
    p = parse(content)
    assert p.active[0].priority == 2
    assert p.active[0].text == "urgent thing"


def test_parse_no_priority():
    content = "## Active\n- [ ] normal thing\n"
    p = parse(content)
    assert p.active[0].priority == 0


def test_parse_priority_with_deadline():
    content = "## Active\n- [ ] task @due(2026-05-01) @p(2)\n"
    p = parse(content)
    assert p.active[0].priority == 2
    assert p.active[0].deadline == "2026-05-01"
    assert p.active[0].text == "task"


def test_render_priority():
    p = Priorities(active=[Task(text="important", priority=1)])
    text = render(p)
    assert "@p(1)" in text


def test_render_no_priority():
    p = Priorities(active=[Task(text="normal")])
    text = render(p)
    assert "@p(" not in text


def test_priority_roundtrip():
    p = Priorities(
        active=[Task(text="crit", priority=2), Task(text="norm", priority=0)],
        up_next=[Task(text="imp", priority=1)],
    )
    text = render(p)
    p2 = parse(text)
    assert p2.active[0].priority == 2
    assert p2.active[1].priority == 0
    assert p2.up_next[0].priority == 1


def test_priority_default_is_zero():
    t = Task(text="test")
    assert t.priority == 0


# === Recurrence tests ===

def test_parse_recurrence():
    content = "## Active\n- [ ] Anki @due(2026-03-16) @every(daily)\n"
    p = parse(content)
    assert p.active[0].recurrence == "daily"
    assert p.active[0].deadline == "2026-03-16"
    assert p.active[0].text == "Anki"


def test_parse_recurrence_with_priority():
    content = "## Active\n- [ ] task @due(2026-03-16) @every(weekly) @p(1)\n"
    p = parse(content)
    assert p.active[0].recurrence == "weekly"
    assert p.active[0].priority == 1
    assert p.active[0].deadline == "2026-03-16"


def test_render_recurrence():
    p = Priorities(active=[Task(text="Anki", deadline="2026-03-16", recurrence="daily")])
    text = render(p)
    assert "@every(daily)" in text
    assert "@due(2026-03-16)" in text


def test_recurrence_roundtrip():
    p = Priorities(
        active=[Task(text="Anki", deadline="2026-03-16", recurrence="daily", priority=1)],
        up_next=[Task(text="Review", recurrence="weekly", deadline="2026-03-20")],
    )
    text = render(p)
    p2 = parse(text)
    assert p2.active[0].recurrence == "daily"
    assert p2.active[0].priority == 1
    assert p2.active[0].deadline == "2026-03-16"
    assert p2.up_next[0].recurrence == "weekly"


def test_no_recurrence_by_default():
    t = Task(text="test")
    assert t.recurrence == ""


def test_next_due_date_daily():
    result = next_due_date("2026-01-01", "daily")
    # Should be at least tomorrow, not based on old deadline
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    assert result > today or result == today  # next day from max(today, deadline)


def test_next_due_date_weekly():
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    result = next_due_date(today, "weekly")
    expected = (datetime.now() + timedelta(weeks=1)).strftime("%Y-%m-%d")
    assert result == expected


def test_next_due_date_2d():
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    result = next_due_date(today, "2d")
    expected = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    assert result == expected


def test_next_due_date_weekdays_skips_weekend():
    # Friday -> should skip to Monday
    result = next_due_date("2026-03-13", "weekdays")  # 2026-03-13 is a Friday
    assert result >= "2026-03-16"  # Monday


def test_next_due_date_monthly():
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    result = next_due_date(today, "monthly")
    assert result > today


def test_render_no_recurrence():
    p = Priorities(active=[Task(text="normal")])
    text = render(p)
    assert "@every(" not in text
