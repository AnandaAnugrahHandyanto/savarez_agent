"""Tests for _normalize_fragmented_escapes — recovery for \\^@XX / NUL+hex
fragmented Unicode escapes emitted by some models in tool_call arguments
(#42801)."""

import json

from agent.message_sanitization import (
    _normalize_fragmented_escapes,
    _repair_tool_call_arguments,
)


class TestNormalizeFragmentedEscapes:
    def test_pre_decode_carat_at_form(self):
        raw = r'{"q":"Ume\^@e5"}'
        normalized = _normalize_fragmented_escapes(raw)
        assert json.loads(normalized) == {"q": "Umeå"}

    def test_post_decode_nul_hex_form(self):
        assert _normalize_fragmented_escapes("Ume\x00e5") == "Umeå"

    def test_lone_nul_dropped(self):
        assert _normalize_fragmented_escapes("Ume\x00") == "Ume"

    def test_clean_string_unchanged(self):
        assert _normalize_fragmented_escapes("Umeå") == "Umeå"

    def test_empty_string_unchanged(self):
        assert _normalize_fragmented_escapes("") == ""

    def test_none_unchanged(self):
        assert _normalize_fragmented_escapes(None) is None

    def test_different_non_ascii_hex(self):
        assert _normalize_fragmented_escapes("se\x00f1or") == "señor"

    def test_end_to_end_via_repair(self):
        repaired = _repair_tool_call_arguments(r'{"query":"Ume\^@e5"}', "search")
        assert json.loads(repaired) == {"query": "Umeå"}
