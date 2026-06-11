"""Tests for agent.brain_host — Phase 3 Brain Host seam.

Coverage:
  * parity     — BrainHost.build_agent forwards kwargs identically to direct AIAgent().
  * singleton  — BrainHost.get() always returns the same instance.
  * flag-gate  — HERMES_BRAIN_HOST=0/unset → brain_host never imported by _make_agent;
                  HERMES_BRAIN_HOST=1 → routes through BrainHost.build_agent.
  * ctx memo   — TASK 2.6 construction-cost cache: the context-length
                  resolution memo installed by build_agent (hit/miss keys,
                  lmstudio/Nous exclusions, TTL, explicit invalidation) plus
                  full-construction parity and MCP-generation invalidation.
"""

from __future__ import annotations

import os
import sys
import time
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_recorder_class():
    """Return a fresh recorder class (captures __init__ kwargs) and a list
    that accumulates every instance created."""
    instances: list = []

    class RecorderAgent:
        def __init__(self, **kwargs):
            self._kwargs = kwargs
            instances.append(self)

    return RecorderAgent, instances


@pytest.fixture(autouse=True)
def _ctx_memo_hygiene():
    """Keep the process-global resolution memo from leaking between tests.

    BrainHost.build_agent installs the host's dict into agent.model_metadata
    (a module global that would otherwise persist for the whole pytest
    process); uninstall it after every test and drop any entries on an
    already-created host singleton.
    """
    yield
    from agent import model_metadata

    model_metadata.install_context_length_cache(None)
    bh = sys.modules.get("agent.brain_host")
    if bh is not None and bh.BrainHost._instance is not None:
        bh.BrainHost._instance.clear_context_length_cache()


def _install_counting_resolver(monkeypatch, value=222_000):
    """Replace model_metadata._resolve_model_context_length (the expensive
    resolver — its step 5e runs a live network probe) with a stub that
    records every invocation and returns *value*."""
    from agent import model_metadata

    calls: list = []

    def fake_resolver(
        model,
        base_url="",
        api_key="",
        config_context_length=None,
        provider="",
        custom_providers=None,
    ):
        calls.append((model, base_url, api_key, config_context_length, provider))
        return value

    monkeypatch.setattr(model_metadata, "_resolve_model_context_length", fake_resolver)
    return calls


class _FakeTime:
    """Stand-in for model_metadata's ``time`` module with a controllable
    monotonic clock; every other attribute delegates to the real module."""

    def __init__(self, start: float = 1_000.0):
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def __getattr__(self, name):
        return getattr(time, name)


# ---------------------------------------------------------------------------
# Parity test
# ---------------------------------------------------------------------------

def test_brain_host_parity():
    """BrainHost.build_agent must pass exactly the same kwargs as a direct call.

    Monkeypatch run_agent.AIAgent with a recorder so we can compare the two
    construction paths without importing the real AIAgent.
    """
    from agent.brain_host import AgentSpec, BrainHost

    RecorderAgent, instances = _make_recorder_class()

    test_kwargs = {
        "model": "claude-opus-4-6",
        "provider": "anthropic",
        "api_key": "sk-test",
        "quiet_mode": True,
    }

    with patch("run_agent.AIAgent", RecorderAgent):
        # --- path 1: via BrainHost ---
        result_hosted = BrainHost.get().build_agent(
            AgentSpec(intent="test", kwargs=test_kwargs)
        )
        # --- path 2: direct ---
        from run_agent import AIAgent as _Direct  # noqa: PLC0415

        result_direct = _Direct(**test_kwargs)

    assert len(instances) == 2
    hosted_kwargs = instances[0]._kwargs
    direct_kwargs = instances[1]._kwargs
    assert hosted_kwargs == direct_kwargs, (
        f"kwargs mismatch:\nhosted={hosted_kwargs}\ndirect={direct_kwargs}"
    )
    # Both return the recorder instance (not None, not a mock wrapper).
    assert isinstance(result_hosted, RecorderAgent)
    assert isinstance(result_direct, RecorderAgent)


# ---------------------------------------------------------------------------
# Singleton test
# ---------------------------------------------------------------------------

