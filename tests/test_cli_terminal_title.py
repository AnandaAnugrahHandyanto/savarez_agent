"""Tests for Hermes CLI terminal title helpers."""

from cli import HermesCLI


def test_clean_terminal_title_removes_controls_and_truncates():
    assert HermesCLI._clean_terminal_title("  修复\n窗口标题1234567890  ", max_len=8) == "修复 窗口标题1"


def test_update_terminal_title_from_session_title_uses_summary_without_pid(monkeypatch):
    cli = HermesCLI.__new__(HermesCLI)
    writes = []
    monkeypatch.setattr("sys.stdout.write", lambda value: writes.append(value))
    monkeypatch.setattr("sys.stdout.flush", lambda: None)

    cli._update_terminal_title_from_session_title("窗口标题概要")

    assert writes == ["\033]0;Hermes CLI 窗口标题概要\007"]
    assert "123" not in writes[0]
