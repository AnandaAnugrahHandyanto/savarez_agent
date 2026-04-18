"""Shared ACP JSON-RPC transport primitives for Hermes ACP clients.

Both :class:`agent.copilot_acp_client.CopilotACPClient` (one-shot per turn)
and :class:`agent.claude_code_acp_client.ClaudeCodeACPClient` (persistent
session) subclass :class:`_AcpClientBase`. The base owns:

* Subprocess launch / teardown with stderr-tail capture.
* JSON-RPC request-id correlation.
* Server-initiated message dispatch: ``session/update``,
  ``session/request_permission``, ``fs/read_text_file``,
  ``fs/write_text_file``.
* Path-boundary enforcement against the session cwd.

Subclasses override :meth:`_create_chat_completion` to pick their turn
lifecycle, :meth:`_handle_session_update` to consume streaming updates,
and optionally :meth:`_build_session_new_params` to inject
``mcpServers`` / ``systemPrompt`` / similar.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import shlex
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _jsonrpc_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": code, "message": message},
    }


def _ensure_path_within_cwd(path_text: str, cwd: str) -> Path:
    candidate = Path(path_text)
    if not candidate.is_absolute():
        raise PermissionError("ACP file-system paths must be absolute.")
    resolved = candidate.resolve()
    root = Path(cwd).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError(
            f"Path '{resolved}' is outside the session cwd '{root}'."
        ) from exc
    return resolved


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
    *,
    preamble: list[str] | None = None,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    tool_call_instructions: str | None = None,
    closing: str | None = "Continue the conversation from the latest user request.",
) -> str:
    """Flatten an OpenAI-style ``messages`` list into one ACP prompt string."""
    sections: list[str] = list(preamble or [])
    if model:
        sections.append(f"Hermes requested model hint: {model}")

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
            header = tool_call_instructions or (
                "Available tools (OpenAI function schema)."
            )
            sections.append(f"{header}\n{json.dumps(tool_specs, ensure_ascii=False)}")

    if tool_choice is not None:
        sections.append(f"Tool choice hint: {json.dumps(tool_choice, ensure_ascii=False)}")

    transcript: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown").strip().lower()
        if role == "tool":
            role = "tool"
        elif role not in {"system", "user", "assistant"}:
            role = "context"

        content = message.get("content")
        rendered = _render_message_content(content)
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

    if closing:
        sections.append(closing)
    return "\n\n".join(section.strip() for section in sections if section and section.strip())


class _ACPChatCompletions:
    def __init__(self, client: "_AcpClientBase"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _ACPChatNamespace:
    def __init__(self, client: "_AcpClientBase"):
        self.completions = _ACPChatCompletions(client)


class _AcpClientBase:
    """Shared ACP subprocess transport.

    Subclasses set class-level defaults (command, args, env vars, labels) and
    implement :meth:`_create_chat_completion`. Subprocess lifetime is the
    subclass's responsibility: one-shot clients (Copilot) call
    :meth:`_start_subprocess` + :meth:`close` per turn; persistent clients
    (Claude Code) spawn once and reuse across turns.
    """

    _provider_label: str = "acp-base"
    _default_command: str = ""
    _default_args: tuple[str, ...] = ()
    _env_command_vars: tuple[str, ...] = ()
    _env_args_var: str = ""
    _marker_base_url: str = "acp://base"
    _default_timeout_seconds: float = 900.0
    _client_name: str = "hermes-agent"

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
        self.api_key = api_key or self._provider_label
        self.base_url = base_url or self._marker_base_url
        self._default_headers = dict(default_headers or {})
        self._acp_command = acp_command or command or self._resolve_command()
        self._acp_args = list(acp_args or args or self._resolve_args())
        self._acp_cwd = str(Path(acp_cwd or os.getcwd()).resolve())
        self.chat = _ACPChatNamespace(self)
        self.is_closed = False
        self._active_process: subprocess.Popen[str] | None = None
        self._active_process_lock = threading.Lock()
        self._next_request_id = 0

    # ------------------------------------------------------------------
    # Env-driven resolution of the launcher path + args
    # ------------------------------------------------------------------

    def _resolve_command(self) -> str:
        for env_var in self._env_command_vars:
            val = os.getenv(env_var, "").strip()
            if val:
                return val
        return self._default_command

    def _resolve_args(self) -> list[str]:
        if self._env_args_var:
            raw = os.getenv(self._env_args_var, "").strip()
            if raw:
                return shlex.split(raw)
        return list(self._default_args)

    # ------------------------------------------------------------------
    # Subprocess lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
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

    def _start_subprocess(self) -> tuple[subprocess.Popen[str], "queue.Queue[dict[str, Any]]", deque[str]]:
        """Launch the ACP subprocess and start reader threads.

        Returns ``(proc, inbox, stderr_tail)``. The caller owns the process
        lifetime: persistent clients keep the reference; one-shot clients
        terminate via :meth:`close` after the request completes.
        """
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
            envs = "/".join(self._env_command_vars) if self._env_command_vars else "the launcher path"
            raise RuntimeError(
                f"Could not start {self._provider_label} command '{self._acp_command}'. "
                f"Install it or set {envs}."
            ) from exc

        if proc.stdin is None or proc.stdout is None:
            proc.kill()
            raise RuntimeError(f"{self._provider_label} process did not expose stdin/stdout.")

        self.is_closed = False
        with self._active_process_lock:
            self._active_process = proc

        inbox: "queue.Queue[dict[str, Any]]" = queue.Queue()
        stderr_tail: deque[str] = deque(maxlen=40)

        def _stdout_reader() -> None:
            for line in proc.stdout:
                try:
                    inbox.put(json.loads(line))
                except Exception:
                    inbox.put({"raw": line.rstrip("\n")})

        def _stderr_reader() -> None:
            if proc.stderr is None:
                return
            for line in proc.stderr:
                stderr_tail.append(line.rstrip("\n"))

        threading.Thread(target=_stdout_reader, daemon=True).start()
        threading.Thread(target=_stderr_reader, daemon=True).start()
        return proc, inbox, stderr_tail

    # ------------------------------------------------------------------
    # JSON-RPC request/response
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._next_request_id += 1
        return self._next_request_id

    def _request(
        self,
        proc: subprocess.Popen[str],
        inbox: "queue.Queue[dict[str, Any]]",
        stderr_tail: deque[str],
        method: str,
        params: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
        dispatch_ctx: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Send a JSON-RPC request and block for the matching response.

        Server-initiated messages are dispatched to
        :meth:`_handle_server_message` until the response arrives or the
        deadline expires.
        """
        timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else self._default_timeout_seconds
        )
        request_id = self._next_id()
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

            if self._handle_server_message(msg, process=proc, dispatch_ctx=dispatch_ctx or {}):
                continue

            if msg.get("id") != request_id:
                continue
            if "error" in msg:
                err = msg.get("error") or {}
                raise RuntimeError(
                    f"{self._provider_label} {method} failed: {err.get('message') or err}"
                )
            return msg.get("result")

        stderr_text = "\n".join(stderr_tail).strip()
        if proc.poll() is not None and stderr_text:
            raise RuntimeError(f"{self._provider_label} process exited early: {stderr_text}")
        raise TimeoutError(
            f"Timed out waiting for {self._provider_label} response to {method}."
        )

    def _notify(
        self,
        proc: subprocess.Popen[str],
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        try:
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
        except Exception:
            logger.debug("Failed to write notification %s", method, exc_info=True)

    # ------------------------------------------------------------------
    # Server-initiated message dispatch
    # ------------------------------------------------------------------

    def _handle_server_message(
        self,
        msg: dict[str, Any],
        *,
        process: subprocess.Popen[str],
        dispatch_ctx: dict[str, Any],
    ) -> bool:
        """Return True if this message was a server-initiated notification /
        request and was handled here; False if it is a response the caller
        must correlate by id."""
        method = msg.get("method")
        if not isinstance(method, str):
            return False

        if method == "session/update":
            params = msg.get("params") or {}
            update = params.get("update") or {}
            self._handle_session_update(update, dispatch_ctx=dispatch_ctx, params=params)
            return True

        if process.stdin is None:
            return True

        message_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "session/request_permission":
            response = self._handle_permission_request(message_id, params)
        elif method == "fs/read_text_file":
            response = self._handle_fs_read(message_id, params)
        elif method == "fs/write_text_file":
            response = self._handle_fs_write(message_id, params)
        else:
            response = _jsonrpc_error(
                message_id,
                -32601,
                f"ACP client method '{method}' is not supported by Hermes yet.",
            )

        try:
            process.stdin.write(json.dumps(response) + "\n")
            process.stdin.flush()
        except Exception:
            logger.debug("Failed to send response for %s", method, exc_info=True)
        return True

    # ------------------------------------------------------------------
    # Default fs / permission handlers (subclasses can override)
    # ------------------------------------------------------------------

    def _handle_permission_request(self, message_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {"outcome": {"outcome": "allow_once"}},
        }

    def _handle_fs_read(self, message_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        try:
            path = _ensure_path_within_cwd(str(params.get("path") or ""), self._acp_cwd)
            content = path.read_text() if path.exists() else ""
            line = params.get("line")
            limit = params.get("limit")
            if isinstance(line, int) and line > 1:
                lines = content.splitlines(keepends=True)
                start = line - 1
                end = start + limit if isinstance(limit, int) and limit > 0 else None
                content = "".join(lines[start:end])
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"content": content},
            }
        except Exception as exc:
            return _jsonrpc_error(message_id, -32602, str(exc))

    def _handle_fs_write(self, message_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        try:
            path = _ensure_path_within_cwd(str(params.get("path") or ""), self._acp_cwd)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(params.get("content") or ""))
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": None,
            }
        except Exception as exc:
            return _jsonrpc_error(message_id, -32602, str(exc))

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    def _create_chat_completion(self, **kwargs: Any) -> Any:
        """Return an OpenAI-shaped chat completion. Subclass must implement."""
        raise NotImplementedError

    def _handle_session_update(
        self,
        update: dict[str, Any],
        *,
        dispatch_ctx: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Handle a ``session/update`` payload. Default: scrape text + thought chunks
        into ``dispatch_ctx``'s ``text_parts`` / ``reasoning_parts`` lists (if provided)."""
        ctx = dispatch_ctx or {}
        kind = str(update.get("sessionUpdate") or "").strip()
        content = update.get("content") or {}
        chunk_text = ""
        if isinstance(content, dict):
            chunk_text = str(content.get("text") or "")
        if kind == "agent_message_chunk":
            text_parts = ctx.get("text_parts")
            if chunk_text and isinstance(text_parts, list):
                text_parts.append(chunk_text)
        elif kind == "agent_thought_chunk":
            reasoning_parts = ctx.get("reasoning_parts")
            if chunk_text and isinstance(reasoning_parts, list):
                reasoning_parts.append(chunk_text)

    def _build_initialize_params(self) -> dict[str, Any]:
        return {
            "protocolVersion": 1,
            "clientCapabilities": {
                "fs": {"readTextFile": True, "writeTextFile": True},
            },
            "clientInfo": {
                "name": self._client_name,
                "title": "Hermes Agent",
                "version": "0.0.0",
            },
        }

    def _build_session_new_params(self) -> dict[str, Any]:
        return {"cwd": self._acp_cwd, "mcpServers": []}

    # ------------------------------------------------------------------
    # Convenience: one-shot request lifecycle (used by Copilot)
    # ------------------------------------------------------------------

    def _run_one_shot(
        self,
        prompt_text: str,
        *,
        timeout_seconds: float,
        text_parts: list[str],
        reasoning_parts: list[str],
    ) -> None:
        """Launch subprocess, initialize, open a session, send one prompt, close.

        Updates ``text_parts`` / ``reasoning_parts`` in place via the default
        :meth:`_handle_session_update` unless a subclass overrides it.
        """
        proc, inbox, stderr_tail = self._start_subprocess()
        try:
            self._request(
                proc, inbox, stderr_tail,
                "initialize", self._build_initialize_params(),
                timeout_seconds=timeout_seconds,
            )
            session = self._request(
                proc, inbox, stderr_tail,
                "session/new", self._build_session_new_params(),
                timeout_seconds=timeout_seconds,
            ) or {}
            session_id = str(session.get("sessionId") or "").strip()
            if not session_id:
                raise RuntimeError(f"{self._provider_label} did not return a sessionId.")
            self._request(
                proc, inbox, stderr_tail,
                "session/prompt",
                {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": prompt_text}],
                },
                timeout_seconds=timeout_seconds,
                dispatch_ctx={"text_parts": text_parts, "reasoning_parts": reasoning_parts},
            )
        finally:
            self.close()


# ---------------------------------------------------------------------------
# Utilities used by subclasses when normalising httpx.Timeout inputs
# ---------------------------------------------------------------------------

def resolve_effective_timeout(timeout: Any, *, default: float) -> float:
    """Translate run_agent's ``timeout`` kwarg (plain number or httpx.Timeout) to seconds."""
    if timeout is None:
        return default
    if isinstance(timeout, (int, float)):
        return float(timeout)
    candidates = [
        getattr(timeout, attr, None)
        for attr in ("read", "write", "connect", "pool", "timeout")
    ]
    numeric = [float(v) for v in candidates if isinstance(v, (int, float))]
    return max(numeric) if numeric else default