def test_brain_host_singleton():
    """BrainHost.get() must return the same object on repeated calls."""
    from agent.brain_host import BrainHost

    a = BrainHost.get()
    b = BrainHost.get()
    assert a is b


# ---------------------------------------------------------------------------
# Flag-gate tests — default OFF
# ---------------------------------------------------------------------------

def _call_make_agent_with_env(env_patch: dict, monkeypatch_patches: dict):
    """Import tui_gateway.server._make_agent under a controlled set of
    patches, call it, and return (mock_ai_agent, sys_modules_snapshot)."""
    fake_runtime = {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key": "sk-test",
        "api_mode": "anthropic_messages",
        "command": None,
        "args": None,
        "credential_pool": None,
    }
    fake_cfg = {"agent": {"system_prompt": ""}, "model": {"default": "claude-opus-4-6"}}

    mock_ai_agent = MagicMock()

    # Remove brain_host from sys.modules to get a clean import-detection slate.
    sys.modules.pop("agent.brain_host", None)

    ctx_managers = [
        patch.dict(os.environ, env_patch, clear=False),
        patch("tui_gateway.server._load_cfg", return_value=fake_cfg),
        patch("tui_gateway.server._get_db", return_value=MagicMock()),
        patch("tui_gateway.server._load_reasoning_config", return_value=None),
        patch("tui_gateway.server._load_service_tier", return_value=None),
        patch("tui_gateway.server._load_enabled_toolsets", return_value=None),
        patch("tui_gateway.server._load_fallback_model", return_value=None),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value=fake_runtime,
        ),
        patch("run_agent.AIAgent", mock_ai_agent),
    ]
    # Apply any extra patches the caller wants.
    for target, new_val in monkeypatch_patches.items():
        ctx_managers.append(patch(target, new_val))

    # Enter all context managers.
    entered = []
    try:
        for cm in ctx_managers:
            entered.append(cm.__enter__())
        from tui_gateway.server import _make_agent  # noqa: PLC0415

        _make_agent("sid-gate", "key-gate")
        modules_after = set(sys.modules.keys())
    finally:
        for cm, result in zip(reversed(ctx_managers), reversed(entered)):
            cm.__exit__(None, None, None)

    return mock_ai_agent, modules_after


def test_flag_gate_off_by_default():
    """When HERMES_BRAIN_HOST is unset, agent.brain_host must NOT be imported."""
    env = {}
    os.environ.pop("HERMES_BRAIN_HOST", None)

    _, mods = _call_make_agent_with_env(env, {})
    assert "agent.brain_host" not in mods, (
        "agent.brain_host was imported even though HERMES_BRAIN_HOST is unset"
    )


def test_flag_gate_off_when_zero():
    """When HERMES_BRAIN_HOST=0, agent.brain_host must NOT be imported."""
    _, mods = _call_make_agent_with_env({"HERMES_BRAIN_HOST": "0"}, {})
    assert "agent.brain_host" not in mods, (
        "agent.brain_host was imported even though HERMES_BRAIN_HOST=0"
    )


def test_flag_gate_on_routes_through_brain_host():
    """When HERMES_BRAIN_HOST=1, _make_agent must call BrainHost.build_agent."""
    from agent.brain_host import BrainHost  # noqa: PLC0415 — ensure loaded

    build_agent_mock = MagicMock(return_value=MagicMock())

    with (
        patch.dict(os.environ, {"HERMES_BRAIN_HOST": "1"}),
        patch("agent.brain_host.BrainHost.build_agent", build_agent_mock),
    ):
        fake_runtime = {
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": "sk-test",
            "api_mode": "anthropic_messages",
            "command": None,
            "args": None,
            "credential_pool": None,
        }
        fake_cfg = {"agent": {"system_prompt": ""}, "model": {"default": "claude-opus-4-6"}}

        with (
            patch("tui_gateway.server._load_cfg", return_value=fake_cfg),
            patch("tui_gateway.server._get_db", return_value=MagicMock()),
            patch("tui_gateway.server._load_reasoning_config", return_value=None),
            patch("tui_gateway.server._load_service_tier", return_value=None),
            patch("tui_gateway.server._load_enabled_toolsets", return_value=None),
            patch("tui_gateway.server._load_fallback_model", return_value=None),
            patch(
                "hermes_cli.runtime_provider.resolve_runtime_provider",
                return_value=fake_runtime,
            ),
            patch("run_agent.AIAgent", MagicMock()),
        ):
            from tui_gateway.server import _make_agent  # noqa: PLC0415

            _make_agent("sid-on", "key-on")

    build_agent_mock.assert_called_once()
    spec = build_agent_mock.call_args.args[0]
    assert spec.intent == "tui_gateway"
    assert isinstance(spec.kwargs, dict)
    # Spot-check a stable key that the gate path must forward.
    assert spec.kwargs.get("quiet_mode") is True


