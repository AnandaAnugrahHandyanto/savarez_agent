"""Shared helpers for classifying and formatting credential-pool status.

These were previously defined in ``hermes_cli/auth_commands.py``. They live
here so non-CLI callers (e.g. the runtime resolver, the gateway logger) can
import them without depending on the ``hermes_cli`` package.
"""

from __future__ import annotations

import math
import time
from typing import Optional

from agent.credential_pool import (
    STATUS_EXHAUSTED,
    CredentialPool,
    PooledCredential,
    _exhausted_until,
)


def classify_exhausted_status(entry: PooledCredential) -> tuple[str, bool]:
    """Classify an exhausted pool entry.

    Returns ``(label, show_retry_window)`` where label is one of
    ``"rate-limited"``, ``"auth failed"``, or ``"exhausted"``.
    ``show_retry_window`` indicates whether displaying a retry-after window
    is meaningful (False for auth failures, which need re-login).
    """
    code = getattr(entry, "last_error_code", None)
    reason = str(getattr(entry, "last_error_reason", "") or "").strip().lower()
    message = str(getattr(entry, "last_error_message", "") or "").strip().lower()

    if code == 429 or any(token in reason for token in ("rate_limit", "usage_limit", "quota", "exhausted")) or any(
        token in message for token in ("rate limit", "usage limit", "quota", "too many requests")
    ):
        return "rate-limited", True

    if code in {401, 403} or any(token in reason for token in ("invalid_token", "invalid_grant", "unauthorized", "forbidden", "auth")) or any(
        token in message for token in ("unauthorized", "forbidden", "expired", "revoked", "invalid token", "authentication")
    ):
        return "auth failed", False

    return "exhausted", True


def format_remaining(remaining_seconds: int) -> str:
    """Format a duration as ``"Xd Yh"`` / ``"Xh Ym"`` / ``"Xm Ys"`` / ``"Xs"``."""
    remaining = max(0, int(remaining_seconds))
    minutes, seconds = divmod(remaining, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_exhausted_status(entry: PooledCredential) -> str:
    """Render a pool entry's exhausted-status suffix for display.

    Returns an empty string for non-exhausted entries. For exhausted entries,
    produces strings like ``" rate-limited usage_limit_reached (429) (1h 12m left)"``.
    """
    if entry.last_status != STATUS_EXHAUSTED:
        return ""
    label, show_retry_window = classify_exhausted_status(entry)
    reason = getattr(entry, "last_error_reason", None)
    reason_text = f" {reason}" if isinstance(reason, str) and reason.strip() else ""
    code = f" ({entry.last_error_code})" if entry.last_error_code else ""
    if not show_retry_window:
        return f" {label}{reason_text}{code} (re-auth may be required)"
    exhausted_until = _exhausted_until(entry)
    if exhausted_until is None:
        return f" {label}{reason_text}{code}"
    remaining = max(0, int(math.ceil(exhausted_until - time.time())))
    if remaining <= 0:
        return f" {label}{reason_text}{code} (ready to retry)"
    return f" {label}{reason_text}{code} ({format_remaining(remaining)} left)"


# Priority order for picking the "primary" classification when multiple
# exhausted entries disagree. Rate-limited wins because it carries an
# actionable reset time; auth-failed beats generic exhausted because it
# tells the user re-login is needed.
_LABEL_PRIORITY = {"rate-limited": 2, "auth failed": 1, "exhausted": 0}


def summarize_pool_exhaustion(pool: CredentialPool) -> Optional[dict]:
    """Summarize exhaustion across a pool's entries.

    Returns None if the pool has no entries, or if any entry is not in
    exhaustion cooldown (i.e. callers should only rely on this summary
    when ``pool.has_credentials() and not pool.has_available()``).

    Otherwise returns a dict with keys:
      - ``kind``: ``"rate_limit"``, ``"auth_failed"``, or ``"exhausted"``
      - ``label``: human-readable label (``"rate-limited"`` etc.)
      - ``provider``: pool provider name
      - ``soonest_reset_at``: unix-ts of earliest reset, or None
      - ``soonest_remaining_seconds``: int seconds until earliest reset, or None
      - ``entry_count``: number of entries in the pool
      - ``last_error_reason``: reason from the best-matching entry, or None
      - ``last_error_code``: status code from the best-matching entry, or None
    """
    entries = pool.entries()
    if not entries:
        return None
    if any(entry.last_status != STATUS_EXHAUSTED for entry in entries):
        return None

    best_priority = -1
    best_entry: Optional[PooledCredential] = None
    best_label = "exhausted"
    soonest_reset: Optional[float] = None

    for entry in entries:
        label, _show_window = classify_exhausted_status(entry)
        priority = _LABEL_PRIORITY.get(label, 0)
        if priority > best_priority:
            best_priority = priority
            best_entry = entry
            best_label = label
        reset_at = _exhausted_until(entry)
        if reset_at is not None and (soonest_reset is None or reset_at < soonest_reset):
            soonest_reset = reset_at

    kind = {
        "rate-limited": "rate_limit",
        "auth failed": "auth_failed",
        "exhausted": "exhausted",
    }.get(best_label, "exhausted")

    remaining: Optional[int] = None
    if soonest_reset is not None:
        remaining = max(0, int(math.ceil(soonest_reset - time.time())))

    return {
        "kind": kind,
        "label": best_label,
        "provider": pool.provider,
        "soonest_reset_at": soonest_reset,
        "soonest_remaining_seconds": remaining,
        "entry_count": len(entries),
        "last_error_reason": getattr(best_entry, "last_error_reason", None) if best_entry else None,
        "last_error_code": getattr(best_entry, "last_error_code", None) if best_entry else None,
    }


def format_pool_exhaustion_message(provider: str, summary: dict) -> str:
    """Render a one-line user-facing message from a ``summarize_pool_exhaustion`` dict."""
    label = summary.get("label", "exhausted")
    reason = summary.get("last_error_reason")
    code = summary.get("last_error_code")
    remaining = summary.get("soonest_remaining_seconds")

    parts = [f"{provider} {label}"]
    detail_bits = []
    if isinstance(reason, str) and reason.strip():
        detail_bits.append(reason.strip())
    if code:
        detail_bits.append(str(code))
    if detail_bits:
        parts.append(f"({', '.join(detail_bits)})")

    if summary.get("kind") == "auth_failed":
        parts.append("- re-authenticate with `hermes auth`")
    elif remaining is None:
        pass
    elif remaining <= 0:
        parts.append("- ready to retry")
    else:
        parts.append(f"- resets in {format_remaining(remaining)}")

    return " ".join(parts)
