"""Pancake web UI -- drag-and-drop priority board backed by PRIORITIES.md."""

import hashlib
import hmac
import io
import json
import os
import secrets
import sys
import tempfile
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from http.server import HTTPServer, SimpleHTTPRequestHandler, HTTPStatus
from http.cookies import SimpleCookie
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import parse_qs

from pancake.priorities import load, save, parse, render, Task, ProjectInfo, Priorities, now_str, vault_path, user_context_path, next_due_date
from pancake.context import build_context
from pancake.chat import is_available as chat_is_available, stream_response, stream_response_with_tools
import pancake.tools
from pancake.tools import TOOLS, execute_tool

PORT = 5790
HOST = os.environ.get("PANCAKE_HOST", "127.0.0.1")
PANCAKE_PASSWORD = os.environ.get("PANCAKE_PASSWORD")
WEB_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parent.parent / "data"
MAX_UNDO = 100
UNDO_FILE = DATA_DIR / "undo_stack.json"
REDO_FILE = DATA_DIR / "redo_stack.json"

# Auth: persistent session tokens (token -> expiry timestamp)
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 days
SESSION_FILE = DATA_DIR / "sessions.json"


def _load_sessions() -> dict[str, float]:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_sessions():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(VALID_SESSIONS))


VALID_SESSIONS: dict[str, float] = _load_sessions()


def _load_stack(path):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return []


def _save_stack(path, stack):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stack))


UNDO_STACK = _load_stack(UNDO_FILE)
REDO_STACK = _load_stack(REDO_FILE)
CHAT_SESSIONS: dict[str, list] = {}  # session_id -> messages
CHAT_DIR = DATA_DIR / "chat_sessions"


def _load_chat_session(session_id: str) -> list:
    """Load chat session from disk."""
    path = CHAT_DIR / f"{session_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return []


def _save_chat_session(session_id: str, messages: list):
    """Save chat session to disk."""
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    # Only save user/assistant text messages for display purposes
    display_msgs = []
    for msg in messages:
        if isinstance(msg.get("content"), str):
            display_msgs.append(msg)
        elif msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            # Extract text from content blocks (SDK objects or dicts)
            text_parts = []
            for block in msg["content"]:
                block_type = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
                block_text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
                if block_type == "text" and block_text:
                    text_parts.append(block_text)
            if text_parts:
                display_msgs.append({"role": "assistant", "content": "".join(text_parts)})
    (CHAT_DIR / f"{session_id}.json").write_text(json.dumps(display_msgs))


# Lazy-loaded Whisper model for transcription
_whisper_model = None

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _snapshot():
    """Take a snapshot of current state for undo."""
    path = vault_path()
    if path.exists():
        UNDO_STACK.append(path.read_text())
        if len(UNDO_STACK) > MAX_UNDO:
            UNDO_STACK.pop(0)
        _save_stack(UNDO_FILE, UNDO_STACK)
    REDO_STACK.clear()
    _save_stack(REDO_FILE, REDO_STACK)


def _snapshot_and_save(p):
    """Snapshot current file to undo stack, then save new state."""
    _snapshot()
    save(p)


# Register snapshot callback so tool actions are undoable
pancake.tools._snapshot_before_save = _snapshot


