import json

import hermes_cli.setup as setup_mod
from hermes_cli.auth import _update_config_for_provider, get_active_provider
from hermes_cli.config import load_config, save_config
from hermes_cli.setup import setup_gateway, setup_model_provider


def _maybe_keep_current_tts(question, choices):
    if question != "Select TTS provider:":
        return None
    assert choices[-1].startswith("Keep current (")
    return len(choices) - 1


def _clear_provider_env(monkeypatch):
    for key in (
        "NOUS_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "LLM_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)



def test_nous_oauth_setup_keeps_current_model_when_syncing_disk_provider(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _clear_provider_env(monkeypatch)

    config = load_config()

    def fake_prompt_choice(question, choices, default=0):
        if question == "Select your inference provider:":
            return 0
        if question == "Configure vision:":
            return len(choices) - 1
        if question == "Select default model:":
            assert choices[-1] == "Keep current (anthropic/claude-opus-4.6)"
            return len(choices) - 1
        tts_idx = _maybe_keep_current_tts(question, choices)
        if tts_idx is not None:
            return tts_idx
        raise AssertionError(f"Unexpected prompt_choice call: {question}")

    monkeypatch.setattr("hermes_cli.setup.prompt_choice", fake_prompt_choice)
    monkeypatch.setattr("hermes_cli.setup.prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr("hermes_cli.auth.detect_external_credentials", lambda: [])

    def _fake_login_nous(*args, **kwargs):
        auth_path = tmp_path / "auth.json"
        auth_path.write_text(json.dumps({"active_provider": "nous", "providers": {}}))
        _update_config_for_provider("nous", "https://inference.example.com/v1")

    monkeypatch.setattr("hermes_cli.auth._login_nous", _fake_login_nous)
    monkeypatch.setattr(
        "hermes_cli.auth.resolve_nous_runtime_credentials",
        lambda *args, **kwargs: {
            "base_url": "https://inference.example.com/v1",
            "api_key": "nous-key",
        },
    )
    monkeypatch.setattr(
        "hermes_cli.auth.fetch_nous_models",
        lambda *args, **kwargs: ["gemini-3-flash"],
    )

    setup_model_provider(config)
    save_config(config)

    reloaded = load_config()

    assert isinstance(reloaded["model"], dict)
    assert reloaded["model"]["provider"] == "nous"
    assert reloaded["model"]["base_url"] == "https://inference.example.com/v1"
    assert reloaded["model"]["default"] == "anthropic/claude-opus-4.6"


def test_custom_setup_clears_active_oauth_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _clear_provider_env(monkeypatch)

    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"active_provider": "nous", "providers": {}}))

    config = load_config()

    def fake_prompt_choice(question, choices, default=0):
        if question == "Select your inference provider:":
            return 3
        tts_idx = _maybe_keep_current_tts(question, choices)
        if tts_idx is not None:
            return tts_idx
        raise AssertionError(f"Unexpected prompt_choice call: {question}")

    monkeypatch.setattr("hermes_cli.setup.prompt_choice", fake_prompt_choice)

    # _model_flow_custom uses builtins.input (URL, key, model, context_length)
    input_values = iter([
        "https://custom.example/v1",
        "custom-api-key",
        "custom/model",
        "",  # context_length (blank = auto-detect)
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(input_values))
    monkeypatch.setattr("hermes_cli.setup.prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr("hermes_cli.auth.detect_external_credentials", lambda: [])
    monkeypatch.setattr("hermes_cli.main._save_custom_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "hermes_cli.models.probe_api_models",
        lambda api_key, base_url: {"models": ["m"], "probed_url": base_url + "/models"},
    )

    setup_model_provider(config)

    # Core assertion: switching to custom endpoint clears OAuth provider
    assert get_active_provider() is None

    # _model_flow_custom writes config via its own load/save cycle
    reloaded = load_config()
    if isinstance(reloaded.get("model"), dict):
        assert reloaded["model"].get("provider") == "custom"
        assert reloaded["model"].get("default") == "custom/model"


def test_codex_setup_uses_runtime_access_token_for_live_model_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test-key")

    config = load_config()

    def fake_prompt_choice(question, choices, default=0):
        if question == "Select your inference provider:":
            return 1
        if question == "Select default model:":
            return 0
        tts_idx = _maybe_keep_current_tts(question, choices)
        if tts_idx is not None:
            return tts_idx
        raise AssertionError(f"Unexpected prompt_choice call: {question}")

    monkeypatch.setattr("hermes_cli.setup.prompt_choice", fake_prompt_choice)
    monkeypatch.setattr("hermes_cli.setup.prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr("hermes_cli.auth.detect_external_credentials", lambda: [])
    monkeypatch.setattr("hermes_cli.auth._login_openai_codex", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "hermes_cli.auth.resolve_codex_runtime_credentials",
        lambda *args, **kwargs: {
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "codex-access-token",
        },
    )

    captured = {}

    def _fake_get_codex_model_ids(access_token=None):
        captured["access_token"] = access_token
        return ["gpt-5.2-codex", "gpt-5.2"]

    monkeypatch.setattr(
        "hermes_cli.codex_models.get_codex_model_ids",
        _fake_get_codex_model_ids,
    )

    setup_model_provider(config)
    save_config(config)

    reloaded = load_config()

    assert captured["access_token"] == "codex-access-token"
    assert isinstance(reloaded["model"], dict)
    assert reloaded["model"]["provider"] == "openai-codex"
    assert reloaded["model"]["default"] == "gpt-5.2-codex"
    assert reloaded["model"]["base_url"] == "https://chatgpt.com/backend-api/codex"


def test_setup_gateway_can_launch_kasia_command(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    for key in (
        "TELEGRAM_BOT_TOKEN",
        "DISCORD_BOT_TOKEN",
        "SLACK_BOT_TOKEN",
        "MATTERMOST_TOKEN",
        "WHATSAPP_ENABLED",
        "KASIA_ENABLED",
        "KASIA_SEED_PHRASE",
        "KASIA_INDEXER_URL",
        "KASIA_NODE_WBORSH_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    config = load_config()

    yes_no_answers = {
        "Set up Telegram bot?": False,
        "Set up Discord bot?": False,
        "Set up Slack bot?": False,
        "Set up Matrix?": False,
        "Set up Mattermost?": False,
        "Set up Kasia?": True,
        "Set up WhatsApp?": False,
    }

    monkeypatch.setattr(
        "hermes_cli.setup.prompt_yes_no",
        lambda question, default=True: yes_no_answers.get(question, default),
    )
    called = {}
    monkeypatch.setattr(
        "hermes_cli.setup._run_kasia_setup_command",
        lambda: called.__setitem__("kasia_called", True),
    )

    setup_gateway(config)

    assert called.get("kasia_called") is True


def test_quick_setup_offers_kasia_in_messaging_checklist(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config = load_config()

    monkeypatch.setattr(
        "hermes_cli.config.get_missing_env_vars",
        lambda required_only=False: [
            {
                "name": "KASIA_SEED_PHRASE",
                "description": "Seed phrase for the dedicated Hermes Kasia identity",
                "prompt": "Kasia seed phrase",
                "password": True,
                "category": "messaging",
                "advanced": False,
            }
        ],
    )
    monkeypatch.setattr("hermes_cli.config.get_missing_config_fields", lambda: [])
    monkeypatch.setattr("hermes_cli.config.check_config_version", lambda: (1, 1))

    captured = {}

    def _fake_prompt_checklist(title, items, pre_selected=None):
        captured["title"] = title
        captured["items"] = list(items)
        return [0]

    monkeypatch.setattr("hermes_cli.setup.prompt_checklist", _fake_prompt_checklist)
    monkeypatch.setattr("hermes_cli.setup._print_setup_summary", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "hermes_cli.setup._run_kasia_setup_command",
        lambda: captured.__setitem__("kasia_called", True),
    )

    setup_mod._run_quick_setup(config, tmp_path)

    assert captured["title"] == "Which platforms would you like to set up?"
    assert "🔐 Kasia" in captured["items"]
    assert captured.get("kasia_called") is True


def test_password_prompt_hides_stored_default(monkeypatch):
    captured = {}

    def _fake_getpass(prompt_text):
        captured["prompt"] = prompt_text
        return ""

    monkeypatch.setattr("getpass.getpass", _fake_getpass)

    result = setup_mod.prompt(
        "Kasia seed phrase",
        default="secret words stay hidden",
        password=True,
    )

    assert result == "secret words stay hidden"
    assert "secret words stay hidden" not in captured["prompt"]
    assert "input hidden" in captured["prompt"]
    assert "keep current" in captured["prompt"]
