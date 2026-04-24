"""Tests for the built-in BOOT.md gateway hook."""

from unittest.mock import patch

from gateway.builtin_hooks import boot_md


def test_resolve_boot_agent_kwargs_uses_configured_runtime_provider(monkeypatch):
    """BOOT.md agents should use the same configured model/provider as gateway chat.

    The hook runs outside normal message handling, so it must explicitly resolve
    runtime provider settings before constructing AIAgent.
    """
    from hermes_cli import config as hermes_config
    from hermes_cli import runtime_provider

    monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "openai-codex")
    monkeypatch.setattr(
        hermes_config,
        "load_config",
        lambda: {"model": {"default": "gpt-5.5"}},
    )

    def fake_resolve_runtime_provider(requested=None):
        assert requested == "openai-codex"
        return {
            "provider": "openai-codex",
            "api_key": "test-key",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_mode": "codex_responses",
            "command": None,
            "args": (),
            "credential_pool": object(),
        }

    monkeypatch.setattr(
        runtime_provider,
        "resolve_runtime_provider",
        fake_resolve_runtime_provider,
    )

    kwargs = boot_md._resolve_boot_agent_kwargs()

    assert kwargs["model"] == "gpt-5.5"
    assert kwargs["provider"] == "openai-codex"
    assert kwargs["api_key"] == "test-key"
    assert kwargs["base_url"] == "https://chatgpt.com/backend-api/codex"
    assert kwargs["api_mode"] == "codex_responses"
    assert kwargs["args"] == []
    assert kwargs["credential_pool"] is not None


def test_run_boot_agent_passes_runtime_kwargs_to_ai_agent(monkeypatch):
    """The boot hook should not rely on AIAgent constructor defaults."""
    captured = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_conversation(self, prompt):
            captured["prompt"] = prompt
            return {"final_response": "[SILENT]"}

    monkeypatch.setattr(
        boot_md,
        "_resolve_boot_agent_kwargs",
        lambda: {
            "model": "gpt-5.5",
            "provider": "openai-codex",
            "api_key": "test-key",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_mode": "codex_responses",
            "command": None,
            "args": [],
            "credential_pool": "pool",
        },
    )

    with patch("run_agent.AIAgent", FakeAgent):
        boot_md._run_boot_agent("Send a startup report.")

    assert captured["quiet_mode"] is True
    assert captured["skip_context_files"] is True
    assert captured["skip_memory"] is True
    assert captured["max_iterations"] == 20
    assert captured["model"] == "gpt-5.5"
    assert captured["provider"] == "openai-codex"
    assert captured["api_mode"] == "codex_responses"
    assert captured["credential_pool"] == "pool"
    assert "Send a startup report." in captured["prompt"]