_LOGIN_TEMPLATE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">'
    '<title>Pancake</title><link rel="icon" type="image/svg+xml" href="static/favicon.svg">'
    "<style>"
    "* { margin: 0; padding: 0; box-sizing: border-box; }"
    "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;"
    " background: #1a1a2e; color: #e0e0e0; min-height: 100vh;"
    " display: flex; align-items: center; justify-content: center; }"
    "form { background: #16213e; border: 1px solid #2a3a5c; border-radius: 12px;"
    " padding: 32px; width: 300px; text-align: center; }"
    "h1 { font-size: 20px; color: #a0b4d0; margin-bottom: 20px; }"
    "input { width: 100%%; padding: 10px 12px; background: #0f1a2e;"
    " border: 1px solid #2a3a5c; border-radius: 6px; color: #e0e0e0;"
    " font-size: 16px; outline: none; margin-bottom: 12px; }"
    "input:focus { border-color: #4a6fa5; }"
    "button { width: 100%%; padding: 10px; background: #2a3a5c; color: #a0b4d0;"
    " border: none; border-radius: 6px; font-size: 14px; cursor: pointer; }"
    "button:hover { background: #3a4a6c; }"
    ".error { color: #e05555; font-size: 13px; margin-bottom: 12px; }"
    "</style></head><body>"
    '<form method="POST" action="/login"><h1>Pancake</h1>'
    "%s"
    '<input type="password" name="password" placeholder="Password" autofocus>'
    '<button type="submit">Log in</button>'
    "</form></body></html>"
)


