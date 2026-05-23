"""OpenAI-client shim that routes auxiliary LLM calls through the Cursor SDK.

When the main provider is ``cursor`` (``cursor://sdk`` / ``cursor_sdk_runtime``),
auxiliary tasks (kanban specify/decompose, title generation, compression, etc.)
must not use an OpenAI HTTP client — that URL is not a real endpoint and fails
with ``APIConnectionError``.  This module exposes ``client.chat.completions.create()``
via ``Agent.prompt()`` instead.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from types import SimpleNamespace
from typing import Any, Optional

logger = logging.getLogger(__name__)

CURSOR_AUX_BASE_URL = "cursor://sdk"
_DEFAULT_AUX_TIMEOUT = 120.0

_sdk_client: Any = None
_sdk_client_lock = threading.Lock()


def _aux_cursor_cwd() -> str:
    env = os.environ.get("HERMES_CURSOR_AUX_CWD", "").strip()
    if env:
        return env
    try:
        cwd = os.getcwd()
        if cwd:
            return cwd
    except Exception:
        pass
    try:
        from hermes_cli.config import get_hermes_home

        return str(get_hermes_home())
    except Exception:
        return os.path.expanduser("~")


def get_cursor_sdk_client(*, cwd: Optional[str] = None) -> Any:
    """Return a process-cached Cursor SDK ``Client`` (bridge launched if needed)."""
    global _sdk_client
    with _sdk_client_lock:
        if _sdk_client is not None:
            return _sdk_client

        from agent.transports.cursor_sdk_session import (
            _bridge_launch_needs_workaround,
            _launch_bridge_threaded,
            preflight_cursor_sdk,
        )

        preflight_cursor_sdk()
        workspace = cwd or _aux_cursor_cwd()

        bridge_url = os.environ.get("CURSOR_SDK_BRIDGE_URL", "").strip()
        bridge_token = (
            os.environ.get("CURSOR_SDK_BRIDGE_TOKEN")
            or os.environ.get("CURSOR_SDK_BRIDGE_AUTH_TOKEN")
            or ""
        ).strip()
        from cursor_sdk import Client

        if bridge_url and bridge_token:
            _sdk_client = Client(
                base_url=bridge_url,
                auth_token=bridge_token,
                allow_api_key_env_fallback=True,
            )
            return _sdk_client

        if _bridge_launch_needs_workaround():
            bridge, _process = _launch_bridge_threaded(workspace)
            _sdk_client = Client(bridge.endpoint, allow_api_key_env_fallback=True)
            return _sdk_client

        from cursor_sdk._client import Client as SdkClient

        _sdk_client = SdkClient.launch_bridge(
            workspace=workspace,
            allow_api_key_env_fallback=True,
        )
        return _sdk_client


def _messages_to_prompt(messages: list) -> str:
    """Flatten chat messages into a single user prompt for ``Agent.prompt``."""
    parts: list[str] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "user").strip().lower()
        content = msg.get("content", "")
        if isinstance(content, list):
            text_bits: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text") or "").strip()
                    if text:
                        text_bits.append(text)
            content = "\n".join(text_bits)
        else:
            content = str(content or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"[Assistant]\n{content}")
        else:
            parts.append(content)
    return "\n\n".join(parts).strip()


def _run_result_to_openai_response(result: Any, *, model: str) -> Any:
    status = str(getattr(result, "status", "") or "")
    text = str(getattr(result, "result", "") or "")
    if status == "error":
        raise RuntimeError(text or "Cursor SDK run failed")
    assistant_message = SimpleNamespace(content=text, tool_calls=None, reasoning=None)
    choice = SimpleNamespace(
        index=0,
        message=assistant_message,
        finish_reason="stop",
    )
    return SimpleNamespace(choices=[choice], model=model, usage=None)


def _cursor_api_key(explicit: Optional[str] = None) -> str:
    """Resolve CURSOR_API_KEY for auxiliary calls.

    Long-lived gateway/dashboard processes may have an empty
    ``os.environ["CURSOR_API_KEY"]`` placeholder that blocks
    :func:`hermes_cli.config.get_env_value` from reading ``~/.hermes/.env``.
    Read the on-disk .env directly when the live env var is blank.
    """
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    env_val = os.environ.get("CURSOR_API_KEY", "")
    if env_val and env_val.strip():
        return env_val.strip()
    try:
        from hermes_cli.config import load_env

        file_val = (load_env().get("CURSOR_API_KEY") or "").strip()
        if file_val:
            return file_val
    except Exception:
        pass
    try:
        from hermes_cli.auth import resolve_api_key_provider_credentials

        creds = resolve_api_key_provider_credentials("cursor")
        return str(creds.get("api_key") or "").strip()
    except Exception:
        return ""


def reset_cursor_sdk_client() -> None:
    """Drop the process-global Cursor SDK client (bridge + HTTP pool)."""
    global _sdk_client
    with _sdk_client_lock:
        if _sdk_client is None:
            return
        try:
            close_fn = getattr(_sdk_client, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:
            pass
        _sdk_client = None


def prepare_cursor_auxiliary_credentials() -> None:
    """Reload Cursor credentials and reset SDK state before an auxiliary call.

    ``hermes kanban specify`` from the CLI starts a fresh process that loads
    ``~/.hermes/.env`` on startup. The dashboard is long-lived: without this
    refresh it can keep a stale API key, an empty env placeholder, or a dead
    bridge — surfacing as ``AuthenticationError`` / unauthorized while the
    CLI still works.
    """
    try:
        from hermes_cli.config import get_hermes_home, invalidate_env_cache
        from hermes_cli.env_loader import load_hermes_dotenv

        load_hermes_dotenv(hermes_home=get_hermes_home())
        invalidate_env_cache()
    except Exception:
        pass
    reset_cursor_sdk_client()
    try:
        from agent import auxiliary_client as aux

        evict_cached_auxiliary_clients = aux.evict_cached_auxiliary_clients
        evict_cached_auxiliary_clients(
            lambda client: type(client).__name__ == "CursorAuxiliaryClient"
        )
    except Exception:
        pass


class _CursorCompletionsAdapter:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        cwd: Optional[str] = None,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._cwd = cwd or _aux_cursor_cwd()

    def create(self, **kwargs: Any) -> Any:
        from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions
        from agent.transports.cursor_sdk_session import build_cursor_model_selection

        messages = kwargs.get("messages") or []
        model = str(kwargs.get("model") or self._model or "composer-2.5")
        timeout = float(kwargs.get("timeout") or _DEFAULT_AUX_TIMEOUT)
        prompt = _messages_to_prompt(messages)
        if not prompt:
            raise ValueError("Cursor auxiliary call requires at least one message")

        api_key = _cursor_api_key(self._api_key)
        if not api_key:
            raise CursorAgentError(
                "CURSOR_API_KEY is not set. Add it to ~/.hermes/.env or export it.",
                is_retryable=False,
            )
        # Keep the live env in sync so cursor-sdk bridge fallback matches AgentOptions.
        os.environ["CURSOR_API_KEY"] = api_key

        selection = build_cursor_model_selection(model)
        options = AgentOptions(
            model=selection,
            api_key=api_key,
            local=LocalAgentOptions(cwd=self._cwd, setting_sources=[]),
        )
        client = get_cursor_sdk_client(cwd=self._cwd)

        def _prompt() -> Any:
            return Agent.prompt(prompt, options, client=client)

        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cursor-aux")
        future = pool.submit(_prompt)
        try:
            result = future.result(timeout=max(1.0, timeout))
        except FuturesTimeoutError as exc:
            raise TimeoutError(
                f"Cursor SDK auxiliary call timed out after {int(timeout)}s"
            ) from exc
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        return _run_result_to_openai_response(result, model=model)


class _CursorChatShim:
    def __init__(self, adapter: _CursorCompletionsAdapter) -> None:
        self.completions = adapter


class CursorAuxiliaryClient:
    """OpenAI-compatible wrapper over ``Agent.prompt`` for side tasks."""

    def __init__(self, *, model: str, api_key: str = "", cwd: Optional[str] = None) -> None:
        self._model = model
        adapter = _CursorCompletionsAdapter(model=model, api_key=api_key, cwd=cwd)
        self.chat = _CursorChatShim(adapter)
        self.api_key = api_key or _cursor_api_key()
        self.base_url = CURSOR_AUX_BASE_URL
        self._real_client = None


class _AsyncCursorCompletionsAdapter:
    def __init__(self, sync_adapter: _CursorCompletionsAdapter) -> None:
        self._sync = sync_adapter

    async def create(self, **kwargs: Any) -> Any:
        import asyncio

        return await asyncio.to_thread(self._sync.create, **kwargs)


class _AsyncCursorChatShim:
    def __init__(self, adapter: _AsyncCursorCompletionsAdapter) -> None:
        self.completions = adapter


class AsyncCursorAuxiliaryClient:
    def __init__(self, sync_wrapper: CursorAuxiliaryClient) -> None:
        sync_adapter = sync_wrapper.chat.completions
        self.chat = _AsyncCursorChatShim(_AsyncCursorCompletionsAdapter(sync_adapter))
        self.api_key = sync_wrapper.api_key
        self.base_url = sync_wrapper.base_url
        self._real_client = sync_wrapper._real_client


def build_cursor_auxiliary_client(
    model: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
) -> tuple[Optional[CursorAuxiliaryClient], Optional[str]]:
    """Build a Cursor SDK auxiliary client when ``CURSOR_API_KEY`` is available."""
    resolved_model = (model or "").strip() or "composer-2.5"
    key = _cursor_api_key(api_key)
    if not key:
        logger.warning(
            "Auxiliary client: cursor requested but CURSOR_API_KEY is not set"
        )
        return None, None
    logger.debug("Auxiliary client: Cursor SDK (%s)", resolved_model)
    return CursorAuxiliaryClient(model=resolved_model, api_key=key), resolved_model
