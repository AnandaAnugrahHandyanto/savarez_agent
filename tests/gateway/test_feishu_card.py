"""Tests for gateway.platforms.feishu_card."""
from __future__ import annotations
import pytest
from gateway.platforms.feishu_card import format_token_count

class TestFormatTokenCount:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (0, "0"),
            (48, "48"),
            (999, "999"),
            (1000, "1.0k"),
            (1100, "1.1k"),
            (11100, "11.1k"),
            (999999, "1000.0k"),
            (1000000, "1.0M"),
            (3400000, "3.4M"),
        ],
    )
    def test_format_token_count(self, value, expected):
        assert format_token_count(value) == expected

    def test_format_token_count_negative_returns_zero(self):
        assert format_token_count(-5) == "0"
