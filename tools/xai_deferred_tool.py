"""xAI deferred chat completion tool.

Submits a chat request with ``deferred=true`` to xAI's
``POST /v1/chat/completions`` and polls
``GET /v1/chat/deferred-completion/{request_id}`` until the response is ready.

Use case
--------
xAI's deferred mode is designed for **long-running** completions (extended
thinking, large context, multi-agent reasoning) where holding an open HTTP
connection for several minutes is impractical. Submitting deferred decouples
the request lifecycle from the network connection — the client can disconnect,
crash, retry, or yield to other work, and pick up the result whenever it's
ready.

This tool implements the simplest pattern: submit + poll until done or until
``max_wait_seconds`` elapses.

References
----------
- Submit:  POST /v1/chat/completions with body field ``deferred: true``
- Poll:    GET /v1/chat/deferred-completion/{request_id}
           - 202 Accepted = still pending
           - 200 OK + standard chat completion body = ready
- Docs:    https://docs.x.ai/docs/api-reference#chat-deferred-completion
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import httpx

from tools.xai_http import hermes_xai_user_agent


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
DEFAULT_MODEL = "grok-4.3"
DEFAULT_MAX_WAIT_SECONDS = 600        # 10 minutes
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_SUBMIT_TIMEOUT_SECONDS = 30
DEFAULT_POLL_TIMEOUT_SECONDS = 30


def _config_section() -> Dict[str, Any]:
    """Read the ``xai_deferred:`` block from the active Hermes config, if any."""
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
    except Exception:
        return {}
    section = cfg.get("xai_deferred") if isinstance(cfg, dict) else None
    return section if isinstance(section, dict) else {}


def _resolve(name: str, default: Any) -> Any:
    section = _config_section()
    val = section.get(name)
    if val is None or (isinstance(val, str) and not val.strip()):
        return default
    return val


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class XaiDeferredError(RuntimeError):
    """Raised when the deferred completion fails or times out."""


# ---------------------------------------------------------------------------
# Public tool
# ---------------------------------------------------------------------------

def xai_deferred_chat(
    prompt: str,
    *,
    model: Optional[str] = None,
    system: Optional[str] = None,
    max_wait_seconds: Optional[int] = None,
    poll_interval_seconds: Optional[float] = None,
    extra_messages: Optional[List[Dict[str, Any]]] = None,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a chat completion via xAI's deferred mode.

    Parameters
    ----------
    prompt : str
        The user message.
    model : str, optional
        xAI model identifier. Defaults to config ``xai_deferred.model`` then
        ``"grok-4.3"``.
    system : str, optional
        Optional system message prepended to the conversation.
    max_wait_seconds : int, optional
        Total polling budget. Defaults to config ``xai_deferred.max_wait_seconds``
        then 600 (10 minutes).
    poll_interval_seconds : float, optional
        Sleep between polls. Defaults to config ``xai_deferred.poll_interval_seconds``
        then 2.0.
    extra_messages : list of message dicts, optional
        Conversation history to prepend (between system and user).
    extra_body : dict, optional
        Extra fields merged into the submit body (e.g. ``reasoning_effort``,
        ``temperature``). ``deferred: true`` is always set.

    Returns
    -------
    dict
        ``{"request_id": str, "completion": <chat completion dict>, "elapsed_seconds": float}``

    Raises
    ------
    XaiDeferredError
        On HTTP errors at submit, on poll timeout, or if the polling budget
        is exhausted before the request completes.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        raise XaiDeferredError("XAI_API_KEY is not set")

    resolved_model = model or _resolve("model", DEFAULT_MODEL)
    resolved_max_wait = int(max_wait_seconds or _resolve("max_wait_seconds", DEFAULT_MAX_WAIT_SECONDS))
    resolved_poll_interval = float(poll_interval_seconds or _resolve("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS))

    if resolved_max_wait <= 0:
        raise ValueError("max_wait_seconds must be positive")
    if resolved_poll_interval <= 0:
        raise ValueError("poll_interval_seconds must be positive")

    messages: List[Dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    if extra_messages:
        messages.extend(extra_messages)
    messages.append({"role": "user", "content": prompt})

    body: Dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "deferred": True,
    }
    if extra_body:
        for k, v in extra_body.items():
            if k == "deferred":
                # Hard-coded — deferred mode is the entire point of this tool.
                continue
            body[k] = v

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": hermes_xai_user_agent(),
    }

    base_url = DEFAULT_BASE_URL.rstrip("/")
    submit_url = f"{base_url}/chat/completions"

    started = time.monotonic()
    request_id = _submit(submit_url, headers, body)
    completion = _poll(
        base_url=base_url,
        headers=headers,
        request_id=request_id,
        started=started,
        max_wait=resolved_max_wait,
        poll_interval=resolved_poll_interval,
    )
    return {
        "request_id": request_id,
        "completion": completion,
        "elapsed_seconds": time.monotonic() - started,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _submit(url: str, headers: Dict[str, str], body: Dict[str, Any]) -> str:
    """Submit the deferred request and return the ``request_id``."""
    try:
        resp = httpx.post(
            url,
            headers=headers,
            json=body,
            timeout=DEFAULT_SUBMIT_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise XaiDeferredError(f"deferred submit failed: {exc}") from exc

    if resp.status_code >= 400:
        raise XaiDeferredError(
            f"deferred submit returned {resp.status_code}: "
            f"{resp.text[:300]}"
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise XaiDeferredError(
            f"deferred submit returned non-JSON body: {resp.text[:300]}"
        ) from exc

    request_id = payload.get("request_id") if isinstance(payload, dict) else None
    if not request_id or not isinstance(request_id, str):
        raise XaiDeferredError(
            f"deferred submit response missing 'request_id': {payload!r}"
        )
    return request_id


def _poll(
    *,
    base_url: str,
    headers: Dict[str, str],
    request_id: str,
    started: float,
    max_wait: int,
    poll_interval: float,
) -> Dict[str, Any]:
    """Poll until the deferred completion is ready or the budget is exhausted."""
    poll_url = f"{base_url}/chat/deferred-completion/{request_id}"
    while True:
        if time.monotonic() - started > max_wait:
            raise XaiDeferredError(
                f"deferred completion {request_id!r} not ready after "
                f"{max_wait}s — aborting poll"
            )
        try:
            resp = httpx.get(
                poll_url,
                headers=headers,
                timeout=DEFAULT_POLL_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise XaiDeferredError(
                f"deferred poll failed for {request_id!r}: {exc}"
            ) from exc

        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError as exc:
                raise XaiDeferredError(
                    f"deferred completion {request_id!r} returned non-JSON: "
                    f"{resp.text[:300]}"
                ) from exc
        if resp.status_code == 202:
            time.sleep(poll_interval)
            continue
        raise XaiDeferredError(
            f"deferred poll for {request_id!r} returned "
            f"{resp.status_code}: {resp.text[:300]}"
        )


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def check_xai_deferred_requirements() -> "tuple[bool, str]":
    """Tool gate: only available when XAI_API_KEY is set."""
    if os.environ.get("XAI_API_KEY", "").strip():
        return True, ""
    return False, "XAI_API_KEY environment variable is not set"


XAI_DEFERRED_SCHEMA = {
    "name": "xai_deferred_chat",
    "description": (
        "Run a long-running chat completion against xAI in deferred mode "
        "(submit + poll). Use for extended-thinking / large-context calls "
        "that would exceed normal HTTP timeouts. The tool blocks the caller "
        "until the response is ready or until max_wait_seconds elapses."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The user message to send.",
            },
            "model": {
                "type": "string",
                "description": (
                    "xAI model identifier (e.g. 'grok-4.3'). Defaults to "
                    "config xai_deferred.model or 'grok-4.3'."
                ),
            },
            "system": {
                "type": "string",
                "description": "Optional system prompt prepended to the conversation.",
            },
            "max_wait_seconds": {
                "type": "integer",
                "description": (
                    "Total polling budget in seconds. Defaults to config "
                    "xai_deferred.max_wait_seconds or 600 (10 minutes)."
                ),
            },
            "poll_interval_seconds": {
                "type": "number",
                "description": (
                    "Sleep between polls in seconds. Defaults to config "
                    "xai_deferred.poll_interval_seconds or 2.0."
                ),
            },
        },
        "required": ["prompt"],
    },
}


def _handle_xai_deferred_tool_call(args: Dict[str, Any], **_kw: Any) -> Dict[str, Any]:
    """Bridge from the registry handler signature to xai_deferred_chat()."""
    return xai_deferred_chat(
        prompt=args.get("prompt", ""),
        model=args.get("model"),
        system=args.get("system"),
        max_wait_seconds=args.get("max_wait_seconds"),
        poll_interval_seconds=args.get("poll_interval_seconds"),
    )


# Self-register at import time. The ``registry`` symbol must come from
# ``tools.registry`` (the ToolRegistry singleton), not the module itself —
# tools/registry.py:_is_registry_register_call also matches the literal name.
from tools.registry import registry  # noqa: E402

registry.register(
    name="xai_deferred_chat",
    toolset="xai_deferred",
    schema=XAI_DEFERRED_SCHEMA,
    handler=_handle_xai_deferred_tool_call,
    check_fn=check_xai_deferred_requirements,
    emoji="⏳",
)
