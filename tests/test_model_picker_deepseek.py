from types import SimpleNamespace


def test_cmd_model_deepseek_picker_routes_to_api_key_flow(monkeypatch):
    from hermes_cli import main as hermes_main

    monkeypatch.setattr(hermes_main, "_require_tty", lambda *a: None)
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "gpt-5", "provider": "openrouter"}},
    )
    monkeypatch.setattr("hermes_cli.auth.resolve_provider", lambda requested, **kwargs: "openrouter")

    captured = {}

    def _fake_prompt_provider_choice(choices):
        for idx, choice in enumerate(choices):
            if choice.startswith("DeepSeek "):
                return idx
        raise AssertionError("DeepSeek was not listed in hermes model provider choices")

    def _fake_api_key_flow(config, provider_id, current_model=""):
        captured["provider_id"] = provider_id
        captured["current_model"] = current_model

    monkeypatch.setattr(hermes_main, "_prompt_provider_choice", _fake_prompt_provider_choice)
    monkeypatch.setattr(hermes_main, "_model_flow_api_key_provider", _fake_api_key_flow)

    hermes_main.cmd_model(SimpleNamespace())

    assert captured == {
        "provider_id": "deepseek",
        "current_model": "gpt-5",
    }
