"""Comprehensive tests for ANSI escape sequence stripping (ECMA-48).

The strip_ansi function in tools/ansi_strip.py is the source-level fix for
ANSI codes leaking into the model's context via terminal/execute_code output.
It must strip ALL terminal escape sequences while preserving legitimate text.
"""

from tools.ansi_strip import strip_ansi


class TestStripAnsiBasicSGR:
    """Select Graphic Rendition — the most common ANSI sequences."""

    def test_reset(self):
        assert strip_ansi("\x1b[0m") == ""

    def test_color(self):
        assert strip_ansi("\x1b[31;1m") == ""

    def test_truecolor_semicolon(self):
        assert strip_ansi("\x1b[38;2;255;0;0m") == ""

    def test_truecolor_colon_separated(self):
        """Modern terminals use colon-separated SGR params."""
        assert strip_ansi("\x1b[38:2:255:0:0m") == ""
        assert strip_ansi("\x1b[48:2:0:255:0m") == ""


class TestStripAnsiCSIPrivateMode:
    """CSI sequences with ? prefix (DEC private modes)."""

    def test_cursor_show_hide(self):
        assert strip_ansi("\x1b[?25h") == ""
        assert strip_ansi("\x1b[?25l") == ""

    def test_alt_screen(self):
        assert strip_ansi("\x1b[?1049h") == ""
        assert strip_ansi("\x1b[?1049l") == ""

    def test_bracketed_paste(self):
        assert strip_ansi("\x1b[?2004h") == ""


class TestStripAnsiCSIIntermediate:
    """CSI sequences with intermediate bytes (space, etc.)."""

    def test_cursor_shape(self):
        assert strip_ansi("\x1b[0 q") == ""
        assert strip_ansi("\x1b[2 q") == ""
        assert strip_ansi("\x1b[6 q") == ""


class TestStripAnsiOSC:
    """Operating System Command sequences."""

    def test_bel_terminator(self):
        assert strip_ansi("\x1b]0;title\x07") == ""

    def test_st_terminator(self):
        assert strip_ansi("\x1b]0;title\x1b\\") == ""

    def test_hyperlink_preserves_text(self):
        assert strip_ansi(
            "\x1b]8;;https://example.com\x1b\\click\x1b]8;;\x1b\\"
        ) == "click"


class TestStripAnsiDECPrivate:
    """DEC private / Fp escape sequences."""

    def test_save_restore_cursor(self):
        assert strip_ansi("\x1b7") == ""
        assert strip_ansi("\x1b8") == ""

    def test_keypad_modes(self):
        assert strip_ansi("\x1b=") == ""
        assert strip_ansi("\x1b>") == ""


class TestStripAnsiFe:
    """Fe (C1 as 7-bit) escape sequences."""

    def test_reverse_index(self):
        assert strip_ansi("\x1bM") == ""

    def test_reset_terminal(self):
        assert strip_ansi("\x1bc") == ""

    def test_index_and_newline(self):
        assert strip_ansi("\x1bD") == ""
        assert strip_ansi("\x1bE") == ""


class TestStripAnsiNF:
    """nF (character set selection) sequences."""

    def test_charset_selection(self):
        assert strip_ansi("\x1b(A") == ""
        assert strip_ansi("\x1b(B") == ""
        assert strip_ansi("\x1b(0") == ""


class TestStripAnsiDCS:
    """Device Control String sequences."""

    def test_dcs(self):
        assert strip_ansi("\x1bP+q\x1b\\") == ""


class TestStripAnsi8BitC1:
    """8-bit C1 control characters."""

    def test_8bit_csi(self):
        assert strip_ansi("\x9b31m") == ""
        assert strip_ansi("\x9b38;2;255;0;0m") == ""

    def test_8bit_standalone(self):
        assert strip_ansi("\x9c") == ""
        assert strip_ansi("\x9d") == ""
        assert strip_ansi("\x90") == ""


class TestStripAnsiRealWorld:
    """Real-world contamination scenarios from bug reports."""

    def test_colored_shebang(self):
        """The original reported bug: shebang corrupted by color codes."""
        assert strip_ansi(
            "\x1b[32m#!/usr/bin/env python3\x1b[0m\nprint('hello')"
        ) == "#!/usr/bin/env python3\nprint('hello')"

    def test_stacked_sgr(self):
        assert strip_ansi(
            "\x1b[1m\x1b[31m\x1b[42mhello\x1b[0m"
        ) == "hello"

    def test_ansi_mid_code(self):
        assert strip_ansi(
            "def foo(\x1b[33m):\x1b[0m\n    return 42"
        ) == "def foo():\n    return 42"


