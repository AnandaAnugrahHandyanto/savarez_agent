from hermes_cli.config import load_config
from hermes_cli.setup import _setup_tts_provider


def test_setup_tts_provider_lists_xai_option(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config = load_config()
    captured = {}

    def _fake_prompt_choice(question, choices, default=0):
        if question == "Select TTS provider:":
            captured["choices"] = choices
            return len(choices) - 1
        return default

    monkeypatch.setattr("hermes_cli.setup.prompt_choice", _fake_prompt_choice)

    _setup_tts_provider(config)

    assert any("xAI TTS" in choice for choice in captured["choices"])


def test_setup_tts_provider_saves_xai_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config = load_config()

    monkeypatch.setattr(
        "hermes_cli.setup.prompt_choice",
        lambda question, choices, default=0: choices.index("xAI TTS (Grok voices, needs API key)"),
    )
    monkeypatch.setattr("hermes_cli.setup.prompt", lambda *a, **kw: "xai-test-key")

    _setup_tts_provider(config)

    saved = load_config()
    assert saved["tts"]["provider"] == "xai"


def test_setup_tts_provider_warns_with_remediation_when_xai_key_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    config = load_config()
    captured = {}

    monkeypatch.setattr(
        "hermes_cli.setup.prompt_choice",
        lambda question, choices, default=0: choices.index("xAI TTS (Grok voices, needs API key)"),
    )
    monkeypatch.setattr("hermes_cli.setup.prompt", lambda *a, **kw: "")
    monkeypatch.setattr("hermes_cli.setup.print_warning", lambda message: captured.setdefault("warning", message))

    _setup_tts_provider(config)

    saved = load_config()
    assert saved["tts"]["provider"] == "edge"
    assert "hermes setup model" in captured["warning"]
    assert "XAI_API_KEY" in captured["warning"]
