"""Tests for the model picker: 'Enter custom model name' must be visually prominent.

Before the fix, 'Enter custom model name' was appended at the end of the
choices list — buried below long OpenRouter / Nous catalogs.  Users on
fast-moving providers like minimax, where the curated list is always a
release behind, had no obvious way to type a model name they saw in the
provider's dashboard.

The fix promotes the custom-name entry to a stable, eye-catching slot
right after the current-model entry, with a leading symbol and a clear
hint.  The Skip entry stays at the bottom.
"""

import io
import sys
import types
from contextlib import redirect_stdout
from unittest.mock import patch

from hermes_cli.auth import _prompt_model_selection


# ---------------------------------------------------------------------------
# Curses / arrow-key menu path
# ---------------------------------------------------------------------------


def _capture_curses_choices(monkeypatch, model_ids, current_model=""):
    """Call _prompt_model_selection with a fake curses_radiolist and
    return the list of choices the picker would have shown."""
    captured = {}

    def fake_radiolist(title, items, **kwargs):
        captured["title"] = title
        captured["items"] = list(items)
        captured["kwargs"] = kwargs
        return -1  # user pressed ESC

    monkeypatch.setattr("hermes_cli.curses_ui.curses_radiolist", fake_radiolist)
    _prompt_model_selection(model_ids, current_model=current_model)
    return captured


def test_custom_model_entry_promoted_to_second_slot_in_curses_picker(monkeypatch):
    """'Enter custom model name' must come right after the current model
    — not buried at the end of a long list."""
    captured = _capture_curses_choices(
        monkeypatch,
        ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2"],
        current_model="MiniMax-M3",
    )

    items = captured["items"]
    assert items, "curses picker was never invoked (curses missing?)"
    # First slot is the current model.
    assert "MiniMax-M3" in items[0]
    # Second slot is the custom-name entry.
    assert "custom" in items[1].lower(), (
        f"Expected 'Enter custom model name' at index 1, got: {items[1]!r}"
    )
    # The custom entry must be visually distinct (symbol/prefix).
    assert any(sym in items[1] for sym in ("→", "✎", "▸", "•", "*")), (
        f"Custom entry should have a leading symbol; got: {items[1]!r}"
    )


def test_custom_model_entry_first_when_no_current_model(monkeypatch):
    """With no current model, the custom-name entry is the very first choice."""
    captured = _capture_curses_choices(
        monkeypatch, ["MiniMax-M3", "MiniMax-M2.7"], current_model=""
    )
    items = captured["items"]
    assert items, "curses picker was never invoked"
    assert "custom" in items[0].lower()


def test_skip_entry_always_last_in_curses_picker(monkeypatch):
    """Skip must remain at the bottom (cancel-out is the safest default)."""
    captured = _capture_curses_choices(monkeypatch, ["a", "b", "c"])
    items = captured["items"]
    assert "skip" in items[-1].lower()


# ---------------------------------------------------------------------------
# Numbered-list fallback path
# ---------------------------------------------------------------------------


def _force_numbered_fallback(monkeypatch):
    """Make the curses_radiolist import raise ImportError so the function
    falls through to the numbered-list branch.  This mirrors what happens
    on Windows non-curses sessions / SSH without TTY."""
    fake = types.ModuleType("hermes_cli.curses_ui")
    def _raise(_name):
        raise ImportError("simulated missing curses")
    fake.__getattr__ = _raise  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "hermes_cli.curses_ui", fake)


def test_custom_model_entry_printed_with_symbol_in_numbered_fallback(monkeypatch):
    """In the non-curses fallback, the printed line for the custom-name
    slot must include a leading symbol so the user can spot it without
    scanning the whole numbered list."""
    _force_numbered_fallback(monkeypatch)

    buf = io.StringIO()
    with redirect_stdout(buf), patch("builtins.input", return_value=""):
        _prompt_model_selection(
            ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.5"],
            current_model="MiniMax-M3",
        )

    output = buf.getvalue()
    # Locate the line for the custom-name slot ("n+1" = 4 in this case).
    custom_lines = [
        line for line in output.splitlines() if "custom" in line.lower()
    ]
    assert custom_lines, (
        f"Expected a 'custom model' line in the numbered menu.\nGot:\n{output}"
    )
    assert any(sym in custom_lines[0] for sym in ("→", "✎", "▸", "•", "*")), (
        f"Custom-name line should have a leading symbol.\n"
        f"Got: {custom_lines[0]!r}\nFull output:\n{output}"
    )


def test_numbered_fallback_custom_slot_still_works(monkeypatch):
    """Regression guard: the custom-name slot must still resolve to the
    input() prompt and return what the user typed, even after we move
    it visually.  New layout (3 models with current_model == ordered[0]):
        1. MiniMax-M3  (current)
        2. → Enter custom model name…  ← custom slot
        3. MiniMax-M2.7
        4. MiniMax-M2.5
        5. Skip (keep current)
    """
    _force_numbered_fallback(monkeypatch)

    with patch("builtins.input", side_effect=["2", "my-minimax-m4-experimental"]):
        result = _prompt_model_selection(
            ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.5"],
            current_model="MiniMax-M3",
        )

    assert result == "my-minimax-m4-experimental"
