"""Tests for agent/credential_status.py helpers."""

from __future__ import annotations

import time

import pytest

from agent.credential_pool import (
    AUTH_TYPE_OAUTH,
    SOURCE_MANUAL,
    STATUS_EXHAUSTED,
    CredentialPool,
    PooledCredential,
)
from agent.credential_status import (
    classify_exhausted_status,
    format_exhausted_status,
    format_pool_exhaustion_message,
    format_remaining,
    summarize_pool_exhaustion,
)


def _make_entry(
    *,
    provider: str = "openai-codex",
    entry_id: str = "abc123",
    last_status: str = STATUS_EXHAUSTED,
    last_error_code: int | None = 429,
    last_error_reason: str | None = "usage_limit_reached",
    last_error_message: str | None = "The usage limit has been reached",
    last_error_reset_at: float | None = None,
    last_status_at: float | None = None,
) -> PooledCredential:
    return PooledCredential(
        provider=provider,
        id=entry_id,
        label=f"{provider}-oauth-1",
        auth_type=AUTH_TYPE_OAUTH,
        priority=0,
        source=SOURCE_MANUAL,
        access_token="tok-" + entry_id,
        refresh_token="ref-" + entry_id,
        last_status=last_status,
        last_status_at=last_status_at,
        last_error_code=last_error_code,
        last_error_reason=last_error_reason,
        last_error_message=last_error_message,
        last_error_reset_at=last_error_reset_at,
    )


def test_classify_rate_limit_from_code() -> None:
    entry = _make_entry(last_error_code=429, last_error_reason=None, last_error_message=None)
    assert classify_exhausted_status(entry) == ("rate-limited", True)


def test_classify_rate_limit_from_reason() -> None:
    entry = _make_entry(last_error_code=None, last_error_reason="usage_limit_reached", last_error_message=None)
    assert classify_exhausted_status(entry) == ("rate-limited", True)


def test_classify_auth_failed() -> None:
    entry = _make_entry(
        last_error_code=401,
        last_error_reason="invalid_token",
        last_error_message="Invalid token",
    )
    label, show_window = classify_exhausted_status(entry)
    assert label == "auth failed"
    assert show_window is False


def test_classify_generic_exhausted() -> None:
    entry = _make_entry(
        last_error_code=500,
        last_error_reason="upstream_error",
        last_error_message="Server error",
    )
    assert classify_exhausted_status(entry) == ("exhausted", True)


def test_format_remaining() -> None:
    assert format_remaining(45) == "45s"
    assert format_remaining(125) == "2m 5s"
    assert format_remaining(3600 * 2 + 60 * 30) == "2h 30m"
    assert format_remaining(86400 * 3 + 3600 * 4) == "3d 4h"
    assert format_remaining(0) == "0s"
    assert format_remaining(-5) == "0s"


def test_format_exhausted_status_with_reset() -> None:
    reset_at = time.time() + 4320  # 1h 12m
    entry = _make_entry(last_error_reset_at=reset_at)
    rendered = format_exhausted_status(entry)
    assert "rate-limited" in rendered
    assert "usage_limit_reached" in rendered
    assert "(429)" in rendered
    assert "left" in rendered
    # Allow off-by-one-second jitter.
    assert "1h 11m" in rendered or "1h 12m" in rendered


def test_format_exhausted_status_non_exhausted_returns_empty() -> None:
    entry = _make_entry(last_status=None)
    assert format_exhausted_status(entry) == ""


def test_format_exhausted_status_auth_failed_omits_window() -> None:
    entry = _make_entry(
        last_error_code=401,
        last_error_reason="invalid_token",
        last_error_message="Unauthorized",
        last_error_reset_at=time.time() + 3600,
    )
    rendered = format_exhausted_status(entry)
    assert "auth failed" in rendered
    assert "re-auth may be required" in rendered
    assert "left" not in rendered


def _make_pool(provider: str, entries: list[PooledCredential]) -> CredentialPool:
    return CredentialPool(provider=provider, entries=entries)


def test_summarize_empty_pool_returns_none() -> None:
    pool = _make_pool("openai-codex", [])
    assert summarize_pool_exhaustion(pool) is None


