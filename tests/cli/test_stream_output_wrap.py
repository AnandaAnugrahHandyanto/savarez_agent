"""Tests for word wrapping in streamed CLI output."""

import os
import re
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _make_cli_stub():
    from cli import HermesCLI

    cli = HermesCLI.__new__(HermesCLI)
    cli.show_reasoning = False
    cli.verbose = False
    cli._stream_buf = ""
    cli._stream_started = False
    cli._stream_box_opened = False
    cli._stream_prefilt = ""
    cli._stream_text_ansi = ""
    cli._stream_in_code_fence = False
    cli._in_reasoning_block = False
    cli._reasoning_box_opened = False
    cli._reasoning_buf = ""
    cli._reasoning_preview_buf = ""
    cli._deferred_content = ""
    cli._close_reasoning_box = lambda: None
    return cli


def _capture_output(mock_print):
    lines = []
    for call in mock_print.call_args_list:
        text = call.args[0]
        lines.append(ANSI_RE.sub("", text))
    return lines


def _patch_skin():
    class _Skin:
        def get_branding(self, key, default):
            return default

        def get_color(self, key, default):
            return default

    return patch("hermes_cli.skin_engine.get_active_skin", return_value=_Skin())


class TestStreamOutputWrap:
    def test_wraps_complete_prose_lines(self):
        cli = _make_cli_stub()
        prose = "This streamed prose sentence should wrap cleanly across multiple lines."

        with patch("cli._cprint") as mock_print, patch("shutil.get_terminal_size", return_value=os.terminal_size((36, 24))), _patch_skin():
            cli._emit_stream_text(prose + "\n")
            cli._flush_stream()

        lines = _capture_output(mock_print)
        body = lines[1:-1]
        assert len(body) >= 2
        assert " ".join(part.strip() for part in body).startswith("This streamed prose sentence")
        assert all(len(part) <= 36 for part in body)

    def test_wraps_partial_line_on_flush(self):
        cli = _make_cli_stub()
        prose = "Partial streamed prose should also wrap when the buffer is flushed."

        with patch("cli._cprint") as mock_print, patch("shutil.get_terminal_size", return_value=os.terminal_size((34, 24))), _patch_skin():
            cli._emit_stream_text(prose)
            cli._flush_stream()

        lines = _capture_output(mock_print)
        body = lines[1:-1]
        assert len(body) >= 2
        assert " ".join(part.strip() for part in body).startswith("Partial streamed prose")
        assert all(len(part) <= 34 for part in body)

    def test_preserves_fenced_and_indented_lines(self):
        cli = _make_cli_stub()
        with patch("cli._cprint") as mock_print, patch("shutil.get_terminal_size", return_value=os.terminal_size((28, 24))), _patch_skin():
            cli._emit_stream_text("```python\n")
            cli._emit_stream_text("print('this line should stay intact even though it is long')\n")
            cli._emit_stream_text("```\n")
            cli._emit_stream_text("    indented preformatted content that should stay intact\n")
            cli._flush_stream()

        lines = _capture_output(mock_print)
        body = lines[1:-1]
        assert "```python" in body
        assert "print('this line should stay intact even though it is long')" in body
        assert "```" in body
        assert "    indented preformatted content that should stay intact" in body
        assert not any("stay intact even though" in part and part != "print('this line should stay intact even though it is long')" for part in body)
