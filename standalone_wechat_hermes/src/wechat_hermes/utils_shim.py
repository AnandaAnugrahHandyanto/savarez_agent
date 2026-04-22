"""Small utils subset (is_truthy_value + normalize_proxy_url)."""

from __future__ import annotations

import os
from urllib.parse import urlparse


TRUTHY_STRINGS = frozenset({"1", "true", "yes", "on"})


def is_truthy_value(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in TRUTHY_STRINGS
    return bool(value)


def normalize_proxy_url(proxy_url: str | None) -> str | None:
    candidate = str(proxy_url or "").strip()
    if not candidate:
        return None
    if candidate.lower().startswith("socks://"):
        return f"socks5://{candidate[len('socks://'):]}"
    return candidate
