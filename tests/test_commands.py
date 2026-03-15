"""Integration tests for CLI commands."""

import os
import tempfile

_tmpdir = tempfile.mkdtemp()
os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")

from pancake.priorities import load, save, Priorities, Task, ProjectInfo
from pancake.commands import focus, note, drop, priority


def setup():
    save(Priorities())


# --- Project management ---

def test_project_add():
    setup()
    priority.add_project("My Project", desc="testing")
    p = load()
    assert len(p.projects) == 1
    assert p.projects[0].description == "testing"


def test_project_add_duplicate(capsys):
    setup()
    priority.add_project("Dup")
    priority.add_project("Dup")
    p = load()
    assert len(p.projects) == 1
    captured = capsys.readouterr()
    assert "already exists" in captured.out


def test_project_add_no_description():
    setup()
    priority.add_project("Bare")
    p = load()
    assert p.projects[0].description == ""


# --- Task add ---

def test_add_task():
    setup()
    priority.add_project("Proj")
    priority.add("fix bug", project="Proj")
    p = load()
    assert len(p.up_next) == 1
    assert p.up_next[0].project == "Proj"


def test_add_task_nonexistent_project(capsys):
    setup()
    priority.add("task", project="Ghost")
    p = load()
    assert len(p.up_next) == 0
    captured = capsys.readouterr()
    assert "No project matching" in captured.out


def test_add_task_fuzzy_project_match():
    setup()
    priority.add_project("My Long Project Name")
    priority.add("task", project="long")
    p = load()
    assert p.up_next[0].project == "My Long Project Name"


def test_add_task_priority_ordering():
    setup()
    priority.add_project("P")
    priority.add("normal task", project="P")
    priority.add("urgent task", level="!!", project="P")
    priority.add("high task", level="!", project="P")
    p = load()
    assert "!!" in p.up_next[0].text
    assert "!" in p.up_next[1].text and "!!" not in p.up_next[1].text


def test_add_multiple_urgent_ordering():
    setup()
    priority.add_project("P")
    priority.add("normal", project="P")
    priority.add("urgent1", level="!!", project="P")
    priority.add("urgent2", level="!!", project="P")
    priority.add("high", level="!", project="P")
    p = load()
    # urgent2 should be at top (last !! inserted at 0)
    assert "urgent2" in p.up_next[0].text
    assert "urgent1" in p.up_next[1].text
    # high after all urgents
    assert "high" in p.up_next[2].text
    assert "normal" in p.up_next[3].text


# --- Activate ---

def test_activate():
    setup()
    priority.add_project("P")
    priority.add("task one", project="P")
    priority.add("task two", project="P")
    focus.activate(1)  # first up_next task
    p = load()
    assert len(p.active) == 1
    assert len(p.up_next) == 1


def test_activate_already_active(capsys):
    setup()
    p = Priorities(
        active=[Task(text="already active", project="P")],
        up_next=[Task(text="waiting", project="P")],
    )
    save(p)
    focus.activate(1)  # task 1 is already active
    p = load()
    assert len(p.active) == 1  # unchanged
    captured = capsys.readouterr()
    assert "already active" in captured.out


def test_activate_out_of_range(capsys):
    setup()
    p = Priorities(up_next=[Task(text="only one", project="P")])
    save(p)
    focus.activate(99)
    captured = capsys.readouterr()
    assert "No task #99" in captured.out


def test_activate_zero_index(capsys):
    setup()
    p = Priorities(up_next=[Task(text="task", project="P")])
    save(p)
    focus.activate(0)
    captured = capsys.readouterr()
    assert "No task #0" in captured.out


# --- Mark done ---

def test_done_first_active():
    setup()
    p = Priorities(
        active=[Task(text="task a", project="P"), Task(text="task b", project="P")],
    )
    save(p)
    focus.mark_done()
    p = load()
    assert len(p.active) == 1
    assert p.active[0].text == "task b"
    assert len(p.done) == 1
    assert p.done[0].done is True


def test_done_by_number():
    setup()
    p = Priorities(
        active=[Task(text="active", project="P")],
        up_next=[Task(text="next one", project="P"), Task(text="next two", project="P")],
    )
    save(p)
    focus.mark_done(3)  # "next two"
    p = load()
    assert len(p.up_next) == 1
    assert p.up_next[0].text == "next one"
    assert len(p.done) == 1


