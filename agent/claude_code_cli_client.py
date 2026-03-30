"""OpenAI-compatible shim that forwards Hermes requests to `claude -p`.

This adapter lets Hermes treat the local Claude Code CLI as a chat-style
backend. Each request flattens the Hermes message list into a single prompt,
executes one short-lived `claude -p` invocation, and converts Claude's
stream-json output into the minimal chat completion shapes Hermes expects.
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

from hermes_native_mcp import (
    build_claude_mcp_tool_names,
    build_hermes_tool_awareness_text,
    resolve_requested_tool_names,
)

MARKER_BASE_URL = "acp://claude-code-cli"
_DEFAULT_TIMEOUT_SECONDS = 900.0
_DEFAULT_MAX_TURNS = 10
_DEFAULT_ALLOWED_TOOLS = "Read,Glob,Grep"
_CLAUDE_TOOL_ORDER = ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]
_HERMES_TOOL_TO_CLAUDE_TOOLS = {
    "read_file": {"Read"},
    "search_files": {"Glob", "Grep"},
    "write_file": {"Write"},
    "patch": {"Edit", "Write"},
    "terminal": {"Bash"},
    "process": {"Bash"},
    "execute_code": {"Bash"},
}


def _resolve_command() -> str:
    return (
        os.getenv("HERMES_CLAUDE_CODE_COMMAND", "").strip()
        or os.getenv("CLAUDE_CODE_PATH", "").strip()
        or "claude"
    )


def _resolve_args() -> list[str]:
    raw = os.getenv("HERMES_CLAUDE_CODE_ARGS", "").strip()
    if not raw:
        return []
    return shlex.split(raw)


def _coerce_timeout_seconds(timeout: Any) -> float:
    if isinstance(timeout, (int, float)):
        return max(float(timeout), 1.0)
    read_timeout = getattr(timeout, "read", None)
    if isinstance(read_timeout, (int, float)):
        return max(float(read_timeout), 1.0)
    return _DEFAULT_TIMEOUT_SECONDS


def _resolve_max_turns() -> int:
    raw = os.getenv("HERMES_CLAUDE_CODE_MAX_TURNS", "").strip()
    if not raw:
        return _DEFAULT_MAX_TURNS
    try:
        return max(int(raw), 1)
    except Exception:
        return _DEFAULT_MAX_TURNS


def _resolve_allowed_tools(enabled_toolsets: list[str] | None = None) -> str:
    raw = os.getenv("HERMES_CLAUDE_CODE_ALLOWED_TOOLS", "").strip()
    if raw:
        return raw

    allowed = set(_DEFAULT_ALLOWED_TOOLS.split(","))
    if enabled_toolsets:
        try:
            from toolsets import resolve_multiple_toolsets

            for hermes_tool in resolve_multiple_toolsets(list(enabled_toolsets)):
                allowed.update(_HERMES_TOOL_TO_CLAUDE_TOOLS.get(hermes_tool, set()))
        except Exception:
            pass

    ordered = [tool for tool in _CLAUDE_TOOL_ORDER if tool in allowed]
    return ",".join(ordered) if ordered else _DEFAULT_ALLOWED_TOOLS


def _resolve_permission_mode() -> str:
    raw = os.getenv("HERMES_CLAUDE_CODE_PERMISSION_MODE", "").strip()
    if raw:
        return raw
    return "acceptEdits"


def _resolve_hermes_mcp_tools() -> list[str]:
    raw = os.getenv("HERMES_CLAUDE_CODE_HERMES_MCP_TOOLS")
    try:
        return resolve_requested_tool_names(raw)
    except Exception:
        return []


def _claude_mcp_bridge_available() -> bool:
    return find_spec("mcp") is not None


def _merge_allowed_tools(allowed_tools: str, extra_tools: list[str] | None = None) -> str:
    ordered: list[str] = []
    for tool_name in [part.strip() for part in (allowed_tools or "").split(",") if part.strip()]:
        if tool_name not in ordered:
            ordered.append(tool_name)
    for tool_name in extra_tools or []:
        if tool_name and tool_name not in ordered:
            ordered.append(tool_name)
    return ",".join(ordered)


def _normalize_model_hint(model: str | None) -> str | None:
    if not model:
        return None
    normalized = str(model).strip()
    if not normalized or normalized == "claude-code-cli":
        return None
    if normalized.startswith("anthropic/"):
        return normalized.split("/", 1)[1]
    return normalized


def _render_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        if "text" in content:
            return str(content.get("text") or "").strip()
        if "content" in content and isinstance(content.get("content"), str):
            return str(content.get("content") or "").strip()
        return json.dumps(content, ensure_ascii=True)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return str(content).strip()


def _format_messages_as_prompt(
    messages: list[dict[str, Any]],
    model: str | None = None,
    hermes_tool_awareness: str | None = None,
) -> str:
    sections: list[str] = [
        "You are being used as the active Claude Code CLI backend for Hermes.",
        "You may use Claude Code tools when they are genuinely needed to complete the request.",
        "Return a final natural-language answer for Hermes once the work is complete.",
        "Do not emit OpenAI tool-call JSON or explain the transport/protocol layer unless the user explicitly asks.",
    ]
    if model:
        sections.append(f"Hermes requested model hint: {model}")
    if hermes_tool_awareness:
        sections.append(hermes_tool_awareness)

    transcript: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown").strip().lower()
        if role == "tool":
            role = "tool"
        elif role not in {"system", "user", "assistant"}:
            role = "context"

        rendered = _render_message_content(message.get("content"))
        if not rendered:
            continue

        label = {
            "system": "System",
            "user": "User",
            "assistant": "Assistant",
            "tool": "Tool",
            "context": "Context",
        }.get(role, role.title())
        transcript.append(f"{label}:\n{rendered}")

    if transcript:
        sections.append("Conversation transcript:\n\n" + "\n\n".join(transcript))

    sections.append("Continue the conversation from the latest user request.")
    return "\n\n".join(section.strip() for section in sections if section and section.strip())


def _extract_text_blocks(message: dict[str, Any]) -> list[str]:
    assistant_message = message.get("message")
    if not isinstance(assistant_message, dict):
        assistant_message = message.get("assistant")
    if not isinstance(assistant_message, dict):
        assistant_message = message

    content = assistant_message.get("content")
    if isinstance(content, str) and content.strip():
        return [content]
    if not isinstance(content, list):
        return []

    text_parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if str(block.get("type") or "").strip().lower() != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text:
            text_parts.append(text)
    return text_parts


def _extract_progress_events(message: dict[str, Any]) -> list[dict[str, str]]:
    assistant_message = message.get("message")
    if not isinstance(assistant_message, dict):
        assistant_message = message.get("assistant")
    if not isinstance(assistant_message, dict):
        assistant_message = message

    content = assistant_message.get("content")
    if not isinstance(content, list):
        return []

    progress: list[dict[str, str]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        if block_type == "tool_use":
            tool_name = str(block.get("name") or "Tool").strip() or "Tool"
            tool_input = block.get("input")
            preview = ""
            if isinstance(tool_input, dict) and tool_input:
                preview = ", ".join(str(key) for key in list(tool_input.keys())[:4])
            elif tool_input not in (None, ""):
                preview = _coerce_output_text(tool_input)[:120]
            progress.append(
                {
                    "kind": "tool",
                    "tool_name": tool_name,
                    "preview": preview,
                    "message": f"Claude Code used {tool_name}",
                }
            )
        elif block_type == "thinking":
            text = str(block.get("thinking") or block.get("text") or "").strip()
            if text:
                first_line = text.splitlines()[0].strip()
                progress.append(
                    {
                        "kind": "thinking",
                        "tool_name": "_thinking",
                        "preview": first_line,
                        "message": first_line,
                    }
                )
    return progress


def _extract_usage(message: dict[str, Any]) -> SimpleNamespace:
    usage = message.get("usage")
    if not isinstance(usage, dict):
        usage = message.get("result")
    if not isinstance(usage, dict):
        usage = {}

    prompt_tokens = usage.get("input_tokens", message.get("input_tokens", 0)) or 0
    completion_tokens = usage.get("output_tokens", message.get("output_tokens", 0)) or 0
    try:
        prompt_tokens = int(prompt_tokens)
    except Exception:
        prompt_tokens = 0
    try:
        completion_tokens = int(completion_tokens)
    except Exception:
        completion_tokens = 0

    return SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )


def _coerce_output_text(value: Any) -> str:
    if value is None:
        return ""
    rendered = _render_message_content(value)
    if rendered:
        return rendered
    if isinstance(value, dict):
        for key in ("output", "result", "text", "content", "message", "error"):
            nested = _coerce_output_text(value.get(key))
            if nested:
                return nested
    if isinstance(value, list):
        parts = [_coerce_output_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    return str(value).strip()


def _build_chunk(*, text: str = "", model: str, finish_reason: str | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(
        content=text or None,
        tool_calls=None,
        reasoning=None,
        reasoning_content=None,
    )
    choice = SimpleNamespace(index=0, delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(model=model, choices=[choice], usage=None)


class _ClaudeCodeChatCompletions:
    def __init__(self, client: "ClaudeCodeCLIClient"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _ClaudeCodeChatNamespace:
    def __init__(self, client: "ClaudeCodeCLIClient"):
        self.completions = _ClaudeCodeChatCompletions(client)


class _ClaudeCodeStream:
    def __init__(
        self,
        client: "ClaudeCodeCLIClient",
        *,
        prompt_text: str,
        model: str | None,
        timeout_seconds: float,
    ):
        self._client = client
        self._prompt_text = prompt_text
        self._model = model or "claude-code-cli"
        self._timeout_seconds = timeout_seconds

    def __iter__(self) -> Iterator[SimpleNamespace]:
        yielded_text = False
        final_usage: SimpleNamespace | None = None
        fallback_output = ""

        for event in self._client._iter_events(
            self._prompt_text,
            model=self._model,
            timeout_seconds=self._timeout_seconds,
        ):
            if event["type"] == "text":
                text = str(event["text"] or "")
                if text:
                    yielded_text = True
                    fallback_output += text
                    yield _build_chunk(text=text, model=self._model)
            elif event["type"] == "result":
                final_usage = event["usage"]
                if event.get("is_error"):
                    raise RuntimeError(
                        event.get("output")
                        or "Claude Code CLI returned an error result."
                    )
                if not yielded_text and event["output"]:
                    fallback_output = str(event["output"])

        if fallback_output and not yielded_text:
            yield _build_chunk(text=fallback_output, model=self._model)

        yield _build_chunk(model=self._model, finish_reason="stop")
        if final_usage is not None:
            yield SimpleNamespace(model=self._model, choices=[], usage=final_usage)


class ClaudeCodeCLIClient:
    """Minimal OpenAI-client-compatible facade for Claude Code CLI."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        cli_command: str | None = None,
        cli_args: list[str] | None = None,
        cli_cwd: str | None = None,
        session_id: str | None = None,
        enabled_toolsets: list[str] | None = None,
        tool_progress_callback: Any | None = None,
        status_callback: Any | None = None,
        thinking_callback: Any | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        **_: Any,
    ):
        self.api_key = api_key or "claude-code-cli"
        self.base_url = base_url or MARKER_BASE_URL
        self._default_headers = dict(default_headers or {})
        self._cli_command = cli_command or command or _resolve_command()
        self._cli_args = list(cli_args or args or _resolve_args())
        self._cli_cwd = str(Path(cli_cwd or os.getcwd()).resolve())
        self._session_id = str(session_id).strip() if session_id else None
        self._enabled_toolsets = list(enabled_toolsets or [])
        self._tool_progress_callback = tool_progress_callback
        self._status_callback = status_callback
        self._thinking_callback = thinking_callback
        self.chat = _ClaudeCodeChatNamespace(self)
        self.is_closed = False
        self._active_process: subprocess.Popen[str] | None = None
        self._active_process_lock = threading.Lock()

    def close(self) -> None:
        proc: subprocess.Popen[str] | None
        with self._active_process_lock:
            proc = self._active_process
            self._active_process = None
        self.is_closed = True
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _get_hermes_mcp_awareness(self) -> str | None:
        requested_tools = _resolve_hermes_mcp_tools()
        if not requested_tools or not _claude_mcp_bridge_available():
            return None
        return build_hermes_tool_awareness_text(requested_tools)

    def _build_hermes_mcp_bundle(
        self,
        prompt_text: str,
    ) -> tuple[str | None, list[str], str | None]:
        requested_tools = _resolve_hermes_mcp_tools()
        if not requested_tools or not _claude_mcp_bridge_available():
            return None, [], None

        script_path = Path(__file__).resolve().parents[1] / "hermes_native_mcp.py"
        if not script_path.exists():
            return None, [], None

        temp_dir = tempfile.mkdtemp(prefix="hermes-claude-mcp-")
        config_path = Path(temp_dir) / ".mcp.json"
        server_env = {"HERMES_NATIVE_MCP_TOOLS": ",".join(requested_tools)}
        if self._session_id:
            server_env["HERMES_NATIVE_MCP_SESSION_ID"] = self._session_id
        if prompt_text.strip():
            server_env["HERMES_NATIVE_MCP_USER_TASK"] = prompt_text[:4000]

        config_payload = {
            "mcpServers": {
                "hermes_native": {
                    "command": sys.executable,
                    "args": [str(script_path)],
                    "env": server_env,
                }
            }
        }
        config_path.write_text(
            json.dumps(config_payload, ensure_ascii=True),
            encoding="utf-8",
        )
        return (
            str(config_path),
            build_claude_mcp_tool_names(requested_tools),
            temp_dir,
        )

    def _create_chat_completion(
        self,
        *,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        timeout: Any = None,
        stream: bool = False,
        **_: Any,
    ) -> Any:
        normalized_model = _normalize_model_hint(model)
        prompt_text = _format_messages_as_prompt(
            messages or [],
            model=normalized_model,
            hermes_tool_awareness=self._get_hermes_mcp_awareness(),
        )
        timeout_seconds = _coerce_timeout_seconds(timeout)

        if stream:
            return _ClaudeCodeStream(
                self,
                prompt_text=prompt_text,
                model=normalized_model,
                timeout_seconds=timeout_seconds,
            )

        response_text = ""
        usage: SimpleNamespace | None = None
        for event in self._iter_events(
            prompt_text,
            model=normalized_model,
            timeout_seconds=timeout_seconds,
        ):
            if event["type"] == "text":
                response_text += str(event["text"] or "")
            elif event["type"] == "result":
                usage = event["usage"]
                if event.get("is_error"):
                    raise RuntimeError(
                        event.get("output")
                        or "Claude Code CLI returned an error result."
                    )
                if not response_text and event["output"]:
                    response_text = str(event["output"])

        if usage is None:
            usage = SimpleNamespace(
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            )

        assistant_message = SimpleNamespace(
            content=response_text,
            tool_calls=[],
            reasoning=None,
            reasoning_content=None,
            reasoning_details=None,
        )
        choice = SimpleNamespace(message=assistant_message, finish_reason="stop")
        return SimpleNamespace(
            choices=[choice],
            usage=usage,
            model=normalized_model or "claude-code-cli",
        )

    def _build_command(
        self,
        prompt_text: str,
        *,
        model: str | None,
        mcp_config_path: str | None = None,
        extra_allowed_tools: list[str] | None = None,
    ) -> list[str]:
        command = [self._cli_command, *self._cli_args, "-p", prompt_text]
        command.extend(["--output-format", "stream-json", "--verbose"])
        max_turns = _resolve_max_turns()
        if max_turns > 0:
            command.extend(["--max-turns", str(max_turns)])
        allowed_tools = _merge_allowed_tools(
            _resolve_allowed_tools(self._enabled_toolsets),
            extra_allowed_tools,
        )
        if allowed_tools:
            command.extend(["--allowedTools", allowed_tools])
        permission_mode = _resolve_permission_mode()
        if permission_mode:
            command.extend(["--permission-mode", permission_mode])
        if mcp_config_path:
            command.extend(["--mcp-config", mcp_config_path])
        if model:
            command.extend(["--model", model])
        return command

    def _iter_events(
        self,
        prompt_text: str,
        *,
        model: str | None,
        timeout_seconds: float,
    ) -> Iterator[dict[str, Any]]:
        mcp_config_path, extra_allowed_tools, temp_dir = self._build_hermes_mcp_bundle(
            prompt_text
        )
        command = self._build_command(
            prompt_text,
            model=model,
            mcp_config_path=mcp_config_path,
            extra_allowed_tools=extra_allowed_tools,
        )
        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self._cli_cwd,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Could not start Claude Code CLI command '{self._cli_command}'. "
                "Install Claude Code or set HERMES_CLAUDE_CODE_COMMAND/CLAUDE_CODE_PATH."
            ) from exc

        if proc.stdout is None:
            proc.kill()
            raise RuntimeError("Claude Code process did not expose stdout.")

        self.is_closed = False
        with self._active_process_lock:
            self._active_process = proc

        stdout_queue: queue.Queue[str | None] = queue.Queue()
        stdout_done = threading.Event()
        stderr_tail: deque[str] = deque(maxlen=40)
        stderr_done = threading.Event()

        def _stdout_reader() -> None:
            try:
                for line in proc.stdout:
                    stdout_queue.put(line)
            finally:
                stdout_done.set()
                stdout_queue.put(None)

        def _stderr_reader() -> None:
            try:
                if proc.stderr is None:
                    return
                for line in proc.stderr:
                    stderr_tail.append(line.rstrip("\n"))
            finally:
                stderr_done.set()

        out_thread = threading.Thread(target=_stdout_reader, daemon=True)
        err_thread = threading.Thread(target=_stderr_reader, daemon=True)
        out_thread.start()
        err_thread.start()
        started_at = time.time()

        try:
            while True:
                if self.is_closed:
                    break
                if (time.time() - started_at) > timeout_seconds:
                    proc.terminate()
                    raise TimeoutError("Timed out waiting for Claude Code CLI response.")
                try:
                    raw_line = stdout_queue.get(timeout=0.1)
                except queue.Empty:
                    if proc.poll() is not None and stdout_done.is_set():
                        break
                    continue

                if raw_line is None:
                    if proc.poll() is not None and stdout_done.is_set():
                        break
                    continue

                line = raw_line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except Exception:
                    continue
                if not isinstance(message, dict):
                    continue

                msg_type = str(message.get("type") or "").strip().lower()
                if msg_type == "assistant":
                    for progress in _extract_progress_events(message):
                        if progress["kind"] == "thinking" and self._thinking_callback:
                            try:
                                self._thinking_callback(progress["preview"])
                            except Exception:
                                pass
                        if self._tool_progress_callback:
                            try:
                                self._tool_progress_callback(
                                    progress["tool_name"],
                                    progress["preview"],
                                )
                            except Exception:
                                pass
                        if self._status_callback:
                            try:
                                self._status_callback("claude_code_cli", progress["message"])
                            except Exception:
                                pass
                    for text in _extract_text_blocks(message):
                        if text:
                            yield {"type": "text", "text": text}
                elif msg_type == "result":
                    output_text = (
                        _coerce_output_text(message.get("result"))
                        or _coerce_output_text(message.get("output"))
                        or _coerce_output_text(message.get("error"))
                        or _coerce_output_text(message.get("message"))
                    )
                    yield {
                        "type": "result",
                        "usage": _extract_usage(message),
                        "output": output_text,
                        "is_error": bool(message.get("is_error")),
                        "subtype": str(message.get("subtype") or "").strip(),
                    }
            remaining = max(timeout_seconds - (time.time() - started_at), 1.0)
            try:
                proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                proc.terminate()
                raise TimeoutError("Timed out waiting for Claude Code CLI response.")

            stderr_done.wait(timeout=1.0)
            stderr_text = "\n".join(stderr_tail).strip()
            if proc.returncode not in (0, None):
                raise RuntimeError(
                    stderr_text or f"Claude Code CLI exited with code {proc.returncode}."
                )
        finally:
            self.close()
            if temp_dir:
                try:
                    import shutil

                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
