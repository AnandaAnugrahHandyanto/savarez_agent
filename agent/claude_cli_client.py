"""OpenAI-compatible facade that routes Hermes requests through Claude Code CLI.

This adapter lets Hermes treat ``claude -p`` as a chat-style backend.
It disables Claude Code built-in tools and asks the model to emit OpenAI-style
tool calls inside ``<tool_call>{...}</tool_call>`` blocks when Hermes tools are
needed. The client remembers the Claude session id and resumes it on later
turns within the same Hermes session.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any


CLAUDE_CLI_MARKER_BASE_URL = "claude-cli://local"
_DEFAULT_TIMEOUT_SECONDS = 900.0

_TOOL_CALL_BLOCK_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_TOOL_CALL_JSON_RE = re.compile(
    r"\{\s*\"id\"\s*:\s*\"[^\"]+\"\s*,\s*\"type\"\s*:\s*\"function\"\s*,\s*\"function\"\s*:\s*\{.*?\}\s*\}",
    re.DOTALL,
)


def _debug_log(message: str) -> None:
    path = os.getenv("HERMES_CLAUDE_CLI_DEBUG_LOG", "").strip()
    if not path:
        return
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _resolve_command() -> str:
    return (
        os.getenv("HERMES_CLAUDE_CLI_COMMAND", "").strip()
        or os.getenv("CLAUDE_CLI_PATH", "").strip()
        or os.getenv("CLAUDE_CODE_CLI_PATH", "").strip()
        or "claude"
    )


def _resolve_args() -> list[str]:
    raw = os.getenv("HERMES_CLAUDE_CLI_ARGS", "").strip()
    if not raw:
        return []
    return shlex.split(raw)


def _normalize_model(model: str | None) -> str | None:
    if not model:
        return None
    normalized = model.strip()
    if normalized.startswith("claude-cli/"):
        normalized = normalized.split("/", 1)[1]
    if normalized.startswith("anthropic/"):
        normalized = normalized.split("/", 1)[1]
    return normalized or None


def _resume_enabled() -> bool:
    raw = os.getenv("HERMES_CLAUDE_CLI_RESUME", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


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
                continue
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "")).strip().lower()
            if item_type in {"text", "input_text"}:
                text = item.get("text") or item.get("input_text") or ""
                parts.append(str(text).strip())
            elif item_type in {"image_url", "input_image"}:
                parts.append("[image omitted]")
            elif item_type in {"tool_result", "tool_use", "function"}:
                parts.append(f"[{item_type} omitted]")
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def _render_assistant_tool_calls(tool_calls: Any) -> str:
    if not isinstance(tool_calls, list) or not tool_calls:
        return ""
    rendered_calls: list[str] = []
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        function = tool_call.get("function") or {}
        if not isinstance(function, dict):
            function = {}
        payload = {
            "id": tool_call.get("call_id") or tool_call.get("id") or "",
            "type": tool_call.get("type") or "function",
            "function": {
                "name": function.get("name") or "",
                "arguments": function.get("arguments") or "{}",
            },
        }
        rendered_calls.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(rendered_calls).strip()


def _format_messages_as_prompt(
    messages: list[dict[str, Any]],
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
) -> str:
    sections: list[str] = [
        "You are the active Claude Code CLI backend for Hermes.",
        "Claude Code built-in tools are disabled for this call.",
        "When Hermes tools are needed, emit tool calls using <tool_call>{...}</tool_call> blocks.",
        "Each tool call JSON must match OpenAI function-call shape exactly: {\"id\":...,\"type\":\"function\",\"function\":{\"name\":...,\"arguments\":\"{...}\"}}.",
        "Assistant tool request(s) in the transcript show the exact tool calls you already asked Hermes to run.",
        "Tool result (...) entries are the results Hermes returned for those tool calls.",
        "After tool results arrive, either issue the next required tool call or give the final answer.",
        "Do not repeat the same failed probe over and over. If a tool result shows a missing binary/config/path, adapt your next tool call to use the concrete path or environment that was discovered.",
        "If no tool is needed, answer normally.",
    ]
    if model:
        sections.append(f"Hermes requested model hint: {model}")

    if isinstance(tools, list) and tools:
        tool_specs: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            fn = tool.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            tool_specs.append(
                {
                    "name": name.strip(),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                }
            )
        if tool_specs:
            sections.append(
                "Available Hermes tools (OpenAI function schema):\n"
                + json.dumps(tool_specs, ensure_ascii=False)
            )

    if tool_choice is not None:
        sections.append(f"Tool choice hint: {json.dumps(tool_choice, ensure_ascii=False)}")

    transcript: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown").strip().lower()
        if role == "assistant":
            rendered = _render_message_content(message.get("content"))
            rendered_tool_calls = _render_assistant_tool_calls(message.get("tool_calls"))
            if rendered:
                transcript.append(f"Assistant:\n{rendered}")
            if rendered_tool_calls:
                transcript.append(
                    "Assistant tool request(s):\n"
                    f"{rendered_tool_calls}"
                )
            continue

        if role == "tool":
            tool_call_id = str(message.get("tool_call_id") or "").strip()
            rendered = _render_message_content(message.get("content"))
            if rendered:
                label = f"Tool result ({tool_call_id})" if tool_call_id else "Tool result"
                transcript.append(f"{label}:\n{rendered}")
            continue

        label = {
            "system": "System",
            "user": "User",
        }.get(role, role.title())
        rendered = _render_message_content(message.get("content"))
        if rendered:
            transcript.append(f"{label}:\n{rendered}")

    if transcript:
        sections.append("Conversation transcript:\n\n" + "\n\n".join(transcript))

    sections.append("Continue the conversation from the latest user request.")
    return "\n\n".join(part.strip() for part in sections if part and part.strip())


def _extract_tool_calls_from_text(text: str) -> tuple[list[SimpleNamespace], str]:
    _debug_log(
        "extract:start "
        f"text_len={len(text) if isinstance(text, str) else -1} "
        f"has_tag={'<tool_call>' in text if isinstance(text, str) else False}"
    )
    if not isinstance(text, str) or not text.strip():
        _debug_log("extract:empty")
        return [], ""

    extracted: list[SimpleNamespace] = []
    consumed_spans: list[tuple[int, int]] = []

    def _try_add_tool_call(raw_json: str) -> None:
        try:
            obj = json.loads(raw_json)
        except Exception:
            return
        if not isinstance(obj, dict):
            return
        fn = obj.get("function")
        if not isinstance(fn, dict):
            return
        fn_name = fn.get("name")
        if not isinstance(fn_name, str) or not fn_name.strip():
            return
        fn_args = fn.get("arguments", "{}")
        if not isinstance(fn_args, str):
            fn_args = json.dumps(fn_args, ensure_ascii=False)
        call_id = obj.get("id")
        if not isinstance(call_id, str) or not call_id.strip():
            call_id = f"claude_cli_call_{len(extracted)+1}"

        extracted.append(
            SimpleNamespace(
                id=call_id,
                call_id=call_id,
                response_item_id=None,
                type="function",
                function=SimpleNamespace(name=fn_name.strip(), arguments=fn_args),
            )
        )

    for match in _TOOL_CALL_BLOCK_RE.finditer(text):
        _try_add_tool_call(match.group(1))
        consumed_spans.append((match.start(), match.end()))

    if not extracted:
        for match in _TOOL_CALL_JSON_RE.finditer(text):
            _try_add_tool_call(match.group(0))
            consumed_spans.append((match.start(), match.end()))

    if not consumed_spans:
        cleaned = text.strip()
        if cleaned in {"</s>", "<|endoftext|>", "<|eot_id|>"}:
            cleaned = ""
        _debug_log(f"extract:none cleaned_len={len(cleaned)}")
        return extracted, cleaned

    consumed_spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in consumed_spans:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))

    parts: list[str] = []
    cursor = 0
    for start, end in merged:
        if cursor < start:
            parts.append(text[cursor:start])
        cursor = max(cursor, end)
    if cursor < len(text):
        parts.append(text[cursor:])

    cleaned = "\n".join(part.strip() for part in parts if part and part.strip()).strip()
    if cleaned in {"</s>", "<|endoftext|>", "<|eot_id|>"}:
        cleaned = ""
    _debug_log(f"extract:done tool_calls={len(extracted)} cleaned_len={len(cleaned)}")
    return extracted, cleaned


class _ClaudeCLIChatCompletions:
    def __init__(self, client: "ClaudeCLIClient"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _ClaudeCLIChatNamespace:
    def __init__(self, client: "ClaudeCLIClient"):
        self.completions = _ClaudeCLIChatCompletions(client)


class _ClaudeCLIStreamChunk(SimpleNamespace):
    """Mimics an OpenAI ChatCompletionChunk with .choices[0].delta."""


def _make_stream_chunk(
    *,
    model: str,
    content: str = "",
    reasoning: str = "",
    tool_call_delta: dict[str, Any] | None = None,
    finish_reason: str | None = None,
    usage: Any = None,
) -> _ClaudeCLIStreamChunk:
    delta_kwargs: dict[str, Any] = {
        "content": None,
        "tool_calls": None,
        "reasoning": None,
        "reasoning_content": None,
    }
    if content or tool_call_delta is not None or reasoning:
        delta_kwargs["role"] = "assistant"
    if content:
        delta_kwargs["content"] = content
    if reasoning:
        delta_kwargs["reasoning"] = reasoning
        delta_kwargs["reasoning_content"] = reasoning
    if tool_call_delta is not None:
        delta_kwargs["tool_calls"] = [
            SimpleNamespace(
                index=tool_call_delta.get("index", 0),
                id=tool_call_delta.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                type="function",
                function=SimpleNamespace(
                    name=tool_call_delta.get("name") or "",
                    arguments=tool_call_delta.get("arguments") or "",
                ),
            )
        ]
    delta = SimpleNamespace(**delta_kwargs)
    choice = SimpleNamespace(index=0, delta=delta, finish_reason=finish_reason)
    return _ClaudeCLIStreamChunk(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        object="chat.completion.chunk",
        created=int(time.time()),
        model=model,
        choices=[choice],
        usage=usage,
    )


class ClaudeCLIClient:
    """Minimal OpenAI-client-compatible facade for Claude Code CLI."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        claude_command: str | None = None,
        claude_args: list[str] | None = None,
        claude_cwd: str | None = None,
        timeout: float | None = None,
        **_: Any,
    ):
        self.api_key = api_key or "claude-cli"
        self.base_url = base_url or CLAUDE_CLI_MARKER_BASE_URL
        self._default_headers = dict(default_headers or {})
        self._command = claude_command or command or _resolve_command()
        self._args = list(claude_args or args or _resolve_args())
        self._cwd = str(Path(claude_cwd or os.getcwd()).resolve())
        self._timeout = (
            float(timeout) if isinstance(timeout, (int, float)) else _DEFAULT_TIMEOUT_SECONDS
        )
        self._last_session_id: str | None = None
        self._last_total_cost_usd: float | None = None
        self._last_stop_reason: str | None = None
        self.chat = _ClaudeCLIChatNamespace(self)
        self.is_closed = False

    def close(self) -> None:
        self.is_closed = True

    def _create_chat_completion(
        self,
        *,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        stream: bool = False,
        **_: Any,
    ) -> Any:
        prompt_text = _format_messages_as_prompt(
            messages or [],
            model=model,
            tools=tools,
            tool_choice=tool_choice,
        )

        if timeout is None:
            effective_timeout = self._timeout
        elif isinstance(timeout, (int, float)):
            effective_timeout = float(timeout)
        else:
            candidates = [
                getattr(timeout, attr, None)
                for attr in ("read", "write", "connect", "pool", "timeout")
            ]
            numeric = [float(v) for v in candidates if isinstance(v, (int, float))]
            effective_timeout = max(numeric) if numeric else self._timeout

        result = self._run_prompt(prompt_text, model=model, timeout_seconds=effective_timeout)
        _debug_log(
            "create:prompt_done "
            f"prompt_len={len(prompt_text)} "
            f"result_keys={sorted(result.keys())}"
        )
        response_text = str(result.get("result") or "").strip()
        _debug_log(f"create:result_text result_len={len(response_text)}")
        tool_calls, cleaned_text = _extract_tool_calls_from_text(response_text)
        _debug_log(
            "create:extract_done "
            f"tool_calls={len(tool_calls)} cleaned_len={len(cleaned_text)}"
        )
        usage_payload = result.get("usage") or {}

        prompt_tokens = int(
            usage_payload.get("input_tokens")
            or usage_payload.get("cache_creation_input_tokens")
            or 0
        )
        completion_tokens = int(usage_payload.get("output_tokens") or 0)
        cached_tokens = int(usage_payload.get("cache_read_input_tokens") or 0)

        usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
        )
        finish_reason = "tool_calls" if tool_calls else "stop"

        if stream:
            return self._stream_completion(
                model=model or "claude-cli",
                content=cleaned_text,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )

        assistant_message = SimpleNamespace(
            content=cleaned_text,
            tool_calls=tool_calls,
            reasoning=None,
            reasoning_content=None,
            reasoning_details=None,
        )
        choice = SimpleNamespace(message=assistant_message, finish_reason=finish_reason)
        return SimpleNamespace(
            choices=[choice],
            usage=usage,
            model=model or "claude-cli",
            claude_session_id=self._last_session_id,
            claude_total_cost_usd=self._last_total_cost_usd,
            claude_stop_reason=self._last_stop_reason,
        )

    def _stream_completion(
        self,
        *,
        model: str,
        content: str,
        tool_calls: list[SimpleNamespace],
        finish_reason: str,
        usage: Any,
    ):
        def _generator():
            if content:
                yield _make_stream_chunk(model=model, content=content)

            for index, tool_call in enumerate(tool_calls):
                yield _make_stream_chunk(
                    model=model,
                    tool_call_delta={
                        "index": index,
                        "id": getattr(tool_call, "id", None),
                        "name": getattr(getattr(tool_call, "function", None), "name", ""),
                        "arguments": getattr(getattr(tool_call, "function", None), "arguments", ""),
                    },
                )

            yield _make_stream_chunk(
                model=model,
                finish_reason=finish_reason,
                usage=usage,
            )

        return _generator()

    def _run_prompt(
        self,
        prompt_text: str,
        *,
        model: str | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        normalized_model = _normalize_model(model)
        command = [self._command, *self._args, "-p", "--output-format", "json", "--tools", ""]
        if normalized_model:
            command.extend(["--model", normalized_model])
        if self._last_session_id and _resume_enabled():
            command.extend(["--resume", self._last_session_id])

        resolved = shutil.which(command[0]) if command and command[0] else None
        if not resolved:
            raise RuntimeError(
                f"Could not find Claude CLI command '{command[0]}'. Install Claude Code or set "
                "HERMES_CLAUDE_CLI_COMMAND/CLAUDE_CLI_PATH."
            )
        command[0] = resolved
        _debug_log(
            "run_prompt:start "
            f"model={normalized_model or ''} "
            f"timeout={timeout_seconds:.1f} "
            f"cwd={self._cwd} "
            f"argv_len={sum(len(part) for part in command)} "
            f"prompt_len={len(prompt_text)}"
        )

        try:
            proc = subprocess.run(
                command,
                input=prompt_text,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                cwd=self._cwd,
            )
        except subprocess.TimeoutExpired as exc:
            _debug_log("run_prompt:timeout")
            raise TimeoutError(f"Claude CLI timed out after {timeout_seconds:.0f}s") from exc

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        _debug_log(
            "run_prompt:done "
            f"rc={proc.returncode} stdout_len={len(stdout)} stderr_len={len(stderr)}"
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Claude CLI returned exit code {proc.returncode}: {stderr or stdout or 'unknown error'}"
            )

        try:
            payload = json.loads(stdout)
        except Exception as exc:
            _debug_log(f"run_prompt:json_error preview={stdout[:200]!r}")
            raise RuntimeError(f"Claude CLI did not return JSON: {stdout[:500]}") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Claude CLI returned unexpected payload shape")

        session_id = str(payload.get("session_id") or "").strip()
        if session_id:
            self._last_session_id = session_id

        total_cost = payload.get("total_cost_usd")
        self._last_total_cost_usd = (
            float(total_cost) if isinstance(total_cost, (int, float)) else None
        )
        stop_reason = payload.get("stop_reason")
        self._last_stop_reason = str(stop_reason).strip() if isinstance(stop_reason, str) else None
        _debug_log(
            "run_prompt:parsed "
            f"session_id={self._last_session_id or ''} "
            f"stop_reason={self._last_stop_reason or ''}"
        )
        return payload
