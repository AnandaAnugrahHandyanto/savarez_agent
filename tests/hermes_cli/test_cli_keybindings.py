"""Regression tests for prompt_toolkit CLI key bindings."""

import ast
from pathlib import Path

import pytest
from prompt_toolkit.key_binding import KeyBindings


CLI_PATH = Path(__file__).resolve().parents[2] / "cli.py"


def _literal_key_sequences_from_cli():
    """Return literal key sequences passed to ``*.add(...)`` in cli.py.

    prompt_toolkit validates key names when decorators are registered. A bad
    key name in the interactive CLI prevents ``hermes`` from starting, so keep
    this lightweight static regression test around for startup safety.
    """
    tree = ast.parse(CLI_PATH.read_text(), filename=str(CLI_PATH))
    sequences = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add":
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "kb":
            continue

        literal_keys = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                literal_keys.append(arg.value)
            else:
                # Dynamic bindings such as kb.add(str(_num), ...) are covered
                # by runtime tests; this check is for hard-coded key names.
                literal_keys = []
                break
        if literal_keys:
            sequences.append(tuple(literal_keys))

    return sequences


@pytest.mark.parametrize("keys", _literal_key_sequences_from_cli())
def test_cli_literal_keybindings_are_valid_prompt_toolkit_keys(keys):
    """Every hard-coded key binding in cli.py must be accepted by prompt_toolkit."""
    kb = KeyBindings()

    @kb.add(*keys)
    def _handler(event):  # pragma: no cover - registration is the assertion
        return None
