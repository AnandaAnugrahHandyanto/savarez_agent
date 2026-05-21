"""Unit tests for gateway smart model routing helpers."""

from __future__ import annotations

from gateway.run import (
    _advisor_parse_verdict,
    _advisor_should_consult,
    _record_gateway_outcome_sync,
    _smart_model_alias_to_tier,
    _smart_model_resolve_route,
    _smart_model_task_tier,
    _strip_gateway_control_tags,
)


def test_model_aliases_include_requested_discord_slugs():
    assert _smart_model_alias_to_tier("k2") == "local"
    assert _smart_model_alias_to_tier("gpt5.5") == "standard"
    assert _smart_model_alias_to_tier("gpt5.3s") == "spark"


def test_model_override_for_gpt53_spark_slug():
    tier, reason = _smart_model_task_tier("#model:gpt5.3s fix this lint")
    assert tier == "spark"
    assert reason == "override"


def test_gateway_control_tags_are_stripped_before_llm_turn():
    assert _strip_gateway_control_tags("#model:gpt5.3s #advise:yes fix this lint") == "fix this lint"
    assert _strip_gateway_control_tags("please #model:k2 summarize") == "please summarize"


def test_heuristic_routes_security_audit_heavy():
    tier, reason = _smart_model_task_tier("security audit the auth migration across the workspace")
    assert tier == "heavy"
    assert reason == "heuristic"


def test_disabled_config_keeps_current_model():
    model, runtime, meta = _smart_model_resolve_route(
        {"smart_model_routing": {"enabled": False}},
        "#model:gpt5.3s fix lint",
        "kimi-k2.6:cloud",
        {"provider": "ollama", "base_url": "http://localhost:11434/v1"},
    )
    assert model == "kimi-k2.6:cloud"
    assert runtime["provider"] == "ollama"
    assert meta == {}


def test_resolve_spark_override_uses_configured_tier(monkeypatch):
    calls = []

    def fake_resolve_runtime_provider(**kwargs):
        calls.append(kwargs)
        return {
            "provider": kwargs["requested"],
            "base_url": "https://example.invalid/v1",
            "api_key": "test-key",
            "api_mode": None,
            "command": None,
            "args": [],
            "credential_pool": None,
        }

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        fake_resolve_runtime_provider,
    )
    model, runtime, meta = _smart_model_resolve_route(
        {
            "smart_model_routing": {
                "enabled": True,
                "tiers": {
                    "spark": {
                        "model": "gpt-5.3-codex-spark",
                        "provider": "openai-codex",
                        "api_mode": "codex_responses",
                    }
                },
            }
        },
        "#model:gpt5.3s fix lint",
        "kimi-k2.6:cloud",
        {"provider": "ollama", "base_url": "http://localhost:11434/v1"},
    )

    assert model == "gpt-5.3-codex-spark"
    assert runtime["provider"] == "openai-codex"
    assert runtime["api_mode"] == "codex_responses"
    assert meta == {"tier": "spark", "reason": "override"}
    assert calls == [
        {
            "requested": "openai-codex",
            "explicit_base_url": None,
            "explicit_api_key": None,
            "target_model": "gpt-5.3-codex-spark",
        }
    ]


def test_advisor_consults_for_standard_tier_and_override():
    cfg = {"agent_advisor": {"enabled": True}}
    assert _advisor_should_consult(cfg, "do this", {"tier": "standard"}) == (True, "tier")
    assert _advisor_should_consult(cfg, "#advise:yes do this", {"tier": "spark"}) == (True, "override_yes")
    assert _advisor_should_consult(cfg, "#advise:no security audit", {"tier": "heavy"}) == (False, "override_no")


def test_advisor_low_confidence_forces_ask_user():
    verdict = _advisor_parse_verdict('{"verdict":"proceed","confidence":0.4,"reasoning":"unclear"}')
    assert verdict["verdict"] == "ask_user"
    assert verdict["confidence"] == 0.4


def test_outcome_recording_is_best_effort_and_uses_fmem_tool(monkeypatch):
    calls = []

    def fake_handle_function_call(name, args, **kwargs):
        calls.append((name, args, kwargs))
        return '{"recorded": true}'

    monkeypatch.setattr("model_tools.handle_function_call", fake_handle_function_call)
    monkeypatch.setattr("tools.mcp_tool.discover_mcp_tools", lambda: ["mcp_ferrosa_memory_record_outcome"])
    _record_gateway_outcome_sync(
        session_id="not-a-uuid-session-id",
        message="security audit auth",
        routing_meta={"tier": "heavy"},
        advisor_meta={"consulted": True, "verdict": "proceed"},
        result={"final_response": "ok", "input_tokens": 10, "output_tokens": 5},
        latency_ms=123,
    )

    assert [c[0] for c in calls] == [
        "mcp_ferrosa_memory_record_outcome",
        "mcp_ferrosa_memory_record_outcome",
    ]
    assert calls[0][1]["program_type"] == "smart_routing:security:heavy"
    assert calls[0][1]["task_complexity"] == "quadratic"
    assert calls[0][1]["succeeded"] is True
    assert calls[0][1]["token_cost"] == 15
    assert calls[0][1]["session_id"] != "not-a-uuid-session-id"
    assert calls[1][1]["program_type"] == "agent_advisor:security:proceed"
