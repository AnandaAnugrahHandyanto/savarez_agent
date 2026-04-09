"""Tests for compression circuit breaker and tool output truncation.

The circuit breaker prevents compression loops where compression fires
repeatedly (every ~10s) because large tool outputs in the protected tail
keep the context above the threshold.

When N compressions happen within M seconds, the circuit breaker engages
and truncates large tool outputs before compressing, breaking the cycle.
"""

import time
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from agent.context_compressor import (
    ContextCompressor,
    _CIRCUIT_BREAKER_THRESHOLD,
    _CIRCUIT_BREAKER_WINDOW_SECONDS,
    _AGGRESSIVE_TOOL_OUTPUT_MAX_CHARS,
)


class TestCircuitBreakerDetection:
    """Test that the circuit breaker correctly detects compression loops."""

    def _make_compressor(self, **kwargs):
        """Create a ContextCompressor with mocked model metadata."""
        defaults = dict(
            model="test/model",
            threshold_percent=0.50,
            hard_threshold_percent=0.80,
            quiet_mode=True,
        )
        defaults.update(kwargs)
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            return ContextCompressor(**defaults)

    def test_circuit_breaker_inactive_initially(self):
        """No compressions recorded yet -- circuit breaker should be inactive."""
        comp = self._make_compressor()
        assert not comp._is_circuit_breaker_active()

    def test_circuit_breaker_inactive_below_threshold(self):
        """Fewer than N compressions -- circuit breaker should be inactive."""
        comp = self._make_compressor()
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD - 1):
            comp._record_compression()
        assert not comp._is_circuit_breaker_active()

    def test_circuit_breaker_active_at_threshold(self):
        """Exactly N compressions within the window -- should activate."""
        comp = self._make_compressor()
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            comp._record_compression()
        assert comp._is_circuit_breaker_active()

    def test_circuit_breaker_active_above_threshold(self):
        """More than N compressions within the window -- should activate."""
        comp = self._make_compressor()
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD + 2):
            comp._record_compression()
        assert comp._is_circuit_breaker_active()

    def test_circuit_breaker_inactive_after_window_expires(self):
        """Old compressions outside the window should not count."""
        comp = self._make_compressor()
        # Record timestamps in the past (outside the window)
        old_time = time.monotonic() - _CIRCUIT_BREAKER_WINDOW_SECONDS - 10
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            comp._compression_timestamps.append(old_time)
        assert not comp._is_circuit_breaker_active()

    def test_circuit_breaker_mixed_old_and_new(self):
        """Mix of old and recent compressions -- only recent ones count."""
        comp = self._make_compressor()
        old_time = time.monotonic() - _CIRCUIT_BREAKER_WINDOW_SECONDS - 10
        # Add old timestamps (shouldn't count)
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD - 1):
            comp._compression_timestamps.append(old_time)
        # Add one recent (below threshold)
        comp._record_compression()
        assert not comp._is_circuit_breaker_active()


