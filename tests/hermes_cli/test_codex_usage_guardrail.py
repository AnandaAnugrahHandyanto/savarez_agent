from types import SimpleNamespace

from hermes_cli.codex_usage_guardrail import (
    codex_usage_pause_path,
    delegation_config_uses_codex,
    format_codex_usage_pause_message,
    is_codex_usage_paused,
    provider_model_uses_codex,
)


def test_pause_path_uses_hermes_root(tmp_path):
    assert codex_usage_pause_path(tmp_path) == tmp_path / "codex_usage_pause.json"


def test_pause_detects_existing_sentinel(tmp_path):
    assert is_codex_usage_paused(tmp_path) is False
    (tmp_path / "codex_usage_pause.json").write_text('{"threshold": 90}', encoding="utf-8")
    assert is_codex_usage_paused(tmp_path) is True


def test_provider_model_uses_codex_requires_actual_codex_provider_context():
    assert provider_model_uses_codex(provider="openai-codex", model="gpt-5.3-codex")
    assert provider_model_uses_codex(provider=None, model="gpt-5.3-codex")
    assert provider_model_uses_codex(
        provider=None,
        model="gpt-5.3-codex",
        base_url="https://chatgpt.com/backend-api/codex",
    )

    assert not provider_model_uses_codex(provider="openrouter", model="gpt-5.3-codex")
    assert provider_model_uses_codex(
        provider="openrouter",
        model="anthropic/claude-sonnet-4",
        base_url="https://chatgpt.com/backend-api/codex",
    )
    assert not provider_model_uses_codex(provider="anthropic", model="claude-sonnet-4")


def test_delegation_config_treats_codex_backend_base_url_as_authoritative():
    assert delegation_config_uses_codex(
        {
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-4",
            "base_url": "https://chatgpt.com/backend-api/codex",
        },
        parent_agent=SimpleNamespace(provider="openrouter", model="claude", base_url=""),
    )
    assert delegation_config_uses_codex(
        {},
        parent_agent=SimpleNamespace(
            provider="custom",
            model="claude",
            base_url="https://chatgpt.com/backend-api/codex",
        ),
    )
    assert not delegation_config_uses_codex(
        {"provider": "openrouter", "model": "gpt-5.3-codex"},
        parent_agent=SimpleNamespace(provider="openai-codex", model="gpt-5.3-codex"),
    )


def test_pause_message_includes_reset_guidance(tmp_path):
    msg = format_codex_usage_pause_message(root=tmp_path, source="delegate_task")
    assert "Codex usage guardrail" in msg
    assert "delegate_task" in msg
    assert str(tmp_path / "codex_usage_pause.json") in msg
    assert "90%" in msg
