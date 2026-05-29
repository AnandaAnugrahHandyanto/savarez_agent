from types import ModuleType, SimpleNamespace

from hermes_cli.fallback_config import (
    get_fallback_chain,
    is_opus_48_model,
    role_fallback_chain,
    sanitize_fallback_chain,
)
from agent.chat_completion_helpers import try_activate_fallback
from skills.productivity.linear.scripts import linear_api


def test_sanitize_fallback_chain_filters_opus_48_and_dedupes():
    raw = [
        {"provider": "anthropic", "model": "claude-opus-4.8"},
        {"provider": "minimax", "model": "MiniMax-M2.7"},
        {"provider": "minimax", "model": "MiniMax-M2.7"},
        {"provider": "openai-codex", "model": "gpt-5.5", "base_url": "https://example.com/"},
    ]

    chain = sanitize_fallback_chain(raw)

    assert len(chain) == 2
    assert all(not is_opus_48_model(entry["model"]) for entry in chain)
    assert chain[0]["provider"] == "minimax"
    assert chain[1]["base_url"] == "https://example.com"


def test_get_fallback_chain_merges_legacy_and_filters_opus_48():
    config = {
        "fallback_providers": [
            {"provider": "anthropic", "model": "claude-opus-4-8"},
            {"provider": "minimax", "model": "MiniMax-M2.7"},
        ],
        "fallback_model": {"provider": "openai-codex", "model": "gpt-5.5"},
    }

    assert get_fallback_chain(config) == [
        {"provider": "minimax", "model": "MiniMax-M2.7"},
        {"provider": "openai-codex", "model": "gpt-5.5"},
    ]


def test_role_fallback_chain_builder_default_semantics():
    chain = role_fallback_chain("builder", {})

    assert [(entry["provider"], entry["model"], entry["reasoning_effort"]) for entry in chain] == [
        ("minimax", "MiniMax-M2.7", "medium"),
        ("openai-codex", "gpt-5.5", "medium"),
        ("openai-codex", "gpt-5.5", "xhigh"),
    ]


def test_runtime_fallback_skips_leaked_opus_48(monkeypatch):
    calls = []

    def fake_resolve_provider_client(provider, model, raw_codex=False, explicit_base_url=None, explicit_api_key=None):
        calls.append((provider, model))
        return SimpleNamespace(base_url="https://chatgpt.com/backend-api/codex", api_key="fallback-key"), model

    monkeypatch.setattr("agent.auxiliary_client.resolve_provider_client", fake_resolve_provider_client)

    agent = SimpleNamespace(
        _fallback_chain=[
            {"provider": "anthropic", "model": "claude-opus-4.8"},
            {"provider": "openai-codex", "model": "gpt-5.5"},
        ],
        _fallback_index=0,
        _fallback_activated=False,
        _primary_runtime={"provider": "anthropic"},
        _rate_limited_until=0,
        provider="anthropic",
        model="claude-sonnet-4.6",
        base_url="https://api.anthropic.com",
        api_key="primary",
        api_mode="anthropic_messages",
        request_overrides={},
        _is_azure_openai_url=lambda _url: False,
        _is_direct_openai_url=lambda _url: False,
        _provider_model_requires_responses_api=lambda _model, provider=None: False,
        _anthropic_prompt_cache_policy=lambda **_kwargs: (False, False),
        _ensure_lmstudio_runtime_loaded=lambda: None,
        _buffer_status=lambda _message: None,
        _replace_primary_openai_client=lambda **_kwargs: None,
        context_compressor=None,
        _try_activate_fallback=lambda: try_activate_fallback(agent),
        _abort_request_openai_client=lambda *_args, **_kwargs: None,
        _close_request_openai_client=lambda *_args, **_kwargs: None,
    )

    assert try_activate_fallback(agent) is True
    assert calls == [("openai-codex", "gpt-5.5")]
    assert agent.provider == "openai-codex"
    assert agent.model == "gpt-5.5"


def test_linear_attribution_replaces_stale_footer(monkeypatch):
    args = SimpleNamespace(
        model="gpt-5.5",
        provider="openai-codex",
        reasoning_effort="xhigh",
        session_id="test-session",
    )
    monkeypatch.setattr(linear_api, "datetime", SimpleNamespace(
        now=lambda _tz: SimpleNamespace(
            replace=lambda microsecond=0: SimpleNamespace(isoformat=lambda: "2026-05-29T00:00:00+00:00")
        )
    ))

    stamped = linear_api._with_attribution("Body\nattr: a=old; m=claude-opus-4.8; src=manual-unverified", args, role="reviewer")

    assert stamped.count("attr:") == 1
    assert "m=gpt-5.5" in stamped
    assert "p=openai-codex" in stamped
    assert "r=reviewer" in stamped
    assert "claude-opus-4.8" not in stamped


def test_delegate_child_uses_builder_role_fallback_chain(monkeypatch):
    import tools.delegate_tool as delegate_tool

    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self._active_children = {}
            self._active_subagents = {}
            self._delegate_role = None

    fake_run_agent = ModuleType("run_agent")
    setattr(fake_run_agent, "AIAgent", FakeAgent)
    monkeypatch.setitem(__import__("sys").modules, "run_agent", fake_run_agent)
    monkeypatch.setattr(delegate_tool, "_load_config", lambda: {})
    monkeypatch.setattr(delegate_tool, "_get_max_spawn_depth", lambda: 1)
    monkeypatch.setattr(delegate_tool, "_get_orchestrator_enabled", lambda: True)
    monkeypatch.setattr(delegate_tool, "_build_child_progress_callback", lambda *args, **kwargs: None)

    parent = SimpleNamespace(
        _delegate_depth=0,
        enabled_toolsets=["terminal"],
        model="claude-sonnet-4.6",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        api_key="primary",
        api_mode="anthropic_messages",
        platform="cli",
        _fallback_chain=[{"provider": "anthropic", "model": "claude-opus-4.8"}],
    )

    child = delegate_tool._build_child_agent(
        task_index=0,
        goal="build",
        context=None,
        toolsets=None,
        model=None,
        max_iterations=1,
        task_count=1,
        parent_agent=parent,
    )

    assert child is not None
    assert captured["fallback_model"] == role_fallback_chain("builder", {})


def test_linear_offline_receipt_queue_and_replay(tmp_path, monkeypatch):
    calls = []

    def failing_once_then_success(query, variables=None):
        calls.append((query, variables))
        if len(calls) == 1:
            raise SystemExit(1)
        return {"commentCreate": {"success": True}}

    monkeypatch.setenv("LINEAR_OFFLINE_RECEIPT_DIR", str(tmp_path))
    monkeypatch.setattr(linear_api, "gql", failing_once_then_success)

    queued = linear_api._mutation_with_receipt(
        "add-comment",
        "mutation X",
        {"input": {"issueId": "ALF-1", "body": "Body"}},
        queue_on_failure=True,
    )
    receipts = list(tmp_path.glob("*.json"))

    assert queued["offlineReceiptQueued"]["operation"] == "add-comment"
    assert len(receipts) == 1

    replay = linear_api.replay_offline_receipts(tmp_path)

    assert replay["replayed"] == 1
    assert replay["failed"] == 0
    assert replay["remaining"] == 0
    assert not list(tmp_path.glob("*.json"))
