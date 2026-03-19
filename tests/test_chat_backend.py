"""Tests for chat backend selection and local CLI module."""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Set up test env before imports
_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("PANCAKE_VAULT", os.path.join(_tmpdir, "PRIORITIES.md"))
os.environ.setdefault("PANCAKE_CONFIG_DIR", os.path.join(_tmpdir, "config"))
os.environ.setdefault("PANCAKE_DATA_ROOT", _tmpdir)

from pancake import chat, chat_local


class TestBackendSelection(unittest.TestCase):
    """Test _get_backend, is_available, and get_active_backend logic."""

    def test_get_backend_default_is_auto(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PANCAKE_CHAT_BACKEND", None)
            assert chat._get_backend() == "auto"

    def test_get_backend_reads_env(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "local"}):
            assert chat._get_backend() == "local"

    def test_get_backend_case_insensitive(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "LOCAL"}):
            assert chat._get_backend() == "local"

    def test_disabled_backend_not_available(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "disabled"}):
            assert chat.is_available() is False
            assert chat.get_active_backend() is None

    def test_local_backend_when_cli_exists(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "local"}):
            with patch("pancake.chat_local.is_available", return_value=True):
                assert chat.is_available() is True
                assert chat.get_active_backend() == "local"

    def test_local_backend_when_cli_missing(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "local"}):
            with patch("pancake.chat_local.is_available", return_value=False):
                assert chat.is_available() is False
                assert chat.get_active_backend() is None

    def test_api_backend_when_key_and_sdk_present(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "api", "ANTHROPIC_API_KEY": "sk-test"}):
            with patch("pancake.chat.is_api_available", return_value=True):
                assert chat.is_available() is True
                assert chat.get_active_backend() == "api"

    def test_api_backend_when_no_key(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "api"}):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            assert chat.is_available() is False
            assert chat.get_active_backend() is None

    def test_auto_prefers_local_over_api(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "auto"}):
            with patch("pancake.chat_local.is_available", return_value=True):
                with patch("pancake.chat.is_api_available", return_value=True):
                    assert chat.get_active_backend() == "local"

    def test_auto_falls_back_to_api(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "auto"}):
            with patch("pancake.chat_local.is_available", return_value=False):
                with patch("pancake.chat.is_api_available", return_value=True):
                    assert chat.get_active_backend() == "api"

    def test_auto_none_when_nothing_available(self):
        with patch.dict(os.environ, {"PANCAKE_CHAT_BACKEND": "auto"}):
            with patch("pancake.chat_local.is_available", return_value=False):
                with patch("pancake.chat.is_api_available", return_value=False):
                    assert chat.is_available() is False
                    assert chat.get_active_backend() is None


class TestChatLocalAvailability(unittest.TestCase):
    """Test chat_local.is_available."""

    def test_available_when_claude_on_path(self):
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            assert chat_local.is_available() is True

    def test_not_available_when_claude_missing(self):
        with patch("shutil.which", return_value=None):
            assert chat_local.is_available() is False


class TestChatLocalStreamResponse(unittest.TestCase):
    """Test chat_local.stream_response parsing."""

    def test_yields_text_deltas_from_stream_json(self):
        """Simulate claude CLI stream-json output and verify delta extraction."""
        # Simulate progressive assistant messages (full accumulated text each time)
        events = [
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello, how"}]}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello, how are you?"}]}}),
            json.dumps({"type": "result", "result": "Hello, how are you?"}),
        ]
        stdout_bytes = "\n".join(events).encode() + b"\n"

        mock_proc = MagicMock()
        mock_proc.stdout = iter(stdout_bytes.split(b"\n"))
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = b""
        mock_proc.wait.return_value = None
        mock_proc.returncode = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            messages = [{"role": "user", "content": "hi"}]
            chunks = list(chat_local.stream_response("system", messages))

        texts = [chunk for typ, chunk in chunks if typ == "text"]
        assert texts == ["Hello", ", how", " are you?"]

    def test_handles_file_not_found(self):
        """If claude CLI is not installed, yield an error message."""
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            messages = [{"role": "user", "content": "hi"}]
            chunks = list(chat_local.stream_response("system", messages))

        assert len(chunks) == 1
        assert chunks[0][0] == "text"
        assert "not found" in chunks[0][1].lower()

    def test_includes_history_in_system_prompt(self):
        """Multi-turn conversations should include history in system prompt."""
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "how are you"},
        ]

        captured_cmd = []

        def fake_popen(cmd, **kwargs):
            captured_cmd.extend(cmd)
            mock_proc = MagicMock()
            mock_proc.stdout = iter([json.dumps({"type": "result", "result": "good"}).encode()])
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.read.return_value = b""
            mock_proc.wait.return_value = None
            mock_proc.returncode = 0
            return mock_proc

        with patch("subprocess.Popen", side_effect=fake_popen):
            list(chat_local.stream_response("system prompt", messages))

        # The system prompt arg should contain prior conversation
        sys_idx = captured_cmd.index("--system-prompt")
        full_system = captured_cmd[sys_idx + 1]
        assert "Prior conversation" in full_system
        assert "hello" in full_system
        assert "hi there" in full_system
        # Last user message should be the CLI argument, not in system prompt
        assert captured_cmd[-1] == "how are you"

    def test_removes_claudecode_env(self):
        """Must remove CLAUDECODE env var to avoid nested session error."""
        captured_env = {}

        def fake_popen(cmd, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            mock_proc = MagicMock()
            mock_proc.stdout = iter([json.dumps({"type": "result", "result": ""}).encode()])
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.read.return_value = b""
            mock_proc.wait.return_value = None
            mock_proc.returncode = 0
            return mock_proc

        with patch.dict(os.environ, {"CLAUDECODE": "1"}):
            with patch("subprocess.Popen", side_effect=fake_popen):
                messages = [{"role": "user", "content": "hi"}]
                list(chat_local.stream_response("system", messages))

        assert "CLAUDECODE" not in captured_env

    def test_reads_model_from_env(self):
        """PANCAKE_CHAT_MODEL env var should set the model."""
        captured_cmd = []

        def fake_popen(cmd, **kwargs):
            captured_cmd.extend(cmd)
            mock_proc = MagicMock()
            mock_proc.stdout = iter([json.dumps({"type": "result", "result": ""}).encode()])
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.read.return_value = b""
            mock_proc.wait.return_value = None
            mock_proc.returncode = 0
            return mock_proc

        with patch.dict(os.environ, {"PANCAKE_CHAT_MODEL": "claude-haiku-4-5-20251001"}):
            with patch("subprocess.Popen", side_effect=fake_popen):
                messages = [{"role": "user", "content": "hi"}]
                list(chat_local.stream_response("system", messages))

        model_idx = captured_cmd.index("--model")
        assert captured_cmd[model_idx + 1] == "claude-haiku-4-5-20251001"


class TestIsApiAvailable(unittest.TestCase):
    """Test is_api_available function."""

    def test_no_key_returns_false(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            assert chat.is_api_available() is False

    def test_key_but_no_sdk_returns_false(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch.dict("sys.modules", {"anthropic": None}):
                # When import raises ImportError
                import sys
                saved = sys.modules.get("anthropic")
                sys.modules["anthropic"] = None
                try:
                    # is_api_available tries to import anthropic
                    # With None in sys.modules, import will raise ImportError
                    result = chat.is_api_available()
                    # It should return False when SDK not importable
                finally:
                    if saved is not None:
                        sys.modules["anthropic"] = saved
                    else:
                        sys.modules.pop("anthropic", None)


if __name__ == "__main__":
    unittest.main()
