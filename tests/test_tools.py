"""Tests for chat tool definitions and executor."""

import os
import tempfile

_tmpdir = tempfile.mkdtemp()
os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")

from pancake.priorities import Priorities, Task, ProjectInfo, save, load
from pancake.tools import execute_tool, TOOLS, _fuzzy_score, _find_task


# --- Tool schema validation ---

def test_all_tools_have_required_fields():
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


def test_set_priority_tool_exists():
    names = [t["name"] for t in TOOLS]
    assert "set_priority" in names


# --- Fuzzy matching ---

def test_fuzzy_exact_match():
    assert _fuzzy_score("hello", "hello") == 1.0


def test_fuzzy_substring():
    score = _fuzzy_score("fix", "fix the bug")
    assert score >= 0.8


def test_fuzzy_word_overlap():
    score = _fuzzy_score("review pr", "review the pr for anki")
    assert score >= 0.5


def test_fuzzy_no_match():
    score = _fuzzy_score("completely different", "hello world")
    assert score < 0.3


def test_find_task_across_sections():
    p = Priorities(
        active=[Task(text="active task")],
        up_next=[Task(text="next task")],
        projects=[ProjectInfo(name="P", tasks=[Task(text="project task")])],
    )
    task, score = _find_task(p, "project task")
    assert task.text == "project task"
    assert score >= 0.8


# --- set_priority tool ---

def test_set_priority_tool():
    save(Priorities(active=[Task(text="important task")]))
    result = execute_tool("set_priority", {"text": "important task", "priority": 2})
    assert "critical" in result
    p = load()
    assert p.active[0].priority == 2


def test_set_priority_clears():
    save(Priorities(active=[Task(text="was important", priority=2)]))
    result = execute_tool("set_priority", {"text": "was important", "priority": 0})
    assert "normal" in result
    p = load()
    assert p.active[0].priority == 0


def test_set_priority_no_match():
    save(Priorities(active=[Task(text="real task")]))
    result = execute_tool("set_priority", {"text": "nonexistent", "priority": 1})
    assert "No task matching" in result


def test_set_priority_project_task():
    save(Priorities(projects=[ProjectInfo(name="P", tasks=[Task(text="proj task")])]))
    result = execute_tool("set_priority", {"text": "proj task", "priority": 1})
    assert "important" in result
    p = load()
    assert p.projects[0].tasks[0].priority == 1


# --- add_task tool ---

def test_add_task_tool():
    save(Priorities())
    result = execute_tool("add_task", {"text": "new task"})
    assert "new task" in result
    p = load()
    assert len(p.inbox) == 1
    assert p.inbox[0].text == "new task"


def test_add_task_to_active():
    save(Priorities())
    result = execute_tool("add_task", {"text": "active one", "section": "active"})
    p = load()
    assert len(p.active) == 1


def test_add_task_with_project():
    save(Priorities())
    execute_tool("add_task", {"text": "tagged", "project": "P"})
    p = load()
    assert p.inbox[0].project == "P"


# --- add_project tool ---

def test_add_project_tool():
    save(Priorities())
    result = execute_tool("add_project", {"name": "NewProj", "description": "desc"})
    assert "NewProj" in result
    p = load()
    assert len(p.projects) == 1
    assert p.projects[0].description == "desc"


def test_add_project_duplicate():
    save(Priorities(projects=[ProjectInfo(name="Existing")]))
    result = execute_tool("add_project", {"name": "Existing"})
    assert "already exists" in result


def test_add_project_with_first_task():
    save(Priorities())
    execute_tool("add_project", {"name": "P", "first_task": "first"})
    p = load()
    assert len(p.projects[0].tasks) == 1
    assert p.projects[0].tasks[0].text == "first"


# --- add_project_task tool ---

def test_add_project_task_tool():
    save(Priorities(projects=[ProjectInfo(name="MyProj")]))
    result = execute_tool("add_project_task", {"project": "MyProj", "text": "subtask"})
    assert "subtask" in result
    p = load()
    assert len(p.projects[0].tasks) == 1


def test_add_project_task_fuzzy():
    save(Priorities(projects=[ProjectInfo(name="Deep Mind Interview Prep")]))
    result = execute_tool("add_project_task", {"project": "deep mind", "text": "study"})
    assert "Deep Mind" in result


def test_add_project_task_no_match():
    save(Priorities())
    result = execute_tool("add_project_task", {"project": "ghost", "text": "t"})
    assert "No project matching" in result


# --- mark_done tool ---

def test_mark_done_tool():
    save(Priorities(active=[Task(text="finish report")]))
    result = execute_tool("mark_done", {"text": "finish report"})
    assert "done" in result.lower()
    p = load()
    assert len(p.active) == 0
    assert len(p.done) == 1


def test_mark_done_fuzzy():
    save(Priorities(up_next=[Task(text="review the pull request")]))
    result = execute_tool("mark_done", {"text": "review pull"})
    assert "done" in result.lower()


def test_mark_done_no_match():
    save(Priorities(active=[Task(text="real task")]))
    result = execute_tool("mark_done", {"text": "zzz nonexistent"})
    assert "No task matching" in result


# --- reorder_up_next tool ---

def test_reorder_up_next_tool():
    save(Priorities(up_next=[Task(text="a"), Task(text="b"), Task(text="c")]))
    result = execute_tool("reorder_up_next", {"task_texts": ["c", "a", "b"]})
    p = load()
    assert [t.text for t in p.up_next] == ["c", "a", "b"]


def test_reorder_up_next_partial():
    save(Priorities(up_next=[Task(text="a"), Task(text="b"), Task(text="c")]))
    execute_tool("reorder_up_next", {"task_texts": ["b"]})
    p = load()
    assert p.up_next[0].text == "b"
    assert len(p.up_next) == 3


# --- unknown tool ---

def test_unknown_tool():
    save(Priorities())
    result = execute_tool("nonexistent", {})
    assert "Unknown tool" in result
