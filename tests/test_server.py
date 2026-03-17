"""Tests for web server API endpoints and undo functionality."""

import json
import os
import tempfile
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen

import pytest

_tmpdir = tempfile.mkdtemp()
os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")
os.environ["PANCAKE_CONFIG_DIR"] = os.path.join(_tmpdir, "config")
os.environ["PANCAKE_DATA_ROOT"] = _tmpdir

from pancake.priorities import Priorities, Task, ProjectInfo, save, load
from web.server import PancakeHandler, UNDO_STACK, VALID_SESSIONS, SESSION_MAX_AGE, _get_undo_stack
import time as _time

# Create a test account so the server allows API access
os.makedirs(os.path.join(_tmpdir, "config"), exist_ok=True)
_test_session_token = "test-session-token-for-tests"

def _setup_test_account():
    """Create test account and session for API access."""
    from pancake.accounts import create_account, create_profile, add_membership
    from pancake.priorities import set_active_profile
    try:
        create_account("testadmin", "Test Admin", "testpass123")
    except ValueError:
        pass  # already exists
    try:
        create_profile("test-personal", "Personal", "testadmin")
    except ValueError:
        pass
    # Add rachel membership for legacy auth mode tests
    try:
        add_membership("rachel", "test-personal", "admin")
    except Exception:
        pass
    # Set active profile so vault_path() resolves correctly in test thread
    set_active_profile("test-personal")
    VALID_SESSIONS[_test_session_token] = {
        "account": "testadmin",
        "expiry": _time.time() + SESSION_MAX_AGE,
    }

_setup_test_account()


def _api(port, path, body=None):
    url = f"http://127.0.0.1:{port}/api/{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    headers["Cookie"] = f"pancake_session={_test_session_token}; pancake_profile=test-personal"
    req = Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    with urlopen(req) as resp:
        return json.loads(resp.read())


