"""Chat backend with support for Anthropic API and local Claude CLI."""

import os

from pancake import chat_local


def _get_api_key() -> str | None:
    """Get ANTHROPIC_API_KEY from environment."""
    return os.environ.get("ANTHROPIC_API_KEY")


def _get_backend() -> str:
    """Read PANCAKE_CHAT_BACKEND from environment.

    Valid values: "local", "api", "auto", "disabled".
    Default: "auto".
    """
    return os.environ.get("PANCAKE_CHAT_BACKEND", "auto").lower()


def is_api_available() -> bool:
    """Check if the Anthropic API backend is usable (key + SDK)."""
    if not _get_api_key():
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def is_local_available() -> bool:
    """Check if the local Claude CLI backend is usable."""
    return chat_local.is_available()


def is_available() -> bool:
    """Check if any chat backend is available."""
    backend = _get_backend()
    if backend == "disabled":
        return False
    if backend == "local":
        return is_local_available()
    if backend == "api":
        return is_api_available()
    # auto: either works
    return is_local_available() or is_api_available()


def get_active_backend() -> str | None:
    """Return the active backend name ("local", "api") or None.

    In "auto" mode, prefer local CLI over API.
    """
    backend = _get_backend()
    if backend == "disabled":
        return None
    if backend == "local":
        return "local" if is_local_available() else None
    if backend == "api":
        return "api" if is_api_available() else None
    # auto: prefer local
    if is_local_available():
        return "local"
    if is_api_available():
        return "api"
    return None


def stream_response(system_prompt: str, messages: list[dict]):
    """Yield text deltas from Claude. Each yield is a string chunk.

    messages: list of {"role": "user"|"assistant", "content": "..."}
    """
    import anthropic

    key = _get_api_key()
    if not key:
        yield "Error: No ANTHROPIC_API_KEY found."
        return

    client = anthropic.Anthropic(api_key=key)

    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_response_with_tools(system_prompt: str, messages: list[dict], tools: list[dict],
                                execute_tool_fn):
    """Yield (type, data) tuples from Claude with tool use support.

    Yields:
        ("text", chunk)   -- text delta to stream to client
        ("action", info)  -- tool was executed: {"tool": name, "input": ..., "result": ...}

    messages list is mutated in-place to accumulate the full conversation.
    """
    import anthropic

    key = _get_api_key()
    if not key:
        yield ("text", "Error: No ANTHROPIC_API_KEY found.")
        return

    client = anthropic.Anthropic(api_key=key)

    max_rounds = 5  # prevent infinite tool loops

    for _ in range(max_rounds):
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            tools=tools,
        ) as stream:
            # Collect text and stream it
            for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield ("text", event.delta.text)

            response = stream.get_final_message()

        # Append assistant message to history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        # Execute tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool_fn(block.name, block.input)
                yield ("action", {"tool": block.name, "input": block.input, "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        # Append tool results and loop for Claude's follow-up
        messages.append({"role": "user", "content": tool_results})
