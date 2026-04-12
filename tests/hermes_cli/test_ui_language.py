"""Tests for CLI/TUI language helpers."""

from hermes_cli.ui_language import (
    alias_description,
    command_description,
    command_help_description,
    display_language_name,
    normalize_display_language,
    parse_display_language,
    ui_text,
)


def test_normalize_display_language_defaults_to_english():
    assert normalize_display_language(None) == "en"
    assert normalize_display_language("") == "en"


def test_normalize_display_language_accepts_chinese_aliases():
    assert normalize_display_language("zh") == "zh-CN"
    assert normalize_display_language("中文") == "zh-CN"
    assert parse_display_language("cn") == "zh-CN"


def test_ui_text_returns_chinese_translation():
    assert ui_text("help_header", "zh-CN") == "(^_^)? 可用命令"
    assert "提示" in ui_text("help_tip_chat", "zh-CN")


def test_command_description_translates_known_commands():
    translated = command_description("lang", "Switch the TUI display language", "zh-CN")
    assert "界面语言" in translated


def test_command_help_description_localizes_usage_suffix():
    translated = command_help_description("skin", "Show or change the display skin/theme", "[name]", "zh-CN")
    assert "查看或切换显示皮肤/主题" in translated
    assert "用法" in translated
    assert "/skin [name]" in translated


def test_alias_description_localizes_suffix():
    assert "别名" in alias_description("显示可用命令", "help", "zh-CN")


def test_display_language_name_is_human_readable():
    assert display_language_name("en") == "English"
    assert display_language_name("zh-CN") == "中文"
