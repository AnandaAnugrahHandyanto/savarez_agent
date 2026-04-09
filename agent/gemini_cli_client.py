"""OpenAI-compatible shim that forwards Hermes requests to local Gemini CLI.

Gemini CLI already handles Google OAuth locally. This adapter invokes it in
headless mode and converts the JSON/text response into the minimal response
shape Hermes expects from an OpenAI chat-completions client.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent.copilot_acp_client import _extract_tool_calls_from_text, _format_messages_as_prompt
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

GEMINI_CLI_MARKER_BASE_URL = "cli://gemini"
_GEMINI_OUTPUT_FORMAT = "json"
_DEFAULT_TIMEOUT_SECONDS = 900.0


def _select_gemini_cli_cwd() -> str:
    override = os.getenv("HERMES_GEMINI_CLI_CWD", "").strip()
    if override:
        return str(Path(override).expanduser().resolve())

    current = Path.cwd().resolve()
    home = Path.home().resolve()
    if current == home:
        sandbox_dir = (get_hermes_home() / "tmp" / "gemini-cli-workspace").resolve()
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Gemini CLI cwd fallback activated: avoiding home directory %s, using %s",
            current,
            sandbox_dir,
        )
        return str(sandbox_dir)

    return str(current)


class _GeminiCLIChatCompletions:
    def __init__(self, client: "GeminiCLIClient"):
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        return self._client._create_chat_completion(**kwargs)


class _GeminiCLIChatNamespace:
    def __init__(self, client: "GeminiCLIClient"):
        self.completions = _GeminiCLIChatCompletions(client)


class GeminiCLIClient:
    """Minimal OpenAI-client-compatible facade for Gemini CLI headless mode."""

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
        **_: Any,
    ):
        self.api_key = api_key or "gemini-cli"
        self.base_url = base_url or GEMINI_CLI_MARKER_BASE_URL
        self._default_headers = dict(default_headers or {})
        self._command = command or acp_command or os.getenv("HERMES_GEMINI_CLI_COMMAND", "").strip() or os.getenv("GEMINI_CLI_PATH", "").strip() or "gemini"
        provided_args = args if args is not None else acp_args
        if provided_args is not None:
            self._args = list(provided_args)
        else:
            raw_args = os.getenv("HERMES_GEMINI_CLI_ARGS", "").strip()
            self._args = shlex.split(raw_args) if raw_args else []
        self._cwd = _select_gemini_cli_cwd()
        self.chat = _GeminiCLIChatNamespace(self)
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
        **_: Any,
    ) -> Any:
        prompt_text = _format_messages_as_prompt(
            messages or [],
            model=model,
            tools=tools,
            tool_choice=tool_choice,
        )
        response_text, reasoning_text = self._run_prompt(
            prompt_text,
            model=model,
            timeout_seconds=float(timeout or _DEFAULT_TIMEOUT_SECONDS),
        )
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
        return SimpleNamespace(choices=[choice], usage=usage, model=model or "gemini-cli")

    def _run_prompt(self, prompt_text: str, *, model: str | None, timeout_seconds: float) -> tuple[str, str]:
        command = [self._command, "--output-format", _GEMINI_OUTPUT_FORMAT]
        if model:
            command.extend(["--model", model])
        if self._args:
            command.extend(self._args)
        try:
            completed = subprocess.run(
                command,
                input=prompt_text,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=self._cwd,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Could not start Gemini CLI command '{self._command}'. "
                "Install Gemini CLI or set HERMES_GEMINI_CLI_COMMAND/GEMINI_CLI_PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"Timed out waiting for Gemini CLI after {int(timeout_seconds)}s.") from exc

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            detail = stderr or stdout or f"exit code {completed.returncode}"
            raise RuntimeError(f"Gemini CLI failed: {detail}")

        payload: dict[str, Any] | None = None
        if stdout:
            try:
                payload = json.loads(stdout)
            except Exception:
                payload = None

        if isinstance(payload, dict):
            response_text = str(payload.get("response") or "")
            reasoning_text = str(payload.get("reasoning") or payload.get("thought") or "")
            return response_text, reasoning_text

        return stdout, ""
