"""Unit tests for ``hermes_cli.model_switch._model_entry_id``.

The normalizer is the source of truth for collapsing every config
``models:`` entry shape Hermes accepts down to a plain id string.
Locked down here so the picker UI (Dashboard + TUI) can keep relying
on string-only model lists end-to-end.  See issue #32334 for the
crash the list-of-dicts shape used to cause.
"""

from __future__ import annotations

import pytest

from hermes_cli.model_switch import _model_entry_id


class TestStringInput:
    def test_returns_plain_string(self):
        assert _model_entry_id("gpt-4") == "gpt-4"

    def test_strips_whitespace(self):
        assert _model_entry_id("  gpt-4  ") == "gpt-4"

    def test_empty_returns_empty(self):
        assert _model_entry_id("") == ""

    def test_whitespace_only_returns_empty(self):
        assert _model_entry_id("   \t  ") == ""


class TestDictInput:
    """Hand-edited / imported configs commonly use list-of-dict shape,
    e.g. ``models: [{id: qwen36-mtp, name: Qwen3.6 MTP}]`` — issue #32334.
    """

    def test_id_field_preferred(self):
        assert _model_entry_id({"id": "qwen36-mtp", "name": "Qwen3.6 MTP"}) == "qwen36-mtp"

    def test_model_field_fallback(self):
        assert _model_entry_id({"model": "gpt-4", "context_length": 8192}) == "gpt-4"

    def test_name_field_last_resort(self):
        # Some legacy export tools only set ``name``.
        assert _model_entry_id({"name": "claude-opus-4-7"}) == "claude-opus-4-7"

    def test_id_wins_over_model_and_name(self):
        assert (
            _model_entry_id({"id": "winner", "model": "loser", "name": "loser"})
            == "winner"
        )

    def test_empty_id_falls_through_to_model(self):
        # An empty/whitespace ``id`` MUST NOT be picked over a real
        # fallback — otherwise we'd silently insert blank picker rows.
        assert _model_entry_id({"id": "  ", "model": "claude-opus-4-7"}) == "claude-opus-4-7"

    def test_no_string_fields_returns_empty(self):
        assert _model_entry_id({"context_length": 8192}) == ""

    def test_non_string_id_returns_empty(self):
        # ``id: 42`` (number) shouldn't be silently stringified — it
        # almost certainly indicates a malformed config that the user
        # should fix, and inserting "42" as a model id would be worse.
        assert _model_entry_id({"id": 42}) == ""

    def test_empty_dict_returns_empty(self):
        assert _model_entry_id({}) == ""


class TestEdgeCases:
    def test_none_returns_empty(self):
        assert _model_entry_id(None) == ""

    def test_list_returns_empty(self):
        # Lists are never valid model entries (they'd nest the list shape).
        # str(list) round-trips fine but the result is repr-style noise.
        assert _model_entry_id(["gpt-4"]) == ""

    def test_int_coerces_to_string(self):
        # Numeric scalars don't appear in practice but the str-fallback
        # should still produce a non-bracketed value rather than crash.
        assert _model_entry_id(42) == "42"

    def test_repr_style_string_rejected(self):
        # Anything beginning with ``<`` is repr noise (``<object at 0x…>``).
        # Letting it through would render as garbage in the picker.
        class _Custom:
            pass

        assert _model_entry_id(_Custom()) == ""
