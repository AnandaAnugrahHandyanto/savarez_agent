"""Regression tests for ANSI / terminal-escape stripping in SessionDB.sanitize_title.

Before the fix, sanitize_title deleted the ESC anchor byte (0x1b is within the
0x0e-0x1f control-char class) but left the printable sequence body behind, so a
pasted "\x1b[31mRed\x1b[0m" became the visible-garbage title "[31mRed[0m".
strip_ansi() (full ECMA-48) now runs first, while the ESC anchor is still present.
"""
import pytest

from hermes_state import SessionDB


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("\x1b[31mRed\x1b[0m", "Red"),                                 # SGR colour
        ("\x1b[1mHello\x1b[0m World", "Hello World"),                  # SGR mid-string
        ("plain title", "plain title"),                                # untouched
        ("[Note] keeps brackets", "[Note] keeps brackets"),           # no bracket false-positive
        ("Résumé \U0001f680", "Résumé \U0001f680"),  # unicode / emoji preserved
    ],
)
def test_sanitize_title_strips_escapes_preserves_text(raw, expected):
    assert SessionDB.sanitize_title(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "\x1b]11;rgb:2828/2c2c/3434\x07",                  # OSC colour query, BEL-terminated
        "\x1b]8;;http://example.com\x1b\\\x1b]8;;\x1b\\",  # OSC-8 hyperlink wrapper, no text
        "\x1b[0m\x1b[1m\x1b[31m",                          # escapes only
    ],
)
def test_sanitize_title_all_escape_input_becomes_none(raw):
    # Stripped to empty -> normalized to None (existing contract).
    assert SessionDB.sanitize_title(raw) is None


def test_sanitize_title_leaves_no_escape_residue():
    raw = "\x1b[32mDeploy\x1b[0m \x1b]0;window-title\x07 done"
    out = SessionDB.sanitize_title(raw)
    assert out is not None
    assert "\x1b" not in out
    assert "[32m" not in out and "]0;" not in out
