"""Chat backend using the locally installed Claude CLI."""

import json
import os
import shutil
import subprocess


def is_available() -> bool:
    """Check if the Claude CLI is installed."""
    return shutil.which("claude") is not None


def stream_response(system_prompt: str, messages: list[dict],
                    model: str = None):
    """Yield ("text", chunk) tuples by spawning the Claude CLI.

    Builds the prompt from message history: include prior conversation turns
    in the system prompt, send only the last user message as the CLI prompt.
    """
    if model is None:
        model = os.environ.get("PANCAKE_CHAT_MODEL", "claude-opus-4-6[1m]")

    # Build a full system prompt that includes conversation history
    full_system = system_prompt
    if len(messages) > 1:
        history_lines = []
        for msg in messages[:-1]:
            role = msg["role"].capitalize()
            content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
            history_lines.append(f"{role}: {content}")
        full_system = system_prompt + "\n\n## Prior conversation\n" + "\n\n".join(history_lines)

    last_user_msg = ""
    for msg in reversed(messages):
        if msg["role"] == "user" and isinstance(msg["content"], str):
            last_user_msg = msg["content"]
            break

    if not last_user_msg:
        yield ("text", "Error: no user message found.")
        return

    cmd = [
        "claude",
        "--print",                          # Non-interactive, exit after response
        "--output-format", "stream-json",   # Stream JSON events to stdout
        "--verbose",                        # Required when using stream-json
        "--model", model,
        "--permission-mode", "plan",        # Read-only, no file edits
        "--tools", "",                      # Disable all tools
        "--system-prompt", full_system,
        "--no-session-persistence",         # Don't save session files
        last_user_msg,
    ]

    # Must remove CLAUDECODE env var or CLI refuses to launch inside another session
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError:
        yield ("text", "Error: Claude CLI not found. Install it or switch to API backend.")
        return

    prev_text = ""

    for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Assistant message content: {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}
        if event.get("type") == "assistant":
            content = event.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "text":
                    full_text = block.get("text", "")
                    if len(full_text) > len(prev_text):
                        delta = full_text[len(prev_text):]
                        prev_text = full_text
                        yield ("text", delta)

        # Result event signals completion
        elif event.get("type") == "result":
            # Emit any remaining text delta
            result_text = event.get("result", "")
            if result_text and len(result_text) > len(prev_text):
                delta = result_text[len(prev_text):]
                yield ("text", delta)
            break

    # Wait for process to finish
    proc.wait()

    if proc.returncode and proc.returncode != 0:
        stderr_output = proc.stderr.read().decode("utf-8", errors="replace").strip()
        # Filter out noisy hook-related lines
        stderr_lines = [
            line for line in stderr_output.splitlines()
            if "hook" not in line.lower()
        ]
        if stderr_lines and not prev_text:
            yield ("text", f"Error: Claude CLI exited with code {proc.returncode}. {' '.join(stderr_lines)}")
