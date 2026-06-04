"""Persistent variant of the Copilot ACP shim.

The default :class:`agent.copilot_acp_client.CopilotACPClient` spawns a fresh
``copilot --acp`` subprocess for every ``chat.completions.create`` call. That
is correct and safe, but it loses the protocol-level affordances ACP is
designed for — session reuse, mid-prompt cancel via ``session/cancel``, and
process-level reconnection across calls.

This module adds a sibling client that keeps one subprocess and one ACP
session alive across multiple completions, while preserving the same
permission/safety behaviour as the one-shot client. It is **opt-in only**:
nothing in Hermes wires it in by default. Provenance: design phase 4 in
``spearhead-execution/20260529-acpx-interop-spike/acp-acpx-interop-design.md``.

Lifecycle contract:

* ``ensure_started()`` — boot the subprocess, send ``initialize`` and
  ``session/new``, cache the session id. Idempotent.
* ``chat.completions.create(...)`` — send ``session/prompt`` against the cached
  session id, gather streamed chunks, return an OpenAI-compatible response.
* ``cancel()`` — send ``session/cancel`` for the live session. The next prompt
  will see ``stop_reason="cancelled"`` once the agent honours it.
* ``close()`` — terminate the subprocess and clear cached session state.

Safety inherits from the one-shot client:

* ``session/request_permission`` answers ``cancelled`` (deny default).
* ``fs/read_text_file`` and ``fs/write_text_file`` reuse the workspace-bound
  path check and the existing read/write denylists.
* No credential is read from the parent process beyond ``HOME`` resolution
  (mirrors the one-shot client). No env keys are forwarded to the child
  beyond what ``os.environ`` already contains.

The class is intentionally a standalone composition rather than a subclass of
``CopilotACPClient`` because the one-shot lifecycle and the persistent one
diverge on subprocess ownership, and mixing them via inheritance hides the
divergence. The safety helpers (``_handle_server_message`` semantics) are
reproduced here so both clients can evolve independently.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.copilot_acp_client import (
    ACP_MARKER_BASE_URL,
    _build_subprocess_env,
    _extract_tool_calls_from_text,
    _format_messages_as_prompt,
    _is_gh_copilot_deprecation_message,
    _jsonrpc_error,
    _permission_denied,
    _resolve_args,
    _resolve_command,
)
from agent.file_safety import get_read_block_error, is_write_denied
from agent.redact import redact_sensitive_text

_DEFAULT_TIMEOUT_SECONDS = 900.0
_BOOTSTRAP_TIMEOUT_SECONDS = 60.0


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


class _PersistentChatCompletions:
    def __init__(self, client: "PersistentCopilotACPClient"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _PersistentChatNamespace:
    def __init__(self, client: "PersistentCopilotACPClient"):
        self.completions = _PersistentChatCompletions(client)


class PersistentCopilotACPClient:
    """Opt-in Copilot ACP client with a long-lived subprocess and session.

    Public surface (``chat.completions.create``, ``close``) matches the
    one-shot :class:`CopilotACPClient` so callers can swap one for the other
    without rewiring. ``ensure_started`` and ``cancel`` are additional
    affordances that only make sense in the persistent variant.
    """

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
        bootstrap_timeout: float = _BOOTSTRAP_TIMEOUT_SECONDS,
        # _subprocess_factory exists so tests can inject a stub process
        # without monkey-patching subprocess.Popen on a module global. The
        # production path always uses subprocess.Popen via the default.
        _subprocess_factory: Any = None,
        **_: Any,
    ) -> None:
        self.api_key = api_key or "copilot-acp"
        self.base_url = base_url or ACP_MARKER_BASE_URL
        self._default_headers = dict(default_headers or {})
        self._acp_command = acp_command or command or _resolve_command()
        self._acp_args = list(acp_args or args or _resolve_args())
        self._acp_cwd = str(Path(acp_cwd or os.getcwd()).resolve())
        self._bootstrap_timeout = float(bootstrap_timeout)
        self._subprocess_factory = _subprocess_factory or subprocess.Popen

        self.chat = _PersistentChatNamespace(self)
        self.is_closed = False

        # Subprocess + reader-thread state. Guarded by _state_lock.
        self._state_lock = threading.Lock()
        self._proc: Any = None
        self._inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr_tail: deque[str] = deque(maxlen=40)
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._session_id: str | None = None
        self._next_id = 0

        # Serializes prompts onto the single subprocess. A future card can
        # relax this if/when the upstream Copilot ACP supports concurrent
        # ``session/prompt`` calls — today it does not.
        self._request_lock = threading.Lock()

    # ── Lifecycle ────────────────────────────────────────────────────

    def ensure_started(self) -> str:
        """Boot subprocess + initialize + session/new if not already live.

        Returns the active ``sessionId``. Idempotent: subsequent calls reuse
        the cached session id without restarting the subprocess.
        """

        with self._state_lock:
            if self._proc is not None and self._proc.poll() is None and self._session_id:
                return self._session_id

            # If we have a dead proc from a previous session, drop it.
            if self._proc is not None and self._proc.poll() is not None:
                self._teardown_locked()

            self._spawn_locked()
            assert self._proc is not None

        # initialize + session/new happen outside _state_lock because they
        # block on inbox reads from the reader thread.
        try:
            self._request(
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
                timeout_seconds=self._bootstrap_timeout,
            )
            session = self._request(
                "session/new",
                {
                    "cwd": self._acp_cwd,
                    "mcpServers": [],
                },
                timeout_seconds=self._bootstrap_timeout,
            ) or {}
        except Exception:
            # Bootstrap failed; surface the error but tear down so the next
            # caller is not stuck talking to a half-initialised process.
            self.close()
            raise

        session_id = str(session.get("sessionId") or "").strip()
        if not session_id:
            self.close()
            raise RuntimeError("Copilot ACP did not return a sessionId.")
        self._session_id = session_id
        return session_id

    def cancel(self) -> None:
        """Send ``session/cancel`` for the active session, if one exists.

        Returns immediately. The agent is expected to honour the notification
        and let the in-flight ``session/prompt`` complete with whatever
        partial output it has produced. The kanban worker translates that
        into a structured stop reason.
        """

        with self._state_lock:
            proc = self._proc
            session_id = self._session_id
            if proc is None or proc.poll() is not None or proc.stdin is None or not session_id:
                return
            # ACP `session/cancel` is a notification (no id, no response).
            payload = {
                "jsonrpc": "2.0",
                "method": "session/cancel",
                "params": {"sessionId": session_id},
            }
            try:
                proc.stdin.write(json.dumps(payload) + "\n")
                proc.stdin.flush()
            except Exception:
                # If the pipe is broken the next prompt will rediscover the
                # dead process and reboot. No need to surface here.
                pass

    def close(self) -> None:
        with self._state_lock:
            self._teardown_locked()
        self.is_closed = True

    def __enter__(self) -> "PersistentCopilotACPClient":
        self.ensure_started()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ── OpenAI-compatible surface ────────────────────────────────────

    def _create_chat_completion(
        self,
        *,
        model: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        **_: Any,
    ) -> Any:
        prompt_text = _format_messages_as_prompt(
            messages or [],
            model=model,
            tools=tools,
            tool_choice=tool_choice,
        )

        if timeout is None:
            effective_timeout = _DEFAULT_TIMEOUT_SECONDS
        elif isinstance(timeout, (int, float)):
            effective_timeout = float(timeout)
        else:
            candidates = [
                getattr(timeout, attr, None)
                for attr in ("read", "write", "connect", "pool", "timeout")
            ]
            numeric = [float(v) for v in candidates if isinstance(v, (int, float))]
            effective_timeout = max(numeric) if numeric else _DEFAULT_TIMEOUT_SECONDS

        # Only one in-flight prompt per persistent session; this matches the
        # upstream Copilot ACP server semantics.
        with self._request_lock:
            session_id = self.ensure_started()

            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            self._request(
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
                text_parts=text_parts,
                reasoning_parts=reasoning_parts,
                timeout_seconds=effective_timeout,
            )

            response_text = "".join(text_parts)
            reasoning_text = "".join(reasoning_parts)

        tool_calls, cleaned_text = _extract_tool_calls_from_text(response_text)

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
            model=model or "copilot-acp",
        )

    # ── Subprocess plumbing ──────────────────────────────────────────

    def _spawn_locked(self) -> None:
        """Boot the subprocess and start reader threads. Caller holds _state_lock."""

        try:
            proc = self._subprocess_factory(
                [self._acp_command] + self._acp_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=self._acp_cwd,
                env=_build_subprocess_env(),
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Could not start Copilot ACP command '{self._acp_command}'. "
                "Install GitHub Copilot CLI or set HERMES_COPILOT_ACP_COMMAND/COPILOT_CLI_PATH."
            ) from exc

        if proc.stdin is None or proc.stdout is None:
            try:
                proc.kill()
            except Exception:
                pass
            raise RuntimeError("Copilot ACP process did not expose stdin/stdout pipes.")

        self._proc = proc
        self.is_closed = False
        self._inbox = queue.Queue()
        self._stderr_tail = deque(maxlen=40)
        self._next_id = 0
        self._session_id = None

        def _stdout_reader(stream: Any, inbox: queue.Queue[dict[str, Any]]) -> None:
            for line in stream:
                try:
                    inbox.put(json.loads(line))
                except Exception:
                    inbox.put({"raw": line.rstrip("\n")})

        def _stderr_reader(stream: Any, tail: deque[str]) -> None:
            for line in stream:
                tail.append(line.rstrip("\n"))

        self._stdout_thread = threading.Thread(
            target=_stdout_reader, args=(proc.stdout, self._inbox), daemon=True
        )
        self._stderr_thread = threading.Thread(
            target=_stderr_reader, args=(proc.stderr, self._stderr_tail), daemon=True
        )
        self._stdout_thread.start()
        if proc.stderr is not None:
            self._stderr_thread.start()

    def _teardown_locked(self) -> None:
        """Best-effort terminate. Caller holds _state_lock."""

        proc = self._proc
        self._proc = None
        self._session_id = None
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

    def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        text_parts: list[str] | None = None,
        reasoning_parts: list[str] | None = None,
        timeout_seconds: float,
    ) -> Any:
        """Send a JSON-RPC request and block on its response or a timeout."""

        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise RuntimeError("Copilot ACP process is not running.")

        self._next_id += 1
        request_id = self._next_id
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        try:
            proc.stdin.write(json.dumps(payload) + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, ValueError) as exc:
            raise RuntimeError(f"Copilot ACP stdin closed before {method}.") from exc

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            try:
                msg = self._inbox.get(timeout=0.1)
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
                raise RuntimeError(
                    f"Copilot ACP {method} failed: {err.get('message') or err}"
                )
            return msg.get("result")

        stderr_text = "\n".join(self._stderr_tail).strip()
        if proc.poll() is not None and stderr_text:
            if _is_gh_copilot_deprecation_message(stderr_text):
                raise RuntimeError(
                    "Hermes ACP mode requires the NEW GitHub Copilot CLI "
                    "(github.com/github/copilot-cli), but the binary it just "
                    "spawned is the deprecated `gh copilot` extension.\n\n"
                    "Install the new CLI:\n"
                    "  npm install -g @github/copilot\n"
                    "  # then verify with: copilot --help\n\n"
                    "If `copilot` already resolves to the new CLI but you still see this,\n"
                    "point Hermes at it explicitly:\n"
                    "  export HERMES_COPILOT_ACP_COMMAND=/path/to/new/copilot\n\n"
                    "Alternative: use the `copilot` provider (no ACP, hits the Copilot API\n"
                    "directly with a Copilot subscription token) via `hermes setup`.\n\n"
                    f"Original error:\n{stderr_text}"
                )
            raise RuntimeError(f"Copilot ACP process exited early: {stderr_text}")
        raise TimeoutError(f"Timed out waiting for Copilot ACP response to {method}.")

    # ── Inbound server-side ACP method handling ──────────────────────

    def _handle_server_message(
        self,
        msg: dict[str, Any],
        *,
        process: Any,
        cwd: str,
        text_parts: list[str] | None,
        reasoning_parts: list[str] | None,
    ) -> bool:
        """Mirror of :meth:`CopilotACPClient._handle_server_message`.

        The behaviour is deliberately identical: deny-default permissions,
        workspace-bounded fs reads/writes, redaction on read, denylist on
        write. Duplicated rather than inherited so the persistent client can
        evolve permission policy without touching the one-shot client.
        """

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
            response = _permission_denied(message_id)
        elif method == "fs/read_text_file":
            try:
                path = _ensure_path_within_cwd(str(params.get("path") or ""), cwd)
                block_error = get_read_block_error(str(path))
                if block_error:
                    raise PermissionError(block_error)
                try:
                    content = path.read_text()
                except FileNotFoundError:
                    content = ""
                line = params.get("line")
                limit = params.get("limit")
                if isinstance(line, int) and line > 1:
                    lines = content.splitlines(keepends=True)
                    start = line - 1
                    end = start + limit if isinstance(limit, int) and limit > 0 else None
                    content = "".join(lines[start:end])
                if content:
                    content = redact_sensitive_text(content, force=True)
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
                if is_write_denied(str(path)):
                    raise PermissionError(
                        f"Write denied: '{path}' is a protected system/credential file."
                    )
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

        try:
            process.stdin.write(json.dumps(response) + "\n")
            process.stdin.flush()
        except Exception:
            # Pipe died mid-write. The next _request() call will see
            # proc.poll() and reboot via ensure_started.
            pass
        return True
