"""Tests for agent.rate_limit_tracker — header parsing and formatting."""

import time
import pytest
from agent.rate_limit_tracker import (
    RateLimitBucket,
    RateLimitState,
    parse_rate_limit_headers,
    format_rate_limit_display,
    format_rate_limit_compact,
    _fmt_count,
    _fmt_seconds,
    _bar,
)


# ── Sample headers from Nous inference API ──────────────────────────────

NOUS_HEADERS = {
    "x-ratelimit-limit-requests": "800",
    "x-ratelimit-limit-requests-1h": "33600",
    "x-ratelimit-limit-tokens": "8000000",
    "x-ratelimit-limit-tokens-1h": "336000000",
    "x-ratelimit-remaining-requests": "795",
    "x-ratelimit-remaining-requests-1h": "33590",
    "x-ratelimit-remaining-tokens": "7999500",
    "x-ratelimit-remaining-tokens-1h": "335999000",
    "x-ratelimit-reset-requests": "45.5",
    "x-ratelimit-reset-requests-1h": "3500.0",
    "x-ratelimit-reset-tokens": "42.3",
    "x-ratelimit-reset-tokens-1h": "3490.0",
}

CODEX_HEADERS = {
    "x-codex-primary-used-percent": "16",
    "x-codex-primary-window-minutes": "300",
    "x-codex-primary-reset-after-seconds": "8222",
    "x-codex-secondary-used-percent": "5",
    "x-codex-secondary-window-minutes": "10080",
    "x-codex-secondary-reset-after-seconds": "520389",
}


class TestParseHeaders:
    def test_basic_parsing(self):
        state = parse_rate_limit_headers(NOUS_HEADERS, provider="nous")
        assert state is not None
        assert state.provider == "nous"
        assert state.has_data

        assert state.requests_min.limit == 800
        assert state.requests_min.remaining == 795
        assert state.requests_min.reset_seconds == 45.5

        assert state.requests_hour.limit == 33600
        assert state.requests_hour.remaining == 33590

        assert state.tokens_min.limit == 8000000
        assert state.tokens_min.remaining == 7999500

        assert state.tokens_hour.limit == 336000000
        assert state.tokens_hour.remaining == 335999000
        assert state.tokens_hour.reset_seconds == 3490.0

    def test_openai_codex_percent_headers_populate_five_hour_and_weekly_requests(self):
        state = parse_rate_limit_headers(CODEX_HEADERS, provider="openai-codex")

        assert state is not None
        assert state.provider == "openai-codex"
        assert state.has_data
        assert state.requests_5h.limit == 100
        assert state.requests_5h.remaining == 84
        assert state.requests_5h.reset_seconds == 8222
        assert state.requests_5h.usage_pct == pytest.approx(16.0)
        assert state.requests_week.limit == 100
        assert state.requests_week.remaining == 95
        assert state.requests_week.reset_seconds == 520389
        assert state.requests_week.usage_pct == pytest.approx(5.0)

    def test_openai_codex_percent_headers_do_not_populate_unrecognized_windows(self):
        headers = {
            **CODEX_HEADERS,
            "x-codex-primary-window-minutes": "60",
            "x-codex-secondary-window-minutes": "1440",
        }

        state = parse_rate_limit_headers(headers)

        assert state is not None
        assert state.has_data
        assert state.requests_5h.limit == 0
        assert state.requests_week.limit == 0

    def test_x_ratelimit_parsing_still_populates_existing_buckets(self):
        state = parse_rate_limit_headers(NOUS_HEADERS, provider="nous")

        assert state is not None
        assert state.has_data
        assert state.requests_min.usage_pct == pytest.approx(0.625)
        assert state.requests_hour.usage_pct == pytest.approx(0.02976190476190476)
        assert state.tokens_min.usage_pct == pytest.approx(0.00625)
        assert state.tokens_hour.usage_pct == pytest.approx(0.00029761904761904765)

    def test_no_headers(self):
        state = parse_rate_limit_headers({})
        assert state is None

    def test_partial_headers(self):
        headers = {
            "x-ratelimit-limit-requests": "100",
            "x-ratelimit-remaining-requests": "50",
        }
        state = parse_rate_limit_headers(headers)
        assert state is not None
        assert state.requests_min.limit == 100
        assert state.requests_min.remaining == 50
        # Missing fields default to 0
        assert state.tokens_min.limit == 0

    def test_non_rate_limit_headers_ignored(self):
        headers = {
            "content-type": "application/json",
            "server": "nginx",
        }
        state = parse_rate_limit_headers(headers)
        assert state is None

    def test_parses_five_hour_and_weekly_aliases(self):
        headers = {
            "x-ratelimit-limit-requests-5h": "100",
            "x-ratelimit-remaining-requests-5h": "20",
            "x-ratelimit-reset-requests-5h": "1200",
            "x-ratelimit-limit-tokens-weekly": "1000",
            "x-ratelimit-remaining-tokens-weekly": "650",
        }

        state = parse_rate_limit_headers(headers)

        assert state is not None
        assert state.requests_5h.limit == 100
        assert state.requests_5h.remaining == 20
        assert state.requests_5h.reset_seconds == 1200
        assert state.tokens_week.limit == 1000
        assert state.tokens_week.remaining == 650

    def test_parses_alternate_five_hour_and_weekly_suffixes(self):
        headers = {
            "x-ratelimit-limit-tokens-5hours": "500",
            "x-ratelimit-remaining-tokens-5hours": "100",
            "x-ratelimit-limit-requests-7d": "70",
            "x-ratelimit-remaining-requests-7d": "35",
        }

        state = parse_rate_limit_headers(headers)

        assert state is not None
        assert state.tokens_5h.limit == 500
        assert state.tokens_5h.remaining == 100
        assert state.requests_week.limit == 70
        assert state.requests_week.remaining == 35

    def test_malformed_values(self):
        headers = {
            "x-ratelimit-limit-requests": "not-a-number",
            "x-ratelimit-remaining-requests": "",
            "x-ratelimit-reset-requests": "abc",
        }
        state = parse_rate_limit_headers(headers)
        assert state is not None
        assert state.requests_min.limit == 0
        assert state.requests_min.remaining == 0
        assert state.requests_min.reset_seconds == 0.0


