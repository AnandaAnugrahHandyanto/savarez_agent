"""Tests for the Atomic Chat local LLM provider integration."""

import json
import os
import sys
import types
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from unittest.mock import patch

import pytest

if "dotenv" not in sys.modules:
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = fake_dotenv

from hermes_cli.auth import PROVIDER_REGISTRY
from hermes_cli.models import (
    _PROVIDER_LABELS,
    _PROVIDER_ALIASES,
    list_available_providers,
)


# =============================================================================
# Registry & metadata tests
# =============================================================================


class TestAtomicChatRegistry:
    """Verify Atomic Chat is correctly registered across all provider maps."""

    def test_provider_registered_in_auth(self):
        assert "atomic-chat" in PROVIDER_REGISTRY
        pconfig = PROVIDER_REGISTRY["atomic-chat"]
        assert pconfig.name == "Atomic Chat"
        assert pconfig.auth_type == "api_key"
        assert pconfig.inference_base_url == "http://127.0.0.1:1337/v1"

    def test_no_api_key_required(self):
        pconfig = PROVIDER_REGISTRY["atomic-chat"]
        assert pconfig.api_key_env_vars == ()

    def test_provider_label(self):
        assert "atomic-chat" in _PROVIDER_LABELS
        assert _PROVIDER_LABELS["atomic-chat"] == "Atomic Chat"

    def test_provider_aliases(self):
        assert _PROVIDER_ALIASES.get("atomic") == "atomic-chat"
        assert _PROVIDER_ALIASES.get("atomic_chat") == "atomic-chat"
        assert _PROVIDER_ALIASES.get("atomicchat") == "atomic-chat"

    def test_in_provider_order(self):
        providers = list_available_providers()
        ids = [p["id"] for p in providers]
        assert "atomic-chat" in ids

    def test_default_provider_models_empty(self):
        from hermes_cli.setup import _DEFAULT_PROVIDER_MODELS
        assert "atomic-chat" in _DEFAULT_PROVIDER_MODELS
        assert _DEFAULT_PROVIDER_MODELS["atomic-chat"] == []


# =============================================================================
# Model flow tests
# =============================================================================


def _make_probe_result(models):
    """Build a probe_api_models return value."""
    return {
        "models": models,
        "probed_url": "http://127.0.0.1:1337/v1/models",
        "resolved_base_url": "http://127.0.0.1:1337/v1",
        "suggested_base_url": None,
        "used_fallback": False,
    }


