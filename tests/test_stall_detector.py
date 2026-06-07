"""Tests for agent.stall_detector — stall detection in the agent loop.

Covers:
- tool_batch_signature normalization
- consecutive stall detection
- window-based stall detection
- hard-stop escalation
- reset behavior
- edge cases (empty batches, single tool, mixed tools)
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agent.stall_detector import (
    StallDetection,
    StallDetector,
    StallDetectorConfig,
    _tc_args,
    _tc_name,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_tc(name: str, args: dict | None = None) -> SimpleNamespace:
    """Build a fake tool_call object matching the OpenAI SDK shape."""
    return SimpleNamespace(
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(args or {}, sort_keys=True),
        )
    )


def _make_tc_dict(name: str, args: dict | None = None) -> dict:
    """Build a tool_call as a plain dict (alternate shape)."""
    return {
        "function": {
            "name": name,
            "arguments": json.dumps(args or {}, sort_keys=True),
        }
    }


# ── tool_batch_signature ────────────────────────────────────────────────

class TestToolBatchSignature:
    def test_empty_batch(self):
        assert StallDetector.tool_batch_signature([]) == ""
        assert StallDetector.tool_batch_signature(None) == ""

    def test_single_tool(self):
        tc = _make_tc("read_file", {"path": "/tmp/a.txt"})
        sig = StallDetector.tool_batch_signature([tc])
        assert "read_file[" in sig
        assert "]" in sig

    def test_same_args_same_signature(self):
        tc1 = _make_tc("read_file", {"path": "/tmp/a.txt"})
        tc2 = _make_tc("read_file", {"path": "/tmp/a.txt"})
        assert StallDetector.tool_batch_signature([tc1]) == StallDetector.tool_batch_signature([tc2])

    def test_different_args_different_signature(self):
        tc1 = _make_tc("read_file", {"path": "/tmp/a.txt"})
        tc2 = _make_tc("read_file", {"path": "/tmp/b.txt"})
        assert StallDetector.tool_batch_signature([tc1]) != StallDetector.tool_batch_signature([tc2])

    def test_order_independent(self):
        tc1 = _make_tc("read_file", {"path": "/a"})
        tc2 = _make_tc("patch", {"path": "/b"})
        sig1 = StallDetector.tool_batch_signature([tc1, tc2])
        sig2 = StallDetector.tool_batch_signature([tc2, tc1])
        assert sig1 == sig2

    def test_dict_tool_call(self):
        tc = _make_tc_dict("terminal", {"command": "ls"})
        sig = StallDetector.tool_batch_signature([tc])
        assert "terminal[" in sig

    def test_string_arguments(self):
        """Arguments can be a raw JSON string (not pre-parsed)."""
        tc = SimpleNamespace(
            function=SimpleNamespace(
                name="tool",
                arguments='{"key": "value"}',
            )
        )
        sig = StallDetector.tool_batch_signature([tc])
        assert "tool[" in sig


# ── Consecutive stall detection ─────────────────────────────────────────

class TestConsecutiveStall:
    def test_no_stall_below_threshold(self):
        det = StallDetector(StallDetectorConfig(consecutive_threshold=3))
        sig = "read_file[abc123]"
        assert det.check(sig).is_stall is False
        assert det.check(sig).is_stall is False  # 2nd time, threshold=3

    def test_stall_at_threshold(self):
        det = StallDetector(StallDetectorConfig(consecutive_threshold=3))
        sig = "read_file[abc123]"
        det.check(sig)
        det.check(sig)
        result = det.check(sig)
        assert result.is_stall is True
        assert result.hard_stop is False  # first stall warning

    def test_different_calls_reset_consecutive(self):
        det = StallDetector(StallDetectorConfig(consecutive_threshold=3))
        det.check("read_file[aaa]")
        det.check("read_file[aaa]")
        det.check("patch[bbb]")  # different — resets consecutive counter
        result = det.check("patch[bbb]")
        assert result.is_stall is False  # only 2 consecutive of patch

    def test_empty_signature_ignored(self):
        det = StallDetector(StallDetectorConfig(consecutive_threshold=2))
        result = det.check("")
        assert result.is_stall is False


# ── Window-based stall detection ────────────────────────────────────────

class TestWindowStall:
    def test_window_pattern_detected(self):
        det = StallDetector(StallDetectorConfig(
            consecutive_threshold=100,  # disable consecutive
            window_size=5,
            window_threshold=4,
        ))
        sigs = ["a[111]", "b[222]", "a[111]", "a[111]", "a[111]"]
        for sig in sigs[:-1]:
            assert det.check(sig).is_stall is False
        result = det.check(sigs[-1])
        assert result.is_stall is True

    def test_window_not_full_no_detection(self):
        det = StallDetector(StallDetectorConfig(
            consecutive_threshold=100,
            window_size=7,
            window_threshold=5,
        ))
        for _ in range(4):
            assert det.check("a[111]").is_stall is False


# ── Hard-stop escalation ────────────────────────────────────────────────

class TestHardStop:
    def test_hard_stop_after_max_stalls(self):
        det = StallDetector(StallDetectorConfig(
            consecutive_threshold=2,
            max_stalls=1,
        ))
        sig = "read_file[abc]"
        det.check(sig)
        r1 = det.check(sig)
        assert r1.is_stall is True
        assert r1.hard_stop is False  # first stall = warning

        det.check("other[xyz]")  # reset consecutive
        det.check(sig)
        r2 = det.check(sig)
        assert r2.is_stall is True
        assert r2.hard_stop is True  # second stall = hard stop

    def test_hard_stop_message_mentions_terminating(self):
        det = StallDetector(StallDetectorConfig(
            consecutive_threshold=2,
            max_stalls=1,
        ))
        det.check("x[1]")
        det.check("x[1]")  # stall 1 (warning)
        det.check("y[2]")
        det.check("x[1]")
        r = det.check("x[1]")  # stall 2 → hard stop
        assert "Terminating" in r.message or "terminating" in r.message.lower()


# ── Reset ───────────────────────────────────────────────────────────────

class TestReset:
    def test_reset_clears_state(self):
        det = StallDetector(StallDetectorConfig(consecutive_threshold=2))
        det.check("a[1]")
        det.check("a[1]")  # stall
        assert det._stall_count == 1
        det.reset()
        assert det._stall_count == 0
        assert det._consecutive_count == 0
        assert len(det._recent_signatures) == 0
        # After reset, same sig should not stall immediately
        assert det.check("a[1]").is_stall is False


# ── _tc_name / _tc_args helpers ─────────────────────────────────────────

class TestTcHelpers:
    def test_tc_name_object(self):
        tc = _make_tc("my_tool")
        assert _tc_name(tc) == "my_tool"

    def test_tc_name_dict(self):
        tc = _make_tc_dict("my_tool")
        assert _tc_name(tc) == "my_tool"

    def test_tc_args_object(self):
        tc = _make_tc("tool", {"key": "val"})
        args = _tc_args(tc)
        assert json.loads(args)["key"] == "val"

    def test_tc_args_dict(self):
        tc = _make_tc_dict("tool", {"key": "val"})
        args = _tc_args(tc)
        assert json.loads(args)["key"] == "val"

    def test_tc_name_unknown_shape(self):
        assert _tc_name("not_a_tc") == ""
        assert _tc_name(None) == ""
