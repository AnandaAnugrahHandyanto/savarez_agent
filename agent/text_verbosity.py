"""OpenAI Responses API text verbosity helpers."""

from __future__ import annotations

from typing import Any

VALID_TEXT_VERBOSITIES = {"low", "medium", "high"}


def parse_text_verbosity(raw: Any) -> str | None:
    """Return a normalized Responses API text verbosity value, or None."""
    value = str(raw or "").strip().lower()
    if not value:
        return None
    if value in VALID_TEXT_VERBOSITIES:
        return value
    return None
