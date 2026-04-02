"""OpenAI-compatible shim that forwards Hermes requests to `copilot --acp`.

This adapter lets Hermes treat the GitHub Copilot ACP server as a chat-style
backend. Each request starts a short-lived ACP session, sends the formatted
conversation as a single prompt, collects text chunks, and converts the result
back into the minimal shape Hermes expects from an OpenAI client.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shlex
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ACP_MARKER_BASE_URL = "acp://copilot"
_DEFAULT_TIMEOUT_SECONDS = 900.0

_TOOL_CALL_BLOCK_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_TOOL_CALL_JSON_RE = re.compile(r"\{\s*\"id\"\s*:\s*\"[^\"]+\"\s*,\s*\"type\"\s*:\s*\"function\"\s*,\s*\"function\"\s*:\s*\{.*?\}\s*\}", re.DOTALL)
_TERMINAL_COMMAND_HINT_RE = re.compile(
    r"(?:ferramenta\s+terminal.*?comando|execute\s+o\s+comando|run\s+the\s+command)\s*[:\-]?\s*[`'\"]([^`'\"\n]+)[`'\"]",
    re.IGNORECASE | re.DOTALL,
)
_VISION_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _resolve_command() -> str:
    return (
        os.getenv("HERMES_COPILOT_ACP_COMMAND", "").strip()
        or os.getenv("COPILOT_CLI_PATH", "").strip()
        or "copilot"
    )


def _resolve_args() -> list[str]:
    raw = os.getenv("HERMES_COPILOT_ACP_ARGS", "").strip()
    if not raw:
        return ["--acp", "--stdio"]
    return shlex.split(raw)


def _jsonrpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _canonicalize_for_signature(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canonicalize_for_signature(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_canonicalize_for_signature(v) for v in value]
    if isinstance(value, tuple):
        return [_canonicalize_for_signature(v) for v in value]
    if isinstance(value, SimpleNamespace):
        return _canonicalize_for_signature(vars(value))
    return value


def _message_signature(message: dict[str, Any]) -> str:
    return json.dumps(_canonicalize_for_signature(message), ensure_ascii=False, sort_keys=True)


def _render_message_entry(message: dict[str, Any]) -> str:
    role = str(message.get("role") or "unknown").strip().lower()
    if role == "tool":
        role = "tool"
    elif role not in {"system", "user", "assistant"}:
        role = "context"

    parts: list[str] = [f'<message role="{role}">']

    name = message.get("name")
    if isinstance(name, str) and name.strip():
        parts.append(f"name: {name.strip()}")

    tool_call_id = message.get("tool_call_id")
    if isinstance(tool_call_id, str) and tool_call_id.strip():
        parts.append(f"tool_call_id: {tool_call_id.strip()}")

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        rendered_tool_calls: list[dict[str, Any]] = []
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            rendered_tool_calls.append(_canonicalize_for_signature(tc))
        if rendered_tool_calls:
            parts.append("tool_calls:")
            parts.append(json.dumps(rendered_tool_calls, ensure_ascii=False, indent=2))

    content = _render_message_content(message.get("content"))
    if content:
        parts.append("content:")
        parts.append(content)

    parts.append("</message>")
    return "\n".join(part for part in parts if part and str(part).strip())


def _format_messages_as_prompt(
    messages: list[dict[str, Any]],
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    *,
    reasoning_effort: str | None = None,
    incremental: bool = False,
) -> str:
    sections: list[str] = [
        "You are being used as the active ACP agent backend for Hermes.",
        "Use ACP capabilities to complete tasks.",
        "IMPORTANT: If you take an action with a tool, you MUST output tool calls using <tool_call>{...}</tool_call> blocks with JSON exactly in OpenAI function-call shape.",
        "If no tool is needed, answer normally.",
    ]
    if model:
        sections.append(f"Hermes requested model hint: {model}")
    if reasoning_effort:
        sections.append(f"Hermes requested reasoning effort: {reasoning_effort}")

    if isinstance(tools, list) and tools:
        tool_specs: list[dict[str, Any]] = []
        for t in tools:
            if not isinstance(t, dict):
                continue
            fn = t.get("function") or {}
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
                "Available tools (OpenAI function schema). "
                "When using a tool, emit ONLY <tool_call>{...}</tool_call> with one JSON object "
                "containing id/type/function{name,arguments}. arguments must be a JSON string.\n"
                + json.dumps(tool_specs, ensure_ascii=False)
            )

    if tool_choice is not None:
        sections.append(f"Tool choice hint: {json.dumps(tool_choice, ensure_ascii=False)}")

    transcript: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        rendered = _render_message_entry(message)
        if rendered:
            transcript.append(rendered)

    if transcript:
        header = "New conversation items since your last turn:" if incremental else "Conversation transcript:"
        sections.append(header + "\n\n" + "\n\n".join(transcript))

    if incremental:
        sections.append("Continue the existing ACP session using only the new messages above.")
    else:
        sections.append("Continue the conversation from the latest user request.")
    return "\n\n".join(section.strip() for section in sections if section and section.strip())


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
        return json.dumps(_canonicalize_for_signature(content), ensure_ascii=False)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                item_type = str(item.get("type") or "").strip().lower()
                text_value = item.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    parts.append(text_value.strip())
                    continue
                if item_type == "input_text":
                    input_text = item.get("text")
                    if isinstance(input_text, str) and input_text.strip():
                        parts.append(input_text.strip())
                        continue
                if item_type in {"image_url", "input_image"}:
                    image_url = item.get("image_url") or item.get("url")
                    if isinstance(image_url, dict):
                        image_url = image_url.get("url")
                    if isinstance(image_url, str) and image_url.strip():
                        parts.append(f"[image] {image_url.strip()}")
                        continue
                parts.append(json.dumps(_canonicalize_for_signature(item), ensure_ascii=False))
        return "\n".join(parts).strip()
    return str(content).strip()


def _extract_tool_calls_from_text(text: str) -> tuple[list[SimpleNamespace], str]:
    if not isinstance(text, str) or not text.strip():
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
            call_id = f"acp_call_{len(extracted)+1}"

        extracted.append(
            SimpleNamespace(
                id=call_id,
                call_id=call_id,
                response_item_id=None,
                type="function",
                function=SimpleNamespace(name=fn_name.strip(), arguments=fn_args),
            )
        )

    for m in _TOOL_CALL_BLOCK_RE.finditer(text):
        raw = m.group(1)
        _try_add_tool_call(raw)
        consumed_spans.append((m.start(), m.end()))

    for m in _TOOL_CALL_JSON_RE.finditer(text):
        raw = m.group(0)
        _try_add_tool_call(raw)
        consumed_spans.append((m.start(), m.end()))

    if not consumed_spans:
        return extracted, text.strip()

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

    cleaned = "\n".join(p.strip() for p in parts if p and p.strip()).strip()
    return extracted, cleaned


def _latest_user_text(messages: list[dict[str, Any]] | None) -> str:
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "").strip().lower()
        if role != "user":
            continue
        return _render_message_content(msg.get("content"))
    return ""


def _heuristic_fallback_tool_calls(
    messages: list[dict[str, Any]] | None,
    response_text: str,
    tools: list[dict[str, Any]] | None = None,
) -> list[SimpleNamespace]:
    """Best-effort fallback when ACP returns prose instead of structured tool calls."""
    user_text = _latest_user_text(messages)
    if not user_text:
        return []

    allowed_tool_names: set[str] = set()
    if isinstance(tools, list):
        for t in tools:
            if not isinstance(t, dict):
                continue
            fn = t.get("function") or {}
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if isinstance(name, str) and name.strip():
                allowed_tool_names.add(name.strip())

    # Additional guard: only trigger when assistant prose indicates intent/action.
    lower_resp = (response_text or "").lower()
    intent_like = (not lower_resp) or any(
        token in lower_resp
        for token in (
            "vou executar",
            "i will run",
            "executar o comando",
            "running",
            "não tenho acesso",
            "nao tenho acesso",
            "não está disponível",
            "not available",
        )
    )
    if not intent_like:
        return []

    # Terminal fallback
    m = _TERMINAL_COMMAND_HINT_RE.search(user_text)
    if m:
        command = (m.group(1) or "").strip()
        if command and ((not allowed_tool_names) or ("terminal" in allowed_tool_names)):
            args = json.dumps({"command": command}, ensure_ascii=False)
            call_id = "acp_fallback_terminal_1"
            return [
                SimpleNamespace(
                    id=call_id,
                    call_id=call_id,
                    response_item_id=None,
                    type="function",
                    function=SimpleNamespace(name="terminal", arguments=args),
                )
            ]

    # Vision fallback
    asks_vision = (
        "vision_analyze" in user_text.lower()
        or "visão" in user_text.lower()
        or "visao" in user_text.lower()
        or "imagem" in user_text.lower()
        or "image" in user_text.lower()
    )
    if asks_vision:
        url_match = _VISION_URL_RE.search(user_text)
        if url_match:
            image_url = url_match.group(0).strip().rstrip('.,)')
            args = json.dumps({"image_url": image_url, "user_prompt": "Descreva em 1 frase."}, ensure_ascii=False)
            call_id = "acp_fallback_vision_1"
            return [
                SimpleNamespace(
                    id=call_id,
                    call_id=call_id,
                    response_item_id=None,
                    type="function",
                    function=SimpleNamespace(name="vision_analyze", arguments=args),
                )
            ]

    return []


def _ensure_path_within_cwd(path_text: str, cwd: str) -> Path:
    candidate = Path(path_text)
    if not candidate.is_absolute():
        raise PermissionError("ACP file-system paths must be absolute.")
    resolved = candidate.resolve()
    root = Path(cwd).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError(f"Path '{resolved}' is outside the session cwd '{root}'.") from exc
    return resolved


class _ACPChatCompletions:
    def __init__(self, client: "CopilotACPClient"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _ACPChatNamespace:
    def __init__(self, client: "CopilotACPClient"):
        self.completions = _ACPChatCompletions(client)


class CopilotACPClient:
    """Minimal OpenAI-client-compatible facade for Copilot ACP."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        acp_command: str | None = None,
        acp_args: list[str] | None = None,
        acp_cwd: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        **_: Any,
    ):
        self.api_key = api_key or "copilot-acp"
        self.base_url = base_url or ACP_MARKER_BASE_URL
        self._default_headers = dict(default_headers or {})
        self._acp_command = acp_command or command or _resolve_command()
        self._acp_args = list(acp_args or args or _resolve_args())
        self._acp_cwd = str(Path(acp_cwd or os.getcwd()).resolve())
        self.chat = _ACPChatNamespace(self)
        self.is_closed = False

        self._state_lock = threading.RLock()
        self._active_process: subprocess.Popen[str] | None = None
        self._inbox: queue.Queue[dict[str, Any]] | None = None
        self._stderr_tail: deque[str] = deque(maxlen=40)
        self._next_id = 0
        self._initialized = False
        self._session_id: str | None = None
        self._session_model: str | None = None
        self._requested_model: str | None = None
        self._last_message_signatures: list[str] = []
        self._last_tools_signature: str | None = None
        self._last_tool_choice_signature: str | None = None

    def close(self) -> None:
        with self._state_lock:
            self._shutdown_process_locked()
            self.is_closed = True

    def _shutdown_process_locked(self) -> None:
        proc = self._active_process
        self._active_process = None
        self._inbox = None
        self._initialized = False
        self._session_id = None
        self._session_model = None
        self._requested_model = None
        self._next_id = 0
        self._last_message_signatures = []
        self._last_tools_signature = None
        self._last_tool_choice_signature = None
        self._stderr_tail.clear()
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

    def _create_chat_completion(
        self,
        *,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        reasoning: Any = None,
        **_: Any,
    ) -> Any:
        timeout_seconds = float(timeout or _DEFAULT_TIMEOUT_SECONDS)
        reasoning_effort = None
        if isinstance(reasoning, dict):
            effort = reasoning.get("effort")
            if isinstance(effort, str) and effort.strip() and effort.strip().lower() != "none":
                reasoning_effort = effort.strip().lower()

        message_list = list(messages or [])
        message_signatures = [_message_signature(m) for m in message_list if isinstance(m, dict)]
        tools_signature = json.dumps(_canonicalize_for_signature(tools or []), ensure_ascii=False, sort_keys=True)
        tool_choice_signature = json.dumps(_canonicalize_for_signature(tool_choice), ensure_ascii=False, sort_keys=True)

        with self._state_lock:
            requested_model_changed = bool(self._session_id) and bool(model) and self._requested_model not in (None, model)
            incremental = (
                bool(self._session_id)
                and not requested_model_changed
                and len(message_signatures) > len(self._last_message_signatures)
                and message_signatures[: len(self._last_message_signatures)] == self._last_message_signatures
                and tools_signature == self._last_tools_signature
                and tool_choice_signature == self._last_tool_choice_signature
            )

            if incremental:
                prompt_messages = message_list[len(self._last_message_signatures):]
            else:
                if self._session_id and (self._last_message_signatures or requested_model_changed):
                    self._shutdown_process_locked()
                prompt_messages = message_list

            prompt_text = _format_messages_as_prompt(
                prompt_messages,
                model=model,
                tools=tools,
                tool_choice=tool_choice,
                reasoning_effort=reasoning_effort,
                incremental=incremental,
            )
            response_text, reasoning_text = self._run_prompt(
                prompt_text,
                timeout_seconds=timeout_seconds,
                model=model,
                reasoning_effort=reasoning_effort,
            )
            self._last_message_signatures = message_signatures
            self._last_tools_signature = tools_signature
            self._last_tool_choice_signature = tool_choice_signature
            self._requested_model = model or self._requested_model

        tool_calls, cleaned_text = _extract_tool_calls_from_text(response_text)
        if not tool_calls:
            tool_calls = _heuristic_fallback_tool_calls(messages, response_text, tools=tools)

        usage = SimpleNamespace(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0),
        )
        assistant_message = SimpleNamespace(
            content=cleaned_text,
            tool_calls=tool_calls,
            reasoning=reasoning_text or None,
            reasoning_content=reasoning_text or None,
            reasoning_details=None,
        )
        finish_reason = "tool_calls" if tool_calls else "stop"
        choice = SimpleNamespace(message=assistant_message, finish_reason=finish_reason)
        return SimpleNamespace(
            choices=[choice],
            usage=usage,
            model=model or self._session_model or "copilot-acp",
        )

    def _start_process_locked(self) -> None:
        if self._active_process is not None and self._active_process.poll() is None:
            return
        try:
            proc = subprocess.Popen(
                [self._acp_command] + self._acp_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self._acp_cwd,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Could not start Copilot ACP command '{self._acp_command}'. "
                "Install GitHub Copilot CLI or set HERMES_COPILOT_ACP_COMMAND/COPILOT_CLI_PATH."
            ) from exc

        if proc.stdin is None or proc.stdout is None:
            proc.kill()
            raise RuntimeError("Copilot ACP process did not expose stdin/stdout pipes.")

        self._active_process = proc
        self._inbox = queue.Queue()
        self.is_closed = False
        self._stderr_tail.clear()

        def _stdout_reader() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                try:
                    self._inbox.put(json.loads(line))
                except Exception:
                    self._inbox.put({"raw": line.rstrip("\n")})

        def _stderr_reader() -> None:
            if proc.stderr is None:
                return
            for line in proc.stderr:
                self._stderr_tail.append(line.rstrip("\n"))

        threading.Thread(target=_stdout_reader, daemon=True).start()
        threading.Thread(target=_stderr_reader, daemon=True).start()

    def _request_locked(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float,
        text_parts: list[str] | None = None,
        reasoning_parts: list[str] | None = None,
    ) -> Any:
        proc = self._active_process
        inbox = self._inbox
        if proc is None or inbox is None or proc.stdin is None:
            raise RuntimeError("Copilot ACP process is not ready.")

        self._next_id += 1
        request_id = self._next_id
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                msg = inbox.get(timeout=0.1)
            except queue.Empty:
                continue

            if self._handle_server_message(
                msg,
                process=proc,
                cwd=self._acp_cwd,
                text_parts=text_parts,
                reasoning_parts=reasoning_parts,
            ):
                continue

            if msg.get("id") != request_id:
                continue
            if "error" in msg:
                err = msg.get("error") or {}
                raise RuntimeError(f"Copilot ACP {method} failed: {err.get('message') or err}")
            return msg.get("result")

        stderr_text = "\n".join(self._stderr_tail).strip()
        if proc.poll() is not None and stderr_text:
            raise RuntimeError(f"Copilot ACP process exited early: {stderr_text}")
        raise TimeoutError(f"Timed out waiting for Copilot ACP response to {method}.")

    def _ensure_session_locked(self, *, timeout_seconds: float) -> str:
        self._start_process_locked()
        if not self._initialized:
            self._request_locked(
                "initialize",
                {
                    "protocolVersion": 1,
                    "clientCapabilities": {
                        "fs": {
                            "readTextFile": True,
                            "writeTextFile": True,
                        }
                    },
                    "clientInfo": {
                        "name": "hermes-agent",
                        "title": "Hermes Agent",
                        "version": "0.0.0",
                    },
                },
                timeout_seconds=timeout_seconds,
            )
            self._initialized = True
        if not self._session_id:
            session = self._request_locked(
                "session/new",
                {
                    "cwd": self._acp_cwd,
                    "mcpServers": [],
                },
                timeout_seconds=timeout_seconds,
            ) or {}
            session_id = str(session.get("sessionId") or "").strip()
            if not session_id:
                raise RuntimeError("Copilot ACP did not return a sessionId.")
            self._session_id = session_id
        return self._session_id

    def _switch_model_locked(self, *, model: str | None, reasoning_effort: str | None, timeout_seconds: float) -> None:
        if not model:
            return
        session_id = self._ensure_session_locked(timeout_seconds=timeout_seconds)
        if self._session_model == model:
            return
        params: dict[str, Any] = {
            "sessionId": session_id,
            "modelId": model,
        }
        if reasoning_effort:
            params["reasoningEffort"] = reasoning_effort
        try:
            self._request_locked("session.model.switchTo", params, timeout_seconds=timeout_seconds)
            self._session_model = model
        except RuntimeError as exc:
            if 'Method not found' not in str(exc):
                raise
            self._session_model = None

    def _run_prompt(
        self,
        prompt_text: str,
        *,
        timeout_seconds: float,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> tuple[str, str]:
        session_id = self._ensure_session_locked(timeout_seconds=timeout_seconds)
        self._switch_model_locked(
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
        )
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        self._request_locked(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [
                    {
                        "type": "text",
                        "text": prompt_text,
                    }
                ],
            },
            timeout_seconds=timeout_seconds,
            text_parts=text_parts,
            reasoning_parts=reasoning_parts,
        )
        return "".join(text_parts), "".join(reasoning_parts)

    def _handle_server_message(
        self,
        msg: dict[str, Any],
        *,
        process: subprocess.Popen[str],
        cwd: str,
        text_parts: list[str] | None,
        reasoning_parts: list[str] | None,
    ) -> bool:
        method = msg.get("method")
        if not isinstance(method, str):
            return False

        if method == "session/update":
            params = msg.get("params") or {}
            update = params.get("update") or {}
            kind = str(update.get("sessionUpdate") or "").strip()
            content = update.get("content") or {}
            chunk_text = ""
            if isinstance(content, dict):
                chunk_text = str(content.get("text") or "")
            if kind == "agent_message_chunk" and chunk_text and text_parts is not None:
                text_parts.append(chunk_text)
            elif kind == "agent_thought_chunk" and chunk_text and reasoning_parts is not None:
                reasoning_parts.append(chunk_text)
            return True

        if process.stdin is None:
            return True

        message_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "session/request_permission":
            response = {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "outcome": {
                        "outcome": "allow_once",
                    }
                },
            }
        elif method == "fs/read_text_file":
            try:
                path = _ensure_path_within_cwd(str(params.get("path") or ""), cwd)
                content = path.read_text() if path.exists() else ""
                line = params.get("line")
                limit = params.get("limit")
                if isinstance(line, int) and line > 1:
                    lines = content.splitlines(keepends=True)
                    start = line - 1
                    end = start + limit if isinstance(limit, int) and limit > 0 else None
                    content = "".join(lines[start:end])
                response = {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "content": content,
                    },
                }
            except Exception as exc:
                response = _jsonrpc_error(message_id, -32602, str(exc))
        elif method == "fs/write_text_file":
            try:
                path = _ensure_path_within_cwd(str(params.get("path") or ""), cwd)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(params.get("content") or ""))
                response = {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": None,
                }
            except Exception as exc:
                response = _jsonrpc_error(message_id, -32602, str(exc))
        else:
            response = _jsonrpc_error(
                message_id,
                -32601,
                f"ACP client method '{method}' is not supported by Hermes yet.",
            )

        process.stdin.write(json.dumps(response) + "\n")
        process.stdin.flush()
        return True
