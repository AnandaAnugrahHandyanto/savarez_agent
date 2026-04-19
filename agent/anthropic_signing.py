"""Claude Code billing-header signing + session/request IDs.

Reverse-engineered from Claude Code's minified ``K19()`` function and mirrored
after the port in ``griffinmartin/opencode-claude-auth`` (``src/signing.ts``).

Anthropic's OAuth (Claude Pro / Max subscription) traffic is validated
server-side based on three things that together identify the request as
legitimate Claude Code traffic:

1. Request headers — ``User-Agent``, ``X-App``, plus per-process
   ``X-Claude-Code-Session-Id`` and per-request ``X-Client-Request-Id`` UUIDs.
2. Beta flags — ``claude-code-20250219``, ``oauth-2025-04-20``, plus
   version-dated prompt-caching / context-management / effort betas.
3. A **system message entry** (NOT an HTTP header) named
   ``x-anthropic-billing-header`` that carries ``cc_version`` /
   ``cc_entrypoint`` / ``cch`` fields.  The ``cc_version`` suffix and ``cch``
   are SHA-256 hashes of a salt, version string, and characters sampled from
   the first user message.

Omitting any of these produces intermittent 400s or unsubscribed-billing
responses when the access token is a subscription OAuth token (as opposed to
a regular ``sk-ant-api*`` API key).

All constants here are reverse-engineered from the official Claude Code CLI
and must match Anthropic's server-side validator byte-for-byte.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Iterable, List, Optional

# ── Billing salt (constant in Claude Code) ─────────────────────────────
# Treat as a protocol constant, not a secret. It's shipped inside the
# public Claude Code JS bundle; rotating it here would break our requests.
_BILLING_SALT = "59cf53e54c78"

# ── Session ID (stable for the lifetime of the Hermes process) ─────────
# Anthropic uses this to correlate requests from the same editor session
# for tracing/billing.  Stable within a process, new per launch.
_SESSION_ID: str = str(uuid.uuid4())


def get_session_id() -> str:
    """Return the per-process Claude Code session UUID."""
    return _SESSION_ID


def new_request_id() -> str:
    """Generate a fresh per-request UUID for the ``X-Client-Request-Id`` header."""
    return str(uuid.uuid4())


# ── cch (content hash) ─────────────────────────────────────────────────

def compute_cch(message_text: str) -> str:
    """Return the first 5 hex chars of SHA-256 over the first user message.

    Matches Claude Code's ``computeCch`` in K19(). Claude Code computes this
    from the plain-text of the first user message (not the full messages
    payload); the empty-string input yields a well-known hash that the
    validator accepts for tool-only sequels.
    """
    return hashlib.sha256(message_text.encode("utf-8")).hexdigest()[:5]


# ── cc_version suffix ──────────────────────────────────────────────────

_SAMPLED_INDICES = (4, 7, 20)


def compute_version_suffix(message_text: str, version: str) -> str:
    """Return the 3-hex-char suffix appended to ``cc_version``.

    ``sha256(BILLING_SALT + sampled_chars + version)[:3]`` where
    ``sampled_chars`` is text[4] + text[7] + text[20] (padded with "0" when
    the message is shorter than the index).

    Matches Claude Code's ``computeVersionSuffix`` in K19().
    """
    sampled_parts: List[str] = []
    for i in _SAMPLED_INDICES:
        sampled_parts.append(message_text[i] if i < len(message_text) else "0")
    sampled = "".join(sampled_parts)
    material = f"{_BILLING_SALT}{sampled}{version}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:3]


# ── First-user-message text extraction ─────────────────────────────────

def extract_first_user_message_text(messages: Iterable[Any]) -> str:
    """Extract the plain-text content of the first ``role=user`` message.

    Supports the two Anthropic content shapes:

    * ``content`` as a string → returned directly
    * ``content`` as a list of blocks → concatenate text from every
      ``{"type": "text", "text": ...}`` block in order (mirrors Claude
      Code's behavior — tool_result text is NOT included).

    Returns the empty string if no user message is present.
    """
    for msg in messages:
        if not isinstance(msg, dict):
            # Anthropic SDK objects (pydantic models) also work; convert
            try:
                msg = dict(msg)
            except Exception:
                continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    txt = block.get("text", "")
                    if isinstance(txt, str):
                        parts.append(txt)
            return "".join(parts)
        return ""
    return ""


# ── Billing header value ───────────────────────────────────────────────

_BILLING_HEADER_PREFIX = "x-anthropic-billing-header"


def build_billing_header_value(
    messages: Iterable[Any],
    version: str,
    entrypoint: str = "cli",
) -> str:
    """Build the ``x-anthropic-billing-header`` system-block text.

    Example output::

        x-anthropic-billing-header: cc_version=2.1.114.a3f; cc_entrypoint=cli; cch=d41d8;

    The format must exactly match what Claude Code sends — any whitespace or
    ordering change triggers a 400.
    """
    text = extract_first_user_message_text(messages)
    cch = compute_cch(text)
    suffix = compute_version_suffix(text, version)
    return (
        f"{_BILLING_HEADER_PREFIX}: "
        f"cc_version={version}.{suffix}; "
        f"cc_entrypoint={entrypoint}; "
        f"cch={cch};"
    )


def is_billing_header_text(text: Optional[str]) -> bool:
    """Return True if the given text is the billing-header system block."""
    return isinstance(text, str) and text.startswith(_BILLING_HEADER_PREFIX)
