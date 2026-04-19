"""Tests for agent/anthropic_signing.py — Claude Code billing-header signing."""

from __future__ import annotations

import hashlib
import re
import uuid

import pytest

from agent.anthropic_signing import (
    build_billing_header_value,
    compute_cch,
    compute_version_suffix,
    extract_first_user_message_text,
    get_session_id,
    is_billing_header_text,
    new_request_id,
)


# ---------------------------------------------------------------------------
# compute_cch
# ---------------------------------------------------------------------------


class TestComputeCch:
    def test_empty_string_returns_known_sha256_prefix(self):
        # Empty input — first 5 hex chars of SHA-256("") == "e3b0c".
        # Reference: sha256(b"").hexdigest()[:5]
        result = compute_cch("")
        assert result == "e3b0c"
        # Double-check vs the stdlib, not just the constant.
        assert result == hashlib.sha256(b"").hexdigest()[:5]

    def test_hello_world_returns_known_sha256_prefix(self):
        result = compute_cch("hello world")
        assert result == "b94d2"
        assert result == hashlib.sha256(b"hello world").hexdigest()[:5]

    def test_returns_5_char_hex_string(self):
        result = compute_cch("some random input 123")
        assert isinstance(result, str)
        assert len(result) == 5
        assert re.fullmatch(r"[0-9a-f]{5}", result)

    def test_unicode_is_utf8_encoded(self):
        text = "héllo"
        result = compute_cch(text)
        assert result == hashlib.sha256(text.encode("utf-8")).hexdigest()[:5]


# ---------------------------------------------------------------------------
# compute_version_suffix
# ---------------------------------------------------------------------------


# Billing salt is a protocol constant from Claude Code's bundle; replicated
# here so the tests assert against an independently computed expected value
# rather than trusting the module constant.
_EXPECTED_BILLING_SALT = "59cf53e54c78"


class TestComputeVersionSuffix:
    def test_empty_message_pads_sampled_chars_with_zeros(self):
        # When the message is empty, indices 4/7/20 all fall past end, so
        # sampled_chars = "000" and the hash material is
        #   salt + "000" + version
        version = "2.1.114"
        expected = hashlib.sha256(
            (_EXPECTED_BILLING_SALT + "000" + version).encode("utf-8")
        ).hexdigest()[:3]
        assert compute_version_suffix("", version) == expected

    def test_sampled_indices_are_4_7_and_20(self):
        # "abcdefghijklmnopqrstuvwxyz" — indices 4/7/20 = 'e', 'h', 'u'.
        # Material:  salt + "ehu" + "2.1.114"
        text = "abcdefghijklmnopqrstuvwxyz"
        version = "2.1.114"
        expected = hashlib.sha256(
            (_EXPECTED_BILLING_SALT + "ehu" + version).encode("utf-8")
        ).hexdigest()[:3]
        assert compute_version_suffix(text, version) == expected

    def test_returns_3_char_hex_string(self):
        result = compute_version_suffix("anything", "2.1.114")
        assert isinstance(result, str)
        assert len(result) == 3
        assert re.fullmatch(r"[0-9a-f]{3}", result)

    def test_partial_length_pads_missing_indices(self):
        # "abcde" — indices 4='e', 7=OOB→'0', 20=OOB→'0'.  So sampled="e00".
        text = "abcde"
        version = "2.1.114"
        expected = hashlib.sha256(
            (_EXPECTED_BILLING_SALT + "e00" + version).encode("utf-8")
        ).hexdigest()[:3]
        assert compute_version_suffix(text, version) == expected


# ---------------------------------------------------------------------------
# extract_first_user_message_text
# ---------------------------------------------------------------------------


