import sys
import types

from providers.base import ProviderProfile


def test_create_openai_client_uses_external_process_profile_client(monkeypatch):
    from agent.agent_runtime_helpers import create_openai_client

    calls = {}
    module = types.ModuleType("fake_external_client")

    class FakeExternalClient:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    module.FakeExternalClient = FakeExternalClient
    monkeypatch.setitem(sys.modules, "fake_external_client", module)

    profile = ProviderProfile(
        name="fake-acp",
        auth_type="external_process",
        base_url="acp://fake",
        client_module="fake_external_client",
        client_class="FakeExternalClient",
        client_receives_agent_context=True,
    )
    monkeypatch.setattr(
        "providers.get_provider_profile",
        lambda name: profile if name == "fake-acp" else None,
    )

    agent = types.SimpleNamespace(
        provider="fake-acp",
        session_id="session-123",
        platform="telegram",
        _client_log_context=lambda: "ctx",
    )

    client = create_openai_client(
        agent,
        {"api_key": "fake-key", "base_url": "acp://fake", "command": "fake"},
        reason="test",
        shared=False,
    )

    assert isinstance(client, FakeExternalClient)
    assert calls["api_key"] == "fake-key"
    assert calls["base_url"] == "acp://fake"
    assert calls["command"] == "fake"
    assert calls["agent"] is agent
    assert calls["hermes_session_id"] == "session-123"
    assert calls["platform"] == "telegram"


def test_external_process_credentials_use_provider_profile(monkeypatch):
    from hermes_cli import auth

    profile = ProviderProfile(
        name="fake-acp",
        auth_type="external_process",
        base_url="acp://fake",
        external_process_api_key="fake-acp",
        external_process_command_env_vars=("FAKE_ACP_COMMAND",),
        external_process_default_command="fake-cli",
        external_process_args_env_var="FAKE_ACP_ARGS",
        external_process_default_args=("--acp", "--stdio"),
    )
    monkeypatch.setattr(
        "providers.get_provider_profile",
        lambda name: profile if name == "fake-acp" else None,
    )
    monkeypatch.setitem(
        auth.PROVIDER_REGISTRY,
        "fake-acp",
        auth.ProviderConfig(
            id="fake-acp",
            name="Fake ACP",
            auth_type="external_process",
            inference_base_url="acp://fake",
            base_url_env_var="FAKE_ACP_BASE_URL",
        ),
    )
    monkeypatch.setenv("FAKE_ACP_COMMAND", "fake-bin")
    monkeypatch.setenv("FAKE_ACP_ARGS", "--stdio --debug")
    monkeypatch.setattr(auth.shutil, "which", lambda command: f"/bin/{command}")

    creds = auth.resolve_external_process_provider_credentials("fake-acp")

    assert creds["provider"] == "fake-acp"
    assert creds["api_key"] == "fake-acp"
    assert creds["base_url"] == "acp://fake"
    assert creds["command"] == "/bin/fake-bin"
    assert creds["args"] == ["--stdio", "--debug"]


def test_runtime_provider_resolves_generic_external_process(monkeypatch):
    from hermes_cli import runtime_provider
    from hermes_cli.auth import ProviderConfig

    monkeypatch.setitem(
        runtime_provider.PROVIDER_REGISTRY,
        "fake-acp",
        ProviderConfig(
            id="fake-acp",
            name="Fake ACP",
            auth_type="external_process",
            inference_base_url="acp://fake",
        ),
    )
    monkeypatch.setattr(
        runtime_provider,
        "resolve_external_process_provider_credentials",
        lambda provider: {
            "provider": provider,
            "api_key": "fake-acp",
            "base_url": "acp://fake",
            "command": "/bin/fake",
            "args": ["--acp"],
            "source": "process",
        },
    )

    resolved = runtime_provider.resolve_runtime_provider(requested="fake-acp")

    assert resolved["provider"] == "fake-acp"
    assert resolved["api_mode"] == "chat_completions"
    assert resolved["base_url"] == "acp://fake"
    assert resolved["api_key"] == "fake-acp"
    assert resolved["command"] == "/bin/fake"
    assert resolved["args"] == ["--acp"]
