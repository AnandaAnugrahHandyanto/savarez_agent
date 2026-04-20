from unittest.mock import patch

import gateway.run as gateway_run


def test_load_ephemeral_system_prompt_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.delenv("HERMES_EPHEMERAL_SYSTEM_PROMPT", raising=False)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"agent": {"system_prompt": "  Global prompt  "}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        prompt = gateway_run.GatewayRunner._load_ephemeral_system_prompt()

    assert prompt == "Global prompt"
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_reasoning_config_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"agent": {"reasoning_effort": "low"}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        reasoning = gateway_run.GatewayRunner._load_reasoning_config()

    assert reasoning == {"enabled": True, "effort": "low"}
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_service_tier_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"agent": {"service_tier": "fast"}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        service_tier = gateway_run.GatewayRunner._load_service_tier()

    assert service_tier == "priority"
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_show_reasoning_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"display": {"show_reasoning": True}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        show_reasoning = gateway_run.GatewayRunner._load_show_reasoning()

    assert show_reasoning is True
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_busy_input_mode_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.delenv("HERMES_GATEWAY_BUSY_INPUT_MODE", raising=False)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"display": {"busy_input_mode": "queue"}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        mode = gateway_run.GatewayRunner._load_busy_input_mode()

    assert mode == "queue"
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_prefill_messages_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.delenv("HERMES_PREFILL_MESSAGES_FILE", raising=False)
    called = {}
    prefill_path = tmp_path / "prefill.json"
    prefill_path.write_text('[{"role": "system", "content": "hello"}]', encoding="utf-8")

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"prefill_messages_file": "prefill.json"}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        messages = gateway_run.GatewayRunner._load_prefill_messages()

    assert messages == [{"role": "system", "content": "hello"}]
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_restart_drain_timeout_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.delenv("HERMES_RESTART_DRAIN_TIMEOUT", raising=False)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"agent": {"restart_drain_timeout": 12}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        timeout = gateway_run.GatewayRunner._load_restart_drain_timeout()

    assert timeout == 12.0
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_provider_routing_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"provider_routing": {"openrouter": {"order": ["anthropic", "openai"]}}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        routing = gateway_run.GatewayRunner._load_provider_routing()

    assert routing == {"openrouter": {"order": ["anthropic", "openai"]}}
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_fallback_model_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"fallback_providers": [{"provider": "openrouter", "model": "gpt-4.1-mini"}]}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        fallback = gateway_run.GatewayRunner._load_fallback_model()

    assert fallback == [{"provider": "openrouter", "model": "gpt-4.1-mini"}]
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_privacy_redact_pii_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"privacy": {"redact_pii": True}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        redact_pii = gateway_run.GatewayRunner._load_privacy_redact_pii()

    assert redact_pii is True
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_session_hygiene_user_config_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {
            "model": {"default": "anthropic/claude-sonnet-4.6", "context_length": 200000},
            "compression": {"enabled": True},
        }

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        cfg = gateway_run.GatewayRunner._load_session_hygiene_user_config()

    assert cfg == {
        "model": {"default": "anthropic/claude-sonnet-4.6", "context_length": 200000},
        "compression": {"enabled": True},
    }
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_load_checkpoints_config_uses_shared_read_user_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"checkpoints": True}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        cfg = gateway_run.GatewayRunner._load_checkpoints_config()

    assert cfg == {"enabled": True}
    assert called["args"] == (True, False, tmp_path / "config.yaml")
