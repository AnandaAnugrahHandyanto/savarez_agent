"""OpenAI-compatible client facade for local MLX models.

The adapter lets Hermes use ``mlx_lm.generate`` without starting a localhost
HTTP server. It intentionally looks like the small subset of the OpenAI SDK
that ``run_agent.py`` consumes: ``client.chat.completions.create(...)`` returns
objects with ``choices[*].message``/``delta``/``usage`` attributes, and supports
both non-streaming and streaming calls.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

MLX_LOCAL_MARKER_BASE_URL = "mlx://local"
_DEFAULT_TIMEOUT_SECONDS = 900.0
_TOOL_CALL_BLOCK_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def _resolve_command(command: str | None = None) -> str:
    explicit = (
        command
        or os.getenv("HERMES_MLX_LOCAL_COMMAND", "").strip()
        or os.getenv("MLX_LM_GENERATE_PATH", "").strip()
    )
    if explicit:
        return explicit

    discovered = shutil.which("mlx_lm.generate")
    if discovered:
        return discovered

    for candidate in (
        Path.home() / ".local/bin/mlx_lm.generate",
        Path("/opt/homebrew/bin/mlx_lm.generate"),
        Path("/usr/local/bin/mlx_lm.generate"),
    ):
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)

    return "mlx_lm.generate"


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts = [
        str(Path.home() / ".local/bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        env.get("PATH", ""),
    ]
    env["PATH"] = os.pathsep.join(part for part in path_parts if part)
    return env


def _timeout_seconds(timeout: Any) -> float:
    if timeout is None:
        return _DEFAULT_TIMEOUT_SECONDS
    if isinstance(timeout, (int, float)):
        return float(timeout)
    candidates = [getattr(timeout, attr, None) for attr in ("read", "write", "connect", "pool", "timeout")]
    numeric = [float(value) for value in candidates if isinstance(value, (int, float))]
    return max(numeric) if numeric else _DEFAULT_TIMEOUT_SECONDS


def _render_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text.strip()
        return json.dumps(content, ensure_ascii=False)
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


def _render_tool_calls(tool_calls: Any) -> str:
    if not isinstance(tool_calls, list):
        return ""
    rendered: list[str] = []
    for index, tool_call in enumerate(tool_calls, start=1):
        if hasattr(tool_call, "function"):
            call_id = getattr(tool_call, "id", None) or getattr(tool_call, "call_id", None)
            function = getattr(tool_call, "function", None)
            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", "{}")
        elif isinstance(tool_call, dict):
            call_id = tool_call.get("id") or tool_call.get("call_id")
            function = tool_call.get("function") or {}
            name = function.get("name") if isinstance(function, dict) else None
            arguments = function.get("arguments", "{}") if isinstance(function, dict) else "{}"
        else:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)
        call_id = call_id if isinstance(call_id, str) and call_id.strip() else f"mlx_call_{index}"
        rendered.append(
            "<tool_call>"
            + json.dumps(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name.strip(), "arguments": arguments},
                },
                ensure_ascii=False,
            )
            + "</tool_call>"
        )
    return "\n".join(rendered)


def _format_messages(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
) -> tuple[str | None, str]:
    system_parts: list[str] = []
    transcript: list[str] = []

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "user").strip().lower()
        rendered = _render_content(message.get("content"))
        if role == "assistant":
            tool_call_text = _render_tool_calls(message.get("tool_calls"))
            if tool_call_text:
                rendered = "\n".join(part for part in (rendered, tool_call_text) if part)
        elif role == "tool":
            call_id = message.get("tool_call_id")
            name = message.get("name") or message.get("tool_name")
            prefix_parts = []
            if isinstance(name, str) and name.strip():
                prefix_parts.append(f"name={name.strip()}")
            if isinstance(call_id, str) and call_id.strip():
                prefix_parts.append(f"tool_call_id={call_id.strip()}")
            if prefix_parts and rendered:
                rendered = f"({' '.join(prefix_parts)})\n{rendered}"
        if not rendered:
            continue
        if role == "system":
            system_parts.append(rendered)
        else:
            label = {
                "user": "User",
                "assistant": "Assistant",
                "tool": "Tool",
            }.get(role, role.title())
            transcript.append(f"{label}:\n{rendered}")

    prompt_sections: list[str] = []
    if tools:
        tool_specs: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            function = tool.get("function") or {}
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            tool_specs.append(
                {
                    "name": name.strip(),
                    "description": function.get("description", ""),
                    "parameters": function.get("parameters", {}),
                }
            )
        if tool_specs:
            prompt_sections.append(
                "Available tools are listed as OpenAI function schemas. "
                "When using a tool, emit only <tool_call>{...}</tool_call> "
                "with one JSON object shaped as {id,type,function:{name,arguments}}. "
                "The function.arguments value must be a JSON string.\n"
                + json.dumps(tool_specs, ensure_ascii=False)
            )

    if tool_choice is not None:
        prompt_sections.append(f"Tool choice hint: {json.dumps(tool_choice, ensure_ascii=False)}")

    if transcript:
        prompt_sections.append("Conversation transcript:\n\n" + "\n\n".join(transcript))
    prompt_sections.append("Continue from the latest user request.")

    system_prompt = "\n\n".join(system_parts).strip() or None
    return system_prompt, "\n\n".join(section.strip() for section in prompt_sections if section.strip())


def _usage() -> SimpleNamespace:
    return SimpleNamespace(
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )


def _parse_tool_calls(text: str) -> tuple[list[SimpleNamespace] | None, str | None]:
    if not text:
        return None, None

    calls: list[SimpleNamespace] = []
    consumed: list[tuple[int, int]] = []
    for match in _TOOL_CALL_BLOCK_RE.finditer(text):
        try:
            obj = json.loads(match.group(1))
        except Exception:
            continue
        function = obj.get("function") if isinstance(obj, dict) else None
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        arguments = function.get("arguments", "{}")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False)
        call_id = obj.get("id")
        if not isinstance(call_id, str) or not call_id.strip():
            call_id = f"mlx_call_{len(calls) + 1}"
        calls.append(
            SimpleNamespace(
                id=call_id,
                call_id=call_id,
                type="function",
                function=SimpleNamespace(name=name.strip(), arguments=arguments),
            )
        )
        consumed.append((match.start(), match.end()))

    cleaned = text.strip()
    if consumed:
        parts: list[str] = []
        cursor = 0
        for start, end in consumed:
            if cursor < start:
                parts.append(text[cursor:start])
            cursor = end
        if cursor < len(text):
            parts.append(text[cursor:])
        cleaned = "\n".join(part.strip() for part in parts if part.strip()).strip()

    return calls or None, cleaned or None


class _MLXChatCompletions:
    def __init__(self, client: "MLXLocalClient"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _MLXChatNamespace:
    def __init__(self, client: "MLXLocalClient"):
        self.completions = _MLXChatCompletions(client)


class MLXLocalClient:
    """Minimal OpenAI-client-compatible facade for ``mlx_lm.generate``."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        timeout: Any = None,
        command: str | None = None,
        **_: Any,
    ):
        self.api_key = api_key or "mlx-local"
        self.base_url = base_url or MLX_LOCAL_MARKER_BASE_URL
        self._default_headers = dict(default_headers or {})
        self._timeout = timeout
        self._command = _resolve_command(command)
        self.chat = _MLXChatNamespace(self)
        self.is_closed = False

    def close(self) -> None:
        self.is_closed = True

    def _create_chat_completion(
        self,
        *,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: Any = None,
        stream: bool = False,
        stream_options: dict[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        response_text = self._run_generate(
            model=model,
            messages=messages or [],
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        tool_calls, content = _parse_tool_calls(response_text)
        finish_reason = "tool_calls" if tool_calls else "stop"
        if stream:
            return self._stream_chunks(
                model=model,
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                include_usage=bool((stream_options or {}).get("include_usage")),
            )

        message = SimpleNamespace(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            reasoning=None,
            reasoning_content=None,
            reasoning_details=None,
        )
        return SimpleNamespace(
            model=model or "mlx-local",
            choices=[SimpleNamespace(index=0, message=message, finish_reason=finish_reason)],
            usage=_usage(),
        )

    def _run_generate(
        self,
        *,
        model: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: Any,
        max_tokens: int | None,
        temperature: float | None,
        timeout: Any,
    ) -> str:
        if not model:
            raise ValueError("MLX local client requires a local model path as the model name.")

        system_prompt, prompt = _format_messages(messages, tools=tools, tool_choice=tool_choice)
        argv = shlex.split(self._command)
        argv += ["--model", model, "--prompt", "-", "--verbose", "False"]
        if system_prompt:
            argv += ["--system-prompt", system_prompt]
        if max_tokens is not None:
            argv += ["--max-tokens", str(max_tokens)]
        if temperature is not None:
            argv += ["--temp", str(temperature)]

        try:
            completed = subprocess.run(
                argv,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=_timeout_seconds(timeout or self._timeout),
                env=_subprocess_env(),
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Could not start mlx_lm.generate. Install mlx-lm or set "
                "HERMES_MLX_LOCAL_COMMAND/MLX_LM_GENERATE_PATH."
            ) from exc

        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(f"mlx_lm.generate failed with exit code {completed.returncode}: {stderr}")
        return (completed.stdout or "").strip()

    def _stream_chunks(
        self,
        *,
        model: str | None,
        content: str | None,
        tool_calls: list[SimpleNamespace] | None,
        finish_reason: str,
        include_usage: bool,
    ) -> Iterable[SimpleNamespace]:
        if tool_calls:
            deltas: list[SimpleNamespace] = []
            for index, call in enumerate(tool_calls):
                deltas.append(
                    SimpleNamespace(
                        index=index,
                        id=call.id,
                        type="function",
                        function=SimpleNamespace(
                            name=call.function.name,
                            arguments=call.function.arguments,
                        ),
                    )
                )
            yield SimpleNamespace(
                model=model or "mlx-local",
                choices=[
                    SimpleNamespace(
                        index=0,
                        delta=SimpleNamespace(content=None, tool_calls=deltas),
                        finish_reason=None,
                    )
                ],
                usage=None,
            )
        elif content:
            yield SimpleNamespace(
                model=model or "mlx-local",
                choices=[
                    SimpleNamespace(
                        index=0,
                        delta=SimpleNamespace(content=content, tool_calls=None),
                        finish_reason=None,
                    )
                ],
                usage=None,
            )

        yield SimpleNamespace(
            model=model or "mlx-local",
            choices=[
                SimpleNamespace(
                    index=0,
                    delta=SimpleNamespace(content=None, tool_calls=None),
                    finish_reason=finish_reason,
                )
            ],
            usage=None,
        )
        if include_usage:
            yield SimpleNamespace(model=model or "mlx-local", choices=[], usage=_usage())
