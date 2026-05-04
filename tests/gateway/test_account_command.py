"""Tests for gateway /account provider selection and all-account usage display."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


SK = "agent:main:whatsapp:private:12345"


def _make_runner(session_key=SK):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._agent_cache = {}
    runner._agent_cache_lock = threading.Lock()
    runner.session_store = MagicMock()
    runner._session_key_for_source = MagicMock(return_value=session_key)
    return runner


@pytest.mark.asyncio
async def test_account_command_without_provider_asks_user_to_choose_provider(monkeypatch):
    runner = _make_runner()
    event = MagicMock()
    event.source = MagicMock()
    event.get_command_args.return_value = ""

    monkeypatch.setattr(
        "gateway.run.list_account_provider_choices",
        lambda active_provider=None: [
            SimpleNamespace(slug="anthropic", name="Anthropic", account_count=1, is_current=False),
            SimpleNamespace(slug="openai-codex", name="OpenAI Codex", account_count=2, is_current=True),
        ],
    )

    result = await runner._handle_account_command(event)

    assert "Select a credential provider" in result
    assert "1 account" in result
    assert "2 accounts" in result
    assert "/account anthropic" in result
    assert "/account openai-codex" in result


@pytest.mark.asyncio
async def test_account_command_with_provider_shows_every_account_in_that_provider(monkeypatch):
    runner = _make_runner()
    event = MagicMock()
    event.source = MagicMock()
    event.get_command_args.return_value = "openai-codex"
    calls = {}

    def _fake_fetch(provider):
        calls["provider"] = provider
        return [object(), object()]

    monkeypatch.setattr("gateway.run.fetch_provider_account_usages", _fake_fetch)
    monkeypatch.setattr(
        "gateway.run.render_provider_account_usage_lines",
        lambda provider, results, markdown=False, **kwargs: [
            "📈 **Account usage for provider: openai-codex**",
            "1. alpha",
            "Session: 90% remaining (10% used)",
            "2. beta",
            "Session: 5% remaining (95% used)",
        ],
    )

    result = await runner._handle_account_command(event)

    assert calls["provider"] == "openai-codex"
    assert "1. alpha" in result
    assert "2. beta" in result
    assert "90% remaining" in result
    assert "5% remaining" in result


@pytest.mark.asyncio
async def test_account_command_with_provider_and_account_target_switches_then_rerenders(monkeypatch):
    runner = _make_runner()
    agent = MagicMock()
    agent.provider = "openai-codex"
    agent._credential_pool = "active-pool"
    runner._agent_cache[SK] = (agent, 0)

    event = MagicMock()
    event.source = MagicMock()
    event.get_command_args.return_value = "openai-codex 2"
    selected = {}

    def _fake_select(provider, target, pool=None):
        selected.update({"provider": provider, "target": target, "pool": pool})
        return 2, SimpleNamespace(label="beta", id="cred-2"), None

    monkeypatch.setattr(
        "gateway.run.list_account_provider_choices",
        lambda active_provider=None: [SimpleNamespace(slug="openai-codex", name="OpenAI Codex", account_count=2, is_current=True)],
    )
    monkeypatch.setattr("gateway.run.select_provider_account", _fake_select)
    monkeypatch.setattr("gateway.run.fetch_provider_account_usages", lambda provider: [object(), object()])
    monkeypatch.setattr(
        "gateway.run.render_provider_account_usage_lines",
        lambda provider, results, markdown=False, **kwargs: ["Hermes Account Center", "2. beta — active"],
    )

    result = await runner._handle_account_command(event)

    assert selected == {"provider": "openai-codex", "target": "2", "pool": "active-pool"}
    agent._swap_credential.assert_called_once()
    assert "Switched account" in result
    assert "Hermes Account Center" in result
    assert "2. beta" in result