def test_summarize_any_healthy_returns_none() -> None:
    healthy = _make_entry(entry_id="healthy", last_status=None, last_error_code=None,
                          last_error_reason=None, last_error_message=None)
    rate_limited = _make_entry(entry_id="rl")
    pool = _make_pool("openai-codex", [healthy, rate_limited])
    assert summarize_pool_exhaustion(pool) is None


def test_summarize_all_rate_limited_picks_soonest_reset() -> None:
    now = time.time()
    early = _make_entry(entry_id="early", last_error_reset_at=now + 600)   # 10m
    late = _make_entry(entry_id="late", last_error_reset_at=now + 4320)    # 1h 12m
    pool = _make_pool("openai-codex", [late, early])

    summary = summarize_pool_exhaustion(pool)
    assert summary is not None
    assert summary["kind"] == "rate_limit"
    assert summary["label"] == "rate-limited"
    assert summary["provider"] == "openai-codex"
    assert summary["entry_count"] == 2
    assert summary["last_error_code"] == 429
    assert summary["last_error_reason"] == "usage_limit_reached"
    assert summary["soonest_reset_at"] == pytest.approx(now + 600, abs=2)
    assert summary["soonest_remaining_seconds"] is not None
    assert 595 <= summary["soonest_remaining_seconds"] <= 605


def test_summarize_mixed_prefers_rate_limit_label() -> None:
    rate_limited = _make_entry(entry_id="rl")
    auth_failed = _make_entry(
        entry_id="af",
        last_error_code=401,
        last_error_reason="invalid_token",
        last_error_message="Unauthorized",
    )
    pool = _make_pool("openai-codex", [auth_failed, rate_limited])
    summary = summarize_pool_exhaustion(pool)
    assert summary is not None
    # Rate-limit wins over auth-failed because it carries actionable
    # reset-time information.
    assert summary["kind"] == "rate_limit"
    assert summary["label"] == "rate-limited"


def test_summarize_all_auth_failed() -> None:
    auth_a = _make_entry(
        entry_id="a",
        last_error_code=401,
        last_error_reason="invalid_token",
        last_error_message="Unauthorized",
    )
    auth_b = _make_entry(
        entry_id="b",
        last_error_code=403,
        last_error_reason="forbidden",
        last_error_message="Forbidden",
    )
    pool = _make_pool("openai-codex", [auth_a, auth_b])
    summary = summarize_pool_exhaustion(pool)
    assert summary is not None
    assert summary["kind"] == "auth_failed"


def test_format_pool_exhaustion_message_rate_limit() -> None:
    summary = {
        "kind": "rate_limit",
        "label": "rate-limited",
        "provider": "openai-codex",
        "soonest_reset_at": None,
        "soonest_remaining_seconds": 4320,
        "last_error_reason": "usage_limit_reached",
        "last_error_code": 429,
        "entry_count": 1,
    }
    msg = format_pool_exhaustion_message("openai-codex", summary)
    assert msg == "openai-codex rate-limited (usage_limit_reached, 429) - resets in 1h 12m"


def test_format_pool_exhaustion_message_auth_failed_skips_window() -> None:
    summary = {
        "kind": "auth_failed",
        "label": "auth failed",
        "provider": "openai-codex",
        "soonest_reset_at": None,
        "soonest_remaining_seconds": 100,
        "last_error_reason": "invalid_token",
        "last_error_code": 401,
        "entry_count": 1,
    }
    msg = format_pool_exhaustion_message("openai-codex", summary)
    assert "auth failed" in msg
    assert "re-authenticate" in msg
    assert "resets in" not in msg


def test_format_pool_exhaustion_message_ready_to_retry() -> None:
    summary = {
        "kind": "rate_limit",
        "label": "rate-limited",
        "provider": "openai-codex",
        "soonest_reset_at": None,
        "soonest_remaining_seconds": 0,
        "last_error_reason": "usage_limit_reached",
        "last_error_code": 429,
        "entry_count": 1,
    }
    msg = format_pool_exhaustion_message("openai-codex", summary)
    assert "ready to retry" in msg
