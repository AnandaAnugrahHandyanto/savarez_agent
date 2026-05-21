"""Layer-2 credential redaction for outbound gateway messages.

Scrubs known credential patterns from any string before it leaves the gateway
toward a chat platform. Pulled from the credential-hygiene skill's Error
Redaction Pattern. Intentionally conservative: only matches patterns with a
distinctive prefix or shape, so legitimate URLs, hashes, and code snippets
pass through unchanged.

This is a defense-in-depth measure; the primary safeguards are not leaking
credentials in the first place (Layer-1: store in env, never echo).
"""

from __future__ import annotations

import re

REDACTION_PLACEHOLDER = "[REDACTED-credential]"

# Patterns ordered roughly most-specific to least-specific. Each pattern
# targets credentials with a recognizable prefix or structure so we avoid
# clobbering ordinary text.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Anthropic API keys: sk-ant-<90+ chars>
    re.compile(r"sk-ant-[A-Za-z0-9_-]{90,}"),
    # OpenAI / OpenAI-style keys: sk-... or sk-proj-...
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}"),
    # OpenRouter
    re.compile(r"sk-or-[A-Za-z0-9_-]{40,}"),
    # Google API keys: AIza<35 chars>
    re.compile(r"AIza[A-Za-z0-9_-]{35}"),
    # AWS Access Key ID: AKIA + 16 uppercase alphanumerics
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # xAI / Grok
    re.compile(r"xai-[A-Za-z0-9]{40,}"),
    # Replicate
    re.compile(r"\br8_[A-Za-z0-9]{40}\b"),
    # GitHub PATs
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgho_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
    # Tavily
    re.compile(r"\btvly-[A-Za-z0-9]{32,}\b"),
    # Discord bot token: <id>.<timestamp>.<hmac>
    re.compile(r"[MN][A-Za-z0-9]{23}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}"),
    # JWT: three dot-separated base64url segments, with a header that decodes
    # plausibly. We don't try to parse — just match the shape, anchored on
    # word boundaries so we don't snag ordinary dotted identifiers.
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    # Basic-auth URLs: scheme://user:password@host
    # Replace only the credentials, keep scheme + host so the URL remains
    # diagnosable.
    re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)[^\s:/@]+:[^\s/@]+@"),
)

# The basic-auth pattern needs a custom replacement that preserves the scheme.
_BASIC_AUTH_PATTERN = _PATTERNS[-1]


def redact_credentials(text: str) -> str:
    """Strip known credential patterns from *text*.

    Returns the redacted string. Non-string inputs are stringified first.
    Safe to call repeatedly (idempotent on already-redacted text).
    """
    if text is None:
        return text  # type: ignore[return-value]
    if not isinstance(text, str):
        text = str(text)

    for pattern in _PATTERNS:
        if pattern is _BASIC_AUTH_PATTERN:
            text = pattern.sub(
                lambda m: f"{m.group('scheme')}{REDACTION_PLACEHOLDER}@",
                text,
            )
        else:
            text = pattern.sub(REDACTION_PLACEHOLDER, text)
    return text


__all__ = ["redact_credentials", "REDACTION_PLACEHOLDER"]