# ---------------------------------------------------------------------------
# Flag-gate tests — gateway/platforms/api_server._create_agent
#
# gateway.platforms.api_server._create_agent is importable and its
# AIAgent construction is refactored into agent_kwargs, so we can drive
# it directly with the same FakeAgent monkeypatching pattern used in
# test_api_server.py.
#
# gateway/run.py's gate lives deep inside GatewayRunner._run_agent (an
# async method with heavy I/O dependencies); that site is verified by
# import-compilation + grep-assert (see task notes) rather than a
# unit-driving test.
# ---------------------------------------------------------------------------

def _make_fake_runtime():
    return {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key": "sk-test",
        "api_mode": "anthropic_messages",
    }


def _patch_api_server_deps(extra_patches=None):
    """Return a list of context managers that stub the heavy dependencies of
    APIServerAdapter._create_agent so we can call it without real config."""
    from unittest.mock import patch, MagicMock

    patches = [
        patch("gateway.run._resolve_runtime_agent_kwargs", return_value=_make_fake_runtime()),
        patch("gateway.run._resolve_gateway_model", return_value="claude-opus-4-6"),
        patch("gateway.run._load_gateway_config", return_value={}),
        patch(
            "gateway.run.GatewayRunner._load_reasoning_config",
            staticmethod(lambda: None),
        ),
        patch(
            "gateway.run.GatewayRunner._load_fallback_model",
            staticmethod(lambda: None),
        ),
        patch("hermes_cli.tools_config._get_platform_tools", lambda *_: set()),
    ]
    if extra_patches:
        patches.extend(extra_patches)
    return patches


def test_api_server_flag_gate_off_by_default():
    """When HERMES_BRAIN_HOST is unset, api_server._create_agent must NOT
    import agent.brain_host."""
    from unittest.mock import MagicMock, patch
    from gateway.platforms.api_server import APIServerAdapter
    from gateway.config import PlatformConfig

    os.environ.pop("HERMES_BRAIN_HOST", None)
    sys.modules.pop("agent.brain_host", None)

    mock_ai_agent = MagicMock()
    adapter = APIServerAdapter(PlatformConfig(enabled=True))

    ctx_managers = _patch_api_server_deps([
        patch("run_agent.AIAgent", mock_ai_agent),
    ])
    entered = []
    try:
        for cm in ctx_managers:
            entered.append(cm.__enter__())
        with patch.object(adapter, "_ensure_session_db", return_value=None):
            with patch.dict(os.environ, {}, clear=False):
                adapter._create_agent(session_id="test-off")
        modules_after = set(sys.modules.keys())
    finally:
        for cm in reversed(ctx_managers):
            cm.__exit__(None, None, None)

    assert "agent.brain_host" not in modules_after, (
        "agent.brain_host was imported even though HERMES_BRAIN_HOST is unset"
    )
    mock_ai_agent.assert_called_once()


