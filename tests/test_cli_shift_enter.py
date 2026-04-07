from prompt_toolkit.input import ansi_escape_sequences
from prompt_toolkit.input.vt100_parser import Vt100Parser
from prompt_toolkit.keys import Keys

import cli as cli_mod


def test_shift_enter_sequence_remaps_to_newline(monkeypatch):
    """Ensure the CSI 27;2;13~ sequence gets remapped to the newline handler."""
    monkeypatch.setitem(
        ansi_escape_sequences.ANSI_SEQUENCES,
        cli_mod._XTERM_SHIFT_ENTER_SEQUENCE,
        Keys.ControlM,
    )

    assert cli_mod._enable_shift_enter_newline_support() is True
    assert (
        ansi_escape_sequences.ANSI_SEQUENCES[cli_mod._XTERM_SHIFT_ENTER_SEQUENCE]
        == Keys.ControlJ
    )

    seen = []
    parser = Vt100Parser(seen.append)
    parser.feed_and_flush(cli_mod._XTERM_SHIFT_ENTER_SEQUENCE)

    assert [keypress.key for keypress in seen] == [Keys.ControlJ]


def test_regular_enter_still_submits():
    """Plain Enter should remain mapped to ControlM/submit."""
    seen = []
    parser = Vt100Parser(seen.append)
    parser.feed_and_flush("\r")
    assert [keypress.key for keypress in seen] == [Keys.ControlM]