class TestExtractFirstUserMessageText:
    def test_empty_list(self):
        assert extract_first_user_message_text([]) == ""

    def test_string_content(self):
        assert extract_first_user_message_text(
            [{"role": "user", "content": "hi"}]
        ) == "hi"

    def test_list_content_concatenates_text_blocks_in_order(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "text", "text": "b"},
                ],
            }
        ]
        assert extract_first_user_message_text(msgs) == "ab"

    def test_skips_assistant_messages_to_find_first_user(self):
        msgs = [
            {"role": "assistant", "content": "x"},
            {"role": "user", "content": "y"},
        ]
        assert extract_first_user_message_text(msgs) == "y"

    def test_tool_result_text_is_not_included(self):
        # Only ``{"type": "text"}`` blocks contribute — tool_result blocks
        # must be skipped (Claude Code's behaviour).
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": "nope"},
                    {"type": "text", "text": "keep"},
                ],
            }
        ]
        assert extract_first_user_message_text(msgs) == "keep"

    def test_handles_mapping_like_object_via_dict_coercion(self):
        # Anthropic SDK returns pydantic-ish objects; the signer coerces them
        # via ``dict(msg)`` when ``isinstance(..., dict)`` is False.  A simple
        # Mapping subclass is enough to exercise that path.

        class MsgMapping(dict):
            """Dict subclass passes the isinstance(dict) check directly."""

        msg = MsgMapping({"role": "user", "content": "hello"})
        assert extract_first_user_message_text([msg]) == "hello"

    def test_unknown_content_shape_returns_empty_string(self):
        msgs = [{"role": "user", "content": 123}]
        assert extract_first_user_message_text(msgs) == ""

    def test_list_content_with_non_text_blocks_only(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {}},
                ],
            }
        ]
        assert extract_first_user_message_text(msgs) == ""


# ---------------------------------------------------------------------------
# build_billing_header_value
# ---------------------------------------------------------------------------


class TestBuildBillingHeaderValue:
    HEADER_PATTERN = re.compile(
        r"^x-anthropic-billing-header: "
        r"cc_version=2\.1\.114\.[0-9a-f]{3}; "
        r"cc_entrypoint=cli; "
        r"cch=[0-9a-f]{5};$"
    )

    def test_matches_exact_pattern(self):
        value = build_billing_header_value(
            [{"role": "user", "content": "hi"}],
            "2.1.114",
            entrypoint="cli",
        )
        assert self.HEADER_PATTERN.match(value), f"Header mismatch: {value!r}"

    def test_matches_pattern_for_empty_messages(self):
        # Empty user list → cch = e3b0c (empty-string SHA-256 prefix).
        value = build_billing_header_value([], "2.1.114", entrypoint="cli")
        assert self.HEADER_PATTERN.match(value), f"Header mismatch: {value!r}"
        assert "cch=e3b0c;" in value

    def test_matches_pattern_for_list_content(self):
        value = build_billing_header_value(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "hello"},
                        {"type": "text", "text": " world"},
                    ],
                }
            ],
            "2.1.114",
            entrypoint="cli",
        )
        assert self.HEADER_PATTERN.match(value), f"Header mismatch: {value!r}"
        assert f"cch={compute_cch('hello world')};" in value

    def test_uses_provided_entrypoint(self):
        value = build_billing_header_value(
            [{"role": "user", "content": "x"}],
            "2.1.114",
            entrypoint="cli",
        )
        assert "cc_entrypoint=cli;" in value


# ---------------------------------------------------------------------------
# Session / request IDs
# ---------------------------------------------------------------------------


class TestSessionAndRequestIds:
    def test_get_session_id_is_stable_within_process(self):
        a = get_session_id()
        b = get_session_id()
        assert a == b

    def test_get_session_id_is_valid_uuid(self):
        # Just try parsing — raises ValueError on bad input.
        uuid.UUID(get_session_id())

    def test_new_request_id_returns_distinct_values(self):
        ids = {new_request_id() for _ in range(10)}
        assert len(ids) == 10

    def test_new_request_id_returns_valid_uuid(self):
        for _ in range(5):
            uuid.UUID(new_request_id())


# ---------------------------------------------------------------------------
# is_billing_header_text
# ---------------------------------------------------------------------------


class TestIsBillingHeaderText:
    def test_recognises_real_billing_header(self):
        value = build_billing_header_value(
            [{"role": "user", "content": "hi"}],
            "2.1.114",
            entrypoint="cli",
        )
        assert is_billing_header_text(value) is True

    def test_recognises_bare_prefix(self):
        assert is_billing_header_text("x-anthropic-billing-header: foo") is True

    def test_rejects_unrelated_string(self):
        assert is_billing_header_text("You are Claude Code") is False

    def test_rejects_none(self):
        assert is_billing_header_text(None) is False

    def test_rejects_non_string(self):
        assert is_billing_header_text(12345) is False
