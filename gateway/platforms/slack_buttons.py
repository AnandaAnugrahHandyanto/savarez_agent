"""Parse agent-emitted button markup and render Slack Block Kit action blocks.

Agents request interactive buttons by embedding a fenced ```buttons block — a
JSON array of button objects — anywhere in their reply.  This module is the
single place that knows that markup syntax and its Block Kit translation, so
the Slack adapter only has to wire it into the send/click paths.

Markup example::

    Pick one:
    ```buttons
    [
      {"text": "Confirm", "value": "confirm order", "style": "primary"},
      {"text": "Keep looking", "value": "keep browsing"},
      {"text": "Docs", "url": "https://example.com"}
    ]
    ```

Rules:
  * ``text`` is required (non-empty string).
  * ``value`` is the text fed back into the conversation when the button is
    clicked (an interactive button).  Defaults to ``text`` when omitted.
  * ``url`` makes a link button — Slack navigates natively, no callback fires.
  * ``style`` may be ``"primary"`` or ``"danger"``; anything else is ignored.
  * ``callback`` is an optional dict with a ``type`` key; when present the
    gateway handles the click deterministically without involving the LLM.

If the block is missing, malformed, or yields no valid buttons, the content is
returned unchanged with an empty button list — the adapter then sends it as
ordinary text, so a broken markup block never loses the agent's message.
"""

import base64
import json
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# action_id prefix the regex handler in SlackAdapter.connect() matches on.
# The button index is appended (e.g. "hermes_btn::0") to keep ids unique
# within a single actions block.
BUTTON_ACTION_PREFIX = "hermes_btn::"

# Prefix used in button values to indicate a typed gateway callback.
# Format: cb:<type>:<base64url(json_payload_without_type)>
CALLBACK_PREFIX = "cb:"

# Slack Block Kit hard limits.
_MAX_BUTTONS = 5          # buttons per actions block we render (Slack allows 25)
_MAX_TEXT_LEN = 75        # button label
_MAX_VALUE_LEN = 2000     # button value payload

_VALID_STYLES = {"primary", "danger"}

# Matches a fenced ```buttons ... ``` block.  Case-insensitive language tag,
# tolerant of CRLF.  Captures the inner JSON payload.
_FENCE_RE = re.compile(
    r"```buttons[ \t]*\r?\n(.*?)\r?\n?```",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class ButtonSpec:
    """A single parsed button."""

    text: str
    value: Optional[str] = None     # interactive button: fed back on click
    url: Optional[str] = None       # link button: native navigation, no callback
    style: Optional[str] = None     # "primary" | "danger"
    callback: Optional[dict] = None  # typed gateway callback; takes priority over value


def _coerce_buttons(payload: object) -> List[ButtonSpec]:
    """Validate a decoded JSON payload into a list of ButtonSpec.

    Returns an empty list if nothing usable is found.  Never raises.
    """
    if not isinstance(payload, list):
        return []

    buttons: List[ButtonSpec] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.strip()[:_MAX_TEXT_LEN]

        url = item.get("url")
        url = url.strip() if isinstance(url, str) and url.strip() else None

        value = item.get("value")
        if isinstance(value, str) and value.strip():
            value = value.strip()[:_MAX_VALUE_LEN]
        elif url is not None:
            # Link button: no feedback value needed.
            value = None
        else:
            # Bare button with no value/url — feed the label back on click.
            value = text[:_MAX_VALUE_LEN]

        style = item.get("style")
        style = style if isinstance(style, str) and style in _VALID_STYLES else None

        # Parse optional callback dict (must have a string "type" key).
        callback = item.get("callback")
        if isinstance(callback, dict) and isinstance(callback.get("type"), str):
            pass  # valid
        else:
            callback = None

        buttons.append(ButtonSpec(text=text, value=value, url=url, style=style, callback=callback))
        if len(buttons) >= _MAX_BUTTONS:
            break

    return buttons


def parse_buttons(content: str) -> Tuple[str, List[ButtonSpec]]:
    """Extract the first ```buttons block from ``content``.

    Returns ``(text_without_block, buttons)``.  On any failure the original
    ``content`` is returned with an empty button list, so callers can safely
    fall back to plain-text sending.
    """
    if not content or "```buttons" not in content.lower():
        return content, []

    match = _FENCE_RE.search(content)
    if not match:
        return content, []

    try:
        payload = json.loads(match.group(1))
    except (ValueError, TypeError):
        return content, []

    buttons = _coerce_buttons(payload)
    if not buttons:
        return content, []

    # Strip the fenced block out of the visible text and tidy whitespace.
    text = (content[: match.start()] + content[match.end():]).strip()
    return text, buttons


def encode_callback(cb: dict) -> str:
    """Encode a callback dict into a ``cb:<type>:<base64url(payload)>`` string.

    The ``type`` key is separated out; the remaining payload is JSON-serialised
    and base64url-encoded so the value survives Slack's button value field.
    This format is self-contained: the gateway can decode it after a restart
    without any in-memory registry.
    """
    cb_type = cb["type"]
    payload = {k: v for k, v in cb.items() if k != "type"}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"{CALLBACK_PREFIX}{cb_type}:{encoded}"


def decode_callback(value: Optional[str]) -> Optional[dict]:
    """Decode a ``cb:<type>:<base64url>`` value back to a callback dict.

    Returns ``{"type": <type>, ...payload}`` on success, ``None`` on any
    failure or if ``value`` does not start with ``CALLBACK_PREFIX``.
    """
    if not value or not value.startswith(CALLBACK_PREFIX):
        return None
    try:
        rest = value[len(CALLBACK_PREFIX):]
        # Split on the first ":" only; type may not contain ":"
        colon = rest.index(":")
        cb_type = rest[:colon]
        b64_part = rest[colon + 1:]
        payload = json.loads(base64.urlsafe_b64decode(b64_part + "==").decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        return {"type": cb_type, **payload}
    except Exception:
        return None


def build_actions_block(buttons: List[ButtonSpec]) -> dict:
    """Build a Block Kit ``actions`` block from parsed buttons.

    Each button's index becomes part of its ``action_id`` so the regex action
    handler can claim them all.  The feedback text lives in the button
    ``value`` (interactive) or mthe click is a no-op feedback-wise (link).
    If a ButtonSpec carries a ``callback``, it is encoded into ``value`` so
    the gateway can handle the click deterministically.
    """
    elements = []
    for idx, b in enumerate(buttons):
        element = {
            "type": "button",
            "text": {"type": "plain_text", "text": b.text, "emoji": True},
            "action_id": f"{BUTTON_ACTION_PREFIX}{idx}",
        }
        if b.url:
            element["url"] = b.url
        # callback takes priority over plain value
        if b.callback is not None:
            element["value"] = encode_callback(b.callback)
        elif b.value is not None:
            element["value"] = b.value
        if b.style:
            element["style"] = b.style
        elements.append(element)

    return {"type": "actions", "elements": elements}


def fallback_text(buttons: List[ButtonSpec]) -> str:
    """A short text fallback for the buttons message (notifications / a11y)."""
    return "Options: " + " / ".join(b.text for b in buttons)
