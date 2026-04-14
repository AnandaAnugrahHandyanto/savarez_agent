"""Tests for smart-route → primary-model fallback injection.

When smart model routing selects a cheap model, the primary (strong) model
should be prepended to the fallback chain so that a 403 from the cheap model
provider retries on the primary before giving up.
"""
from gateway.run import GatewayRunner


# -- GatewayRunner._effective_fallback (static method) -----------------------

def test_no_injection_when_label_is_none():
    """When turn_route['label'] is None (primary model used), return fallback unchanged."""
    turn_route = {"label": None, "model": "claude-opus-4-6", "runtime": {}}
    existing_fb = [{"provider": "openai", "model": "gpt-4o", "base_url": ""}]
    result = GatewayRunner._effective_fallback(
        turn_route, existing_fb, "claude-opus-4-6", "copilot",
    )
    assert result is existing_fb  # exact same object, untouched


def test_prepends_primary_when_label_set_and_no_existing_fallback():
    """When smart route active and no user fallback, create a list with just the primary."""
    turn_route = {"label": "smart route → gpt-5-mini (copilot)", "model": "gpt-5-mini"}
    result = GatewayRunner._effective_fallback(
        turn_route, None, "claude-opus-4-6", "copilot", "https://api.githubcopilot.com",
    )
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["model"] == "claude-opus-4-6"
    assert result[0]["provider"] == "copilot"
    assert result[0]["base_url"] == "https://api.githubcopilot.com"


def test_prepends_primary_when_label_set_and_existing_list_fallback():
    """When smart route active and user has a fallback list, primary goes first."""
    turn_route = {"label": "smart route → gpt-5-mini (copilot)"}
    existing_fb = [
        {"provider": "openai", "model": "gpt-4o", "base_url": ""},
    ]
    result = GatewayRunner._effective_fallback(
        turn_route, existing_fb, "claude-opus-4-6", "copilot",
    )
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["model"] == "claude-opus-4-6"
    assert result[0]["provider"] == "copilot"
    assert result[1] == existing_fb[0]


def test_prepends_primary_when_label_set_and_existing_dict_fallback():
    """When smart route active and user has a legacy dict fallback, produce [primary, dict]."""
    turn_route = {"label": "smart route → gpt-5-mini (copilot)"}
    existing_fb = {"provider": "openai", "model": "gpt-4o"}
    result = GatewayRunner._effective_fallback(
        turn_route, existing_fb, "claude-opus-4-6", "copilot",
    )
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["model"] == "claude-opus-4-6"
    assert result[1] is existing_fb


def test_base_url_defaults_to_empty_string():
    """If no base_url is passed, the fallback entry should have ''."""
    turn_route = {"label": "smart route → cheap"}
    result = GatewayRunner._effective_fallback(
        turn_route, None, "my-model", "my-provider",
    )
    assert result[0]["base_url"] == ""
