from hermes_cli.model_switch import list_authenticated_providers


def test_list_authenticated_providers_includes_openai_oauth_from_external_auth(monkeypatch):
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(
        "hermes_cli.auth.get_openai_oauth_auth_status",
        lambda: {"logged_in": True},
    )
    monkeypatch.setattr("hermes_cli.auth._load_auth_store", lambda: {})

    class _Pool:
        def has_credentials(self):
            return False

    monkeypatch.setattr("agent.credential_pool.load_pool", lambda _provider: _Pool())

    providers = list_authenticated_providers(
        current_provider="",
        user_providers={},
        custom_providers=[],
        max_models=8,
    )

    row = next((p for p in providers if p["slug"] == "openai-oauth"), None)
    assert row is not None
    assert row["name"] == "OpenAI (OAuth)"
    assert row["models"][:3] == ["gpt-5.4", "gpt-5.4-mini", "gpt-5-mini"]