class PancakeHandler(SimpleHTTPRequestHandler):
    def _check_auth(self) -> bool:
        """Return True if authenticated or auth is disabled."""
        if not PANCAKE_PASSWORD:
            return True
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token_morsel = cookie.get("pancake_session")
        if not token_morsel:
            return False
        token = token_morsel.value
        expiry = VALID_SESSIONS.get(token)
        if expiry and time.time() < expiry:
            return True
        VALID_SESSIONS.pop(token, None)
        _save_sessions()
        return False

    def _serve_login(self, error=""):
        error_html = f'<div class="error">{error}</div>' if error else ""
        html = (_LOGIN_TEMPLATE % error_html).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _require_auth(self) -> bool:
        """Check auth; if not authenticated, serve login page and return False."""
        if self._check_auth():
            return True
        self._serve_login()
        return False

    def do_GET(self):
        # Strip query string for routing
        path_no_qs = self.path.split("?")[0]

        # Auth-exempt routes
        if path_no_qs == "/static/favicon.svg":
            self._serve_file("static/favicon.svg", "image/svg+xml")
            return
        if path_no_qs == "/apple-touch-icon.png" or path_no_qs == "/static/apple-touch-icon.png":
            self._serve_file("static/apple-touch-icon.png", "image/png")
            return
        if path_no_qs == "/manifest.json":
            self._serve_file("static/manifest.json", "application/json")
            return
        if path_no_qs == "/static/sw.js":
            self._serve_file("static/sw.js", "application/javascript")
            return

        # Static assets are auth-exempt (Caddy shared auth protects the site)
        if path_no_qs == "/static/app.js":
            self._serve_file("static/app.js", "application/javascript")
            return
        if path_no_qs == "/static/style.css":
            self._serve_file("static/style.css", "text/css")
            return

        if not self._require_auth():
            return

        if path_no_qs == "/" or path_no_qs == "/index.html":
            self._serve_file("templates/index.html", "text/html")
        elif self.path == "/api/priorities":
            self._json_response(self._get_priorities())
        elif self.path == "/api/chat/status":
            self._json_response({"available": chat_is_available()})
        elif self.path.startswith("/api/chat/history?"):
            qs = parse_qs(self.path.split("?", 1)[1])
            sid = qs.get("session_id", [""])[0]
            msgs = _load_chat_session(sid) if sid else []
            self._json_response({"messages": msgs})
        elif self.path == "/api/user-context":
            text = ""
            ucp = user_context_path()
            if ucp.exists():
                try:
                    text = ucp.read_text()
                except OSError:
                    pass
            self._json_response({"text": text})
        else:
            self.send_error(404)

    def do_POST(self):
        # Login route -- exempt from auth
        if self.path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode()
            params = parse_qs(raw)
            password = params.get("password", [""])[0]
            if PANCAKE_PASSWORD and hmac.compare_digest(password, PANCAKE_PASSWORD):
                token = secrets.token_urlsafe(32)
                VALID_SESSIONS[token] = time.time() + SESSION_MAX_AGE
                _save_sessions()
                self.send_response(303)
                secure_flag = "; Secure" if HOST != "127.0.0.1" else ""
                self.send_header("Set-Cookie",
                    f"pancake_session={token}; HttpOnly; SameSite=Lax; "
                    f"Max-Age={SESSION_MAX_AGE}; Path=/{secure_flag}")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                self._serve_login(error="Wrong password.")
            return

        if not self._check_auth():
            self._serve_login()
            return

        # Transcribe handles raw audio, not JSON
        if self.path == "/api/transcribe":
            self._handle_transcribe()
            return

        body = self._read_body()

        if self.path == "/api/task/add":
            self._handle_add_task(body)
        elif self.path == "/api/task/done":
            self._handle_done(body)
        elif self.path == "/api/task/edit":
            self._handle_edit(body)
        elif self.path == "/api/task/delete":
            self._handle_delete(body)
        elif self.path == "/api/reorder":
            self._handle_reorder(body)
        elif self.path == "/api/project/add":
            self._handle_add_project(body)
        elif self.path == "/api/project/edit":
            self._handle_edit_project(body)
        elif self.path == "/api/note/add":
            self._handle_add_note(body)
        elif self.path == "/api/note/delete":
            self._handle_delete_note(body)
        elif self.path == "/api/project/task/add":
            self._handle_add_project_task(body)
        elif self.path == "/api/project/task/delete":
            self._handle_delete_project_task(body)
        elif self.path == "/api/project/task/done":
            self._handle_done_project_task(body)
        elif self.path == "/api/project/rename":
            self._handle_rename_project(body)
        elif self.path == "/api/project/archive":
            self._handle_archive_project(body)
        elif self.path == "/api/project/delete":
            self._handle_delete_project(body)
        elif self.path == "/api/project/reorder":
            self._handle_reorder_projects(body)
        elif self.path == "/api/task/add_note":
            self._handle_task_sub(body, "notes", "text")
        elif self.path == "/api/task/delete_note":
            self._handle_task_sub_delete(body, "notes")
        elif self.path == "/api/task/deadline":
            self._handle_task_deadline(body)
        elif self.path == "/api/task/priority":
            self._handle_task_priority(body)
        elif self.path == "/api/task/recurrence":
            self._handle_task_recurrence(body)
        elif self.path == "/api/task/move":
            self._handle_task_move(body)
        elif self.path == "/api/task/undone":
            self._handle_undone(body)
        elif self.path == "/api/undo":
            self._handle_undo(body)
        elif self.path == "/api/redo":
            self._handle_redo(body)
        elif self.path == "/api/claude":
            self._handle_claude(body)
        elif self.path == "/api/chat":
            self._handle_chat(body)
        elif self.path == "/api/user-context":
            self._handle_save_user_context(body)
        else:
            self.send_error(404)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        return json.loads(raw) if raw else {}

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _serve_file(self, rel_path, content_type):
        path = WEB_DIR / rel_path
        if not path.exists():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    @staticmethod
    def _task_dict(t):
        return {"text": t.text, "project": t.project, "done": t.done,
                "notes": t.notes, "deadline": t.deadline, "priority": t.priority,
                "recurrence": t.recurrence}

    @staticmethod
    def _task_from_dict(t):
        return Task(text=t["text"], project=t.get("project", ""), done=t.get("done", False),
                     notes=t.get("notes", []),
                     deadline=t.get("deadline", ""), priority=t.get("priority", 0),
                     recurrence=t.get("recurrence", ""))

    def _get_priorities(self) -> dict:
        p = load()
        td = self._task_dict
        return {
            "active": [td(t) for t in p.active],
            "up_next": [td(t) for t in p.up_next],
            "inbox": [td(t) for t in p.inbox],
            "projects": [{"name": pr.name, "description": pr.description, "tasks": [td(t) for t in pr.tasks], "archived": pr.archived} for pr in p.projects],
            "done": [td(t) for t in p.done],
            "notes": p.notes,
        }

    def _handle_add_task(self, body):
        p = load()
        task = Task(text=body["text"], project=body.get("project", ""))
        section = body.get("section", "up_next")
        if section == "active":
            p.active.append(task)
        elif section == "inbox":
            p.inbox.append(task)
        else:
            p.up_next.insert(0, task)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_done(self, body):
        p = load()
        section = body["section"]
        idx = body["index"]
        if section == "active" and idx < len(p.active):
            task = p.active[idx]
            if task.recurrence:
                task.deadline = next_due_date(task.deadline, task.recurrence)
            else:
                task = p.active.pop(idx)
                task.done = True
                p.done.insert(0, task)
        elif section == "up_next" and idx < len(p.up_next):
            task = p.up_next[idx]
            if task.recurrence:
                task.deadline = next_due_date(task.deadline, task.recurrence)
            else:
                task = p.up_next.pop(idx)
                task.done = True
                p.done.insert(0, task)
        elif section == "inbox" and idx < len(p.inbox):
            task = p.inbox[idx]
            if task.recurrence:
                task.deadline = next_due_date(task.deadline, task.recurrence)
            else:
                task = p.inbox.pop(idx)
                task.done = True
                p.done.insert(0, task)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_edit(self, body):
        p = load()
        section = body["section"]
        idx = body["index"]
        if section.startswith("project:"):
            proj = p.get_project(section[8:])
            tasks = proj.tasks if proj else []
        else:
            tasks = getattr(p, section, [])
        if idx < len(tasks):
            tasks[idx].text = body["text"]
            if "project" in body:
                tasks[idx].project = body["project"]
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_delete(self, body):
        p = load()
        section = body["section"]
        idx = body["index"]
        tasks = getattr(p, section, [])
        if idx < len(tasks):
            tasks.pop(idx)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_reorder(self, body):
        """Handle drag-and-drop reorder. Body: {active: [...], up_next: [...], projects: {name: [tasks]}}"""
        p = load()
        tf = self._task_from_dict
        if "active" in body:
            p.active = [tf(t) for t in body["active"]]
        if "up_next" in body:
            p.up_next = [tf(t) for t in body["up_next"]]
        if "inbox" in body:
            p.inbox = [tf(t) for t in body["inbox"]]
        if "projects" in body:
            for proj_name, tasks in body["projects"].items():
                proj = p.get_project(proj_name)
                if proj:
                    proj.tasks = [tf(t) for t in tasks]
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_add_project(self, body):
        p = load()
        if not p.get_project(body["name"]):
            p.projects.append(ProjectInfo(name=body["name"], description=body.get("description", "")))
            _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_edit_project(self, body):
        p = load()
        proj = p.get_project(body["name"])
        if proj:
            if "description" in body:
                proj.description = body["description"]
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_rename_project(self, body):
        old_name = body.get("old_name", "")
        new_name = body.get("new_name", "").strip()
        if not old_name or not new_name or old_name == new_name:
            self._json_response(self._get_priorities())
            return
        p = load()
        # Don't rename if target name already exists (case-insensitive)
        if p.get_project(new_name) and p.get_project(new_name).name != p.get_project(old_name).name:
            self._json_response(self._get_priorities())
            return
        proj = p.get_project(old_name)
        if proj:
            proj.name = new_name
            # Update project reference on all tasks (active, up_next, done, project tasks)
            for task_list in [p.active, p.up_next, p.done]:
                for t in task_list:
                    if t.project and t.project.lower() == old_name.lower():
                        t.project = new_name
            for t in proj.tasks:
                if t.project and t.project.lower() == old_name.lower():
                    t.project = new_name
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_add_note(self, body):
        p = load()
        p.notes.append(f"[{now_str()}] {body['text']}")
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_reorder_projects(self, body):
        """Reorder projects. Body: {order: ["name1", "name2", ...]}"""
        p = load()
        name_to_proj = {proj.name: proj for proj in p.projects}
        ordered = []
        for name in body.get("order", []):
            if name in name_to_proj:
                ordered.append(name_to_proj.pop(name))
        # Append any projects not mentioned (shouldn't happen but safe)
        ordered.extend(name_to_proj.values())
        p.projects = ordered
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_archive_project(self, body):
        p = load()
        proj = p.get_project(body["name"])
        if proj:
            proj.archived = body.get("archived", True)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_delete_project(self, body):
        p = load()
        proj = p.get_project(body["name"])
        if proj:
            p.projects.remove(proj)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_add_project_task(self, body):
        p = load()
        proj = p.get_project(body["name"])
        if proj:
            proj.tasks.append(Task(text=body["text"], project=proj.name))
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_delete_project_task(self, body):
        p = load()
        proj = p.get_project(body["name"])
        if proj and body["index"] < len(proj.tasks):
            proj.tasks.pop(body["index"])
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_done_project_task(self, body):
        p = load()
        proj = p.get_project(body["name"])
        if proj and body["index"] < len(proj.tasks):
            task = proj.tasks[body["index"]]
            if task.recurrence:
                task.deadline = next_due_date(task.deadline, task.recurrence)
            else:
                task = proj.tasks.pop(body["index"])
                task.done = True
                p.done.insert(0, task)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _get_task(self, body):
        """Get a task by section + index. Supports active, up_next, project:Name."""
        p = load()
        section = body.get("section", "")
        idx = body.get("index", 0)
        if section.startswith("project:"):
            proj = p.get_project(section[8:])
            if proj and idx < len(proj.tasks):
                return p, proj.tasks[idx]
        else:
            tasks = getattr(p, section, [])
            if idx < len(tasks):
                return p, tasks[idx]
        return p, None

    def _handle_task_sub(self, body, field, value_key):
        p, task = self._get_task(body)
        if task:
            getattr(task, field).append(body[value_key])
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_task_sub_delete(self, body, field):
        p, task = self._get_task(body)
        if task:
            items = getattr(task, field)
            sub_idx = body.get("sub_index", 0)
            if sub_idx < len(items):
                items.pop(sub_idx)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_task_deadline(self, body):
        p, task = self._get_task(body)
        if task:
            task.deadline = body.get("deadline", "")
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_task_priority(self, body):
        p, task = self._get_task(body)
        if task:
            task.priority = body.get("priority", 0)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_task_recurrence(self, body):
        p, task = self._get_task(body)
        if task:
            task.recurrence = body.get("recurrence", "")
            # Auto-set deadline to today if setting recurrence without a deadline
            if task.recurrence and not task.deadline:
                from datetime import datetime
                task.deadline = datetime.now().strftime("%Y-%m-%d")
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_task_move(self, body):
        """Move a task up or down within its section."""
        p = load()
        section = body.get("section", "")
        idx = body.get("index", 0)
        direction = body.get("direction", "")
        if section.startswith("project:"):
            proj = p.get_project(section[8:])
            if proj:
                tasks = proj.tasks
                if direction == "up" and idx > 0:
                    tasks[idx], tasks[idx - 1] = tasks[idx - 1], tasks[idx]
                elif direction == "down" and idx < len(tasks) - 1:
                    tasks[idx], tasks[idx + 1] = tasks[idx + 1], tasks[idx]
        else:
            tasks = getattr(p, section, [])
            if direction == "up" and idx > 0:
                tasks[idx], tasks[idx - 1] = tasks[idx - 1], tasks[idx]
            elif direction == "down" and idx < len(tasks) - 1:
                tasks[idx], tasks[idx + 1] = tasks[idx + 1], tasks[idx]
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_undone(self, body):
        """Move a task from done back to its project (or up_next if no project). Unarchive if needed."""
        p = load()
        idx = body.get("index", 0)
        if idx < len(p.done):
            task = p.done.pop(idx)
            task.done = False
            if task.project:
                proj = p.get_project(task.project)
                if proj:
                    proj.tasks.insert(0, task)
                    if proj.archived:
                        proj.archived = False
                else:
                    p.up_next.insert(0, task)
            else:
                p.up_next.insert(0, task)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_delete_note(self, body):
        p = load()
        idx = body["index"]
        if idx < len(p.notes):
            p.notes.pop(idx)
        _snapshot_and_save(p)
        self._json_response(self._get_priorities())

    def _handle_undo(self, body):
        if not UNDO_STACK:
            self._json_response(self._get_priorities())
            return
        path = vault_path()
        if path.exists():
            REDO_STACK.append(path.read_text())
            _save_stack(REDO_FILE, REDO_STACK)
        content = UNDO_STACK.pop()
        _save_stack(UNDO_FILE, UNDO_STACK)
        import fcntl
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(content)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        self._json_response(self._get_priorities())

    def _handle_redo(self, body):
        if not REDO_STACK:
            self._json_response(self._get_priorities())
            return
        path = vault_path()
        if path.exists():
            UNDO_STACK.append(path.read_text())
            _save_stack(UNDO_FILE, UNDO_STACK)
        content = REDO_STACK.pop()
        _save_stack(REDO_FILE, REDO_STACK)
        import fcntl
        with open(path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(content)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        self._json_response(self._get_priorities())

    def _handle_claude(self, body):
        self._json_response({"error": "Terminal launch not available on remote server. Use the chat panel instead."}, 400)

    def _handle_chat(self, body):
        """Stream a chat response via SSE."""
        session_id = body.get("session_id", str(uuid.uuid4()))
        message = body.get("message", "").strip()
        if not message:
            self._json_response({"error": "empty message"}, 400)
            return

        if session_id not in CHAT_SESSIONS:
            CHAT_SESSIONS[session_id] = _load_chat_session(session_id)

        history = CHAT_SESSIONS[session_id]
        history.append({"role": "user", "content": message})

        # Build context
        p = load()
        system_prompt = build_context(p, user_context_path())

        # SSE response
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            for event_type, event_data in stream_response_with_tools(
                system_prompt, history, TOOLS, execute_tool
            ):
                if event_type == "text":
                    data = json.dumps({"type": "delta", "text": event_data})
                elif event_type == "action":
                    data = json.dumps({"type": "action", "tool": event_data["tool"],
                                       "input": event_data["input"], "result": event_data["result"]})
                else:
                    continue
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
        except Exception as e:
            err = json.dumps({"type": "error", "text": str(e)})
            self.wfile.write(f"data: {err}\n\n".encode())
            self.wfile.flush()

        # Persist session to disk
        _save_chat_session(session_id, history)

        done = json.dumps({"type": "done"})
        self.wfile.write(f"data: {done}\n\n".encode())
        self.wfile.flush()

    def _handle_transcribe(self):
        """Accept audio blob, transcribe with Whisper, return text."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0 or length > 10 * 1024 * 1024:  # 10MB max
            self._json_response({"error": "invalid audio size"}, 400)
            return
        audio_data = self.rfile.read(length)
        try:
            # Write to temp file for faster-whisper
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_data)
                tmp_path = f.name
            model = _get_whisper_model()
            segments, _ = model.transcribe(tmp_path, language="en")
            text = " ".join(seg.text.strip() for seg in segments).strip()
            os.unlink(tmp_path)
            self._json_response({"text": text})
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _handle_save_user_context(self, body):
        text = body.get("text", "")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        user_context_path().write_text(text)
        self._json_response({"ok": True})

    def log_message(self, format, *args):
        pass  # quiet


def main():
    server = ThreadingHTTPServer((HOST, PORT), PancakeHandler)
    auth_note = " (password protected)" if PANCAKE_PASSWORD else ""
    print(f"Pancake UI running at http://{HOST}:{PORT}{auth_note}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
