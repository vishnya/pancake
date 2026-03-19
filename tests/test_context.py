"""Tests for pancake.context -- system prompt assembly."""

import os
import tempfile
from pathlib import Path

import pytest

from pancake.context import build_context, _first_paragraph, _resolve_wikilinks
from pancake.priorities import Priorities, Task, ProjectInfo


@pytest.fixture
def tmp_user_context(tmp_path):
    path = tmp_path / "user_context.md"
    return path


def test_build_context_empty(tmp_user_context):
    p = Priorities()
    ctx = build_context(p, tmp_user_context)
    assert "accountability coach" in ctx
    # No sections beyond header
    assert "## Active" not in ctx


def test_build_context_with_user_context(tmp_user_context):
    tmp_user_context.write_text("I'm a software engineer focused on side projects.")
    p = Priorities()
    ctx = build_context(p, tmp_user_context)
    assert "software engineer" in ctx
    assert "About the user" in ctx


def test_build_context_active_tasks(tmp_user_context):
    p = Priorities(active=[
        Task(text="Fix login bug", project="WebApp", deadline="2026-03-20"),
        Task(text="Write tests", project="WebApp", notes=["unit tests for auth"]),
    ])
    ctx = build_context(p, tmp_user_context)
    assert "Fix login bug" in ctx
    assert "[WebApp]" in ctx
    assert "due 2026-03-20" in ctx
    assert "unit tests for auth" in ctx


def test_build_context_up_next_limited_to_10(tmp_user_context):
    tasks = [Task(text=f"Task {i}") for i in range(15)]
    p = Priorities(up_next=tasks)
    ctx = build_context(p, tmp_user_context)
    assert "Task 9" in ctx
    assert "Task 10" not in ctx


def test_build_context_projects(tmp_user_context):
    p = Priorities(projects=[
        ProjectInfo(name="Alpha", description="Main project", tasks=[
            Task(text="Deploy v2"),
            Task(text="Update docs"),
        ]),
        ProjectInfo(name="Archived", description="Old", tasks=[], archived=True),
    ])
    ctx = build_context(p, tmp_user_context)
    assert "Alpha" in ctx
    assert "Main project" in ctx
    assert "Deploy v2" in ctx
    assert "Archived" not in ctx  # Archived projects excluded


def test_build_context_done_tasks(tmp_user_context):
    p = Priorities(done=[
        Task(text="Shipped feature X", project="Beta", done=True),
    ])
    ctx = build_context(p, tmp_user_context)
    assert "Shipped feature X" in ctx
    assert "Recently completed" in ctx


def test_build_context_notes(tmp_user_context):
    p = Priorities(notes=["[2026-03-14 10:00] Focus on shipping MVP"])
    ctx = build_context(p, tmp_user_context)
    assert "Focus on shipping MVP" in ctx


def test_build_context_budget_truncation(tmp_user_context):
    # Create enough content to exceed a small budget -- verify truncation happens
    tasks = [Task(text=f"Important task number {i} with a long description") for i in range(50)]
    p = Priorities(active=tasks[:5], up_next=tasks[5:20], done=tasks[20:])
    full = build_context(p, tmp_user_context, budget_chars=100000)
    truncated = build_context(p, tmp_user_context, budget_chars=2000)
    assert len(truncated) < len(full)  # Budget actually truncated something


def test_first_paragraph():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Title\n\nThis is the first paragraph.\n\n## Section\n\nMore text.\n")
        f.flush()
        result = _first_paragraph(Path(f.name))
    os.unlink(f.name)
    assert result == "This is the first paragraph."


def test_first_paragraph_missing_file():
    assert _first_paragraph(Path("/nonexistent/file.md")) == ""


def test_resolve_wikilinks():
    text = "See [[Project Alpha]] and [[Meeting Notes|notes]] for details."
    links = _resolve_wikilinks(text)
    assert links == ["Project Alpha", "Meeting Notes"]


def test_resolve_wikilinks_empty():
    assert _resolve_wikilinks("No links here.") == []


def test_context_shows_priority(tmp_user_context):
    """Priority markers appear in the system prompt context."""
    p = Priorities(
        active=[Task(text="urgent", priority=2), Task(text="normal")],
        up_next=[Task(text="important", priority=1)],
    )
    ctx = build_context(p, tmp_user_context)
    assert "urgent !!" in ctx
    assert "important !" in ctx
    assert "normal" in ctx
    # Normal task should NOT have a priority marker
    for line in ctx.split("\n"):
        if "normal" in line and "urgent" not in line:
            assert "!" not in line


def test_context_shows_project_task_priority(tmp_user_context):
    p = Priorities(
        projects=[ProjectInfo(name="P", tasks=[Task(text="critical proj task", priority=2)])],
    )
    ctx = build_context(p, tmp_user_context)
    assert "critical proj task !!" in ctx


def test_context_priority_system_rule(tmp_user_context):
    """System prompt mentions the priority system."""
    p = Priorities()
    ctx = build_context(p, tmp_user_context)
    assert "PRIORITY SYSTEM" in ctx