def test_api_server_flag_gate_off_when_zero():
    """When HERMES_BRAIN_HOST=0, api_server._create_agent must NOT import
    agent.brain_host."""
    from unittest.mock import MagicMock, patch
    from gateway.platforms.api_server import APIServerAdapter
    from gateway.config import PlatformConfig

    sys.modules.pop("agent.brain_host", None)

    mock_ai_agent = MagicMock()
    adapter = APIServerAdapter(PlatformConfig(enabled=True))

    ctx_managers = _patch_api_server_deps([
        patch("run_agent.AIAgent", mock_ai_agent),
        patch.dict(os.environ, {"HERMES_BRAIN_HOST": "0"}, clear=False),
    ])
    entered = []
    try:
        for cm in ctx_managers:
            entered.append(cm.__enter__())
        with patch.object(adapter, "_ensure_session_db", return_value=None):
            adapter._create_agent(session_id="test-zero")
        modules_after = set(sys.modules.keys())
    finally:
        for cm in reversed(ctx_managers):
            cm.__exit__(None, None, None)

    assert "agent.brain_host" not in modules_after, (
        "agent.brain_host was imported even though HERMES_BRAIN_HOST=0"
    )
    mock_ai_agent.assert_called_once()


def test_api_server_flag_gate_on_routes_through_brain_host():
    """When HERMES_BRAIN_HOST=1, api_server._create_agent must call
    BrainHost.build_agent with intent='api-server'."""
    from unittest.mock import MagicMock, patch
    from agent.brain_host import BrainHost  # ensure loaded
    from gateway.platforms.api_server import APIServerAdapter
    from gateway.config import PlatformConfig

    build_agent_mock = MagicMock(return_value=MagicMock())
    adapter = APIServerAdapter(PlatformConfig(enabled=True))

    ctx_managers = _patch_api_server_deps([
        patch("run_agent.AIAgent", MagicMock()),
        patch("agent.brain_host.BrainHost.build_agent", build_agent_mock),
        patch.dict(os.environ, {"HERMES_BRAIN_HOST": "1"}, clear=False),
    ])
    entered = []
    try:
        for cm in ctx_managers:
            entered.append(cm.__enter__())
        with patch.object(adapter, "_ensure_session_db", return_value=None):
            adapter._create_agent(session_id="test-on")
    finally:
        for cm in reversed(ctx_managers):
            cm.__exit__(None, None, None)

    build_agent_mock.assert_called_once()
    spec = build_agent_mock.call_args.args[0]
    assert spec.intent == "api-server"
    assert isinstance(spec.kwargs, dict)
    # Spot-check stable keys that the gate path must forward.
    assert spec.kwargs.get("quiet_mode") is True
    assert spec.kwargs.get("platform") == "api_server"


# ---------------------------------------------------------------------------
# brain_host_gate.build_agent — the one-line gate helper every migrated
# construction site calls.
# ---------------------------------------------------------------------------

def test_gate_helper_flag_off_constructs_directly_without_importing_brain_host():
    """With the flag unset, build_agent must construct via run_agent.AIAgent
    and must NOT import agent.brain_host (zero-footprint invariant)."""
    from agent.brain_host_gate import build_agent

    RecorderAgent, instances = _make_recorder_class()

    os.environ.pop("HERMES_BRAIN_HOST", None)
    sys.modules.pop("agent.brain_host", None)

    with patch("run_agent.AIAgent", RecorderAgent):
        result = build_agent("test-intent", model="m", quiet_mode=True)

    assert "agent.brain_host" not in sys.modules, (
        "agent.brain_host was imported even though HERMES_BRAIN_HOST is unset"
    )
    assert isinstance(result, RecorderAgent)
    assert instances[0]._kwargs == {"model": "m", "quiet_mode": True}


def test_gate_helper_flag_zero_constructs_directly():
    """HERMES_BRAIN_HOST=0 behaves identically to unset."""
    from agent.brain_host_gate import build_agent

    RecorderAgent, instances = _make_recorder_class()
    sys.modules.pop("agent.brain_host", None)

    with (
        patch.dict(os.environ, {"HERMES_BRAIN_HOST": "0"}, clear=False),
        patch("run_agent.AIAgent", RecorderAgent),
    ):
        result = build_agent("test-intent", model="m")

    assert "agent.brain_host" not in sys.modules
    assert isinstance(result, RecorderAgent)
    assert instances[0]._kwargs == {"model": "m"}


