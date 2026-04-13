"""AgentLair Tool — send messages via AgentLair email API.

A thin integration layer that lets the agent send emails through an
AgentLair-claimed address. The caller controls the from address, subject,
and body; this tool handles auth, error normalisation, and rate-limit hints.

Configuration
-------------
AGENTLAIR_API_KEY   — API key for agentlair.dev (required)
AGENTLAIR_FROM      — Default sender address (e.g. publisher@agentlair.dev)

The tool registers itself under the "agentlair" toolset and is gated on
AGENTLAIR_API_KEY being present in the environment.
"""

import json
import logging
import os
import urllib.request

from tools.registry import registry

logger = logging.getLogger(__name__)

_API_BASE = "https://agentlair.dev/v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_key() -> str:
    return os.environ.get("AGENTLAIR_API_KEY", "")


def _post(path: str, payload: dict) -> dict:
    """Perform a JSON POST to the AgentLair API; raise on non-2xx."""
    key = _api_key()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{_API_BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str) -> dict:
    """Perform a JSON GET to the AgentLair API; raise on non-2xx."""
    key = _api_key()
    req = urllib.request.Request(
        f"{_API_BASE}{path}",
        headers={"Authorization": f"Bearer {key}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Inbox drain helper (used by the lifecycle hook)
# ---------------------------------------------------------------------------

def drain_inbox(address: str, limit: int = 20) -> list[dict]:
    """Fetch unread messages for *address* from the AgentLair inbox.

    Returns a list of message dicts (trimmed to essential fields). An empty
    list means no pending messages or the API is unreachable.
    """
    try:
        from urllib.parse import quote
        path = f"/email/inbox?address={quote(address)}&limit={limit}"
        result = _get(path)
        messages = result.get("messages", [])
        # Return only unread messages
        return [m for m in messages if not m.get("read", False)]
    except Exception as exc:
        logger.warning("agentlair: inbox drain failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def _send_agentlair_message(args: dict, **_kw) -> str:
    """Send an email via AgentLair.

    Required args: to, subject, text
    Optional args: from_address (falls back to AGENTLAIR_FROM env var)
    """
    to = args.get("to", "").strip()
    subject = args.get("subject", "").strip()
    text = args.get("text", "").strip()

    if not to:
        return json.dumps({"error": "'to' is required"})
    if not subject:
        return json.dumps({"error": "'subject' is required"})
    if not text:
        return json.dumps({"error": "'text' is required"})

    from_address = (
        args.get("from_address", "").strip()
        or os.environ.get("AGENTLAIR_FROM", "").strip()
    )
    if not from_address:
        return json.dumps({
            "error": (
                "No sender address. Set 'from_address' arg or "
                "AGENTLAIR_FROM environment variable."
            )
        })

    payload: dict = {
        "from": from_address,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "text": text,
    }

    html = args.get("html", "").strip()
    if html:
        payload["html"] = html

    try:
        result = _post("/email/send", payload)
        return json.dumps(result, ensure_ascii=False)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.warning("agentlair: send failed %s: %s", exc.code, body)
        return json.dumps({"error": f"HTTP {exc.code}", "detail": body})
    except Exception as exc:
        logger.error("agentlair: unexpected error: %s", exc)
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SEND_AGENTLAIR_MESSAGE_SCHEMA = {
    "name": "send_agentlair_message",
    "description": (
        "Send an email via AgentLair. "
        "Requires AGENTLAIR_API_KEY and AGENTLAIR_FROM (or the from_address arg). "
        "Use this for explicit agent-to-agent or agent-to-human email delivery."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address.",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line.",
            },
            "text": {
                "type": "string",
                "description": "Plain-text message body.",
            },
            "html": {
                "type": "string",
                "description": "Optional HTML version of the body.",
            },
            "from_address": {
                "type": "string",
                "description": (
                    "Sender address (must be claimed on your AgentLair account). "
                    "Defaults to AGENTLAIR_FROM env var."
                ),
            },
        },
        "required": ["to", "subject", "text"],
    },
}


def _check_requirements() -> bool:
    return bool(_api_key())


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="send_agentlair_message",
    toolset="agentlair",
    schema=SEND_AGENTLAIR_MESSAGE_SCHEMA,
    handler=_send_agentlair_message,
    check_fn=_check_requirements,
    emoji="📨",
)
