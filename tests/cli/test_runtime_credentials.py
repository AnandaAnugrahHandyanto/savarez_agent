from types import SimpleNamespace

from cli import HermesCLI


def _runtime_cli_stub(**overrides):
    attrs = {
        "requested_provider": "kimi-coding",
        "_explicit_api_key": None,
        "_explicit_base_url": None,
        "_fallback_model": [],
        "api_mode": "chat_completions",
        "provider": "kimi-coding",
        "acp_command": None,
        "acp_args": [],
        "_credential_pool": None,
        "_provider_source": None,
        "api_key": "old-key",
        "base_url": "https://old.example/v1",
        "model": "kimi-for-coding",
        "agent": object(),
        "_active_agent_route_signature": ("stale",),
        "_normalize_model_for_provider": lambda provider: False,
    }
    attrs.update(overrides)
    return SimpleNamespace(**attrs)


def test_ensure_runtime_credentials_resolves_for_current_model(monkeypatch):
    """Mid-session /model choices must drive runtime api_mode resolution."""
    calls = []

    def fake_resolve_runtime_provider(**kwargs):
        calls.append(kwargs)
        return {
            "api_key": "new-key",
            "base_url": "https://api.kimi.com/coding",
            "provider": "kimi-coding",
            "api_mode": "anthropic_messages",
            "credential_pool": None,
            "source": "test",
        }

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        fake_resolve_runtime_provider,
    )

    cli = _runtime_cli_stub()

    assert HermesCLI._ensure_runtime_credentials(cli) is True

    assert calls == [
        {
            "requested": "kimi-coding",
            "explicit_api_key": None,
            "explicit_base_url": None,
            "target_model": "kimi-for-coding",
        }
    ]
    assert cli.api_mode == "anthropic_messages"
    assert cli.agent is None
    assert cli._active_agent_route_signature is None
