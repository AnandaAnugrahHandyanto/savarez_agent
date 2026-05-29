"""Rate limit tracking for inference API responses.

Captures x-ratelimit-* and x-codex-* headers from provider responses and provides
formatted display for the /usage slash command.  Currently supports
the Nous Portal header format (also used by OpenRouter and OpenAI-compatible
APIs that follow the same convention) and OpenAI Codex percent-window headers.

Header schema (12 headers total):
    x-ratelimit-limit-requests          RPM cap
    x-ratelimit-limit-requests-1h       RPH cap
    x-ratelimit-limit-tokens            TPM cap
    x-ratelimit-limit-tokens-1h         TPH cap
    x-ratelimit-remaining-requests      requests left in minute window
    x-ratelimit-remaining-requests-1h   requests left in hour window
    x-ratelimit-remaining-tokens        tokens left in minute window
    x-ratelimit-remaining-tokens-1h     tokens left in hour window
    x-ratelimit-reset-requests          seconds until minute request window resets
    x-ratelimit-reset-requests-1h       seconds until hour request window resets
    x-ratelimit-reset-tokens            seconds until minute token window resets
    x-ratelimit-reset-tokens-1h         seconds until hour token window resets
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass
class RateLimitBucket:
    """One rate-limit window (e.g. requests per minute)."""

    limit: int = 0
    remaining: int = 0
    reset_seconds: float = 0.0
    captured_at: float = 0.0  # time.time() when this was captured

    @property
    def used(self) -> int:
        return max(0, self.limit - self.remaining)

    @property
    def usage_pct(self) -> float:
        if self.limit <= 0:
            return 0.0
        return (self.used / self.limit) * 100.0

    @property
    def remaining_seconds_now(self) -> float:
        """Estimated seconds remaining until reset, adjusted for elapsed time."""
        elapsed = time.time() - self.captured_at
        return max(0.0, self.reset_seconds - elapsed)


@dataclass
class RateLimitState:
    """Full rate-limit state parsed from response headers."""

    requests_min: RateLimitBucket = field(default_factory=RateLimitBucket)
    requests_hour: RateLimitBucket = field(default_factory=RateLimitBucket)
    requests_5h: RateLimitBucket = field(default_factory=RateLimitBucket)
    requests_week: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens_min: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens_hour: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens_5h: RateLimitBucket = field(default_factory=RateLimitBucket)
    tokens_week: RateLimitBucket = field(default_factory=RateLimitBucket)
    captured_at: float = 0.0  # when the headers were captured
    provider: str = ""

    @property
    def has_data(self) -> bool:
        return self.captured_at > 0

    @property
    def age_seconds(self) -> float:
        if not self.has_data:
            return float("inf")
        return time.time() - self.captured_at


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _codex_percent_bucket(prefix: str, window_minutes: int, lowered: Mapping[str, str], now: float) -> RateLimitBucket:
    percent_key = f"x-codex-{prefix}-used-percent"
    window_key = f"x-codex-{prefix}-window-minutes"
    if percent_key not in lowered or _safe_int(lowered.get(window_key)) != window_minutes:
        return RateLimitBucket(captured_at=now)

    used_percent = max(0, min(100, _safe_int(lowered.get(percent_key))))
    return RateLimitBucket(
        limit=100,
        remaining=100 - used_percent,
        reset_seconds=_safe_float(lowered.get(f"x-codex-{prefix}-reset-after-seconds")),
        captured_at=now,
    )


def parse_rate_limit_headers(
    headers: Mapping[str, str],
    provider: str = "",
) -> Optional[RateLimitState]:
    """Parse x-ratelimit-* and x-codex-* headers into a RateLimitState.

    Returns None if no rate limit headers are present.
    """
    # Normalize to lowercase so lookups work regardless of how the server
    # capitalises headers (HTTP header names are case-insensitive per RFC 7230).
    lowered = {k.lower(): v for k, v in headers.items()}

    # Quick check: at least one supported rate-limit header must exist.
    has_any = any(k.startswith("x-ratelimit-") or k.startswith("x-codex-") for k in lowered)
    if not has_any:
        return None

    now = time.time()

    def _bucket(resource: str, suffix: str = "") -> RateLimitBucket:
        # e.g. resource="requests", suffix="" -> per-minute
        #      resource="tokens", suffix="-1h" -> per-hour
        tag = f"{resource}{suffix}"
        return RateLimitBucket(
            limit=_safe_int(lowered.get(f"x-ratelimit-limit-{tag}")),
            remaining=_safe_int(lowered.get(f"x-ratelimit-remaining-{tag}")),
            reset_seconds=_safe_float(lowered.get(f"x-ratelimit-reset-{tag}")),
            captured_at=now,
        )

    def _bucket_any(resource: str, suffixes: tuple[str, ...]) -> RateLimitBucket:
        for suffix in suffixes:
            tag = f"{resource}{suffix}"
            if any(
                f"x-ratelimit-{field}-{tag}" in lowered
                for field in ("limit", "remaining", "reset")
            ):
                return _bucket(resource, suffix)
        return RateLimitBucket(captured_at=now)

    five_hour_suffixes = ("-5h", "-5hr", "-5hour", "-5hours")
    week_suffixes = ("-1w", "-7d", "-week", "-weekly")

    state = RateLimitState(
        requests_min=_bucket("requests"),
        requests_hour=_bucket("requests", "-1h"),
        requests_5h=_bucket_any("requests", five_hour_suffixes),
        requests_week=_bucket_any("requests", week_suffixes),
        tokens_min=_bucket("tokens"),
        tokens_hour=_bucket("tokens", "-1h"),
        tokens_5h=_bucket_any("tokens", five_hour_suffixes),
        tokens_week=_bucket_any("tokens", week_suffixes),
        captured_at=now,
        provider=provider,
    )

    codex_primary = _codex_percent_bucket("primary", 300, lowered, now)
    if codex_primary.limit > 0:
        state.requests_5h = codex_primary
    codex_secondary = _codex_percent_bucket("secondary", 10080, lowered, now)
    if codex_secondary.limit > 0:
        state.requests_week = codex_secondary

    return state


# ── Formatting ──────────────────────────────────────────────────────────


def _fmt_count(n: int) -> str:
    """Human-friendly number: 7999856 -> '8.0M', 33599 -> '33.6K', 799 -> '799'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_seconds(seconds: float) -> str:
    """Seconds -> human-friendly duration: '58s', '2m 14s', '58m 57s', '1h 2m'."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        m, sec = divmod(s, 60)
        return f"{m}m {sec}s" if sec else f"{m}m"
    h, remainder = divmod(s, 3600)
    m = remainder // 60
    return f"{h}h {m}m" if m else f"{h}h"


def _bar(pct: float, width: int = 20) -> str:
    """ASCII progress bar: [████████░░░░░░░░░░░░] 40%."""
    filled = int(pct / 100.0 * width)
    filled = max(0, min(width, filled))
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


def _bucket_line(label: str, bucket: RateLimitBucket, label_width: int = 14) -> str:
    """Format one bucket as a single line."""
    if bucket.limit <= 0:
        return f"  {label:<{label_width}}  (no data)"

    pct = bucket.usage_pct
    used = _fmt_count(bucket.used)
    limit = _fmt_count(bucket.limit)
    remaining = _fmt_count(bucket.remaining)
    reset = _fmt_seconds(bucket.remaining_seconds_now)

    bar = _bar(pct)
    return f"  {label:<{label_width}} {bar} {pct:5.1f}%  {used}/{limit} used  ({remaining} left, resets in {reset})"


def format_rate_limit_display(state: RateLimitState) -> str:
    """Format rate limit state for terminal/chat display."""
    if not state.has_data:
        return "No rate limit data yet — make an API request first."

    age = state.age_seconds
    if age < 5:
        freshness = "just now"
    elif age < 60:
        freshness = f"{int(age)}s ago"
    else:
        freshness = f"{_fmt_seconds(age)} ago"

    provider_label = state.provider.title() if state.provider else "Provider"

    lines = [
        f"{provider_label} Rate Limits (captured {freshness}):",
        "",
        _bucket_line("Requests/min", state.requests_min),
        _bucket_line("Requests/hr", state.requests_hour),
    ]
    if state.requests_5h.limit > 0:
        lines.append(_bucket_line("Requests/5h", state.requests_5h))
    if state.requests_week.limit > 0:
        lines.append(_bucket_line("Requests/week", state.requests_week))
    lines.extend([
        "",
        _bucket_line("Tokens/min", state.tokens_min),
        _bucket_line("Tokens/hr", state.tokens_hour),
    ])
    if state.tokens_5h.limit > 0:
        lines.append(_bucket_line("Tokens/5h", state.tokens_5h))
    if state.tokens_week.limit > 0:
        lines.append(_bucket_line("Tokens/week", state.tokens_week))

    # Add warnings if any bucket is getting hot
    warnings = []
    for label, bucket in [
        ("requests/min", state.requests_min),
        ("requests/hr", state.requests_hour),
        ("requests/5h", state.requests_5h),
        ("requests/week", state.requests_week),
        ("tokens/min", state.tokens_min),
        ("tokens/hr", state.tokens_hour),
        ("tokens/5h", state.tokens_5h),
        ("tokens/week", state.tokens_week),
    ]:
        if bucket.limit > 0 and bucket.usage_pct >= 80:
            reset = _fmt_seconds(bucket.remaining_seconds_now)
            warnings.append(f"  ⚠ {label} at {bucket.usage_pct:.0f}% — resets in {reset}")

    if warnings:
        lines.append("")
        lines.extend(warnings)

    return "\n".join(lines)


def format_rate_limit_compact(state: RateLimitState) -> str:
    """One-line compact summary for status bars / gateway messages."""
    if not state.has_data:
        return "No rate limit data."

    rm = state.requests_min
    tm = state.tokens_min
    rh = state.requests_hour
    th = state.tokens_hour
    r5h = state.requests_5h
    t5h = state.tokens_5h
    rw = state.requests_week
    tw = state.tokens_week

    parts = []
    if rm.limit > 0:
        parts.append(f"RPM: {rm.remaining}/{rm.limit}")
    if rh.limit > 0:
        parts.append(f"RPH: {_fmt_count(rh.remaining)}/{_fmt_count(rh.limit)} (resets {_fmt_seconds(rh.remaining_seconds_now)})")
    if tm.limit > 0:
        parts.append(f"TPM: {_fmt_count(tm.remaining)}/{_fmt_count(tm.limit)}")
    if th.limit > 0:
        parts.append(f"TPH: {_fmt_count(th.remaining)}/{_fmt_count(th.limit)} (resets {_fmt_seconds(th.remaining_seconds_now)})")
    if r5h.limit > 0:
        parts.append(f"R5H: {_fmt_count(r5h.remaining)}/{_fmt_count(r5h.limit)} (resets {_fmt_seconds(r5h.remaining_seconds_now)})")
    if t5h.limit > 0:
        parts.append(f"T5H: {_fmt_count(t5h.remaining)}/{_fmt_count(t5h.limit)} (resets {_fmt_seconds(t5h.remaining_seconds_now)})")
    if rw.limit > 0:
        parts.append(f"RW: {_fmt_count(rw.remaining)}/{_fmt_count(rw.limit)} (resets {_fmt_seconds(rw.remaining_seconds_now)})")
    if tw.limit > 0:
        parts.append(f"TW: {_fmt_count(tw.remaining)}/{_fmt_count(tw.limit)} (resets {_fmt_seconds(tw.remaining_seconds_now)})")

    return " | ".join(parts)