class TestStripAnsiPassthrough:
    """Clean content must pass through unmodified."""

    def test_plain_text(self):
        assert strip_ansi("normal text") == "normal text"

    def test_empty(self):
        assert strip_ansi("") == ""

    def test_none(self):
        assert strip_ansi(None) is None

    def test_whitespace_preserved(self):
        assert strip_ansi("line1\nline2\ttab") == "line1\nline2\ttab"

    def test_unicode_safe(self):
        assert strip_ansi("emoji 🎉 and ñ café") == "emoji 🎉 and ñ café"

    def test_backslash_in_code(self):
        code = "path = 'C:\\\\Users\\\\test'"
        assert strip_ansi(code) == code

    def test_square_brackets_in_code(self):
        """Array indexing must not be confused with CSI."""
        code = "arr[0] = arr[31]"
        assert strip_ansi(code) == code




class TestStripAnsiOSC1337Preservation:
    """Tests for OSC 1337 (iTerm2 inline images) preservation."""

    def test_osc1337_basic_preserved(self):
        """OSC 1337 should be preserved when preserve_osc1337=True."""
        seq = "\x1b]1337;name=test\x07"
        result = strip_ansi(seq, preserve_osc1337=True)
        assert "1337" in result
        assert seq in result

    def test_osc1337_with_text(self):
        """Text around OSC 1337 should be preserved."""
        text = "Before\x1b]1337;name=image\x07After"
        result = strip_ansi(text, preserve_osc1337=True)
        assert "Before" in result
        assert "After" in result
        assert "1337" in result

    def test_osc1337_with_other_ansi(self):
        """OSC 1337 preserved, other ANSI stripped."""
        text = "\x1b[31mRed\x1b[0m\x1b]1337;name=img\x07"
        result = strip_ansi(text, preserve_osc1337=True)
        # Color codes should be stripped
        assert "\x1b[31m" not in result
        assert "\x1b[0m" not in result
        # But text and OSC 1337 should remain
        assert "Red" in result
        assert "1337" in result

    def test_osc1337_st_terminator(self):
        """OSC 1337 with ST terminator should be preserved."""
        seq = "\x1b]1337;name=test;size=100\x1b\\"
        result = strip_ansi(seq, preserve_osc1337=True)
        assert "1337" in result

    def test_osc1337_bel_terminator(self):
        """OSC 1337 with BEL terminator should be preserved."""
        seq = "\x1b]1337;name=test;size=100\x07"
        result = strip_ansi(seq, preserve_osc1337=True)
        assert "1337" in result

    def test_osc_non1337_stripped(self):
        """Non-1337 OSC sequences should be stripped even with preserve_osc1337=True."""
        text = "Before\x1b]0;title\x07After\x1b]1337;name=img\x07Done"
        result = strip_ansi(text, preserve_osc1337=True)
        # Title OSC should be stripped
        assert "\x1b]0" not in result
        # But 1337 and text should remain
        assert "Before" in result
        assert "After" in result
        assert "Done" in result
        assert "1337" in result

    def test_preserve_osc1337_false_strips_all(self):
        """With preserve_osc1337=False (default), all ANSI including 1337 should be stripped."""
        text = "Text\x1b]1337;name=img\x07More"
        result = strip_ansi(text, preserve_osc1337=False)
        assert "Text" in result
        assert "More" in result
        # OSC 1337 should be stripped
        assert "1337" not in result

    def test_osc1337_with_base64_data(self):
        """OSC 1337 with actual base64 image data should be preserved."""
        # Realistic OSC 1337: iTerm2 inline image format
        text = "Image:\x1b]1337;name=bG9nbw==;width=100%;preserveAspectRatio=1:aGVsbG8gd29ybGQ=\x07Done"
        result = strip_ansi(text, preserve_osc1337=True)
        assert "Image:" in result
        assert "Done" in result
        assert "1337" in result

    def test_multiple_osc1337_sequences(self):
        """Multiple OSC 1337 sequences should all be preserved."""
        text = "\x1b]1337;name=img1\x07\x1b]1337;name=img2\x07\x1b]1337;name=img3\x07"
        result = strip_ansi(text, preserve_osc1337=True)
        assert result.count("1337") == 3

    def test_backward_compatibility_default_false(self):
        """Default behavior (preserve_osc1337=False) should strip OSC 1337."""
        text = "\x1b]1337;name=img\x07"
        result = strip_ansi(text)  # No parameter = False
        assert "1337" not in result
