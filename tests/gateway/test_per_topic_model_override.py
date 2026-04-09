"""Tests for per-topic model/provider override in gateway/run.py.

Covers _resolve_per_topic_model_override — a pure helper that reads
telegram.groups.<chat_id>.topics.<thread_id>.model/provider from config.
"""

from types import SimpleNamespace

import pytest

from gateway.run import _resolve_per_topic_model_override


def _source(chat_id="-1001234567890", thread_id="42"):
    return SimpleNamespace(chat_id=chat_id, thread_id=thread_id)


def _config(model=None, provider=None, chat_id="-1001234567890", thread_id="42"):
    topic = {"agent_id": "main"}
    if model:
        topic["model"] = model
    if provider:
        topic["provider"] = provider
    return {
        "telegram": {
            "groups": {
                chat_id: {
                    "topics": {
                        thread_id: topic
                    }
                }
            }
        }
    }


# ── no-op cases ──

def test_returns_none_none_when_source_is_none():
    assert _resolve_per_topic_model_override({}, None) == (None, None)


def test_returns_none_none_when_no_thread_id():
    source = SimpleNamespace(chat_id="-100123", thread_id=None)
    assert _resolve_per_topic_model_override(_config(), source) == (None, None)


def test_returns_none_none_when_no_chat_id():
    source = SimpleNamespace(chat_id=None, thread_id="42")
    assert _resolve_per_topic_model_override(_config(), source) == (None, None)


def test_returns_none_none_when_chat_not_in_config():
    source = _source(chat_id="-999")
    assert _resolve_per_topic_model_override(_config(), source) == (None, None)


def test_returns_none_none_when_thread_not_in_config():
    source = _source(thread_id="999")
    assert _resolve_per_topic_model_override(_config(model="x/y"), source) == (None, None)


def test_returns_none_none_when_topic_has_no_override():
    assert _resolve_per_topic_model_override(_config(), _source()) == (None, None)


# ── override cases ──

def test_returns_model_only():
    cfg = _config(model="google/gemini-2.5-flash")
    model, provider = _resolve_per_topic_model_override(cfg, _source())
    assert model == "google/gemini-2.5-flash"
    assert provider is None


def test_returns_model_and_provider():
    cfg = _config(model="minimax/minimax-m2.7", provider="opencode-go")
    model, provider = _resolve_per_topic_model_override(cfg, _source())
    assert model == "minimax/minimax-m2.7"
    assert provider == "opencode-go"


def test_returns_provider_only():
    cfg = _config(provider="openrouter")
    model, provider = _resolve_per_topic_model_override(cfg, _source())
    assert model is None
    assert provider == "openrouter"


def test_chat_id_matched_as_string():
    """chat_id may come in as int from some platforms — must still match."""
    cfg = _config(model="x/y", chat_id="-1001234567890")
    source = SimpleNamespace(chat_id="-1001234567890", thread_id="42")
    model, _ = _resolve_per_topic_model_override(cfg, source)
    assert model == "x/y"


def test_thread_id_matched_as_string():
    cfg = _config(model="x/y", thread_id="3954")
    source = _source(thread_id="3954")
    model, _ = _resolve_per_topic_model_override(cfg, source)
    assert model == "x/y"


# ── malformed config ──

def test_graceful_when_groups_is_not_dict():
    cfg = {"telegram": {"groups": "bad"}}
    assert _resolve_per_topic_model_override(cfg, _source()) == (None, None)


def test_graceful_when_topics_is_not_dict():
    cfg = {"telegram": {"groups": {"-1001234567890": {"topics": ["bad"]}}}}
    assert _resolve_per_topic_model_override(cfg, _source()) == (None, None)


def test_graceful_when_topic_entry_is_not_dict():
    cfg = {"telegram": {"groups": {"-1001234567890": {"topics": {"42": "string"}}}}}
    assert _resolve_per_topic_model_override(cfg, _source()) == (None, None)


def test_graceful_when_telegram_section_missing():
    assert _resolve_per_topic_model_override({}, _source()) == (None, None)


def test_empty_string_model_treated_as_none():
    cfg = _config(model="", provider="openrouter")
    model, provider = _resolve_per_topic_model_override(cfg, _source())
    assert model is None
    assert provider == "openrouter"