@pytest.fixture()
def server():
    # Restore env vars to this test module's tmpdir (other test files may change them)
    os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")
    os.environ["PANCAKE_CONFIG_DIR"] = os.path.join(_tmpdir, "config")
    os.environ["PANCAKE_DATA_ROOT"] = _tmpdir
    # Ensure test account and session exist
    _setup_test_account()
    VALID_SESSIONS[_test_session_token] = {
        "account": "testadmin",
        "expiry": _time.time() + SESSION_MAX_AGE,
    }
    srv = HTTPServer(("127.0.0.1", 0), PancakeHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _get_undo_stack().clear()
    yield port
    srv.shutdown()


def _seed(**kwargs):
    from pancake.priorities import set_active_profile
    set_active_profile("test-personal")
    defaults = dict(
        active=[Task(text="active task", project="Test")],
        up_next=[Task(text="next task", project="Test")],
        projects=[ProjectInfo(name="Test", description="testing")],
    )
    defaults.update(kwargs)
    p = Priorities(**defaults)
    save(p)
    _get_undo_stack().clear()


# =============================================================================
# GET /api/priorities
# =============================================================================

def test_get_priorities(server):
    _seed()
    data = _api(server, "priorities")
    assert len(data["active"]) == 1
    assert len(data["up_next"]) == 1
    assert len(data["projects"]) == 1
    assert data["active"][0]["text"] == "active task"
    assert data["active"][0]["project"] == "Test"


def test_get_priorities_empty(server):
    save(Priorities())
    data = _api(server, "priorities")
    assert data["active"] == []
    assert data["up_next"] == []
    assert data["projects"] == []
    assert data["done"] == []
    assert data["notes"] == []


def test_get_priorities_includes_notes_and_deadline(server):
    p = Priorities(active=[
        Task(text="task", project="P", notes=["a note", "https://url.com"], deadline="2026-05-01"),
    ], projects=[ProjectInfo(name="P")])
    save(p)
    data = _api(server, "priorities")
    t = data["active"][0]
    assert t["notes"] == ["a note", "https://url.com"]
    assert t["deadline"] == "2026-05-01"


# =============================================================================
# POST /api/task/add
# =============================================================================

def test_add_task_to_up_next(server):
    _seed()
    data = _api(server, "task/add", {"text": "new task", "project": "Test"})
    assert len(data["up_next"]) == 2
    assert data["up_next"][0]["text"] == "new task"  # inserted at front


def test_add_task_to_active(server):
    _seed()
    data = _api(server, "task/add", {"text": "urgent", "section": "active"})
    assert len(data["active"]) == 2


# =============================================================================
# POST /api/task/done
# =============================================================================

def test_mark_task_done_active(server):
    _seed()
    data = _api(server, "task/done", {"section": "active", "index": 0})
    assert len(data["active"]) == 0
    assert len(data["done"]) == 1
    assert data["done"][0]["text"] == "active task"
    assert data["done"][0]["done"] is True


def test_mark_task_done_up_next(server):
    _seed()
    data = _api(server, "task/done", {"section": "up_next", "index": 0})
    assert len(data["up_next"]) == 0
    assert len(data["done"]) == 1


def test_mark_task_done_preserves_notes(server):
    p = Priorities(
        active=[Task(text="task", project="P", notes=["keep me"])],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "task/done", {"section": "active", "index": 0})
    assert data["done"][0]["notes"] == ["keep me"]


# =============================================================================
# POST /api/task/edit
# =============================================================================

def test_edit_task_text(server):
    _seed()
    data = _api(server, "task/edit", {"section": "active", "index": 0, "text": "renamed"})
    assert data["active"][0]["text"] == "renamed"


def test_edit_task_project(server):
    _seed()
    data = _api(server, "task/edit", {"section": "active", "index": 0, "text": "same", "project": "Other"})
    assert data["active"][0]["project"] == "Other"


# =============================================================================
# POST /api/task/delete
# =============================================================================

def test_delete_task(server):
    _seed()
    data = _api(server, "task/delete", {"section": "active", "index": 0})
    assert len(data["active"]) == 0


def test_delete_from_up_next(server):
    _seed()
    data = _api(server, "task/delete", {"section": "up_next", "index": 0})
    assert len(data["up_next"]) == 0


def test_delete_out_of_range(server):
    _seed()
    data = _api(server, "task/delete", {"section": "active", "index": 99})
    assert len(data["active"]) == 1  # unchanged


# =============================================================================
# POST /api/task/add_note, /api/task/delete_note
# =============================================================================

def test_add_note_to_task(server):
    _seed()
    data = _api(server, "task/add_note", {"section": "active", "index": 0, "text": "my note"})
    assert data["active"][0]["notes"] == ["my note"]


def test_add_multiple_notes(server):
    _seed()
    _api(server, "task/add_note", {"section": "active", "index": 0, "text": "note 1"})
    data = _api(server, "task/add_note", {"section": "active", "index": 0, "text": "note 2"})
    assert len(data["active"][0]["notes"]) == 2


def test_add_note_to_project_task(server):
    _seed(projects=[ProjectInfo(name="Test", tasks=[Task(text="proj task", project="Test")])])
    data = _api(server, "task/add_note", {"section": "project:Test", "index": 0, "text": "proj note"})
    assert data["projects"][0]["tasks"][0]["notes"] == ["proj note"]


def test_delete_note_from_task(server):
    p = Priorities(
        active=[Task(text="task", project="P", notes=["note0", "note1"])],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "task/delete_note", {"section": "active", "index": 0, "sub_index": 0})
    assert data["active"][0]["notes"] == ["note1"]


def test_delete_note_out_of_range(server):
    p = Priorities(
        active=[Task(text="task", project="P", notes=["only"])],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "task/delete_note", {"section": "active", "index": 0, "sub_index": 99})
    assert data["active"][0]["notes"] == ["only"]  # unchanged


# =============================================================================
# POST /api/task/deadline
# =============================================================================

def test_set_deadline(server):
    _seed()
    data = _api(server, "task/deadline", {"section": "active", "index": 0, "deadline": "2026-06-01"})
    assert data["active"][0]["deadline"] == "2026-06-01"


def test_clear_deadline(server):
    p = Priorities(
        active=[Task(text="task", project="P", deadline="2026-06-01")],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "task/deadline", {"section": "active", "index": 0, "deadline": ""})
    assert data["active"][0]["deadline"] == ""


def test_set_deadline_on_project_task(server):
    _seed(projects=[ProjectInfo(name="Test", tasks=[Task(text="pt", project="Test")])])
    data = _api(server, "task/deadline", {"section": "project:Test", "index": 0, "deadline": "2026-07-01"})
    assert data["projects"][0]["tasks"][0]["deadline"] == "2026-07-01"


# =============================================================================
# POST /api/reorder
# =============================================================================

def test_reorder_active(server):
    p = Priorities(
        active=[Task(text="a", project="P"), Task(text="b", project="P")],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    # Swap order
    data = _api(server, "reorder", {
        "active": [{"text": "b", "project": "P", "done": False, "notes": [], "deadline": ""},
                    {"text": "a", "project": "P", "done": False, "notes": [], "deadline": ""}],
        "up_next": [],
    })
    assert data["active"][0]["text"] == "b"
    assert data["active"][1]["text"] == "a"


def test_reorder_up_next(server):
    p = Priorities(
        up_next=[Task(text="x", project="P"), Task(text="y", project="P"), Task(text="z", project="P")],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "reorder", {
        "active": [],
        "up_next": [
            {"text": "z", "project": "P", "done": False, "notes": [], "deadline": ""},
            {"text": "x", "project": "P", "done": False, "notes": [], "deadline": ""},
            {"text": "y", "project": "P", "done": False, "notes": [], "deadline": ""},
        ],
    })
    assert [t["text"] for t in data["up_next"]] == ["z", "x", "y"]


def test_reorder_project_tasks(server):
    _seed(projects=[ProjectInfo(name="Test", tasks=[
        Task(text="p1", project="Test"),
        Task(text="p2", project="Test"),
    ])])
    data = _api(server, "reorder", {
        "active": [{"text": "active task", "project": "Test", "done": False, "notes": [], "deadline": ""}],
        "up_next": [{"text": "next task", "project": "Test", "done": False, "notes": [], "deadline": ""}],
        "projects": {
            "Test": [
                {"text": "p2", "project": "Test", "done": False, "notes": [], "deadline": ""},
                {"text": "p1", "project": "Test", "done": False, "notes": [], "deadline": ""},
            ]
        },
    })
    assert data["projects"][0]["tasks"][0]["text"] == "p2"


def test_reorder_move_between_sections(server):
    """Move a task from up_next to active via reorder."""
    _seed()
    data = _api(server, "reorder", {
        "active": [
            {"text": "active task", "project": "Test", "done": False, "notes": [], "deadline": ""},
            {"text": "next task", "project": "Test", "done": False, "notes": [], "deadline": ""},
        ],
        "up_next": [],
    })
    assert len(data["active"]) == 2
    assert len(data["up_next"]) == 0


def test_reorder_preserves_notes_and_deadline(server):
    p = Priorities(
        active=[Task(text="a", project="P", notes=["note1"], deadline="2026-05-01")],
        up_next=[],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "reorder", {
        "active": [{"text": "a", "project": "P", "done": False, "notes": ["note1"], "deadline": "2026-05-01"}],
        "up_next": [],
    })
    assert data["active"][0]["notes"] == ["note1"]
    assert data["active"][0]["deadline"] == "2026-05-01"


# =============================================================================
# POST /api/project/*
# =============================================================================

def test_add_project(server):
    _seed(projects=[])
    data = _api(server, "project/add", {"name": "NewProj", "description": "desc"})
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "NewProj"
    assert data["projects"][0]["description"] == "desc"


def test_add_duplicate_project(server):
    _seed()
    data = _api(server, "project/add", {"name": "Test"})
    assert len(data["projects"]) == 1  # still just one


def test_edit_project_description(server):
    _seed()
    data = _api(server, "project/edit", {"name": "Test", "description": "updated desc"})
    assert data["projects"][0]["description"] == "updated desc"


def test_add_project_task(server):
    _seed()
    data = _api(server, "project/task/add", {"name": "Test", "text": "new proj task"})
    assert len(data["projects"][0]["tasks"]) == 1
    assert data["projects"][0]["tasks"][0]["text"] == "new proj task"
    assert data["projects"][0]["tasks"][0]["project"] == "Test"


def test_delete_project_task(server):
    _seed(projects=[ProjectInfo(name="Test", tasks=[
        Task(text="t1", project="Test"),
        Task(text="t2", project="Test"),
    ])])
    data = _api(server, "project/task/delete", {"name": "Test", "index": 0})
    assert len(data["projects"][0]["tasks"]) == 1
    assert data["projects"][0]["tasks"][0]["text"] == "t2"


def test_done_project_task(server):
    _seed(projects=[ProjectInfo(name="Test", tasks=[Task(text="proj task", project="Test")])])
    data = _api(server, "project/task/done", {"name": "Test", "index": 0})
    assert len(data["projects"][0]["tasks"]) == 0
    assert len(data["done"]) == 1
    assert data["done"][0]["text"] == "proj task"
    assert data["done"][0]["done"] is True


# =============================================================================
# POST /api/note/*
# =============================================================================

def test_add_global_note(server):
    _seed()
    data = _api(server, "note/add", {"text": "remember this"})
    assert len(data["notes"]) == 1
    assert "remember this" in data["notes"][0]


def test_delete_global_note(server):
    p = Priorities(notes=["note0", "note1", "note2"])
    save(p)
    data = _api(server, "note/delete", {"index": 1})
    assert len(data["notes"]) == 2
    assert "note1" not in data["notes"]


# =============================================================================
# POST /api/undo
# =============================================================================

def test_undo_restores_deleted_task(server):
    _seed()
    _api(server, "task/delete", {"section": "active", "index": 0})
    data = _api(server, "priorities")
    assert len(data["active"]) == 0

    data = _api(server, "undo", {})
    assert len(data["active"]) == 1
    assert data["active"][0]["text"] == "active task"


def test_undo_multiple_steps(server):
    _seed()
    _api(server, "task/delete", {"section": "active", "index": 0})
    _api(server, "task/delete", {"section": "up_next", "index": 0})
    data = _api(server, "priorities")
    assert len(data["active"]) == 0
    assert len(data["up_next"]) == 0

    data = _api(server, "undo", {})
    assert len(data["up_next"]) == 1
    assert len(data["active"]) == 0

    data = _api(server, "undo", {})
    assert len(data["active"]) == 1
    assert len(data["up_next"]) == 1


def test_undo_empty_stack(server):
    _seed()
    data = _api(server, "undo", {})
    assert len(data["active"]) == 1  # unchanged


def test_undo_stack_limit(server):
    from web.server import MAX_UNDO
    _seed()
    for i in range(MAX_UNDO + 5):
        _api(server, "task/add", {"text": f"task {i}", "section": "up_next"})
    assert len(_get_undo_stack()) == MAX_UNDO


def test_undo_restores_task_edit(server):
    _seed()
    _api(server, "task/edit", {"section": "active", "index": 0, "text": "changed"})
    data = _api(server, "priorities")
    assert data["active"][0]["text"] == "changed"

    data = _api(server, "undo", {})
    assert data["active"][0]["text"] == "active task"


def test_undo_restores_added_note(server):
    _seed()
    _api(server, "task/add_note", {"section": "active", "index": 0, "text": "my note"})
    data = _api(server, "priorities")
    assert len(data["active"][0]["notes"]) == 1

    data = _api(server, "undo", {})
    assert len(data["active"][0]["notes"]) == 0


def test_undo_restores_deadline_change(server):
    _seed()
    _api(server, "task/deadline", {"section": "active", "index": 0, "deadline": "2026-08-01"})
    data = _api(server, "undo", {})
    assert data["active"][0]["deadline"] == ""


def test_undo_restores_project_add(server):
    _seed(projects=[])
    _api(server, "project/add", {"name": "NewProj"})
    data = _api(server, "priorities")
    assert len(data["projects"]) == 1

    data = _api(server, "undo", {})
    assert len(data["projects"]) == 0


def test_undo_restores_reorder(server):
    p = Priorities(
        up_next=[Task(text="a", project="P"), Task(text="b", project="P")],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    UNDO_STACK.clear()

    _api(server, "reorder", {
        "active": [],
        "up_next": [
            {"text": "b", "project": "P", "done": False, "notes": [], "deadline": ""},
            {"text": "a", "project": "P", "done": False, "notes": [], "deadline": ""},
        ],
    })
    data = _api(server, "undo", {})
    assert data["up_next"][0]["text"] == "a"
    assert data["up_next"][1]["text"] == "b"


# =============================================================================
# _get_task helper (project: prefix)
# =============================================================================

def test_get_task_from_project_section(server):
    """Notes/deadline on project tasks should work via project: prefix."""
    _seed(projects=[ProjectInfo(name="Test", tasks=[Task(text="pt", project="Test")])])
    data = _api(server, "task/add_note", {"section": "project:Test", "index": 0, "text": "proj note"})
    assert data["projects"][0]["tasks"][0]["notes"] == ["proj note"]


def test_get_task_nonexistent_project(server):
    _seed()
    # Should not crash, just no-op
    data = _api(server, "task/add_note", {"section": "project:Ghost", "index": 0, "text": "note"})
    # Verify state unchanged
    assert len(data["active"]) == 1


# =============================================================================
# Task serialization round-trip
# =============================================================================

def test_task_dict_roundtrip(server):
    """Verify _task_dict and _task_from_dict are inverses."""
    p = Priorities(
        active=[Task(text="t", project="P", notes=["n1", "n2"], deadline="2026-01-01")],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "priorities")
    t = data["active"][0]
    assert t == {"text": "t", "project": "P", "done": False, "notes": ["n1", "n2"], "deadline": "2026-01-01", "priority": 0, "recurrence": ""}


# =============================================================================
# Priority
# =============================================================================

def test_set_priority(server):
    _seed()
    data = _api(server, "task/priority", {"section": "active", "index": 0, "priority": 2})
    assert data["active"][0]["priority"] == 2


def test_set_priority_up_next(server):
    _seed()
    data = _api(server, "task/priority", {"section": "up_next", "index": 0, "priority": 1})
    assert data["up_next"][0]["priority"] == 1


def test_set_priority_project_task(server):
    _seed(projects=[ProjectInfo(name="P", tasks=[Task(text="proj task")])])
    data = _api(server, "task/priority", {"section": "project:P", "index": 0, "priority": 2})
    assert data["projects"][0]["tasks"][0]["priority"] == 2


def test_clear_priority(server):
    _seed(active=[Task(text="t", priority=2)])
    data = _api(server, "task/priority", {"section": "active", "index": 0, "priority": 0})
    assert data["active"][0]["priority"] == 0


def test_priority_survives_roundtrip(server):
    """Priority is preserved through save/load cycle."""
    _seed(active=[Task(text="important", priority=1)])
    data = _api(server, "priorities")
    assert data["active"][0]["priority"] == 1


def test_priority_undo(server):
    _seed()
    _api(server, "task/priority", {"section": "active", "index": 0, "priority": 2})
    data = _api(server, "undo", {})
    assert data["active"][0]["priority"] == 0


def test_done_preserves_priority(server):
    _seed(active=[Task(text="urgent", priority=2)])
    data = _api(server, "task/done", {"section": "active", "index": 0})
    assert data["done"][0]["priority"] == 2


def test_reorder_preserves_priority(server):
    _seed(active=[Task(text="a", priority=1), Task(text="b", priority=2)])
    data = _api(server, "reorder", {"active": [
        {"text": "b", "priority": 2}, {"text": "a", "priority": 1}
    ]})
    assert data["active"][0]["priority"] == 2
    assert data["active"][1]["priority"] == 1


# =============================================================================
# Project reorder
# =============================================================================

def test_reorder_projects(server):
    _seed(projects=[
        ProjectInfo(name="A", tasks=[Task(text="t1")]),
        ProjectInfo(name="B", tasks=[Task(text="t2")]),
        ProjectInfo(name="C", tasks=[Task(text="t3")]),
    ])
    data = _api(server, "project/reorder", {"order": ["C", "A", "B"]})
    names = [p["name"] for p in data["projects"]]
    assert names == ["C", "A", "B"]


def test_reorder_projects_preserves_tasks(server):
    _seed(projects=[
        ProjectInfo(name="X", tasks=[Task(text="xt")]),
        ProjectInfo(name="Y", tasks=[Task(text="yt1"), Task(text="yt2")]),
    ])
    data = _api(server, "project/reorder", {"order": ["Y", "X"]})
    assert len(data["projects"][0]["tasks"]) == 2
    assert data["projects"][0]["tasks"][0]["text"] == "yt1"
    assert len(data["projects"][1]["tasks"]) == 1


def test_reorder_projects_partial(server):
    """Projects not mentioned in order are appended at the end."""
    _seed(projects=[
        ProjectInfo(name="A", tasks=[Task(text="t")]),
        ProjectInfo(name="B", tasks=[Task(text="t")]),
        ProjectInfo(name="C", tasks=[Task(text="t")]),
    ])
    data = _api(server, "project/reorder", {"order": ["C"]})
    names = [p["name"] for p in data["projects"]]
    assert names[0] == "C"
    assert set(names) == {"A", "B", "C"}


def test_reorder_inbox_to_project_updates_project_tag(server):
    """Dragging a task from inbox to a project should update the task's project field."""
    _seed(
        inbox=[Task(text="unsorted task")],
        projects=[ProjectInfo(name="MyProj", tasks=[])],
    )
    data = _api(server, "reorder", {
        "inbox": [],
        "projects": {"MyProj": [{"text": "unsorted task", "project": "MyProj", "done": False, "notes": [], "deadline": ""}]},
    })
    assert len(data["inbox"]) == 0
    proj = next(p for p in data["projects"] if p["name"] == "MyProj")
    assert len(proj["tasks"]) == 1
    assert proj["tasks"][0]["text"] == "unsorted task"


def test_reorder_includes_inbox(server):
    """Reorder payload with inbox field should update inbox tasks."""
    _seed(inbox=[Task(text="a"), Task(text="b")])
    data = _api(server, "reorder", {
        "inbox": [
            {"text": "b", "project": "", "done": False, "notes": [], "deadline": ""},
            {"text": "a", "project": "", "done": False, "notes": [], "deadline": ""},
        ],
    })
    assert data["inbox"][0]["text"] == "b"
    assert data["inbox"][1]["text"] == "a"


def test_reorder_projects_undo(server):
    _seed(projects=[
        ProjectInfo(name="A", tasks=[Task(text="t")]),
        ProjectInfo(name="B", tasks=[Task(text="t")]),
    ])
    _api(server, "project/reorder", {"order": ["B", "A"]})
    data = _api(server, "undo", {})
    names = [p["name"] for p in data["projects"]]
    assert names == ["A", "B"]


# =============================================================================
# POST /api/redo
# =============================================================================

def test_redo_after_undo(server):
    _seed()
    _api(server, "task/delete", {"section": "active", "index": 0})
    _api(server, "undo", {})
    data = _api(server, "redo", {})
    assert len(data["active"]) == 0  # deletion re-applied


def test_redo_empty_stack(server):
    _seed()
    data = _api(server, "redo", {})
    assert len(data["active"]) == 1  # unchanged


def test_redo_multiple_steps(server):
    _seed()
    _api(server, "task/add", {"text": "extra", "section": "active"})
    _api(server, "task/add", {"text": "more", "section": "active"})
    _api(server, "undo", {})
    _api(server, "undo", {})
    data = _api(server, "redo", {})
    assert len(data["active"]) == 2  # first redo
    data = _api(server, "redo", {})
    assert len(data["active"]) == 3  # second redo


def test_redo_cleared_on_new_action(server):
    _seed()
    _api(server, "task/delete", {"section": "active", "index": 0})
    _api(server, "undo", {})  # active has 1 task again
    # New action should clear redo stack
    _api(server, "task/add", {"text": "fresh", "section": "active"})
    data = _api(server, "redo", {})
    # Redo should be empty, state unchanged
    assert len(data["active"]) == 2  # original + fresh, no redo effect


# =============================================================================
# POST /api/project/rename
# =============================================================================

def test_rename_project(server):
    _seed()
    data = _api(server, "project/rename", {"old_name": "Test", "new_name": "Renamed"})
    assert data["projects"][0]["name"] == "Renamed"


def test_rename_project_updates_task_refs(server):
    _seed()
    data = _api(server, "project/rename", {"old_name": "Test", "new_name": "Renamed"})
    assert data["active"][0]["project"] == "Renamed"
    assert data["up_next"][0]["project"] == "Renamed"


def test_rename_project_no_op_same_name(server):
    _seed()
    data = _api(server, "project/rename", {"old_name": "Test", "new_name": "Test"})
    assert data["projects"][0]["name"] == "Test"


def test_rename_project_no_op_empty_name(server):
    _seed()
    data = _api(server, "project/rename", {"old_name": "Test", "new_name": ""})
    assert data["projects"][0]["name"] == "Test"


def test_rename_project_no_op_if_target_exists(server):
    _seed(projects=[ProjectInfo(name="A"), ProjectInfo(name="B")])
    data = _api(server, "project/rename", {"old_name": "A", "new_name": "B"})
    names = [p["name"] for p in data["projects"]]
    assert "A" in names and "B" in names  # both still exist, no rename


def test_rename_project_updates_done_tasks(server):
    _seed(done=[Task(text="old task", project="Test", done=True)])
    data = _api(server, "project/rename", {"old_name": "Test", "new_name": "New"})
    assert data["done"][0]["project"] == "New"


def test_rename_project_undo(server):
    _seed()
    _api(server, "project/rename", {"old_name": "Test", "new_name": "Renamed"})
    data = _api(server, "undo", {})
    assert data["projects"][0]["name"] == "Test"
    assert data["active"][0]["project"] == "Test"


# =============================================================================
# POST /api/project/delete
# =============================================================================

def test_delete_project(server):
    _seed()
    data = _api(server, "project/delete", {"name": "Test"})
    assert len(data["projects"]) == 0


def test_delete_project_preserves_tasks(server):
    """Deleting a project doesn't remove tasks from active/up_next."""
    _seed()
    data = _api(server, "project/delete", {"name": "Test"})
    assert len(data["active"]) == 1
    assert len(data["up_next"]) == 1


def test_delete_nonexistent_project(server):
    _seed()
    data = _api(server, "project/delete", {"name": "Ghost"})
    assert len(data["projects"]) == 1  # unchanged


def test_delete_project_undo(server):
    _seed()
    _api(server, "project/delete", {"name": "Test"})
    data = _api(server, "undo", {})
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "Test"


def test_delete_project_with_tasks(server):
    _seed(projects=[ProjectInfo(name="P", tasks=[Task(text="pt1"), Task(text="pt2")])])
    data = _api(server, "project/delete", {"name": "P"})
    # Project and its tasks are gone
    assert not any(p["name"] == "P" for p in data["projects"])


# =============================================================================
# POST /api/project/archive
# =============================================================================

def test_archive_project(server):
    _seed()
    data = _api(server, "project/archive", {"name": "Test", "archived": True})
    assert data["projects"][0]["archived"] is True


def test_unarchive_project(server):
    _seed(projects=[ProjectInfo(name="Test", archived=True)])
    data = _api(server, "project/archive", {"name": "Test", "archived": False})
    assert data["projects"][0]["archived"] is False


def test_archive_preserves_tasks(server):
    _seed(projects=[ProjectInfo(name="Test", tasks=[Task(text="pt")])])
    data = _api(server, "project/archive", {"name": "Test", "archived": True})
    assert len(data["projects"][0]["tasks"]) == 1


def test_archive_undo(server):
    _seed()
    _api(server, "project/archive", {"name": "Test", "archived": True})
    data = _api(server, "undo", {})
    assert data["projects"][0]["archived"] is False


# =============================================================================
# POST /api/task/undone
# =============================================================================

def test_undone_moves_to_project(server):
    _seed(
        done=[Task(text="was done", project="Test", done=True)],
        projects=[ProjectInfo(name="Test", tasks=[])],
    )
    data = _api(server, "task/undone", {"index": 0})
    assert len(data["done"]) == 0
    assert data["projects"][0]["tasks"][0]["text"] == "was done"
    assert data["projects"][0]["tasks"][0]["done"] is False


def test_undone_moves_to_up_next_if_no_project(server):
    _seed(done=[Task(text="was done", project="", done=True)])
    data = _api(server, "task/undone", {"index": 0})
    assert len(data["done"]) == 0
    assert data["up_next"][0]["text"] == "was done"


def test_undone_moves_to_up_next_if_project_missing(server):
    _seed(done=[Task(text="orphan", project="Deleted", done=True)])
    data = _api(server, "task/undone", {"index": 0})
    assert len(data["done"]) == 0
    assert data["up_next"][0]["text"] == "orphan"


def test_undone_unarchives_project(server):
    _seed(
        done=[Task(text="was done", project="Test", done=True)],
        projects=[ProjectInfo(name="Test", archived=True)],
    )
    data = _api(server, "task/undone", {"index": 0})
    assert data["projects"][0]["archived"] is False


def test_undone_out_of_range(server):
    _seed(done=[Task(text="only", done=True)])
    data = _api(server, "task/undone", {"index": 99})
    assert len(data["done"]) == 1  # unchanged


def test_undone_undo(server):
    _seed(
        done=[Task(text="was done", project="Test", done=True)],
        projects=[ProjectInfo(name="Test")],
    )
    _api(server, "task/undone", {"index": 0})
    data = _api(server, "undo", {})
    assert len(data["done"]) == 1
    assert data["done"][0]["text"] == "was done"


# =============================================================================
# POST /api/user-context
# =============================================================================

def test_save_and_get_user_context(server):
    # Save
    _api(server, "user-context", {"text": "I am a developer"})
    # Get
    resp = _api_raw(server, "GET", "/api/user-context")
    data = json.loads(resp.read())
    assert data["text"] == "I am a developer"


def test_save_empty_user_context(server):
    _api(server, "user-context", {"text": "something"})
    _api(server, "user-context", {"text": ""})
    resp = _api_raw(server, "GET", "/api/user-context")
    data = json.loads(resp.read())
    assert data["text"] == ""


# =============================================================================
# Authentication
# =============================================================================

def test_auth_with_session_cookie(server):
    """With a valid session cookie, API endpoints are accessible."""
    data = _api(server, "priorities")
    assert "active" in data


def _api_raw(port, method, path, body=None, headers=None, with_auth=True):
    """Low-level HTTP request returning response object for header inspection."""
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"} if body is not None else {}
    if with_auth:
        hdrs["Cookie"] = f"pancake_session={_test_session_token}; pancake_profile=test-personal"
    if headers:
        hdrs.update(headers)
    req = Request(url, data=data, headers=hdrs, method=method)
    try:
        return urlopen(req)
    except HTTPError as e:
        return e


@pytest.fixture()
def auth_server():
    """Server with password protection enabled."""
    # Restore env vars
    os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")
    os.environ["PANCAKE_CONFIG_DIR"] = os.path.join(_tmpdir, "config")
    os.environ["PANCAKE_DATA_ROOT"] = _tmpdir
    _setup_test_account()
    import web.server as ws
    old_pw = ws.PANCAKE_PASSWORD
    old_sessions = ws.VALID_SESSIONS.copy()
    ws.PANCAKE_PASSWORD = "testpass123"
    ws.VALID_SESSIONS.clear()

    srv = HTTPServer(("127.0.0.1", 0), PancakeHandler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _get_undo_stack().clear()
    yield port
    srv.shutdown()
    ws.PANCAKE_PASSWORD = old_pw
    ws.VALID_SESSIONS.clear()
    ws.VALID_SESSIONS.update(old_sessions)


def test_auth_required_redirects_to_login(auth_server):
    """Without session cookie, GET / returns login page."""
    resp = _api_raw(auth_server, "GET", "/", with_auth=False)
    html = resp.read().decode()
    assert "Log in" in html
    assert "password" in html


def test_auth_wrong_password(auth_server):
    """Wrong password shows error on login page."""
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    data = urlencode({"password": "wrong"}).encode()
    req = Request(f"http://127.0.0.1:{auth_server}/login", data=data, method="POST")
    resp = urlopen(req)
    html = resp.read().decode()
    assert "Wrong" in html


def test_auth_correct_password_sets_cookie(auth_server):
    """Correct password sets session cookie and redirects."""
    from urllib.parse import urlencode
    from urllib.request import Request, build_opener, HTTPCookieProcessor
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    data = urlencode({"password": "testpass123"}).encode()
    req = Request(f"http://127.0.0.1:{auth_server}/login", data=data, method="POST")
    resp = opener.open(req)
    cookies = {c.name: c for c in jar}
    assert "pancake_session" in cookies


def test_auth_session_cookie_grants_access(auth_server):
    """After login with username+password, session cookie grants access to API."""
    import http.client
    from urllib.parse import urlencode
    conn = http.client.HTTPConnection("127.0.0.1", auth_server)
    # Login with the testadmin account (multi-account mode since accounts exist)
    body = urlencode({"username": "testadmin", "password": "testpass123"})
    conn.request("POST", "/login", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    cookie_hdr = resp.getheader("Set-Cookie")
    assert cookie_hdr and "pancake_session=" in cookie_hdr
    session_token = cookie_hdr.split("pancake_session=")[1].split(";")[0]
    conn.close()
    # Seed data and access API
    _seed()
    conn2 = http.client.HTTPConnection("127.0.0.1", auth_server)
    conn2.request("GET", "/api/priorities",
                  headers={"Cookie": f"pancake_session={session_token}; pancake_profile=test-personal"})
    resp2 = conn2.getresponse()
    result = json.loads(resp2.read())
    assert "active" in result
    conn2.close()


def test_auth_exempt_favicon(auth_server):
    """Favicon is accessible without auth."""
    resp = _api_raw(auth_server, "GET", "/static/favicon.svg", with_auth=False)
    body = resp.read().decode()
    assert "Log in" not in body


def test_auth_api_post_requires_auth(auth_server):
    """POST to API without auth serves login page."""
    _seed()
    resp = _api_raw(auth_server, "POST", "/api/task/add",
                    body={"text": "sneak", "project": "X"}, with_auth=False)
    html = resp.read().decode()
    assert "Log in" in html or "password" in html


# =============================================================================
# POST /api/task/recurrence
# =============================================================================

def test_set_recurrence(server):
    _seed()
    data = _api(server, "task/recurrence", {"section": "active", "index": 0, "recurrence": "daily"})
    assert data["active"][0]["recurrence"] == "daily"
    assert data["active"][0]["deadline"] != ""  # auto-sets deadline


def test_clear_recurrence(server):
    p = Priorities(
        active=[Task(text="task", project="P", recurrence="daily", deadline="2026-03-16")],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "task/recurrence", {"section": "active", "index": 0, "recurrence": ""})
    assert data["active"][0]["recurrence"] == ""


def test_set_recurrence_on_project_task(server):
    _seed(projects=[ProjectInfo(name="Test", tasks=[Task(text="pt", project="Test")])])
    data = _api(server, "task/recurrence", {"section": "project:Test", "index": 0, "recurrence": "weekly"})
    assert data["projects"][0]["tasks"][0]["recurrence"] == "weekly"


def test_recurring_task_done_resets_in_place(server):
    """Checking off a recurring task should NOT move it to Done -- it resets with a new deadline."""
    p = Priorities(
        active=[Task(text="Anki", project="SP", recurrence="daily", deadline="2026-03-16")],
        projects=[ProjectInfo(name="SP")],
    )
    save(p)
    data = _api(server, "task/done", {"section": "active", "index": 0})
    assert len(data["active"]) == 1  # still in active
    assert len(data["done"]) == 0  # NOT in done
    assert data["active"][0]["deadline"] != "2026-03-16"  # deadline bumped


def test_nonrecurring_task_done_moves_to_done(server):
    """Non-recurring tasks should still move to Done as before."""
    p = Priorities(
        active=[Task(text="one-off", project="P")],
        projects=[ProjectInfo(name="P")],
    )
    save(p)
    data = _api(server, "task/done", {"section": "active", "index": 0})
    assert len(data["active"]) == 0
    assert len(data["done"]) == 1


def test_recurring_project_task_done_resets(server):
    """Recurring project task should reset in place, not move to Done."""
    p = Priorities(
        projects=[ProjectInfo(name="SP", tasks=[
            Task(text="Anki", project="SP", recurrence="daily", deadline="2026-03-16"),
        ])],
    )
    save(p)
    data = _api(server, "project/task/done", {"name": "SP", "index": 0})
    assert len(data["projects"][0]["tasks"]) == 1  # still in project
    assert len(data["done"]) == 0
    assert data["projects"][0]["tasks"][0]["deadline"] != "2026-03-16"


def test_recurrence_in_task_dict(server):
    p = Priorities(active=[Task(text="t", recurrence="weekly", deadline="2026-03-20")])
    save(p)
    data = _api(server, "priorities")
    assert data["active"][0]["recurrence"] == "weekly"


def test_auth_expired_session(auth_server):
    """Expired session token is rejected."""
    import web.server as ws
    expired_token = "expired_token_123"
    ws.VALID_SESSIONS[expired_token] = 0  # expired in 1970
    resp = _api_raw(auth_server, "GET", "/api/priorities",
                    headers={"Cookie": f"pancake_session={expired_token}"})
    html = resp.read().decode()
    assert "Log in" in html or "password" in html
    # Token should be purged
    assert expired_token not in ws.VALID_SESSIONS


# =============================================================================
# HTTP method support -- ensures all routes accept the correct methods
# =============================================================================

def test_post_login_returns_200_not_501(server):
    """POST /login must be handled (not return 501 Unsupported method)."""
    from urllib.parse import urlencode
    resp = _api_raw(server, "POST", "/login",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status != 501, "POST /login returned 501 -- do_POST not handling /login"


def test_post_login_with_password_returns_200(auth_server):
    """POST /login with wrong password returns login page, not 501."""
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    data = urlencode({"username": "bad", "password": "wrong"}).encode()
    req = Request(f"http://127.0.0.1:{auth_server}/login", data=data, method="POST")
    resp = urlopen(req)
    assert resp.status == 200
    html = resp.read().decode()
    assert "Wrong" in html


def test_login_form_action_is_relative():
    """Login form action must be relative (not /login) to work behind path prefixes."""
    from web.server import _LOGIN_TEMPLATE
    assert 'action="/login"' not in _LOGIN_TEMPLATE, \
        "Login form uses absolute /login action -- breaks behind reverse proxy path prefixes"
    assert 'action="login"' in _LOGIN_TEMPLATE


def test_all_post_api_routes_accept_post(server):
    """Every API route that requires POST should respond (not 501/405)."""
    _seed()
    post_routes = [
        ("/api/task/add", {"text": "t", "project": "Test"}),
        ("/api/task/done", {"section": "active", "index": 0}),
        ("/api/task/edit", {"section": "active", "index": 0, "text": "e"}),
        ("/api/task/delete", {"section": "active", "index": 0}),
        ("/api/task/add_note", {"section": "active", "index": 0, "text": "n"}),
        ("/api/task/deadline", {"section": "active", "index": 0, "deadline": ""}),
        ("/api/task/priority", {"section": "active", "index": 0, "priority": 0}),
        ("/api/task/recurrence", {"section": "active", "index": 0, "recurrence": ""}),
        ("/api/task/move", {"section": "active", "index": 0, "direction": "up"}),
        ("/api/task/undone", {"index": 0}),
        ("/api/reorder", {"active": [], "up_next": []}),
        ("/api/project/add", {"name": "NewP"}),
        ("/api/project/edit", {"name": "Test", "description": "d"}),
        ("/api/project/task/add", {"name": "Test", "text": "t"}),
        ("/api/project/rename", {"old_name": "Test", "new_name": "Test"}),
        ("/api/project/archive", {"name": "Test", "archived": False}),
        ("/api/project/delete", {"name": "Ghost"}),
        ("/api/project/reorder", {"order": []}),
        ("/api/note/add", {"text": "n"}),
        ("/api/note/delete", {"index": 99}),
        ("/api/undo", {}),
        ("/api/redo", {}),
        ("/api/user-context", {"text": "ctx"}),
    ]
    for path, body in post_routes:
        _seed()  # reset state for each
        resp = _api_raw(server, "POST", path, body=body)
        assert resp.status != 501, f"POST {path} returned 501 -- do_POST missing or not routing"
        assert resp.status != 405, f"POST {path} returned 405 -- method not allowed"


def test_get_api_routes_accept_get(server):
    """Every API route that requires GET should respond (not 501/405)."""
    _seed()
    get_routes = [
        "/",
        "/api/priorities",
        "/api/chat/status",
        "/api/user-context",
        "/api/profiles",
        "/api/profile/members",
    ]
    for path in get_routes:
        resp = _api_raw(server, "GET", path)
        assert resp.status != 501, f"GET {path} returned 501"
        assert resp.status != 405, f"GET {path} returned 405"


def test_static_assets_accessible(server):
    """Static assets should return 200, not redirect to login."""
    static_routes = [
        "/static/favicon.svg",
        "/static/app.js",
        "/static/style.css",
    ]
    for path in static_routes:
        resp = _api_raw(server, "GET", path)
        body = resp.read().decode()
        assert "Log in" not in body, f"GET {path} returned login page instead of asset"


def test_post_to_unknown_route_returns_404_not_501(server):
    """POST to a non-existent API route should return 404, not 501."""
    resp = _api_raw(server, "POST", "/api/nonexistent", body={"x": 1})
    assert resp.status == 404, f"POST /api/nonexistent returned {resp.status}, expected 404"


def test_login_correct_password_redirects_to_root(auth_server):
    """Successful login should redirect (303) to ./ (relative)."""
    from urllib.parse import urlencode
    from urllib.request import Request
    import http.client
    # Use raw HTTP to avoid auto-redirect
    conn = http.client.HTTPConnection("127.0.0.1", auth_server)
    body = urlencode({"password": "testpass123"})
    conn.request("POST", "/login", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 303, f"Login returned {resp.status}, expected 303 redirect"
    location = resp.getheader("Location")
    assert location == "./", f"Login redirected to {location}, expected ./"
    conn.close()


def test_login_sets_session_cookie_with_correct_flags(auth_server):
    """Login should set HttpOnly, SameSite=Lax cookie."""
    import http.client
    from urllib.parse import urlencode
    conn = http.client.HTTPConnection("127.0.0.1", auth_server)
    body = urlencode({"password": "testpass123"})
    conn.request("POST", "/login", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    cookie_header = resp.getheader("Set-Cookie")
    assert cookie_header is not None, "No Set-Cookie header on successful login"
    assert "pancake_session=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=Lax" in cookie_header
    conn.close()


def test_auth_server_login_with_username(auth_server):
    """Login with username field should work in legacy mode."""
    import http.client
    from urllib.parse import urlencode
    conn = http.client.HTTPConnection("127.0.0.1", auth_server)
    body = urlencode({"username": "rachel", "password": "testpass123"})
    conn.request("POST", "/login", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 303, f"Login with username returned {resp.status}, expected 303"
    conn.close()


def test_get_unknown_route_returns_404(server):
    """GET to a non-existent route should return 404."""
    resp = _api_raw(server, "GET", "/nonexistent")
    assert resp.status == 404


def test_auth_required_for_api_routes_when_password_set(auth_server):
    """API routes should require auth when password is set."""
    _seed()
    protected_get_routes = ["/api/priorities", "/api/profiles"]
    for path in protected_get_routes:
        resp = _api_raw(auth_server, "GET", path, with_auth=False)
        html = resp.read().decode()
        assert "Log in" in html or "password" in html, \
            f"GET {path} accessible without auth"

    protected_post_routes = [
        ("/api/task/add", {"text": "t"}),
        ("/api/undo", {}),
    ]
    for path, body in protected_post_routes:
        resp = _api_raw(auth_server, "POST", path, body=body, with_auth=False)
        html = resp.read().decode()
        assert "Log in" in html or "password" in html, \
            f"POST {path} accessible without auth"


# =============================================================================
# Registration
# =============================================================================

def test_register_page_loads(server):
    """GET /register should return the registration form."""
    resp = _api_raw(server, "GET", "/register")
    assert resp.status == 200
    html = resp.read().decode()
    assert "Create Account" in html
    assert 'name="username"' in html
    assert 'name="password"' in html


def test_register_creates_account(server):
    """POST /register with valid data should create account, profile, and auto-login."""
    import http.client
    from urllib.parse import urlencode
    conn = http.client.HTTPConnection("127.0.0.1", server)
    body = urlencode({"username": "testuser", "display_name": "Test User",
                      "password": "secret123", "password2": "secret123"})
    conn.request("POST", "/register", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 303, f"Expected 303 redirect after registration, got {resp.status}"
    location = resp.getheader("Location")
    assert location == "./", f"Expected redirect to ./, got {location}"
    cookie = resp.getheader("Set-Cookie")
    assert "pancake_session=" in cookie, "No session cookie set after registration"
    conn.close()
    # Verify account exists
    from pancake.accounts import get_account, get_memberships_for_account
    account = get_account("testuser")
    assert account is not None
    assert account["display_name"] == "Test User"
    # Verify default profile was created
    memberships = get_memberships_for_account("testuser")
    assert len(memberships) >= 1
    assert memberships[0]["role"] == "admin"


def test_register_password_mismatch(server):
    """POST /register with mismatched passwords should show error."""
    import http.client
    from urllib.parse import urlencode
    conn = http.client.HTTPConnection("127.0.0.1", server)
    body = urlencode({"username": "baduser", "display_name": "Bad",
                      "password": "pass123", "password2": "pass456"})
    conn.request("POST", "/register", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    html = resp.read().decode()
    assert "do not match" in html
    conn.close()


def test_register_short_password(server):
    """POST /register with short password should show error."""
    import http.client
    from urllib.parse import urlencode
    conn = http.client.HTTPConnection("127.0.0.1", server)
    body = urlencode({"username": "shortpw", "display_name": "Short",
                      "password": "ab", "password2": "ab"})
    conn.request("POST", "/register", body=body,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    html = resp.read().decode()
    assert "at least 6" in html
    conn.close()


def test_login_page_has_register_link(server):
    """Login page should have a link to the registration page."""
    resp = _api_raw(server, "GET", "/login")
    html = resp.read().decode()
    assert "Create account" in html
    assert "register" in html