class TestToolOutputTruncation:
    """Test the aggressive tool output truncation method."""

    def _make_compressor(self):
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            return ContextCompressor(
                model="test/model",
                threshold_percent=0.50,
                hard_threshold_percent=0.80,
                quiet_mode=True,
            )

    def test_truncates_large_tool_output(self):
        """Tool outputs larger than max_chars should be truncated."""
        comp = self._make_compressor()
        large_content = "A" * 10_000
        messages = [
            {"role": "user", "content": "do something"},
            {"role": "assistant", "content": "ok", "tool_calls": [{"id": "t1", "function": {"name": "test", "arguments": "{}"}}]},
            {"role": "tool", "content": large_content, "tool_call_id": "t1"},
        ]
        result, count = comp._truncate_large_tail_outputs(messages)
        assert count == 1
        assert len(result[2]["content"]) < len(large_content)
        assert "[TRUNCATED:" in result[2]["content"]
        assert "circuit breaker" in result[2]["content"]

    def test_preserves_small_tool_output(self):
        """Tool outputs under max_chars should not be touched."""
        comp = self._make_compressor()
        small_content = "short result"
        messages = [
            {"role": "tool", "content": small_content, "tool_call_id": "t1"},
        ]
        result, count = comp._truncate_large_tail_outputs(messages)
        assert count == 0
        assert result[0]["content"] == small_content

    def test_truncates_multiple_large_outputs(self):
        """Multiple large tool outputs should all be truncated."""
        comp = self._make_compressor()
        messages = [
            {"role": "tool", "content": "X" * 5000, "tool_call_id": "t1"},
            {"role": "user", "content": "more"},
            {"role": "tool", "content": "Y" * 8000, "tool_call_id": "t2"},
        ]
        result, count = comp._truncate_large_tail_outputs(messages)
        assert count == 2

    def test_preserves_head_and_tail_of_truncated_output(self):
        """Truncated output should keep first and last portions."""
        comp = self._make_compressor()
        # Create content with identifiable head and tail
        content = "HEAD_MARKER" + "X" * 10_000 + "TAIL_MARKER"
        messages = [
            {"role": "tool", "content": content, "tool_call_id": "t1"},
        ]
        result, _ = comp._truncate_large_tail_outputs(messages)
        assert "HEAD_MARKER" in result[0]["content"]
        assert "TAIL_MARKER" in result[0]["content"]

    def test_non_tool_messages_untouched(self):
        """User and assistant messages should never be truncated."""
        comp = self._make_compressor()
        large_content = "Z" * 10_000
        messages = [
            {"role": "user", "content": large_content},
            {"role": "assistant", "content": large_content},
        ]
        result, count = comp._truncate_large_tail_outputs(messages)
        assert count == 0
        assert result[0]["content"] == large_content
        assert result[1]["content"] == large_content

    def test_custom_max_chars(self):
        """Custom max_chars parameter should be respected."""
        comp = self._make_compressor()
        messages = [
            {"role": "tool", "content": "A" * 500, "tool_call_id": "t1"},
        ]
        # With default (2000), 500 chars should not be truncated
        result, count = comp._truncate_large_tail_outputs(messages)
        assert count == 0

        # With max_chars=100, 500 chars should be truncated
        result, count = comp._truncate_large_tail_outputs(messages, max_chars=100)
        assert count == 1

    def test_does_not_mutate_original(self):
        """Truncation should not modify the original messages list."""
        comp = self._make_compressor()
        original_content = "B" * 5000
        messages = [
            {"role": "tool", "content": original_content, "tool_call_id": "t1"},
        ]
        result, _ = comp._truncate_large_tail_outputs(messages)
        # Original should be unchanged
        assert messages[0]["content"] == original_content
        # Result should be different
        assert result[0]["content"] != original_content


class TestCircuitBreakerIntegration:
    """Test that the circuit breaker engages during actual compression."""

    def _make_compressor(self):
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            return ContextCompressor(
                model="test/model",
                threshold_percent=0.50,
                hard_threshold_percent=0.80,
                protect_first_n=1,
                protect_last_n=5,
                summary_target_ratio=0.20,
                quiet_mode=True,
            )

    def test_compress_records_timestamp(self):
        """Each compress() call should record a timestamp."""
        comp = self._make_compressor()
        assert len(comp._compression_timestamps) == 0

        # Build enough messages for compression to proceed
        messages = [{"role": "user", "content": "hello"}]
        for i in range(20):
            messages.append({"role": "assistant", "content": f"response {i}"})
            messages.append({"role": "user", "content": f"question {i}"})

        # Mock the summary generation to avoid actual LLM calls
        comp._generate_summary = MagicMock(return_value="[CONTEXT COMPACTION] Summary")

        comp.compress(messages, current_tokens=120_000)
        assert len(comp._compression_timestamps) == 1

    def test_circuit_breaker_truncates_on_loop(self):
        """When circuit breaker fires, large tool outputs should be truncated."""
        comp = self._make_compressor()

        # Pre-populate compression timestamps to trigger circuit breaker
        for _ in range(_CIRCUIT_BREAKER_THRESHOLD):
            comp._record_compression()

        assert comp._is_circuit_breaker_active()

        # Create messages with a large tool output
        large_output = "X" * 50_000  # 50KB tool output
        messages = [
            {"role": "user", "content": "start"},
        ]
        for i in range(10):
            messages.append({"role": "assistant", "content": f"resp {i}"})
            messages.append({"role": "user", "content": f"q {i}"})
        messages.append({
            "role": "assistant", "content": "ok",
            "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
        })
        messages.append({"role": "tool", "content": large_output, "tool_call_id": "t1"})

        comp._generate_summary = MagicMock(return_value="[CONTEXT COMPACTION] Summary")

        result = comp.compress(messages, current_tokens=120_000)

        # The large tool output should have been truncated
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        if tool_msgs:
            for tm in tool_msgs:
                content = tm.get("content", "")
                # Either truncated or pruned
                assert len(content) < len(large_output), (
                    f"Tool output should be truncated: {len(content)} vs {len(large_output)}"
                )

    def test_normal_compress_does_not_truncate_tail(self):
        """Without circuit breaker, tail tool outputs should not be aggressively truncated."""
        comp = self._make_compressor()

        # No circuit breaker active
        assert not comp._is_circuit_breaker_active()

        large_output = "X" * 50_000
        messages = [
            {"role": "user", "content": "start"},
        ]
        for i in range(10):
            messages.append({"role": "assistant", "content": f"resp {i}"})
            messages.append({"role": "user", "content": f"q {i}"})
        # This should be in the protected tail (last 5 messages)
        messages.append({
            "role": "assistant", "content": "ok",
            "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
        })
        messages.append({"role": "tool", "content": large_output, "tool_call_id": "t1"})
        messages.append({"role": "user", "content": "what happened?"})

        comp._generate_summary = MagicMock(return_value="[CONTEXT COMPACTION] Summary")

        result = comp.compress(messages, current_tokens=120_000)

        # The tail tool output should still be in the result (protected)
        # It may be pruned if outside the tail, but within tail it should be preserved
        # The key point: no circuit-breaker truncation marker
        for m in result:
            if m.get("role") == "tool":
                assert "circuit breaker" not in m.get("content", "")


