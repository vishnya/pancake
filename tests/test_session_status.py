"""Tests for session status read/write/format."""

import json
import os
import tempfile
from pathlib import Path

from pancake.session_status import SessionStatus


@staticmethod
def _make_status(tmp_path):
    return SessionStatus(status_file=tmp_path / "status.json", auto_push=False)


def test_write_and_read(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.write({"phase": "testing", "status": "running"})
    data = s.read()
    assert data["phase"] == "testing"
    assert data["status"] == "running"
    assert "updated_at" in data


def test_read_nonexistent(tmp_path):
    s = SessionStatus(status_file=tmp_path / "nope.json")
    assert s.read() is None


def test_read_corrupt_json(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("not json{{{")
    s = SessionStatus(status_file=f)
    assert s.read() is None


def test_clear(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.write({"phase": "x"})
    assert s.read() is not None
    s.clear()
    assert s.read() is None


def test_clear_nonexistent(tmp_path):
    s = SessionStatus(status_file=tmp_path / "nope.json")
    s.clear()  # should not raise


def test_mark_phase(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_phase("processing", "step 1")
    data = s.read()
    assert data["phase"] == "processing"
    assert data["detail"] == "step 1"
    assert data["status"] == "running"
    assert "started_at" in data


def test_mark_phase_preserves_started_at(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_phase("phase1", "starting")
    first_start = s.read()["started_at"]
    s.mark_phase("phase2", "continuing")
    assert s.read()["started_at"] == first_start


def test_mark_done(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_phase("working", "doing stuff")
    s.mark_done("finished all the stuff")
    data = s.read()
    assert data["status"] == "done"
    assert data["phase"] == "complete"
    assert data["summary"] == "finished all the stuff"


def test_mark_done_preserves_existing_fields(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_phase("working", "detail here")
    s.mark_done("done")
    data = s.read()
    assert data["detail"] == "detail here"  # preserved from mark_phase


def test_mark_error(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_phase("processing")
    s.mark_error("something broke")
    data = s.read()
    assert data["status"] == "error"
    assert data["error"] == "something broke"


def test_format_no_session(tmp_path):
    s = SessionStatus(status_file=tmp_path / "nope.json")
    assert "No active session" in s.format()


def test_format_running(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_phase("indexing", "processing files")
    output = s.format()
    assert "[>>]" in output
    assert "running" in output
    assert "indexing" in output
    assert "processing files" in output


def test_format_done(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_done("all good")
    output = s.format()
    assert "[OK]" in output
    assert "all good" in output


def test_format_error(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.mark_error("crash")
    output = s.format()
    assert "[!!]" in output
    assert "crash" in output


def test_format_with_progress(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.write({"status": "running", "phase": "scan", "percent": 42.5, "items_done": 85, "items_total": 200})
    output = s.format()
    assert "42.5%" in output
    assert "85/200" in output


def test_write_adds_updated_at(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.write({"phase": "test"})
    data = s.read()
    assert "updated_at" in data


def test_write_does_not_overwrite_custom_updated_at(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json")
    s.write({"phase": "test", "updated_at": "custom-time"})
    data = s.read()
    assert data["updated_at"] == "custom-time"


def test_auto_push_counter(tmp_path):
    s = SessionStatus(status_file=tmp_path / "status.json", auto_push=False, push_every_n=3)
    for i in range(5):
        s.write({"i": i})
    # Without auto_push, counter increments but no push
    assert s._updates_since_push == 5
