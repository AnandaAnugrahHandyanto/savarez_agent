from pathlib import Path

import pytest
from prompt_toolkit.key_binding import KeyBindings


@pytest.mark.parametrize("key", ["c-S-c"])
def test_prompt_toolkit_rejects_non_portable_key_names(key):
    kb = KeyBindings()

    with pytest.raises(Exception, match="Invalid key"):
        kb.add(key)(lambda event: None)


def test_cli_does_not_register_invalid_ctrl_shift_c_binding():
    source = Path(__file__).resolve().parents[2] / "cli.py"

    assert "@kb.add('c-S-c')" not in source.read_text()
