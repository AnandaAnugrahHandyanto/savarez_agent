"""Tests for ``BasePlatformAdapter.prepare_tts_text`` — the per-platform
text-cleanup that runs immediately before handing a reply to the TTS tool.

The default strips markdown-like characters that would otherwise be read
literally (``*_`#()[]``). Square brackets are intentionally **preserved**
when the active TTS provider is Inworld TTS-2 because that backend treats
``[directive]`` as performance steering (instruction tags like
``[say excitedly]``, non-verbal tags like ``[laugh]``). Stripping the
brackets would turn the directive prose into literal speech — the bug this
gating exists to prevent.
"""
from __future__ import annotations

import pytest

from gateway.platforms.base import BasePlatformAdapter


# ``BasePlatformAdapter`` is ABC; ``prepare_tts_text`` only touches its
# ``text`` argument, so we exercise it as an unbound function.
prepare = BasePlatformAdapter.prepare_tts_text


def _patch_tts(monkeypatch, provider: str, model_id: str = "") -> None:
    """Mirror the patch helper from ``TestInworldTts2Rules`` so test setup
    reads the same across the two TTS-2 gating call sites."""
    cfg = {"provider": provider, "inworld": {"model_id": model_id}}
    monkeypatch.setattr("tools.tts_tool._load_tts_config", lambda: cfg)
    monkeypatch.setattr("tools.tts_tool._get_provider", lambda _cfg: provider)


# -- default behavior: brackets stripped for non-TTS-2 providers ------------

def test_default_strips_brackets_when_provider_unknown(monkeypatch):
    """Config-load failure (or no provider configured) must fall back to the
    strip-all default — readers of bare ``[label]`` would otherwise hear the
    label spoken aloud."""
    def _boom():
        raise RuntimeError("config unreadable")
    monkeypatch.setattr("tools.tts_tool._load_tts_config", _boom)
    out = prepare(None, "[say excitedly] hello (aside) **bold**")
    assert out == "say excitedly hello aside bold"


def test_elevenlabs_strips_brackets(monkeypatch):
    _patch_tts(monkeypatch, "elevenlabs")
    out = prepare(None, "[say excitedly] hello")
    assert out == "say excitedly hello"


def test_openai_strips_brackets(monkeypatch):
    _patch_tts(monkeypatch, "openai")
    out = prepare(None, "[laugh] ok")
    assert out == "laugh ok"


def test_inworld_old_model_strips_brackets(monkeypatch):
    """Inworld TTS 1.x does not honor bracket directives — keep stripping."""
    _patch_tts(monkeypatch, "inworld", "inworld-tts-1.5-max")
    out = prepare(None, "[say excitedly] hello")
    assert out == "say excitedly hello"


# -- bracket preservation: only for Inworld + inworld-tts-2 -----------------

def test_inworld_tts2_preserves_brackets(monkeypatch):
    _patch_tts(monkeypatch, "inworld", "inworld-tts-2")
    text = "[say excitedly with a high pitch and fast pace] Oh you want me to show off the voice tags?"
    out = prepare(None, text)
    assert out == text


def test_inworld_tts2_preserves_non_verbal_tags(monkeypatch):
    _patch_tts(monkeypatch, "inworld", "inworld-tts-2")
    text = "[laugh] okay here's one with a sigh. [sigh] long night coding huh?"
    out = prepare(None, text)
    assert out == text


def test_inworld_tts2_preserves_multiple_directives(monkeypatch):
    """The reported repro: multi-paragraph reply with several directives.
    Pre-fix this came out with every bracket character deleted, which fed
    the directive prose into Inworld as literal speech."""
    _patch_tts(monkeypatch, "inworld", "inworld-tts-2")
    text = (
        "[say excitedly with a high pitch and fast pace] One.\n\n"
        "[sound concerned with a measured pace and low tone] Two.\n\n"
        "[laugh] Three. [sigh] Four."
    )
    out = prepare(None, text)
    assert out == text


def test_inworld_tts2_model_id_case_insensitive(monkeypatch):
    """Mirrors ``TestInworldTts2Rules.test_model_id_is_case_insensitive`` —
    config keys are user-edited and people will capitalise the model id."""
    _patch_tts(monkeypatch, "inworld", "Inworld-TTS-2")
    out = prepare(None, "[laugh] ok")
    assert out == "[laugh] ok"


def test_inworld_tts2_provider_case_insensitive(monkeypatch):
    _patch_tts(monkeypatch, "Inworld", "inworld-tts-2")
    out = prepare(None, "[laugh] ok")
    assert out == "[laugh] ok"


# -- other markdown still stripped under TTS-2 ------------------------------

def test_inworld_tts2_still_strips_non_bracket_markdown(monkeypatch):
    """Only the bracket characters get reprieved — asterisks, backticks,
    parens, hashes, and underscores remain markdown noise even with TTS-2.
    TTS-2's emphasis convention is CAPS, not asterisks."""
    _patch_tts(monkeypatch, "inworld", "inworld-tts-2")
    out = prepare(None, "[say excitedly] **bold** `code` (aside) # header _underscore_")
    assert out == "[say excitedly] bold code aside  header underscore"


# -- truncation and whitespace ----------------------------------------------

def test_truncates_to_4000_chars(monkeypatch):
    _patch_tts(monkeypatch, "inworld", "inworld-tts-2")
    long_text = "[laugh] " + ("a" * 5000)
    out = prepare(None, long_text)
    assert len(out) == 4000


def test_strips_surrounding_whitespace(monkeypatch):
    _patch_tts(monkeypatch, "inworld", "inworld-tts-2")
    out = prepare(None, "   [laugh] hello   \n")
    assert out == "[laugh] hello"