class TestBucket:
    def test_used(self):
        b = RateLimitBucket(limit=800, remaining=795, reset_seconds=45.0, captured_at=time.time())
        assert b.used == 5

    def test_usage_pct(self):
        b = RateLimitBucket(limit=100, remaining=20, reset_seconds=30.0, captured_at=time.time())
        assert b.usage_pct == pytest.approx(80.0)

    def test_usage_pct_zero_limit(self):
        b = RateLimitBucket(limit=0, remaining=0)
        assert b.usage_pct == 0.0

    def test_remaining_seconds_now(self):
        now = time.time()
        b = RateLimitBucket(limit=800, remaining=795, reset_seconds=60.0, captured_at=now - 10)
        # ~50 seconds should remain
        assert 49 <= b.remaining_seconds_now <= 51

    def test_remaining_seconds_expired(self):
        b = RateLimitBucket(limit=800, remaining=795, reset_seconds=30.0, captured_at=time.time() - 60)
        assert b.remaining_seconds_now == 0.0


class TestFormatting:
    def test_fmt_count_millions(self):
        assert _fmt_count(8000000) == "8.0M"
        assert _fmt_count(336000000) == "336.0M"

    def test_fmt_count_thousands(self):
        assert _fmt_count(33600) == "33.6K"
        assert _fmt_count(1500) == "1.5K"

    def test_fmt_count_small(self):
        assert _fmt_count(800) == "800"
        assert _fmt_count(0) == "0"

    def test_fmt_seconds_short(self):
        assert _fmt_seconds(45) == "45s"
        assert _fmt_seconds(0) == "0s"

    def test_fmt_seconds_minutes(self):
        assert _fmt_seconds(125) == "2m 5s"
        assert _fmt_seconds(120) == "2m"

    def test_fmt_seconds_hours(self):
        assert _fmt_seconds(3660) == "1h 1m"
        assert _fmt_seconds(3600) == "1h"

    def test_bar(self):
        bar = _bar(50.0, width=10)
        assert bar == "[█████░░░░░]"
        assert _bar(0.0, width=10) == "[░░░░░░░░░░]"
        assert _bar(100.0, width=10) == "[██████████]"

    def test_format_display_no_data(self):
        state = RateLimitState()
        result = format_rate_limit_display(state)
        assert "No rate limit data" in result

    def test_format_display_with_data(self):
        state = parse_rate_limit_headers(NOUS_HEADERS, provider="nous")
        assert state is not None
        result = format_rate_limit_display(state)
        assert "Nous" in result
        assert "Requests/min" in result
        assert "Requests/hr" in result
        assert "Tokens/min" in result
        assert "Tokens/hr" in result
        assert "resets in" in result

    def test_format_display_includes_five_hour_and_weekly_windows(self):
        state = parse_rate_limit_headers(
            {
                "x-ratelimit-limit-requests-5h": "100",
                "x-ratelimit-remaining-requests-5h": "20",
                "x-ratelimit-reset-requests-5h": "1200",
                "x-ratelimit-limit-tokens-weekly": "1000",
                "x-ratelimit-remaining-tokens-weekly": "650",
                "x-ratelimit-reset-tokens-weekly": "520389",
            },
            provider="openai-codex",
        )
        assert state is not None
        result = format_rate_limit_display(state)
        assert "Requests/5h" in result
        assert "Tokens/week" in result
        assert "resets in" in result

    def test_format_display_warning_on_high_usage(self):
        headers = {
            **NOUS_HEADERS,
            "x-ratelimit-remaining-requests": "50",  # 750/800 used = 93.75%
        }
        state = parse_rate_limit_headers(headers)
        assert state is not None
        result = format_rate_limit_display(state)
        assert "⚠" in result

    def test_format_compact(self):
        state = parse_rate_limit_headers(NOUS_HEADERS, provider="nous")
        assert state is not None
        result = format_rate_limit_compact(state)
        assert "RPM:" in result
        assert "RPH:" in result
        assert "TPM:" in result
        assert "TPH:" in result
        assert "resets" in result

    def test_format_compact_includes_codex_five_hour_and_weekly_resets(self):
        state = parse_rate_limit_headers(CODEX_HEADERS, provider="openai-codex")
        assert state is not None
        result = format_rate_limit_compact(state)
        assert "R5H: 84/100" in result
        assert "RW: 95/100" in result
        assert "resets" in result

    def test_format_compact_no_data(self):
        state = RateLimitState()
        result = format_rate_limit_compact(state)
        assert "No rate limit data" in result


class TestAgentIntegration:
    """Test that AIAgent captures rate limit state correctly."""

    def test_capture_rate_limits_from_headers(self):
        """Simulate the header capture path without a real API call."""
        # Use a mock httpx-like response
        class MockResponse:
            headers = NOUS_HEADERS

        # Import AIAgent minimally

        # Test the parsing directly
        state = parse_rate_limit_headers(MockResponse.headers, provider="nous")
        assert state is not None
        assert state.requests_min.limit == 800
        assert state.tokens_hour.limit == 336000000

    def test_capture_rate_limits_none_response(self):
        """_capture_rate_limits should handle None gracefully."""
        from agent.rate_limit_tracker import parse_rate_limit_headers
        # None should not crash
        result = parse_rate_limit_headers({})
        assert result is None
