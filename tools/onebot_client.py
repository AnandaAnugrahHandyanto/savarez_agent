"""Shared OneBot v11 HTTP client for QQ integrations.

Several Hermes tools talk to a running OneBot v11 implementation
(NapCat / Lagrange.Core): the ``qzone`` tool borrows the logged-in QQ
session to publish 说说, and the ``qq_voice`` tool sends synthesized
speech as a native QQ voice message. Both need the same HTTP plumbing,
so it lives here in one place rather than being duplicated per tool.

Configuration (environment variables):
- ``ONEBOT_HTTP_URL``     -- base URL of the OneBot HTTP API, e.g.
                             ``http://127.0.0.1:3000`` (required).
- ``ONEBOT_ACCESS_TOKEN`` -- optional bearer token, if the OneBot HTTP
                             server has ``access-token`` configured.

This is a plain helper module — it registers no tools, so the registry's
module scan never imports it as a tool. Tools import the functions here.
"""

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# Default per-request timeout (seconds). Callers that do heavier work
# (e.g. uploading media) may pass a larger value.
ONEBOT_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def onebot_base_url() -> str:
    """Return the configured OneBot HTTP base URL (no trailing slash)."""
    return os.getenv("ONEBOT_HTTP_URL", "").strip().rstrip("/")


def onebot_access_token() -> str:
    """Return the optional OneBot HTTP access token."""
    return os.getenv("ONEBOT_ACCESS_TOKEN", "").strip()


def onebot_configured() -> bool:
    """Return True when an OneBot HTTP URL is configured.

    Used as the ``check_fn`` for OneBot-backed tools so they are gated out
    of the model's schema entirely when no OneBot connection is set up.
    """
    return bool(onebot_base_url())


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

def onebot_call(
    action: str,
    params: dict | None = None,
    *,
    timeout: int = ONEBOT_TIMEOUT,
) -> dict:
    """Invoke a OneBot v11 HTTP action and return its ``data`` object.

    Raises ``RuntimeError`` on transport errors, a ``failed`` status, or a
    missing ``data`` field so callers can surface one clear message to the
    model instead of leaking a stack trace.
    """
    base = onebot_base_url()
    if not base:
        raise RuntimeError("ONEBOT_HTTP_URL is not configured.")

    url = f"{base}/{action}"
    body = json.dumps(params or {}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = onebot_access_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:  # noqa: BLE001 — best-effort detail only
            pass
        raise RuntimeError(
            f"OneBot HTTP {e.code} for action '{action}'. {detail}".strip()
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach OneBot at {base} — is NapCat/Lagrange running? ({e.reason})"
        ) from e

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"OneBot action '{action}' returned non-JSON: {raw[:200]}"
        ) from e

    if payload.get("status") == "failed":
        msg = payload.get("message") or payload.get("wording") or "unknown error"
        raise RuntimeError(
            f"OneBot action '{action}' failed: {msg} "
            f"(retcode={payload.get('retcode')})"
        )

    data = payload.get("data")
    if data is None:
        raise RuntimeError(f"OneBot action '{action}' returned no data.")
    return data
