"""Tests for session hygiene observability (issue #12626).

Verifies:
- Configurable hard message limit from config
- /usage shows message count and hygiene state
- Hygiene reason is correctly determined
"""

import threading
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_hygiene_config(hyg_data, default=400):
    """Replicate the config-reading logic from gateway/run.py hygiene block."""
    _hyg_hygiene_cfg = (
        hyg_data.get("gateway", {}).get("session_hygiene", {})
        if isinstance(hyg_data, dict) else {}
    )
    _raw_msg_limit = _hyg_hygiene_cfg.get("max_messages", default)
    try:
        limit = int(_raw_msg_limit)
    except (TypeError, ValueError):
        limit = default
    return limit


def _compute_hygiene_reason(msg_count, msg_limit, approx_tokens, compress_threshold):
    """Replicate the reason-determination logic."""
    msg_limit_enabled = msg_limit > 0
    needs_compress = approx_tokens >= compress_threshold or (
        msg_limit_enabled and msg_count >= msg_limit
    )
    reason = (
        "message_count"
        if (msg_limit_enabled and msg_count >= msg_limit)
        else "token_pressure"
    )
    return needs_compress, reason


def _make_runner(config=None):
    """Create a minimal GatewayRunner with mocked internals."""
    from gateway.run import GatewayRunner

    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = config if config is not None else {}
    runner._agent_cache = {}
    runner._agent_cache_lock = threading.Lock()
    runner._running_agents = {}
    runner.session_store = MagicMock()
    runner.adapters = {}
    return runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHardMsgLimitReadsFromConfig:
    """Verify the configurable hard message limit."""

    def test_default_limit(self):
        assert _parse_hygiene_config({}) == 400

    def test_custom_limit(self):
        cfg = {"gateway": {"session_hygiene": {"max_messages": 200}}}
        assert _parse_hygiene_config(cfg) == 200

    def test_zero_disables(self):
        cfg = {"gateway": {"session_hygiene": {"max_messages": 0}}}
        assert _parse_hygiene_config(cfg) == 0

    def test_invalid_value_falls_back(self):
        cfg = {"gateway": {"session_hygiene": {"max_messages": "not_a_number"}}}
        assert _parse_hygiene_config(cfg) == 400

    def test_non_dict_data(self):
        assert _parse_hygiene_config(None, default=400) == 400


class TestHygieneReason:
    """Verify _hygiene_reason is set correctly."""

    def test_token_pressure(self):
        """Tokens exceed threshold, msg count below limit -> token_pressure."""
        needs, reason = _compute_hygiene_reason(
            msg_count=100, msg_limit=400,
            approx_tokens=90000, compress_threshold=85000,
        )
        assert needs is True
        assert reason == "token_pressure"

    def test_message_count(self):
        """Msg count at limit, tokens below threshold -> message_count."""
        needs, reason = _compute_hygiene_reason(
            msg_count=400, msg_limit=400,
            approx_tokens=50000, compress_threshold=85000,
        )
        assert needs is True
        assert reason == "message_count"

    def test_no_compression_needed(self):
        """Both below thresholds -> no compression needed."""
        needs, reason = _compute_hygiene_reason(
            msg_count=100, msg_limit=400,
            approx_tokens=50000, compress_threshold=85000,
        )
        assert needs is False
        assert reason == "token_pressure"  # default when msg limit not hit

    def test_disabled_msg_limit(self):
        """Limit=0 means message count never triggers."""
        needs, reason = _compute_hygiene_reason(
            msg_count=9999, msg_limit=0,
            approx_tokens=50000, compress_threshold=85000,
        )
        assert needs is False
        assert reason == "token_pressure"


class TestUsageShowsMessageCount:
    """Verify /usage includes message count and hygiene info."""

    @pytest.mark.asyncio
    async def test_fallback_branch_shows_count_and_limit(self):
        """No-agent fallback includes Messages: N / limit (pct%)."""
        runner = _make_runner(config={"gateway": {"session_hygiene": {"max_messages": 400}}})

        # Mock session store to return some messages
        fake_session = MagicMock()
        fake_session.session_id = "test_session"
        runner.session_store.get_or_create_session.return_value = fake_session
        fake_msgs = [{"role": "user", "content": f"msg {i}"} for i in range(50)]
        fake_msgs += [{"role": "assistant", "content": f"reply {i}"} for i in range(50)]
        runner.session_store.load_transcript.return_value = fake_msgs

        event = MagicMock()
        event.source = MagicMock()
        event.source.platform = MagicMock()

        # No running or cached agent
        runner._running_agents = {}
        runner._session_key_for_source = MagicMock(return_value="test_key")

        with patch("agent.model_metadata.estimate_messages_tokens_rough", return_value=5000):
            result = await runner._handle_usage_command(event)

        assert "Messages: 100 / 400 (25%)" in result

    @pytest.mark.asyncio
    async def test_fallback_warning_at_90_percent(self):
        """Warning appears when messages >= 90% of limit."""
        runner = _make_runner(config={"gateway": {"session_hygiene": {"max_messages": 100}}})

        fake_session = MagicMock()
        fake_session.session_id = "test_session"
        runner.session_store.get_or_create_session.return_value = fake_session
        fake_msgs = [{"role": "user", "content": f"msg {i}"} for i in range(95)]
        runner.session_store.load_transcript.return_value = fake_msgs

        event = MagicMock()
        event.source = MagicMock()
        event.source.platform = MagicMock()
        runner._running_agents = {}
        runner._session_key_for_source = MagicMock(return_value="test_key")

        with patch("agent.model_metadata.estimate_messages_tokens_rough", return_value=5000):
            result = await runner._handle_usage_command(event)

        assert "Approaching message limit" in result
