"""
session_status.py -- Cross-device session status for Pancake.

Writes a lightweight JSON status file that can be synced via git so
other devices (e.g. a phone Claude session) can monitor progress.

Usage from the working machine:
    status = SessionStatus(auto_push=True)
    status.mark_phase("morning_grooming", "reviewing priorities")
    status.mark_done("groomed 5 items, set focus to cache fix")

Usage from any other device:
    status = SessionStatus()
    status.pull()
    print(status.format())

CLI:
    python -m pancake.status_cli              # read local status
    python -m pancake.status_cli --pull       # pull from remote, then display
    python -m pancake.status_cli --push       # push current status to remote
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STATUS_FILE = Path(__file__).parent.parent / "data" / "session_status.json"


class SessionStatus:
    """Read/write session status for cross-device visibility."""

    def __init__(
        self,
        status_file: Path = DEFAULT_STATUS_FILE,
        auto_push: bool = False,
        push_every_n: int = 10,
    ) -> None:
        self.status_file = Path(status_file)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.auto_push = auto_push
        self._push_every_n = push_every_n
        self._updates_since_push = 0

    def write(self, status: dict) -> None:
        status.setdefault("updated_at", _now_iso())
        self.status_file.write_text(json.dumps(status, indent=2, default=str) + "\n")
        self._updates_since_push += 1

        if self.auto_push and self._updates_since_push >= self._push_every_n:
            self._git_push_status()
            self._updates_since_push = 0

    def read(self) -> dict | None:
        if not self.status_file.exists():
            return None
        try:
            return json.loads(self.status_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def pull(self) -> dict | None:
        self._git_pull_status()
        return self.read()

    def push(self) -> None:
        self._git_push_status()

    def clear(self) -> None:
        self.status_file.unlink(missing_ok=True)

    # -- Pancake-specific phase markers --

    def mark_phase(self, phase: str, detail: str = "") -> None:
        self.write({
            "phase": phase,
            "detail": detail,
            "status": "running",
            "started_at": (self.read() or {}).get("started_at", _now_iso()),
        })

    def mark_done(self, summary: str = "") -> None:
        existing = self.read() or {}
        self.write({
            **existing,
            "phase": "complete",
            "status": "done",
            "summary": summary,
        })
        if self.auto_push:
            self._git_push_status()

    def mark_error(self, error: str) -> None:
        existing = self.read() or {}
        self.write({
            **existing,
            "status": "error",
            "error": error,
        })
        if self.auto_push:
            self._git_push_status()

    # -- Pretty display --

    def format(self) -> str:
        s = self.read()
        if s is None:
            return "No active session found."

        lines = []
        status_icon = {"running": ">>", "done": "OK", "error": "!!"}.get(
            s.get("status", ""), "??"
        )
        lines.append(f"[{status_icon}] Session status: {s.get('status', 'unknown')}")
        lines.append(f"    Phase: {s.get('phase', 'unknown')}")

        if s.get("percent") is not None:
            lines.append(f"    Progress: {s.get('percent', 0)}%")
        if s.get("items_done") is not None:
            lines.append(
                f"    Items: {s['items_done']}/{s.get('items_total', '?')}"
            )
        if s.get("detail"):
            lines.append(f"    Detail: {s['detail']}")
        if s.get("summary"):
            lines.append(f"    Summary: {s['summary']}")
        if s.get("error"):
            lines.append(f"    Error: {s['error']}")
        if s.get("updated_at"):
            lines.append(f"    Last update: {s['updated_at']}")
        if s.get("started_at"):
            lines.append(f"    Started: {s['started_at']}")

        return "\n".join(lines)

    # -- Git sync helpers --

    def _repo_root(self) -> Path:
        return self.status_file.parent.parent

    def _git_push_status(self) -> None:
        try:
            root = self._repo_root()
            rel_path = self.status_file.relative_to(root)
            subprocess.run(
                ["git", "add", str(rel_path)],
                cwd=root, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", "sync: update session status"],
                cwd=root, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "push"],
                cwd=root, capture_output=True, timeout=30,
            )
            logger.info("Pushed session status to remote")
        except Exception as e:
            logger.warning("Failed to push session status: %s", e)

    def _git_pull_status(self) -> None:
        try:
            root = self._repo_root()
            subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=root, capture_output=True, timeout=30,
            )
        except Exception as e:
            logger.warning("Failed to pull session status: %s", e)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