def test_gate_helper_flag_on_routes_through_brain_host_with_intent():
    """HERMES_BRAIN_HOST=1 routes through BrainHost.build_agent, forwarding the
    intent tag and the exact kwargs on the AgentSpec."""
    from agent.brain_host import BrainHost  # noqa: PLC0415 — ensure loaded
    from agent.brain_host_gate import build_agent

    build_agent_mock = MagicMock(return_value=MagicMock())

    with (
        patch.dict(os.environ, {"HERMES_BRAIN_HOST": "1"}, clear=False),
        patch("agent.brain_host.BrainHost.build_agent", build_agent_mock),
    ):
        build_agent("cron", model="m", quiet_mode=True)

    build_agent_mock.assert_called_once()
    spec = build_agent_mock.call_args.args[0]
    assert spec.intent == "cron"
    assert spec.kwargs == {"model": "m", "quiet_mode": True}


def test_gate_helper_off_on_kwargs_parity():
    """The kwargs that reach AIAgent must be identical on both gate paths."""
    from agent.brain_host_gate import build_agent

    RecorderAgent, instances = _make_recorder_class()
    test_kwargs = {"model": "claude-opus-4-6", "api_key": "sk-test", "quiet_mode": True}

    with patch("run_agent.AIAgent", RecorderAgent):
        os.environ.pop("HERMES_BRAIN_HOST", None)
        build_agent("parity", **test_kwargs)

        with patch.dict(os.environ, {"HERMES_BRAIN_HOST": "1"}, clear=False):
            build_agent("parity", **test_kwargs)

    assert len(instances) == 2
    assert instances[0]._kwargs == instances[1]._kwargs == test_kwargs


# ---------------------------------------------------------------------------
# Site-table source check — every migrated construction site must call
# build_agent with its registered intent.  This is the practical substitute
# for unit-driving call sites that live deep inside async/thread workers.
# ---------------------------------------------------------------------------

# (relative file path, expected intents constructed in that file)
_MIGRATED_SITES = [
    ("tui_gateway/server.py", ["tui_gateway", "tui-background", "preview-restart"]),
    ("gateway/run.py", ["gateway-run", "history-hygiene", "gateway-background"]),
    ("gateway/platforms/api_server.py", ["api-server"]),
    ("gateway/platforms/feishu_comment.py", ["feishu-comment"]),
    ("gateway/slash_commands.py", ["compress"]),
    ("hermes_cli/prompt_size.py", ["prompt-size"]),
    ("hermes_cli/oneshot.py", ["oneshot"]),
    ("hermes_cli/cli_commands_mixin.py", ["cli-background"]),
    ("hermes_cli/cli_agent_setup_mixin.py", ["cli"]),
    ("agent/background_review.py", ["background-review"]),
    ("agent/curator.py", ["curator"]),
    ("acp_adapter/session.py", ["acp"]),
    ("cron/scheduler.py", ["cron"]),
    ("batch_runner.py", ["batch"]),
    ("run_agent.py", ["run-agent-cli"]),
    ("tools/delegate_tool.py", ["delegate"]),
]


def test_all_migrated_sites_use_gate_helper():
    """Every registered construction site calls build_agent("<intent>", ...)."""
    import pathlib
    import re

    root = pathlib.Path(__file__).parents[2]
    missing = []
    for rel_path, intents in _MIGRATED_SITES:
        src = (root / rel_path).read_text()
        for intent in intents:
            # Matches both single-line build_agent("cron", ...) and the
            # multi-line call style build_agent(\n    "cron",\n    ...
            if not re.search(r'build_agent\(\s*"' + re.escape(intent) + r'"', src):
                missing.append(f'{rel_path}: build_agent("{intent}" …)')
    assert not missing, "sites not routed through brain_host_gate:\n" + "\n".join(missing)


# ---------------------------------------------------------------------------
# Context-length resolution memo (TASK 2.6)
#
# BrainHost.build_agent installs the host-owned dict into
# agent.model_metadata via install_context_length_cache; the consult/store
# logic lives in model_metadata.get_model_context_length.  These tests pin
# the key/TTL/exclusion rules documented next to the implementation, plus
# the flag-off zero-footprint invariant, full-construction parity, and the
# MCP-generation invalidation of the (pre-existing) tool-definitions memo
# that the host deliberately does NOT duplicate.
# ---------------------------------------------------------------------------

