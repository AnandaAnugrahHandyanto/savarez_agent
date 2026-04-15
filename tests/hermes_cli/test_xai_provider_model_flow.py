from unittest.mock import patch


def test_xai_setup_flow_uses_standard_model_selection(monkeypatch):
    from hermes_cli.main import _model_flow_api_key_provider

    captured = {}

    monkeypatch.setenv("XAI_API_KEY", "xai-test-key")

    def _capture_models(models, current_model=""):
        captured["models"] = models
        return None

    with (
        patch("hermes_cli.main.input", return_value=""),
        patch("agent.models_dev.list_agentic_models", return_value=["grok-2-1212", "grok-4-fast"]),
        patch("hermes_cli.models.fetch_api_models", return_value=["grok-2-1212"]),
        patch("hermes_cli.auth._prompt_model_selection", side_effect=_capture_models),
        ):
            _model_flow_api_key_provider({}, "xai")

    assert captured["models"] == ["grok-2-1212", "grok-4-fast"]


def test_xai_provider_uses_codex_responses_transport():
    from hermes_cli.providers import determine_api_mode, get_provider

    provider = get_provider("xai")

    assert provider is not None
    assert provider.transport == "codex_responses"
    assert determine_api_mode("xai") == "codex_responses"


def test_xai_auxiliary_model_uses_grok_420():
    from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS

    assert _API_KEY_PROVIDER_AUX_MODELS["xai"] == "grok-4.20-reasoning"
