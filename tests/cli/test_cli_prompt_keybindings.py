"""Tests for Hermes CLI prompt key binding semantics."""

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from cli import _bind_prompt_submit_keys


def _bound_key_tuples(kb: KeyBindings):
    return {binding.keys for binding in kb.bindings}


def test_submit_binding_uses_normal_enter_only_not_ctrl_j():
    """Ctrl+Enter arrives as c-j in many terminals and must stay multiline."""
    kb = KeyBindings()

    def submit_handler(event):
        pass

    _bind_prompt_submit_keys(kb, submit_handler)

    keys = _bound_key_tuples(kb)
    assert (Keys.ControlM,) in keys  # prompt_toolkit's normal Enter / CR
    assert (Keys.ControlJ,) not in keys  # Ctrl+Enter / LF is reserved for newline
