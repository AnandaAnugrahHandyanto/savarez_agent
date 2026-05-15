"""Tests for direct OpenAI API service-tier routing."""

from types import SimpleNamespace

from tests.cli.test_fast_command import _import_cli


def _make_cli_stub(
    *,
    model="gpt-5.5",
    base_url="https://api.openai.com/v1",
    api_service_tier=None,
    api_service_tier_fallback=None,
    service_tier=None,
):
    return SimpleNamespace(
        model=model,
        api_key="test",
        base_url=base_url,
        provider="custom",
        api_mode="codex_responses",
        acp_command=None,
        acp_args=[],
        _credential_pool=None,
        service_tier=service_tier,
        api_service_tier=api_service_tier,
        api_service_tier_fallback=api_service_tier_fallback,
    )


def test_parse_api_service_tier_config_accepts_flex_and_standard():
    cli_mod = _import_cli()
    assert cli_mod._parse_api_service_tier_config("flex") == "flex"
    assert cli_mod._parse_api_service_tier_config("standard") is None
    assert cli_mod._parse_api_service_tier_config("normal") is None
    assert cli_mod._parse_api_service_tier_config("") is None


def test_parse_api_service_tier_fallback_config_accepts_standard_only():
    cli_mod = _import_cli()
    assert cli_mod._parse_api_service_tier_fallback_config("standard") == "standard"
    assert cli_mod._parse_api_service_tier_fallback_config("auto") == "standard"
    assert cli_mod._parse_api_service_tier_fallback_config("none") is None


def test_direct_openai_api_flex_adds_service_tier_flex():
    cli_mod = _import_cli()
    stub = _make_cli_stub(api_service_tier="flex", api_service_tier_fallback=None, service_tier=None)
    route = cli_mod.HermesCLI._resolve_turn_agent_config(stub, "hi")
    assert route["request_overrides"] == {"service_tier": "flex"}


def test_direct_openai_api_flex_can_fallback_to_standard():
    cli_mod = _import_cli()
    stub = _make_cli_stub(api_service_tier="flex", api_service_tier_fallback="standard", service_tier=None)
    route = cli_mod.HermesCLI._resolve_turn_agent_config(stub, "hi")
    assert route["request_overrides"] == {
        "service_tier": "flex",
        "_fallback_request_overrides": {},
    }


def test_direct_openai_api_standard_ignores_fast_service_tier():
    cli_mod = _import_cli()
    stub = _make_cli_stub(model="gpt-5.4", api_service_tier=None, service_tier="priority")
    route = cli_mod.HermesCLI._resolve_turn_agent_config(stub, "hi")
    assert route["request_overrides"] is None


def test_non_openai_api_keeps_existing_fast_service_tier_behavior():
    cli_mod = _import_cli()
    stub = _make_cli_stub(
        model="gpt-5.4",
        base_url="https://openrouter.ai/api/v1",
        api_service_tier="flex",
        api_service_tier_fallback="standard",
        service_tier="priority",
    )
    route = cli_mod.HermesCLI._resolve_turn_agent_config(stub, "hi")
    assert route["request_overrides"] == {"service_tier": "priority"}
