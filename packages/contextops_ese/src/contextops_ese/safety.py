"""Fail-closed leak safety gate for ContextOps/ESE.

A :class:`~contextops_ese.contracts.ContextPack` is a minimal restore/avoid
contract — it is **not** a transcript, a provider request/response payload, a
secret store, or a raw id dump. This module is the single, testable place that
decides whether a string is safe to place in a pack.

Every check fails closed: an ambiguous string is treated as unsafe and the
caller is expected to raise rather than scrub-and-continue. The categories
mirror the boundary distinctions in ``docs/contextops/standalone-boundary.md``.
"""

from __future__ import annotations

import re

from .contracts import ContextPack

# A pack field is a short cognitive label; anything longer is itself suspect.
_MAX_FIELD_CHARS = 400

# Raw transcript / chat-turn role markers (line-anchored, case-insensitive).
_TRANSCRIPT_TURN_RE = re.compile(
    r"(?im)^\s*(?:user|assistant|system|human|ai|tool|developer)\s*:"
)
# Chat-turn control tokens used by provider chat templates.
_CHAT_MARKER_RE = re.compile(
    r"<\|?(?:im_start|im_end|endoftext|eot_id|start_header_id|end_header_id)\|?>"
    r"|\[/?INST\]|<<SYS>>"
)

# Provider request/response payload JSON shapes.
_PROVIDER_JSON_RE = re.compile(
    r'"(?:messages|choices|role|content|model|completion|finish_reason'
    r"|stop_reason|tool_calls|prompt_tokens|completion_tokens|input_tokens"
    r'|output_tokens|usage)"\s*:'
)

# Credential / secret-like key words.
_SECRET_KEY_RE = re.compile(
    r"(?i)\b(?:api[_-]?keys?|apikey|secrets?|passwords?|passwd|bearer"
    r"|access[_-]?tokens?|auth[_-]?tokens?|refresh[_-]?tokens?"
    r"|client[_-]?secret|private[_-]?key|credentials?)\b"
)
# Secret-like assignment (``token=...``, ``key: ...``).
_SECRET_ASSIGN_RE = re.compile(r"(?i)\b(?:token|key|secret|password|pwd)\b\s*[=:]\s*\S")
# Token-looking values: AWS keys, OpenAI keys, GitHub/Slack tokens, JWTs, long hex.
_TOKEN_VALUE_RE = re.compile(
    r"\bAKIA[0-9A-Z]{16}\b"
    r"|\bsk-[A-Za-z0-9]{16,}\b"
    r"|\bghp_[A-Za-z0-9]{20,}\b"
    r"|\bxox[baprs]-[A-Za-z0-9-]{10,}\b"
    r"|\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{2,}\b"
    r"|\b[0-9a-fA-F]{32,}\b"
)

# Raw message/session/id field names.
_RAW_ID_FIELD_RE = re.compile(
    r"(?i)\b(?:raw_id|message_id|msg_id|session_id|sess_id|chat_id"
    r"|thread_id|conversation_id|conv_id|user_id|event_id)\b"
)
# Raw id-shaped values (``msg-00042``, ``sess-9f3c``) — prefix + digit-bearing tail.
_RAW_ID_VALUE_RE = re.compile(
    r"(?i)\b(?:msg|sess|session|message|conversation|conv)[-_][a-z0-9]*\d[a-z0-9]*\b"
)

# Absolute POSIX paths, user-home (~/...), and Windows drive paths.
_ABS_PATH_RE = re.compile(r"(?:^|\s)(?:/[^\s/]|~/|[A-Za-z]:[\\/])")

# Ordered so the most specific / most serious leak is reported first.
_CHECKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_TRANSCRIPT_TURN_RE, "raw transcript / chat-turn marker"),
    (_CHAT_MARKER_RE, "chat-turn control marker"),
    (_PROVIDER_JSON_RE, "provider payload JSON shape"),
    (_TOKEN_VALUE_RE, "token-looking value"),
    (_SECRET_ASSIGN_RE, "secret-like assignment"),
    (_SECRET_KEY_RE, "credential/secret-like key"),
    (_RAW_ID_FIELD_RE, "raw id field name"),
    (_RAW_ID_VALUE_RE, "raw id-shaped value"),
    (_ABS_PATH_RE, "absolute filesystem path"),
)

_REF_PREFIX = "ref:"
# An opaque ref is the literal prefix plus a lowercase-hex digest only —
# nothing that could carry a raw id, path, or transcript fragment.
_REF_TOKEN_RE = re.compile(r"ref:[0-9a-f]{6,64}\Z")


def scan_unsafe(text: str) -> str | None:
    """Return a reason string if ``text`` is unsafe for a pack, else ``None``.

    This is the read-only detector. It never mutates or scrubs — callers
    fail closed on a non-``None`` result.
    """

    if not isinstance(text, str):
        return "field is not a string"
    for pattern, reason in _CHECKS:
        if pattern.search(text):
            return reason
    return None


def assert_text_safe(text: str, field: str = "field") -> str:
    """Validate one pack-bound string, raising ``ValueError`` if unsafe.

    Returns the (stripped) text on success so callers can use it directly.
    """

    if not isinstance(text, str):
        raise ValueError(f"{field} must be a string")
    if not text.isprintable():
        raise ValueError(f"{field} must be printable single-line text")
    if len(text) > _MAX_FIELD_CHARS:
        raise ValueError(f"{field} exceeds {_MAX_FIELD_CHARS} chars; summarise upstream")
    reason = scan_unsafe(text)
    if reason is not None:
        raise ValueError(f"{field} rejected by leak gate: {reason}")
    return text


def assert_ref_safe(ref: str, field: str = "ref") -> str:
    """Validate one pack ref is an opaque ``ref:<hex-digest>`` token.

    A ref must never carry a raw id, path, or any other evidence payload —
    only the deterministic digest produced by :func:`contextops_ese.safe_ref`.
    Raises ``ValueError`` (fail closed) on anything else.
    """

    if not isinstance(ref, str):
        raise ValueError(f"{field} must be a string")
    text = ref.strip()
    if not _REF_TOKEN_RE.fullmatch(text):
        raise ValueError(f"{field} must be an opaque 'ref:<hex>' token, got {ref!r}")
    return text


def assert_pack_safe(pack: ContextPack) -> ContextPack:
    """Fail-closed gate over **every** string field of a built ``ContextPack``.

    Runs after construction so an unsafe pack can never leave the builder,
    even if an upstream check regresses. Raises ``ValueError`` on any unsafe
    field or any ref that is not an opaque ``ref:`` token.
    """

    assert_text_safe(pack.id, "pack id")
    for line in pack.restore:
        assert_text_safe(line, "pack restore line")
    for line in pack.avoid:
        assert_text_safe(line, "pack avoid line")
    for ref in pack.refs:
        assert_text_safe(ref, "pack ref")
        assert_ref_safe(ref, "pack ref")
    return pack
