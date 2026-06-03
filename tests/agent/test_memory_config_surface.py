"""Tests for the Desktop memory-provider config surface (ABC layer).

Covers field normalization/derivation (back-compat with legacy schemas),
the default conventional reader, secret masking, and the assembled
``desktop_config_surface`` payload.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import pytest

from agent.memory_config_surface import (
    KIND_BOOL,
    KIND_NUMBER,
    KIND_SECRET,
    KIND_SELECT,
    KIND_TEXT,
    TIER_ADVANCED,
    TIER_SAFE,
    default_read_config,
    enrich_schema,
    normalize_field,
)
from agent.memory_provider import MemoryProvider


# --- field derivation / back-compat -----------------------------------------

def test_secret_derives_kind_and_env_key():
    f = normalize_field(
        {"key": "api_key", "description": "X", "secret": True, "env_var": "FOO_KEY"}
    )
    assert f["kind"] == KIND_SECRET
    assert f["env_key"] == "FOO_KEY"
    assert f["tier"] == TIER_SAFE  # default


def test_choices_derive_select_with_options():
    f = normalize_field({"key": "mode", "choices": ["cloud", "local_external"]})
    assert f["kind"] == KIND_SELECT
    assert [o["value"] for o in f["options"]] == ["cloud", "local_external"]


def test_plain_field_is_text():
    assert normalize_field({"key": "base_url"})["kind"] == KIND_TEXT


def test_explicit_kind_respected():
    assert normalize_field({"key": "x", "kind": KIND_BOOL})["kind"] == KIND_BOOL
    assert normalize_field({"key": "y", "kind": KIND_NUMBER})["kind"] == KIND_NUMBER


def test_label_prettifies_snake_and_camel():
    assert normalize_field({"key": "api_key"})["label"] == "Api Key"
    assert normalize_field({"key": "baseUrl"})["label"] == "Base Url"


def test_explicit_label_wins():
    assert normalize_field({"key": "k", "label": "Custom"})["label"] == "Custom"


def test_tier_advanced_passthrough_and_invalid_falls_back_safe():
    assert normalize_field({"key": "k", "tier": "advanced"})["tier"] == TIER_ADVANCED
    assert normalize_field({"key": "k", "tier": "bogus"})["tier"] == TIER_SAFE


def test_enrich_skips_keyless_fields():
    out = enrich_schema([{"key": "a"}, {"description": "no key"}, {"key": "b"}])
    assert [f["key"] for f in out] == ["a", "b"]


# --- default conventional reader ---------------------------------------------

def _write_provider_config(home, name, data):
    d = home / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps(data), encoding="utf-8")


def test_default_reader_returns_values_and_defaults(tmp_path):
    schema = [
        {"key": "api_url", "default": "https://default"},
        {"key": "bank_id", "default": "hermes"},
    ]
    _write_provider_config(tmp_path, "demo", {"api_url": "https://custom"})
    state = default_read_config(schema, "demo", str(tmp_path))
    assert state["api_url"] == {"value": "https://custom", "is_set": True}
    # falls back to schema default when not in file
    assert state["bank_id"]["value"] == "hermes"


def test_default_reader_never_returns_secret_value(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_KEY", "super-secret")
    schema = [{"key": "api_key", "secret": True, "env_var": "DEMO_KEY"}]
    state = default_read_config(schema, "demo", str(tmp_path))
    assert state["api_key"]["value"] == ""
    assert state["api_key"]["is_set"] is True
    assert "super-secret" not in json.dumps(state)


def test_default_reader_secret_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("DEMO_KEY", raising=False)
    schema = [{"key": "api_key", "secret": True, "env_var": "DEMO_KEY"}]
    state = default_read_config(schema, "demo", str(tmp_path))
    assert state["api_key"] == {"value": "", "is_set": False}


# --- desktop_config_surface assembly via the ABC -----------------------------

class _FakeProvider(MemoryProvider):
    """Minimal provider exercising the default surface path."""

    @property
    def name(self) -> str:
        return "demo"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "api_key", "secret": True, "env_var": "DEMO_KEY", "description": "key"},
            {"key": "api_url", "default": "https://default"},
            {"key": "mode", "choices": ["cloud", "local"], "tier": "advanced"},
        ]


class _NoConfigProvider(MemoryProvider):
    @property
    def name(self) -> str:
        return "builtin"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []


def test_desktop_surface_masks_secret_and_carries_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_KEY", "abc123")
    _write_provider_config(tmp_path, "demo", {"api_url": "https://custom"})
    surface = _FakeProvider().desktop_config_surface(str(tmp_path))

    assert surface["name"] == "demo"
    fields = {f["key"]: f for f in surface["fields"]}
    assert fields["api_key"]["kind"] == "secret"
    assert fields["api_key"]["value"] == ""
    assert fields["api_key"]["is_set"] is True
    assert fields["api_url"]["value"] == "https://custom"
    assert fields["mode"]["kind"] == "select"
    assert fields["mode"]["tier"] == "advanced"
    assert "abc123" not in json.dumps(surface)


def test_provider_without_schema_renders_empty(tmp_path):
    surface = _NoConfigProvider().desktop_config_surface(str(tmp_path))
    assert surface["fields"] == []