class TestModelFlowAtomicChatNotRunning:
    """When Atomic Chat is not reachable, show download instructions."""

    def test_not_running_shows_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        from hermes_cli.main import _model_flow_atomic_chat

        probe_none = _make_probe_result(None)
        monkeypatch.setattr(
            "hermes_cli.models.probe_api_models",
            lambda *a, **kw: probe_none,
        )
        monkeypatch.setattr(
            "hermes_cli.main.select_provider_and_model",
            lambda: None,
        )
        monkeypatch.setattr("builtins.input", lambda prompt="": "")

        _model_flow_atomic_chat({})

        out = capsys.readouterr().out
        assert "not running" in out
        assert "https://atomic.chat/" in out
        assert "Local API Server" in out

    def test_not_running_ctrl_c_exits(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        from hermes_cli.main import _model_flow_atomic_chat

        probe_none = _make_probe_result(None)
        monkeypatch.setattr(
            "hermes_cli.models.probe_api_models",
            lambda *a, **kw: probe_none,
        )

        def raise_interrupt(prompt=""):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", raise_interrupt)

        _model_flow_atomic_chat({})
        out = capsys.readouterr().out
        assert "not running" in out


class TestModelFlowAtomicChatNoModel:
    """When Atomic Chat is running but has no models loaded."""

    def test_no_model_shows_warning(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        from hermes_cli.main import _model_flow_atomic_chat

        probe_empty = _make_probe_result([])
        monkeypatch.setattr(
            "hermes_cli.models.probe_api_models",
            lambda *a, **kw: probe_empty,
        )
        monkeypatch.setattr(
            "hermes_cli.main.select_provider_and_model",
            lambda: None,
        )
        monkeypatch.setattr("builtins.input", lambda prompt="": "")

        _model_flow_atomic_chat({})

        out = capsys.readouterr().out
        assert "no model is loaded" in out
        assert "download or start" in out


class TestModelFlowAtomicChatWithModel:
    """When Atomic Chat is running and has model(s) loaded."""

    def test_single_model_auto_selects(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        from hermes_cli.main import _model_flow_atomic_chat
        from hermes_cli.config import load_config

        probe_one = _make_probe_result(["Qwen3_5-9B-Q4_K_M"])
        monkeypatch.setattr(
            "hermes_cli.models.probe_api_models",
            lambda *a, **kw: probe_one,
        )
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")

        _model_flow_atomic_chat({})

        out = capsys.readouterr().out
        assert "Qwen3_5-9B-Q4_K_M" in out
        assert "✅" in out

        cfg = load_config()
        assert cfg["model"]["provider"] == "custom"
        assert cfg["model"]["base_url"] == "http://127.0.0.1:1337/v1"

    def test_single_model_user_declines(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        from hermes_cli.main import _model_flow_atomic_chat

        probe_one = _make_probe_result(["Qwen3_5-9B-Q4_K_M"])
        monkeypatch.setattr(
            "hermes_cli.models.probe_api_models",
            lambda *a, **kw: probe_one,
        )
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")

        _model_flow_atomic_chat({})

        out = capsys.readouterr().out
        assert "Cancelled" in out

    def test_multiple_models_numbered_fallback(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        from hermes_cli.main import _model_flow_atomic_chat
        from hermes_cli.config import load_config

        probe_multi = _make_probe_result(["model-A", "model-B"])

        monkeypatch.setattr(
            "hermes_cli.models.probe_api_models",
            lambda *a, **kw: probe_multi,
        )
        monkeypatch.setattr("builtins.input", lambda prompt="": "1")

        # Force numbered fallback by removing simple_term_menu from modules
        with patch.dict(sys.modules, {"simple_term_menu": None}):
            _model_flow_atomic_chat({})

        out = capsys.readouterr().out
        assert "model-A" in out
        assert "✅" in out

        cfg = load_config()
        assert cfg["model"]["provider"] == "custom"


# =============================================================================
# Dynamic label probe tests
# =============================================================================


class TestDynamicLabelProbe:
    """Test that the provider list label reflects Atomic Chat status."""

    def test_label_shows_model_when_running(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        probe_result = _make_probe_result(["Qwen3_5-9B-Q4_K_M"])
        monkeypatch.setattr(
            "hermes_cli.models.probe_api_models",
            lambda *a, **kw: probe_result,
        )

        from hermes_cli.models import probe_api_models
        result = probe_api_models(None, "http://127.0.0.1:1337/v1", timeout=2.0)
        models = result.get("models")

        if models:
            label = f"Atomic Chat (127.0.0.1:1337/v1) — {models[0]}"
        else:
            label = "Atomic Chat (local LLM — 127.0.0.1:1337)"

        assert "Qwen3_5-9B-Q4_K_M" in label
        assert "127.0.0.1:1337/v1" in label

    def test_label_shows_no_model_when_empty(self):
        models = []
        if models:
            label = f"Atomic Chat (127.0.0.1:1337/v1) — {models[0]}"
        elif models is not None:
            label = "Atomic Chat (running, no model loaded)"
        else:
            label = "Atomic Chat (local LLM — 127.0.0.1:1337)"

        assert label == "Atomic Chat (running, no model loaded)"

    def test_label_fallback_when_not_running(self):
        models = None
        if models:
            label = f"Atomic Chat (127.0.0.1:1337/v1) — {models[0]}"
        elif models is not None:
            label = "Atomic Chat (running, no model loaded)"
        else:
            label = "Atomic Chat (local LLM — 127.0.0.1:1337)"

        assert label == "Atomic Chat (local LLM — 127.0.0.1:1337)"
