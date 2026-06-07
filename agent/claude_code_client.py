"""OpenAI-compatible facade backed by the installed Claude Code CLI."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.copilot_acp_client import (
    _extract_tool_calls_from_text,
    _format_messages_as_prompt,
)

CLAUDE_CODE_MARKER_BASE_URL = "claude-code://cli"
_DEFAULT_TIMEOUT_SECONDS = 600


def _resolve_command() -> str:
    return (
        os.getenv("HERMES_CLAUDE_CODE_COMMAND", "").strip()
        or os.getenv("CLAUDE_CODE_CLI_PATH", "").strip()
        or "claude"
    )


def _resolve_args() -> list[str]:
    raw = os.getenv("HERMES_CLAUDE_CODE_ARGS", "").strip()
    if raw:
        import shlex

        return shlex.split(raw)
    return [
        "--print",
        "--output-format",
        "json",
        "--tools",
        "",
        "--permission-mode",
        "dontAsk",
        "--no-session-persistence",
    ]


def _build_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    if not env.get("HOME"):
        hermes_home = env.get("HERMES_HOME")
        profile_home = Path(hermes_home) / "home" if hermes_home else None
        env["HOME"] = str(profile_home) if profile_home and profile_home.exists() else str(Path.home())
    return env


def _usage_from_claude_payload(payload: dict[str, Any]) -> SimpleNamespace:
    raw_usage = payload.get("usage")
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens") or 0)
    return SimpleNamespace(
        prompt_tokens=input_tokens + cache_read + cache_creation,
        completion_tokens=output_tokens,
        total_tokens=input_tokens + cache_read + cache_creation + output_tokens,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cache_read),
    )


class _ClaudeCodeChatCompletions:
    def __init__(self, client: "ClaudeCodeClient"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _ClaudeCodeChatNamespace:
    def __init__(self, client: "ClaudeCodeClient"):
        self.completions = _ClaudeCodeChatCompletions(client)


class ClaudeCodeClient:
    """Minimal OpenAI-client-compatible facade for Claude Code print mode."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        acp_command: str | None = None,
        acp_args: list[str] | None = None,
        acp_cwd: str | None = None,
        **_: Any,
    ):
        self.api_key = api_key or "claude-code-cli"
        self.base_url = base_url or CLAUDE_CODE_MARKER_BASE_URL
        self._default_headers = dict(default_headers or {})
        self._command = command or acp_command or _resolve_command()
        self._args = list(args or acp_args or _resolve_args())
        self._cwd = str(Path(acp_cwd or os.getcwd()).resolve())
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

        payload = self._run_prompt(prompt_text, model=model, timeout_seconds=effective_timeout)
        response_text = str(payload.get("result") or "").strip()
        tool_calls, cleaned_text = _extract_tool_calls_from_text(response_text)
        usage = _usage_from_claude_payload(payload)
        assistant_message = SimpleNamespace(
            content=cleaned_text,
            tool_calls=tool_calls,
            reasoning=None,
            reasoning_content=None,
            reasoning_details=None,
        )
        finish_reason = "tool_calls" if tool_calls else "stop"
        choice = SimpleNamespace(message=assistant_message, finish_reason=finish_reason)
        return SimpleNamespace(
            choices=[choice],
            usage=usage,
            model=model or payload.get("model") or "claude-code",
        )

    def _build_command(self, prompt_text: str, *, model: str | None = None) -> list[str]:
        cmd = [self._command] + list(self._args)
        if model and "--model" not in cmd:
            cmd.extend(["--model", model])
        cmd.append(prompt_text)
        return cmd

    def _run_prompt(self, prompt_text: str, *, model: str | None, timeout_seconds: float) -> dict[str, Any]:
        cmd = self._build_command(prompt_text, model=model)
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self._cwd,
                env=_build_subprocess_env(),
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Could not start Claude Code CLI command '{self._command}'. "
                "Install Claude Code or set HERMES_CLAUDE_CODE_COMMAND/CLAUDE_CODE_CLI_PATH."
            ) from exc

        self.is_closed = False
        with self._active_process_lock:
            self._active_process = proc

        stdout_parts: list[str] = []
        stderr_tail: deque[str] = deque(maxlen=40)
        stdout_queue: queue.Queue[str] = queue.Queue()
        stderr_queue: queue.Queue[str] = queue.Queue()

        def _read_stdout() -> None:
            if proc.stdout is None:
                return
            stdout_queue.put(proc.stdout.read())

        def _read_stderr() -> None:
            if proc.stderr is None:
                return
            for line in proc.stderr:
                stderr_queue.put(line.rstrip("\n"))

        out_thread = threading.Thread(target=_read_stdout, daemon=True)
        err_thread = threading.Thread(target=_read_stderr, daemon=True)
        out_thread.start()
        err_thread.start()

        deadline = time.monotonic() + timeout_seconds
        while proc.poll() is None and time.monotonic() < deadline:
            try:
                stdout_parts.append(stdout_queue.get_nowait())
            except queue.Empty:
                pass
            try:
                while True:
                    stderr_tail.append(stderr_queue.get_nowait())
            except queue.Empty:
                pass
            time.sleep(0.05)

        if proc.poll() is None:
            proc.kill()
            raise RuntimeError(f"Claude Code CLI timed out after {timeout_seconds:.0f}s.")

        try:
            stdout_parts.append(stdout_queue.get(timeout=0.2))
        except queue.Empty:
            pass
        try:
            while True:
                stderr_tail.append(stderr_queue.get_nowait())
        except queue.Empty:
            pass

        with self._active_process_lock:
            if self._active_process is proc:
                self._active_process = None

        stdout = "".join(stdout_parts).strip()
        stderr = "\n".join(stderr_tail).strip()
        if proc.returncode != 0:
            detail = stderr or stdout or f"exit code {proc.returncode}"
            raise RuntimeError(f"Claude Code CLI failed: {detail}")
        try:
            payload = json.loads(stdout)
        except Exception as exc:
            raise RuntimeError(f"Claude Code CLI returned non-JSON output: {stdout[:500]}") from exc
        if payload.get("is_error"):
            detail = payload.get("result") or payload.get("api_error_status") or stderr or "unknown error"
            raise RuntimeError(f"Claude Code CLI returned an error: {detail}")
        return payload