_MEMO_ARGS = {
    "model": "claude-opus-4-6",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": "sk-test",
    "provider": "openrouter",
}


def test_ctx_memo_flag_off_global_stays_none(monkeypatch):
    """Flag off: construction never installs the memo — the module global
    stays None (install_context_length_cache's only caller is brain_host,
    which must not even be imported)."""
    from agent import model_metadata
    from agent.brain_host_gate import build_agent

    model_metadata.install_context_length_cache(None)
    RecorderAgent, _ = _make_recorder_class()

    monkeypatch.delenv("HERMES_BRAIN_HOST", raising=False)
    sys.modules.pop("agent.brain_host", None)

    with patch("run_agent.AIAgent", RecorderAgent):
        build_agent("test-intent", model="m", quiet_mode=True)

    assert "agent.brain_host" not in sys.modules
    assert model_metadata._brain_host_context_length_cache is None


def test_ctx_memo_flag_off_resolver_runs_every_time(monkeypatch):
    """With no memo installed (the default), get_model_context_length is a
    plain passthrough — the resolver runs on every call and nothing is
    cached anywhere."""
    from agent import model_metadata

    model_metadata.install_context_length_cache(None)
    calls = _install_counting_resolver(monkeypatch)

    assert model_metadata.get_model_context_length(**_MEMO_ARGS) == 222_000
    assert model_metadata.get_model_context_length(**_MEMO_ARGS) == 222_000
    assert len(calls) == 2
    assert model_metadata._brain_host_context_length_cache is None


def test_ctx_memo_hit_skips_resolver(monkeypatch):
    """Second resolution with identical inputs inside the TTL is served from
    the memo without re-running the resolver."""
    from agent import model_metadata

    calls = _install_counting_resolver(monkeypatch)
    cache: dict = {}
    model_metadata.install_context_length_cache(cache)

    first = model_metadata.get_model_context_length(**_MEMO_ARGS)
    second = model_metadata.get_model_context_length(**_MEMO_ARGS)

    assert first == second == 222_000
    assert len(calls) == 1, "second resolution must be a memo hit"
    assert len(cache) == 1


def test_ctx_memo_miss_on_any_key_input_change(monkeypatch):
    """Changing any resolution input (model, base_url, provider, config
    override, api_key) produces a different key — each variant re-resolves."""
    from agent import model_metadata

    calls = _install_counting_resolver(monkeypatch)
    model_metadata.install_context_length_cache({})

    base = dict(_MEMO_ARGS, config_context_length=None)
    variants = [
        dict(base, model="some/other-model"),
        dict(base, base_url="https://api.x.ai/v1"),
        dict(base, provider="xai"),
        dict(base, config_context_length=131_072),
        dict(base, api_key="sk-other"),
    ]

    model_metadata.get_model_context_length(**base)
    assert len(calls) == 1
    for expected, kw in enumerate(variants, start=2):
        model_metadata.get_model_context_length(**kw)
        assert len(calls) == expected, f"expected a memo miss for {kw}"

    # The original key is still warm — repeating it is a hit.
    model_metadata.get_model_context_length(**base)
    assert len(calls) == len(variants) + 1


def test_ctx_memo_never_caches_lmstudio_or_nous(monkeypatch):
    """LM Studio (transient loaded context) and Nous (portal-authoritative)
    never enter the cache — by provider name (case-insensitive) or by
    Nous-inferred base_url."""
    from agent import model_metadata

    calls = _install_counting_resolver(monkeypatch)
    cache: dict = {}
    model_metadata.install_context_length_cache(cache)

    excluded = [
        dict(model="local-model", base_url="http://localhost:1234/v1", provider="lmstudio"),
        dict(model="local-model", base_url="http://localhost:1234/v1", provider="LMStudio"),
        dict(model="Hermes-4-405B", base_url="https://inference-api.nousresearch.com/v1", provider="nous"),
        # provider unset but the URL infers to nous — still excluded.
        dict(model="Hermes-4-405B", base_url="https://inference-api.nousresearch.com/v1", provider=""),
    ]
    for kw in excluded:
        before = len(calls)
        model_metadata.get_model_context_length(**kw)
        model_metadata.get_model_context_length(**kw)
        assert len(calls) == before + 2, f"{kw} must resolve every time"
    assert cache == {}


