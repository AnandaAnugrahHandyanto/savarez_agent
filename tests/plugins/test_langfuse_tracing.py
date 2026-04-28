"""Tests for the bundled langfuse_tracing plugin.

Covers: fail-open when langfuse SDK is absent, env-gating, hook
registration, pre/post tool call span lifecycle, and pre/post LLM
call span lifecycle.
"""
from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_plugin(monkeypatch, *, langfuse_available: bool = True):
    """Import the plugin module with a controlled langfuse stub or absence."""
    # Remove any cached module so each test gets a fresh state.
    for key in list(sys.modules):
        if "langfuse_tracing" in key:
            del sys.modules[key]

    if langfuse_available:
        langfuse_mod = types.ModuleType("langfuse")
        langfuse_mod.Langfuse = MagicMock()
        langfuse_mod.propagate_attributes = None
        monkeypatch.setitem(sys.modules, "langfuse", langfuse_mod)
    else:
        monkeypatch.delitem(sys.modules, "langfuse", raising=False)
        # Make import fail
        import builtins
        real_import = builtins.__import__

        def _blocked_import(name, *args, **kwargs):
            if name == "langfuse":
                raise ImportError("langfuse not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _blocked_import)

    import plugins.langfuse_tracing as mod
    return mod


# ---------------------------------------------------------------------------
# fail-open when langfuse SDK is missing
# ---------------------------------------------------------------------------

def test_plugin_loads_without_langfuse_sdk(monkeypatch):
    mod = _load_plugin(monkeypatch, langfuse_available=False)
    assert mod.Langfuse is None
    # _is_enabled must return False, not raise
    assert mod._is_enabled() is False


# ---------------------------------------------------------------------------
# env-gating
# ---------------------------------------------------------------------------

def test_is_enabled_false_when_no_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    mod = _load_plugin(monkeypatch)
    monkeypatch.delenv("HERMES_LANGFUSE_ENABLED", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("HERMES_LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("HERMES_LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert mod._is_enabled() is False


def test_is_enabled_true_with_hermes_vars(monkeypatch):
    mod = _load_plugin(monkeypatch)
    monkeypatch.setenv("HERMES_LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("HERMES_LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("HERMES_LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert mod._is_enabled() is True


def test_is_enabled_true_with_standard_langfuse_vars(monkeypatch):
    """LANGFUSE_* env vars (without HERMES_ prefix) also activate the plugin."""
    mod = _load_plugin(monkeypatch)
    monkeypatch.setenv("HERMES_LANGFUSE_ENABLED", "true")
    monkeypatch.delenv("HERMES_LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("HERMES_LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    assert mod._is_enabled() is True


def test_no_cc_aliases(monkeypatch):
    """CC_* env var aliases from Continue.dev must NOT be present."""
    mod = _load_plugin(monkeypatch)
    import inspect
    src = inspect.getsource(mod)
    assert "CC_LANGFUSE" not in src, "CC_LANGFUSE aliases must not be present in the plugin"


# ---------------------------------------------------------------------------
# hook registration
# ---------------------------------------------------------------------------

def test_register_hooks(monkeypatch):
    mod = _load_plugin(monkeypatch)
    ctx = MagicMock()
    mod.register(ctx)
    hook_names = {call.args[0] for call in ctx.register_hook.call_args_list}
    assert "pre_tool_call" in hook_names
    assert "post_tool_call" in hook_names
    # At least one LLM hook variant must be registered
    assert hook_names & {"pre_llm_call", "pre_api_request"}
    assert hook_names & {"post_llm_call", "post_api_request"}


# ---------------------------------------------------------------------------
# pre/post tool call span lifecycle
# ---------------------------------------------------------------------------

def test_pre_post_tool_call_span(monkeypatch):
    mod = _load_plugin(monkeypatch)
    # Clear any stale trace state
    mod._TRACE_STATE.clear()
    mod._LANGFUSE_CLIENT = None

    # Inject a fake trace state so pre_tool_call has something to attach to
    fake_span = MagicMock()
    fake_span.start_observation.return_value = MagicMock()
    state = mod.TraceState(
        trace_id="trace-123",
        root_ctx=MagicMock(),
        root_span=fake_span,
    )
    task_key = mod._trace_key("test-tool", "")
    mod._TRACE_STATE[task_key] = state

    # Patch _get_langfuse so the hooks don't gate on env vars
    fake_client = MagicMock()
    monkeypatch.setattr(mod, "_get_langfuse", lambda: fake_client)

    mod.on_pre_tool_call(
        tool_name="terminal",
        args={"command": "echo hi"},
        task_id="test-tool",
        session_id="",
        tool_call_id="tc-1",
    )
    assert "tc-1" in state.tools

    mod.on_post_tool_call(
        tool_name="terminal",
        args={"command": "echo hi"},
        result='{"output": "hi", "exit_code": 0}',
        task_id="test-tool",
        session_id="",
        tool_call_id="tc-1",
    )
    assert "tc-1" not in state.tools


# ---------------------------------------------------------------------------
# _safe_value edge cases
# ---------------------------------------------------------------------------

def test_safe_value_truncates_long_string(monkeypatch):
    mod = _load_plugin(monkeypatch)
    long_str = "x" * 20000
    result = mod._safe_value(long_str, max_chars=100)
    assert len(result) < 20000
    assert "truncated" in result


def test_safe_value_handles_bytes(monkeypatch):
    mod = _load_plugin(monkeypatch)
    result = mod._safe_value(b"binary data")
    assert result == {"type": "bytes", "len": 11}


def test_safe_value_none_passthrough(monkeypatch):
    mod = _load_plugin(monkeypatch)
    assert mod._safe_value(None) is None


def test_is_enabled_via_config_yaml(monkeypatch, tmp_path):
    """HERMES_LANGFUSE_ENABLED in config.yaml takes precedence over .env."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    # Write config.yaml with plugins.langfuse_tracing.enabled = true
    import yaml
    config = {"plugins": {"langfuse_tracing": {"enabled": True}}}
    (hermes_home / "config.yaml").write_text(yaml.dump(config), encoding="utf-8")
    # Set credentials in env
    monkeypatch.setenv("HERMES_LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("HERMES_LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.delenv("HERMES_LANGFUSE_ENABLED", raising=False)
    mod = _load_plugin(monkeypatch)
    assert mod._is_enabled() is True


def test_is_enabled_config_yaml_disabled(monkeypatch, tmp_path):
    """plugins.langfuse_tracing.enabled = false in config disables even with env var set."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    import yaml
    config = {"plugins": {"langfuse_tracing": {"enabled": False}}}
    (hermes_home / "config.yaml").write_text(yaml.dump(config), encoding="utf-8")
    monkeypatch.setenv("HERMES_LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("HERMES_LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("HERMES_LANGFUSE_SECRET_KEY", "sk-lf-test")
    mod = _load_plugin(monkeypatch)
    assert mod._is_enabled() is False


def test_pre_api_request_wired_to_on_pre_llm_request(monkeypatch):
    """pre_api_request must be registered to on_pre_llm_request, not on_pre_llm_call."""
    mod = _load_plugin(monkeypatch)
    ctx = MagicMock()
    mod.register(ctx)
    hook_map = {call.args[0]: call.args[1] for call in ctx.register_hook.call_args_list}
    assert hook_map.get("pre_api_request") is mod.on_pre_llm_request, (
        "pre_api_request must be wired to on_pre_llm_request (not on_pre_llm_call)"
    )
    assert hook_map.get("pre_llm_call") is mod.on_pre_llm_call