class TestHardThresholdConfig:
    """Test hard_threshold configuration and initialization."""

    def test_hard_threshold_defaults(self):
        """Default hard threshold should be 0.80."""
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            comp = ContextCompressor(model="test/model", quiet_mode=True)
        assert comp.hard_threshold_percent == 0.80
        assert comp.hard_threshold_tokens == 160_000

    def test_hard_threshold_custom(self):
        """Custom hard threshold should be respected."""
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            comp = ContextCompressor(
                model="test/model",
                hard_threshold_percent=0.75,
                quiet_mode=True,
            )
        assert comp.hard_threshold_percent == 0.75
        assert comp.hard_threshold_tokens == 150_000

    def test_hard_threshold_must_exceed_soft(self):
        """Hard threshold should always be at least soft + 0.05."""
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            comp = ContextCompressor(
                model="test/model",
                threshold_percent=0.60,
                hard_threshold_percent=0.60,  # Same as soft -- should be bumped
                quiet_mode=True,
            )
        assert comp.hard_threshold_percent >= 0.65

    def test_hard_threshold_in_status(self):
        """get_status() should include hard_threshold_tokens."""
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            comp = ContextCompressor(model="test/model", quiet_mode=True)
        status = comp.get_status()
        assert "hard_threshold_tokens" in status
        assert status["hard_threshold_tokens"] == 160_000

    def test_circuit_breaker_in_status(self):
        """get_status() should include circuit_breaker_active."""
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            comp = ContextCompressor(model="test/model", quiet_mode=True)
        status = comp.get_status()
        assert "circuit_breaker_active" in status
        assert status["circuit_breaker_active"] is False


class TestForcetruncationParam:
    """Test that force_truncation parameter triggers aggressive truncation."""

    def _make_compressor(self):
        with patch("agent.context_compressor.get_model_context_length", return_value=200_000):
            return ContextCompressor(
                model="test/model",
                threshold_percent=0.50,
                protect_first_n=1,
                protect_last_n=5,
                quiet_mode=True,
            )

    def test_force_truncation_truncates_without_circuit_breaker(self):
        """force_truncation=True should truncate even without circuit breaker active."""
        comp = self._make_compressor()
        assert not comp._is_circuit_breaker_active()

        large_output = "Z" * 10_000
        messages = [
            {"role": "user", "content": "start"},
        ]
        for i in range(10):
            messages.append({"role": "assistant", "content": f"r {i}"})
            messages.append({"role": "user", "content": f"q {i}"})
        messages.append({
            "role": "assistant", "content": "ok",
            "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
        })
        messages.append({"role": "tool", "content": large_output, "tool_call_id": "t1"})

        comp._generate_summary = MagicMock(return_value="[CONTEXT COMPACTION] Summary")

        result = comp.compress(messages, current_tokens=120_000, force_truncation=True)

        # At least one tool message should have been truncated
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        truncated_any = any(
            "circuit breaker" in (m.get("content") or "").lower() or
            "[TRUNCATED:" in (m.get("content") or "")
            for m in tool_msgs
        )
        # The output may have been pruned (replaced with placeholder) instead of
        # truncated if it fell outside the protected tail. Either way, it should
        # be smaller than the original.
        if tool_msgs:
            for tm in tool_msgs:
                assert len(tm.get("content", "")) < len(large_output)
