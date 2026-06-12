"""
Config-driven Slack slash-command HTTP forwarding.

When Socket Mode is enabled on a Slack app, Slack delivers every
manifest-declared slash command over the WebSocket and never calls the
command's HTTP Request URL. Commands owned by an external local service
(e.g. a profile's approval/ops server) would therefore vanish without an
ack ("dispatch_failed" on the user's screen).

A profile can declare forwards in config.yaml::

    slack:
      slash_forwards:
        wpc-order: http://127.0.0.1:8787/slack/commands/order-collect

The gateway acks the slash, re-encodes the payload as
``application/x-www-form-urlencoded``, signs it with the standard Slack v0
scheme using ``SLACK_SIGNING_SECRET`` from the gateway's environment, and
POSTs it to the configured URL — so the receiving service's existing Slack
signature verification keeps working unchanged.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

FORWARD_TIMEOUT_SECONDS = 90.0


def parse_slash_forwards(raw: Any) -> Dict[str, str]:
    """Normalize a ``slash_forwards`` config value to ``{name: url}``.

    Names are stored without the leading slash; entries with an empty name
    or URL are dropped. Non-dict input yields an empty mapping.
    """
    if not isinstance(raw, dict):
        return {}
    forwards: Dict[str, str] = {}
    for name, url in raw.items():
        clean_name = str(name).lstrip("/").strip()
        clean_url = str(url).strip() if url else ""
        if clean_name and clean_url:
            forwards[clean_name] = clean_url
    return forwards


def build_signed_request(
    command: Dict[str, Any],
    signing_secret: str,
    *,
    timestamp: Optional[str] = None,
) -> Tuple[bytes, Dict[str, str]]:
    """Encode a slash payload as a form body with Slack v0 signature headers.

    Only scalar fields are forwarded — that covers every field Slack puts in
    a slash-command payload (command, text, user_id, channel_id, ...).
    """
    ts = timestamp if timestamp is not None else str(int(time.time()))
    fields = {
        key: str(value)
        for key, value in command.items()
        if isinstance(value, (str, int, float, bool))
    }
    body = urllib.parse.urlencode(fields).encode("utf-8")
    base = b"v0:" + ts.encode("utf-8") + b":" + body
    signature = "v0=" + hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": signature,
    }
    return body, headers


def _default_session_factory():
    import aiohttp

    return aiohttp.ClientSession(trust_env=True)


async def forward_slash_command(
    command: Dict[str, Any],
    url: str,
    signing_secret: str,
    *,
    timeout_seconds: float = FORWARD_TIMEOUT_SECONDS,
    session_factory: Optional[Callable[[], Any]] = None,
) -> Dict[str, Any]:
    """Relay a slash payload to ``url`` and report the outcome.

    Returns ``{"ok": True, "payload": <dict>}`` on HTTP 200 (non-JSON bodies
    are wrapped as an ephemeral text payload), otherwise ``{"ok": False,
    "error": <message>}`` with ``status`` set when a response was received.
    """
    if not signing_secret:
        return {"ok": False, "error": "SLACK_SIGNING_SECRET is not configured in the gateway environment"}

    body, headers = build_signed_request(command, signing_secret)
    factory = session_factory or _default_session_factory
    try:
        async with factory() as session:
            kwargs: Dict[str, Any] = {"data": body, "headers": headers}
            if session_factory is None:
                import aiohttp

                kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout_seconds)
            async with session.post(url, **kwargs) as resp:
                status = resp.status
                text = await resp.text()
    except Exception as exc:
        logger.warning("[Slack] slash forward to %s failed: %s", url, exc)
        return {"ok": False, "error": str(exc)}

    if status != 200:
        logger.warning("[Slack] slash forward to %s returned %s: %s", url, status, text[:200])
        return {"ok": False, "status": status, "error": text[:500] or f"HTTP {status}"}

    try:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("non-object JSON")
    except (ValueError, json.JSONDecodeError):
        payload = {"response_type": "ephemeral", "text": text[:1500]}
    return {"ok": True, "status": status, "payload": payload}


async def post_response_url(
    response_url: str,
    payload: Dict[str, Any],
    *,
    session_factory: Optional[Callable[[], Any]] = None,
) -> bool:
    """POST a message payload to a Slack ``response_url``."""
    factory = session_factory or _default_session_factory
    try:
        async with factory() as session:
            kwargs: Dict[str, Any] = {"json": payload}
            if session_factory is None:
                import aiohttp

                kwargs["timeout"] = aiohttp.ClientTimeout(total=15.0)
            async with session.post(response_url, **kwargs) as resp:
                return resp.status == 200
    except Exception as exc:
        logger.warning("[Slack] response_url post failed: %s", exc)
        return False
