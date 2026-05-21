"""Unit tests for agent.commitment_validator (S-0518-01).

Covers pure-Python logic — auxiliary LLM call is monkey-patched so tests
don't require an OpenRouter / OpenAI key.
"""

from __future__ import annotations

import pytest

from agent import commitment_validator as cv


# =========================================================================
# _was_enqueue_called
# =========================================================================

class TestWasEnqueueCalled:
    def test_empty_messages_returns_false(self):
        assert cv._was_enqueue_called(None) is False
        assert cv._was_enqueue_called([]) is False

    def test_messages_with_no_tool_calls(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello", "tool_calls": None},
        ]
        assert cv._was_enqueue_called(msgs) is False

    def test_messages_with_other_tool_calls(self):
        msgs = [
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "mcp_artemis_tools_get_strategy"}},
                    {"function": {"name": "mcp_artemis_tools_save_user_profile"}},
                ],
            },
        ]
        assert cv._was_enqueue_called(msgs) is False

    def test_messages_with_enqueue_action_call(self):
        msgs = [
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "mcp_artemis_tools_enqueue_action"}},
                ],
            },
        ]
        assert cv._was_enqueue_called(msgs) is True

    def test_messages_with_bare_enqueue_name(self):
        """Bare 'enqueue_action' (no MCP prefix) also counts — defensive."""
        msgs = [
            {
                "role": "assistant",
                "tool_calls": [{"function": {"name": "enqueue_action"}}],
            },
        ]
        assert cv._was_enqueue_called(msgs) is True

    def test_malformed_tool_call_entries_dont_crash(self):
        msgs = [
            {"role": "assistant", "tool_calls": "not a list"},
            {"role": "assistant", "tool_calls": [None, "string", 42]},
            {"role": "assistant", "tool_calls": [{"function": None}]},
        ]
        assert cv._was_enqueue_called(msgs) is False


# =========================================================================
# _parse_validator_response
# =========================================================================

class TestParseValidatorResponse:
    def test_clean_json(self):
        raw = '{"has_unmet_commitment": true, "sub_agent": "analyst"}'
        parsed = cv._parse_validator_response(raw)
        assert parsed["has_unmet_commitment"] is True
        assert parsed["sub_agent"] == "analyst"

    def test_json_with_markdown_fence(self):
        raw = '```json\n{"has_unmet_commitment": false}\n```'
        parsed = cv._parse_validator_response(raw)
        assert parsed == {"has_unmet_commitment": False}

    def test_json_with_bare_fence(self):
        raw = '```\n{"has_unmet_commitment": false}\n```'
        parsed = cv._parse_validator_response(raw)
        assert parsed == {"has_unmet_commitment": False}

    def test_empty_string_returns_none(self):
        assert cv._parse_validator_response("") is None
        assert cv._parse_validator_response(None) is None

    def test_invalid_json_returns_none(self):
        assert cv._parse_validator_response("not json") is None
        assert cv._parse_validator_response("{invalid") is None

    def test_non_dict_json_returns_none(self):
        """A JSON array or scalar shouldn't be accepted."""
        assert cv._parse_validator_response("[1, 2, 3]") is None
        assert cv._parse_validator_response('"a string"') is None


# =========================================================================
# check_unmet_commitment — happy paths + skip paths
# =========================================================================

