from unittest.mock import patch

from gateway.run import _format_verbose_tool_progress


def test_format_verbose_tool_progress_uses_tool_emoji():
    with patch("agent.display.get_tool_emoji", return_value="🔍"):
        msg = _format_verbose_tool_progress("web_search", {"query": "btc"}, preview_len=0)

    assert msg.startswith("🔍 web_search(")
    assert '"query": "btc"' in msg


def test_format_verbose_tool_progress_truncates_when_preview_len_positive():
    with patch("agent.display.get_tool_emoji", return_value="💻"):
        msg = _format_verbose_tool_progress("terminal", {"command": "x" * 80}, preview_len=30)

    assert msg.startswith("💻 terminal(")
    assert msg.endswith("...")