def test_done_no_active_tasks(capsys):
    setup()
    p = Priorities()
    save(p)
    focus.mark_done()
    captured = capsys.readouterr()
    assert "No active tasks" in captured.out


def test_done_out_of_range(capsys):
    setup()
    p = Priorities(active=[Task(text="one", project="P")])
    save(p)
    focus.mark_done(99)
    captured = capsys.readouterr()
    assert "No task #99" in captured.out


def test_done_preserves_notes():
    """Notes on a task should survive being marked done."""
    setup()
    p = Priorities(
        active=[Task(text="task", project="P", notes=["important note"])],
    )
    save(p)
    focus.mark_done()
    p = load()
    assert p.done[0].notes == ["important note"]


def test_done_preserves_deadline():
    setup()
    p = Priorities(
        active=[Task(text="task", project="P", deadline="2026-05-01")],
    )
    save(p)
    focus.mark_done()
    p = load()
    assert p.done[0].deadline == "2026-05-01"


# --- Bump ---

def test_bump_to_top():
    setup()
    p = Priorities(
        up_next=[
            Task(text="first", project="P"),
            Task(text="second", project="P"),
            Task(text="third", project="P"),
        ],
    )
    save(p)
    focus.bump(3)  # move "third" to top
    p = load()
    assert p.up_next[0].text == "third"


def test_bump_to_position():
    setup()
    p = Priorities(
        active=[Task(text="active", project="P")],
        up_next=[
            Task(text="first", project="P"),
            Task(text="second", project="P"),
            Task(text="third", project="P"),
        ],
    )
    save(p)
    focus.bump(4, 2)  # move "third" (global #4) to position 2
    p = load()
    assert p.up_next[0].text == "third"


def test_bump_out_of_range(capsys):
    setup()
    p = Priorities(up_next=[Task(text="only", project="P")])
    save(p)
    focus.bump(99)
    captured = capsys.readouterr()
    assert "No task #99" in captured.out


# --- Park ---

def test_park():
    setup()
    p = Priorities(
        active=[Task(text="task a", project="P"), Task(text="task b", project="P")],
        up_next=[Task(text="waiting", project="P")],
    )
    save(p)
    focus.park(2)  # park "task b"
    p = load()
    assert len(p.active) == 1
    assert p.up_next[0].text == "task b"  # parked to top of up_next


def test_park_out_of_range(capsys):
    setup()
    p = Priorities(active=[Task(text="one", project="P")])
    save(p)
    focus.park(5)
    captured = capsys.readouterr()
    assert "No active task #5" in captured.out


def test_park_no_active(capsys):
    setup()
    p = Priorities()
    save(p)
    focus.park(1)
    captured = capsys.readouterr()
    assert "No active task" in captured.out


# --- Progress ---

def test_progress():
    setup()
    p = Priorities(active=[Task(text="task a", project="P")])
    save(p)
    focus.log_progress("halfway done")
    p = load()
    assert any("halfway done" in n for n in p.notes)


def test_progress_no_active(capsys):
    setup()
    p = Priorities()
    save(p)
    focus.log_progress("some progress")
    captured = capsys.readouterr()
    assert "No active tasks" in captured.out


def test_progress_tags_project():
    setup()
    p = Priorities(active=[Task(text="task", project="MyProj")])
    save(p)
    focus.log_progress("did something")
    p = load()
    assert any("[MyProj]" in n for n in p.notes)


# --- Note ---

def test_note():
    setup()
    p = Priorities(active=[Task(text="task a", project="Proj")])
    save(p)
    note.run("remember this")
    p = load()
    assert len(p.notes) == 1
    assert "remember this" in p.notes[0]
    assert "Proj" in p.notes[0]


# --- Drop ---

def test_drop_with_url():
    setup()
    p = Priorities(active=[Task(text="task", project="Proj")])
    save(p)
    drop.run("https://example.com")
    p = load()
    assert len(p.notes) == 1
    assert "https://example.com" in p.notes[0]
    assert "[link]" in p.notes[0]


