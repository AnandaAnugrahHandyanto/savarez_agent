"""Tests for OSC-8 hyperlink stripping in ChatConsole (issue #25939).

ChatConsole.print() must strip OSC-8 escape sequences before passing
output to prompt_toolkit's ANSI formatter, which doesn't understand
them and renders the URL/params as visible garbage.
"""

import re
from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# The regex used in cli.py — we import it via the module for white-box tests
import cli


# =========================================================================
# _strip_osc8_sequences — pure function tests
# =========================================================================

_OPEN_HYPERLINK = "\x1b]8;id=12345;https://github.com/NousResearch/hermes-agent/releases/tag/v2026.4.23\x1b\\"
_CLOSE_HYPERLINK = "\x1b]8;;\x1b\\"


def test_strip_osc8_open_and_close():
    """OSC-8 open + close wrapping text should be stripped, leaving the text."""
    raw = f"prefix{_OPEN_HYPERLINK}Hello{_CLOSE_HYPERLINK}suffix"
    result = cli._strip_osc8_sequences(raw)
    assert result == "prefixHellosuffix"


def test_strip_osc8_open_only():
    """OSC-8 open sequence alone should be removed."""
    raw = f"before{_OPEN_HYPERLINK}after"
    result = cli._strip_osc8_sequences(raw)
    assert result == "beforeafter"


def test_strip_osc8_close_only():
    """OSC-8 close sequence alone should be removed."""
    raw = f"text{_CLOSE_HYPERLINK}"
    result = cli._strip_osc8_sequences(raw)
    assert result == "text"


def test_strip_osc8_plain_text_unchanged():
    """Plain text with no OSC-8 sequences should pass through unchanged."""
    text = "Hello, world! This is a normal string."
    assert cli._strip_osc8_sequences(text) == text


def test_strip_osc8_preserves_sgr_ansi():
    """Regular SGR color/style escapes are NOT stripped."""
    text = "\x1b[31mred\x1b[0m \x1b[1mbold\x1b[0m"
    expected = text
    assert cli._strip_osc8_sequences(text) == expected


def test_strip_osc8_multiple_hyperlinks():
    """Multiple OSC-8 hyperlinks in one string are all stripped."""
    link1_open = "\x1b]8;id=a;http://example.com\x1b\\"
    link1_close = "\x1b]8;;\x1b\\"
    link2_open = "\x1b]8;id=b;http://test.org\x1b\\"
    link2_close = "\x1b]8;;\x1b\\"
    raw = f"{link1_open}first{link1_close} and {link2_open}second{link2_close}"
    result = cli._strip_osc8_sequences(raw)
    assert result == "first and second"


def test_strip_osc8_no_params():
    """OSC-8 open with empty params field (semicolons only) is handled."""
    raw = "\x1b]8;;http://example.com\x1b\\"
    result = cli._strip_osc8_sequences(raw)
    assert result == ""


def test_strip_osc8_with_sgr_nearby():
    """OSC-8 sequences interleaved with SGR codes are all stripped
    while SGR codes are preserved."""
    raw = f"\x1b[1m{_OPEN_HYPERLINK}Click here{_CLOSE_HYPERLINK}\x1b[0m"
    result = cli._strip_osc8_sequences(raw)
    assert result == "\x1b[1mClick here\x1b[0m"


# =========================================================================
# Integration test — Rich-generated output with [link=...] markup
# =========================================================================

def test_chatconsole_strips_osc8_from_rich_panel():
    """When ChatConsole.print() renders a Rich Panel with [link=...],
    the output passed to _cprint must not contain OSC-8 sequences."""
    buf = []
    with patch("cli._cprint", side_effect=lambda s: buf.append(s)):
        # Build a Panel with a hyperlinked title (same pattern as the welcome banner)
        title = "[link=https://github.com/NousResearch/hermes-agent]Hermes Agent v1.0[/link]"
        panel = Panel("content", title=title)

        cc = cli.ChatConsole()
        cc.print(panel)

    # Combine all lines
    combined = "".join(buf)

    # No OSC-8 sequences should survive
    assert "\x1b]8;" not in combined, "OSC-8 sequences leaked through ChatConsole.print()"

    # The actual label text should still be present
    assert "Hermes Agent v1.0" in combined, "Link label text was dropped"

    # The URL should NOT appear as visible text
    assert "github.com/NousResearch/" not in combined, "URL leaked as visible text"


def test_chatconsole_preserves_regular_ansi():
    """SGR color/style ANSI escapes should survive ChatConsole.print()."""
    buf = []
    with patch("cli._cprint", side_effect=lambda s: buf.append(s)):
        cc = cli.ChatConsole()
        cc.print("[bold red]Hello[/] [green]World[/]")

    combined = "".join(buf)
    assert "\x1b[1;31m" in combined, f"SGR bold+red lost, got: {repr(combined[:100])}"
    assert "\x1b[32m" in combined, f"SGR green lost, got: {repr(combined[:100])}"
    assert "Hello" in combined
    assert "World" in combined


def test_chatconsole_plain_text_passthrough():
    """Plain text without any markup passes through unchanged."""
    buf = []
    with patch("cli._cprint", side_effect=lambda s: buf.append(s)):
        cc = cli.ChatConsole()
        cc.print("Just some plain text")

    combined = "".join(buf)
    assert "Just some plain text" in combined


def test_strip_osc8_compiled_regexp():
    """Smoke test: verify the compiled regex compiles and works."""
    assert hasattr(cli, "_OSC8_PATTERN")
    assert isinstance(cli._OSC8_PATTERN, re.Pattern)
    # Should match open sequence
    assert cli._OSC8_PATTERN.search(_OPEN_HYPERLINK)
    # Should match close sequence
    assert cli._OSC8_PATTERN.search(_CLOSE_HYPERLINK)
    # Should not match plain text
    assert not cli._OSC8_PATTERN.search("just plain text")
    # Should not match SGR sequences
    assert not cli._OSC8_PATTERN.search("\x1b[31mred\x1b[0m")
