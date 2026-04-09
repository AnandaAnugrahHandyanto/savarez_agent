from hermes_cli.model_switch import list_authenticated_providers


def test_list_authenticated_providers_includes_gemini_cli_when_binary_exists(monkeypatch):
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr("hermes_cli.auth._load_auth_store", lambda: {})
    monkeypatch.setattr("hermes_cli.auth.get_external_process_provider_status", lambda provider_id: {
        "configured": provider_id == "gemini-cli",
        "logged_in": provider_id == "gemini-cli",
    })

    providers = list_authenticated_providers(max_models=3)
    slugs = [p["slug"] for p in providers]

    assert "gemini-cli" in slugs