def test_ctx_memo_ttl_expiry(monkeypatch):
    """Entries expire after _CONTEXT_LENGTH_CACHE_TTL_S (1 h, the catalog
    horizon): a hit just inside the deadline, a re-resolve at it."""
    from agent import model_metadata

    clock = _FakeTime(start=1_000.0)
    monkeypatch.setattr(model_metadata, "time", clock)
    calls = _install_counting_resolver(monkeypatch)
    model_metadata.install_context_length_cache({})

    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert len(calls) == 1

    clock.now = 1_000.0 + model_metadata._CONTEXT_LENGTH_CACHE_TTL_S - 1
    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert len(calls) == 1, "inside the TTL must be a hit"

    clock.now = 1_000.0 + model_metadata._CONTEXT_LENGTH_CACHE_TTL_S
    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert len(calls) == 2, "at/after the deadline the entry must re-resolve"


def test_ctx_memo_fallback_gets_short_ttl(monkeypatch):
    """A DEFAULT_FALLBACK_CONTEXT result (probe-down fallback) is cached for
    only _CONTEXT_LENGTH_FALLBACK_TTL_S so a transient outage cannot freeze
    an under-reported window for the full hour; real values ride out the
    same interval."""
    from agent import model_metadata

    clock = _FakeTime(start=1_000.0)
    monkeypatch.setattr(model_metadata, "time", clock)

    calls: list = []

    def split_resolver(model, base_url="", api_key="", config_context_length=None,
                       provider="", custom_providers=None):
        calls.append(model)
        if model == "probe-down-model":
            return model_metadata.DEFAULT_FALLBACK_CONTEXT
        return 222_000

    monkeypatch.setattr(model_metadata, "_resolve_model_context_length", split_resolver)
    model_metadata.install_context_length_cache({})

    fb = dict(_MEMO_ARGS, model="probe-down-model")
    model_metadata.get_model_context_length(**fb)
    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert len(calls) == 2

    # Just inside the short TTL: both are hits.
    clock.now = 1_000.0 + model_metadata._CONTEXT_LENGTH_FALLBACK_TTL_S - 1
    model_metadata.get_model_context_length(**fb)
    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert len(calls) == 2

    # Past the short TTL: the fallback re-resolves, the real value does not.
    clock.now = 1_000.0 + model_metadata._CONTEXT_LENGTH_FALLBACK_TTL_S + 1
    model_metadata.get_model_context_length(**fb)
    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert calls.count("probe-down-model") == 2
    assert calls.count(_MEMO_ARGS["model"]) == 1


def test_clear_context_length_cache_drops_entries(monkeypatch):
    """BrainHost.clear_context_length_cache empties the memo — the next
    resolution re-runs the resolver."""
    from agent import model_metadata
    from agent.brain_host import BrainHost

    host = BrainHost.get()
    host.clear_context_length_cache()
    model_metadata.install_context_length_cache(host._context_length_cache)
    calls = _install_counting_resolver(monkeypatch)

    model_metadata.get_model_context_length(**_MEMO_ARGS)
    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert len(calls) == 1
    assert len(host._context_length_cache) == 1

    host.clear_context_length_cache()
    assert host._context_length_cache == {}

    model_metadata.get_model_context_length(**_MEMO_ARGS)
    assert len(calls) == 2, "explicit invalidation must force a re-resolve"


def test_ctx_memo_cap_eviction(monkeypatch):
    """The memo is bounded at _CONTEXT_LENGTH_CACHE_MAX entries with
    oldest-first eviction (mirrors the model_tools memo)."""
    from agent import model_metadata

    calls = _install_counting_resolver(monkeypatch)
    cache: dict = {}
    model_metadata.install_context_length_cache(cache)

    cap = model_metadata._CONTEXT_LENGTH_CACHE_MAX
    for i in range(cap):
        model_metadata.get_model_context_length(**dict(_MEMO_ARGS, model=f"model-{i}"))
    assert len(cache) == cap

    model_metadata.get_model_context_length(**dict(_MEMO_ARGS, model="model-overflow"))
    assert len(cache) == cap, "cap must hold after overflow"

    # The oldest entry (model-0) was evicted — resolving it again is a miss
    # (which in turn evicts model-1, the next-oldest); the newest entry is
    # still warm.
    before = len(calls)
    model_metadata.get_model_context_length(**dict(_MEMO_ARGS, model="model-0"))
    assert len(calls) == before + 1
    model_metadata.get_model_context_length(**dict(_MEMO_ARGS, model="model-overflow"))
    assert len(calls) == before + 1


