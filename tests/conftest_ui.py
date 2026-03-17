"""Shared fixtures for Playwright UI tests."""

import json
import os
import sys
import tempfile
import threading
from http.server import HTTPServer

import pytest

# Make the shared ux_checks library importable
sys.path.insert(0, os.path.expanduser("~/code"))

_tmpdir = tempfile.mkdtemp()
os.environ["PANCAKE_VAULT"] = os.path.join(_tmpdir, "PRIORITIES.md")

from pancake.priorities import Priorities, Task, ProjectInfo, save
from web.server import PancakeHandler, UNDO_STACK


DESKTOP_VIEWPORT = {"width": 1280, "height": 720}
IPHONE_VIEWPORT = {"width": 375, "height": 812}

# Single server instance shared across all tests (session-scoped)
_server = None
_server_url = None


def _ensure_server():
    global _server, _server_url
    if _server is None:
        _server = HTTPServer(("127.0.0.1", 0), PancakeHandler)
        port = _server.server_address[1]
        _server_url = f"http://127.0.0.1:{port}"
        t = threading.Thread(target=_server.serve_forever, daemon=True)
        t.start()
    return _server_url


@pytest.fixture()
def server_url():
    """Return the shared server URL, resetting state for each test."""
    url = _ensure_server()
    UNDO_STACK.clear()
    save(Priorities())
    return url


def seed(**kwargs):
    """Seed the vault with test data."""
    defaults = dict(
        active=[Task(text="active task", project="Test")],
        up_next=[Task(text="next task", project="Test")],
        projects=[ProjectInfo(name="Test", description="testing")],
    )
    defaults.update(kwargs)
    p = Priorities(**defaults)
    save(p)
    UNDO_STACK.clear()
