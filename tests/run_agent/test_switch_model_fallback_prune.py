"""Regression test for TUI v2 blitz bug: explicit /model --provider switch
silently fell back to the old primary provider on the next turn because the
fallback chain — seeded from config at agent __init__ — kept entries for the
provider the user just moved away from.

Reported: "switched from openrouter provider to anthropic api key via hermes
model and the tui keeps trying openrouter".
"""

from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_agent(chain):
    agent = AIAgent.__new__(AIAgent)

    agent.provider = "openrouter"
    agent.model = "x-ai/grok-4"
    agent.base_url = "https://openrouter.ai/api/v1"
    agent.api_key = "or-key"
    agent.api_mode = "chat_completions"
    agent.client = MagicMock()
    agent._client_kwargs = {"api_key": "or-key", "base_url": "https://openrouter.ai/api/v1"}
    agent.context_compressor = None
    agent._anthropic_api_key = ""
    agent._anthropic_base_url = None
    agent._anthropic_client = None
    agent._is_anthropic_oauth = False
    agent._cached_system_prompt = "cached"
    agent._primary_runtime = {}
    agent._fallback_activated = False
    agent._fallback_index = 0
    agent._fallback_chain = list(chain)
    agent._fallback_model = chain[0] if chain else None

    return agent


def _switch_to_anthropic(agent):
    with (
        patch("agent.anthropic_adapter.build_anthropic_client", return_value=MagicMock()),
        patch("agent.anthropic_adapter.resolve_anthropic_token", return_value="sk-ant-xyz"),
        patch("agent.anthropic_adapter._is_oauth_token", return_value=False),
        patch("hermes_cli.timeouts.get_provider_request_timeout", return_value=None),
    ):
        agent.switch_model(
            new_model="claude-sonnet-4-5",
            new_provider="anthropic",
            api_key="sk-ant-xyz",
            base_url="https://api.anthropic.com",
            api_mode="anthropic_messages",
        )


def test_switch_drops_old_primary_from_fallback_chain():
    agent = _make_agent([
        {"provider": "openrouter", "model": "x-ai/grok-4"},
        {"provider": "nous", "model": "hermes-4"},
    ])

    _switch_to_anthropic(agent)

    providers = [entry["provider"] for entry in agent._fallback_chain]

    assert "openrouter" not in providers, "old primary must be pruned"
    assert "anthropic" not in providers, "new primary is redundant in the chain"
    assert providers == ["nous"]
    assert agent._fallback_model == {"provider": "nous", "model": "hermes-4"}


def test_switch_with_empty_chain_stays_empty():
    agent = _make_agent([])

    _switch_to_anthropic(agent)

    assert agent._fallback_chain == []
    assert agent._fallback_model is None


def test_switch_initializes_missing_fallback_attrs():
    agent = _make_agent([])
    del agent._fallback_chain
    del agent._fallback_model

    _switch_to_anthropic(agent)

    assert agent._fallback_chain == []
    assert agent._fallback_model is None


def test_switch_within_same_provider_preserves_chain():
    chain = [{"provider": "openrouter", "model": "x-ai/grok-4"}]
    agent = _make_agent(chain)

    with patch("hermes_cli.timeouts.get_provider_request_timeout", return_value=None):
        agent.switch_model(
            new_model="openai/gpt-5",
            new_provider="openrouter",
            api_key="or-key",
            base_url="https://openrouter.ai/api/v1",
        )

    assert agent._fallback_chain == chain


def test_switch_model_clears_stale_recovery_state_for_next_turn():
    agent = _make_agent([])
    guardrails = MagicMock()
    agent._tool_guardrails = guardrails

    # Seed stale, in-band recovery flags from a previous failure flow.
    agent._empty_content_retries = 3
    agent._invalid_tool_retries = 2
    agent._invalid_json_retries = 1
    agent._incomplete_scratchpad_retries = 1
    agent._codex_incomplete_retries = 1
    agent._thinking_prefill_retries = 4
    agent._post_tool_empty_retried = True
    agent._last_content_with_tools = {"role": "assistant", "content": "stale"}
    agent._last_content_tools_all_housekeeping = True
    agent._mute_post_response = True
    agent._vision_supported = False
    agent._unicode_sanitization_passes = 2
    agent._tool_guardrail_halt_decision = "preexisting-block"

    # Prevent client creation from touching external transport code in this
    # minimal, __new__-backed fixture.
    agent._create_openai_client = MagicMock(return_value=MagicMock())

    with patch("hermes_cli.timeouts.get_provider_request_timeout", return_value=None):
        agent.switch_model(
            new_model="qwen/qwen3-14b",
            new_provider="openrouter",
            api_key="or-key",
            base_url="https://openrouter.ai/api/v1",
            api_mode="chat_completions",
        )

    assert agent._empty_content_retries == 0
    assert agent._invalid_tool_retries == 0
    assert agent._invalid_json_retries == 0
    assert agent._incomplete_scratchpad_retries == 0
    assert agent._codex_incomplete_retries == 0
    assert agent._thinking_prefill_retries == 0
    assert agent._post_tool_empty_retried is False
    assert agent._last_content_with_tools is None
    assert agent._last_content_tools_all_housekeeping is False
    assert agent._mute_post_response is False
    assert agent._vision_supported is True
    assert agent._unicode_sanitization_passes == 0
    assert agent._tool_guardrail_halt_decision is None
    guardrails.reset_for_turn.assert_called_once_with()