def test_ctx_memo_full_construction_parity(monkeypatch, tmp_path):
    """Flag ON: a BrainHost-built agent resolves the same context length as a
    direct (flag-off) construction, and the second hosted construction is
    served entirely from the memo.

    Real AIAgent constructions with the expensive resolver patched to a
    fixed value (no network); HERMES_HOME is isolated so user config can't
    skew the resolution inputs.
    """
    from agent import model_metadata
    from agent.brain_host import BrainHost
    from agent.brain_host_gate import build_agent

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / ".env").write_text("", encoding="utf-8")

    calls: list = []

    def fixed_resolver(model, base_url="", api_key="", config_context_length=None,
                       provider="", custom_providers=None):
        calls.append(model)
        return 200_000  # comfortably above MINIMUM_CONTEXT_LENGTH (64k)

    monkeypatch.setattr(model_metadata, "_resolve_model_context_length", fixed_resolver)
    model_metadata.install_context_length_cache(None)
    BrainHost.get().clear_context_length_cache()

    kwargs = dict(
        model="claude-opus-4-6",
        api_key="inspect-only",
        base_url="https://openrouter.ai/api/v1",
        quiet_mode=True,
        save_trajectories=False,
        skip_context_files=True,
        skip_memory=True,
        platform="cli",
    )

    # --- flag OFF: direct construction, memo never installed ---
    monkeypatch.delenv("HERMES_BRAIN_HOST", raising=False)
    direct = build_agent("parity-ctx", **kwargs)
    assert len(calls) >= 1
    assert model_metadata._brain_host_context_length_cache is None

    # --- flag ON: hosted construction installs + populates the memo ---
    monkeypatch.setenv("HERMES_BRAIN_HOST", "1")
    hosted_cold = build_agent("parity-ctx", **kwargs)
    n_after_cold = len(calls)
    hosted_warm = build_agent("parity-ctx", **kwargs)

    assert direct.context_compressor.context_length == 200_000
    assert hosted_cold.context_compressor.context_length == 200_000
    assert hosted_warm.context_compressor.context_length == 200_000
    # The warm hosted construction resolved every context length from the memo.
    assert len(calls) == n_after_cold, (
        "second hosted construction must not re-run the resolver"
    )


def test_mcp_generation_bump_invalidates_tool_defs_memo(monkeypatch):
    """The tool-definitions memo the Brain Host relies on (and deliberately
    does not duplicate) is keyed on registry._generation: an MCP
    register/deregister bumps the generation and forces a recompute."""
    import model_tools

    calls: list = []

    def fake_compute(enabled_toolsets=None, disabled_toolsets=None, quiet_mode=False,
                     skip_tool_search_assembly=False):
        calls.append(1)
        return []

    monkeypatch.setattr(model_tools, "_compute_tool_definitions", fake_compute)
    saved = dict(model_tools._tool_defs_cache)
    model_tools._tool_defs_cache.clear()
    try:
        model_tools.get_tool_definitions(quiet_mode=True)
        model_tools.get_tool_definitions(quiet_mode=True)
        assert len(calls) == 1, "repeat call must be served from the memo"

        # Simulate an MCP register/deregister: the registry bumps _generation.
        monkeypatch.setattr(
            model_tools.registry, "_generation", model_tools.registry._generation + 1
        )
        model_tools.get_tool_definitions(quiet_mode=True)
        assert len(calls) == 2, "generation bump must invalidate the memo"
    finally:
        model_tools._tool_defs_cache.clear()
        model_tools._tool_defs_cache.update(saved)
