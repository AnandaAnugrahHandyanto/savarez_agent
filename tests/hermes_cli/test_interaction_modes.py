"""Tests for session interaction mode helpers."""

from hermes_cli.interaction_modes import mode_label, mode_prompt, normalize_mode


def test_normalize_mode_accepts_known_modes_and_slash_prefixes():
    assert normalize_mode("9010") == "9010"
    assert normalize_mode("/transparency") == "transparency"


def test_normalize_mode_clears_normal_aliases():
    for value in (None, "", "normal", "/normal", "off", "clear"):
        assert normalize_mode(value) is None


def test_mode_prompt_only_returns_prompt_for_active_modes():
    assert "90/10 autonomous" in mode_prompt("9010")
    assert "transparency" in mode_prompt("transparency")
    assert mode_prompt("normal") == ""


def test_mode_label_uses_normal_fallback():
    assert mode_label("9010") == "90/10 autonomous mode"
    assert mode_label(None) == "normal mode"