class TestCheckUnmetCommitment:
    def test_short_reply_is_skipped(self, monkeypatch):
        """Reply below threshold short-circuits — no aux call."""
        called = {"aux": False}

        def _fake_call_llm(**kwargs):
            called["aux"] = True
            raise AssertionError("should not be called")

        monkeypatch.setattr(
            "agent.auxiliary_client.call_llm", _fake_call_llm, raising=False
        )
        result = cv.check_unmet_commitment("Makes sense.", [], chat_id="C1")
        assert result["checked"] is False
        assert result["skipped"] == "reply_too_short"
        assert called["aux"] is False

    def test_enqueue_called_short_circuits(self, monkeypatch):
        """When enqueue_action was called this turn, skip aux call —
        commitment is already backed by backend state."""
        called = {"aux": False}

        def _fake_call_llm(**kwargs):
            called["aux"] = True
            raise AssertionError("should not be called")

        monkeypatch.setattr(
            "agent.auxiliary_client.call_llm", _fake_call_llm, raising=False
        )
        long_reply = "I'll have Analyst put a cheat sheet together for next time. " * 3
        msgs = [
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "mcp_artemis_tools_enqueue_action"}}
                ],
            }
        ]
        result = cv.check_unmet_commitment(long_reply, msgs, chat_id="C1")
        assert result["checked"] is False
        assert result["skipped"] == "enqueue_called"
        assert called["aux"] is False

    def test_aux_call_with_unmet_commitment(self, monkeypatch):
        """When aux LLM returns mismatch=true, result reflects it."""

        class _FakeMsg:
            content = (
                '{"has_unmet_commitment": true, "sub_agent": "analyst", '
                '"future_tense_phrase": "I\'ll have the team pull together '
                'a cheat sheet", "confidence": "high", '
                '"reasoning": "future-tense team commitment without enqueue"}'
            )

        class _FakeChoice:
            message = _FakeMsg()

        class _FakeResponse:
            choices = [_FakeChoice()]

        def _fake_call_llm(**kwargs):
            return _FakeResponse()

        monkeypatch.setattr(
            "agent.auxiliary_client.call_llm", _fake_call_llm, raising=False
        )

        long_reply = (
            "That ugh is so real. I'll have the team pull together a "
            "Pocket Metrics sheet for you so you have them on lock for "
            "the next round."
        )
        result = cv.check_unmet_commitment(long_reply, [], chat_id="C1")
        assert result["checked"] is True
        assert result["skipped"] is None
        assert result["has_unmet_commitment"] is True
        assert result["sub_agent"] == "analyst"
        assert "cheat sheet" in (result["future_tense_phrase"] or "")
        assert result["confidence"] == "high"

    def test_aux_call_clean_reply(self, monkeypatch):
        """When aux LLM returns mismatch=false, result reflects it."""

        class _FakeMsg:
            content = (
                '{"has_unmet_commitment": false, "sub_agent": null, '
                '"future_tense_phrase": null, "confidence": "high", '
                '"reasoning": "no future-tense sub-agent commitment"}'
            )

        class _FakeChoice:
            message = _FakeMsg()

        class _FakeResponse:
            choices = [_FakeChoice()]

        def _fake_call_llm(**kwargs):
            return _FakeResponse()

        monkeypatch.setattr(
            "agent.auxiliary_client.call_llm", _fake_call_llm, raising=False
        )

        long_reply = (
            "Makes sense — variety's a solid reason to lean that way. "
            "You'll see more industries in a year at an agency than most "
            "people do in five on the brand side."
        )
        result = cv.check_unmet_commitment(long_reply, [], chat_id="C1")
        assert result["checked"] is True
        assert result["has_unmet_commitment"] is False
        assert result["sub_agent"] is None

    def test_aux_call_failure_is_silent(self, monkeypatch):
        """An exception inside call_llm doesn't crash the hook."""

        def _fake_call_llm(**kwargs):
            raise RuntimeError("network error")

        monkeypatch.setattr(
            "agent.auxiliary_client.call_llm", _fake_call_llm, raising=False
        )

        long_reply = "x" * 200
        result = cv.check_unmet_commitment(long_reply, [], chat_id="C1")
        assert result["checked"] is False
        assert result["skipped"] is not None
        assert "aux_call_failed" in result["skipped"]

    def test_aux_call_returns_garbage_json(self, monkeypatch):
        """Aux returns non-JSON → parse failure logged, no crash."""

        class _FakeMsg:
            content = "this is not json at all"

        class _FakeChoice:
            message = _FakeMsg()

        class _FakeResponse:
            choices = [_FakeChoice()]

        def _fake_call_llm(**kwargs):
            return _FakeResponse()

        monkeypatch.setattr(
            "agent.auxiliary_client.call_llm", _fake_call_llm, raising=False
        )

        long_reply = "x" * 200
        result = cv.check_unmet_commitment(long_reply, [], chat_id="C1")
        assert result["checked"] is False
        assert result["skipped"] == "aux_parse_failed"


# =========================================================================
# Log shape — the validator emits exactly one log line per call
# =========================================================================

class TestLoggingShape:
    def test_emits_single_commitment_check_log(self, monkeypatch, caplog):
        """Each invocation logs one line starting with 'commitment-check:'."""

        class _FakeMsg:
            content = (
                '{"has_unmet_commitment": false, "sub_agent": null, '
                '"future_tense_phrase": null, "confidence": "high", '
                '"reasoning": "clean"}'
            )

        class _FakeChoice:
            message = _FakeMsg()

        class _FakeResponse:
            choices = [_FakeChoice()]

        def _fake_call_llm(**kwargs):
            return _FakeResponse()

        monkeypatch.setattr(
            "agent.auxiliary_client.call_llm", _fake_call_llm, raising=False
        )

        with caplog.at_level("INFO", logger="agent.commitment_validator"):
            cv.check_unmet_commitment("x" * 200, [], chat_id="DTEST")

        lines = [
            r.message for r in caplog.records
            if r.message.startswith("commitment-check:")
        ]
        assert len(lines) == 1
        assert "chat=DTEST" in lines[0]
        assert "checked=True" in lines[0]
        assert "mismatch=False" in lines[0]
