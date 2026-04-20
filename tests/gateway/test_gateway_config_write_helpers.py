from unittest.mock import patch

import yaml

import gateway.run as gateway_run


def test_load_gateway_user_config_for_write_uses_shared_read_user_config_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    called = {}

    def fake_read_user_config_raw(*, config_path=None):
        called["config_path"] = config_path
        return {"agent": {"system_prompt": "keep raw"}}

    with patch("hermes_cli.config.read_user_config_raw", side_effect=fake_read_user_config_raw):
        cfg = gateway_run.GatewayRunner._load_gateway_user_config_for_write()

    assert cfg == {"agent": {"system_prompt": "keep raw"}}
    assert called["config_path"] == tmp_path / "config.yaml"


def test_save_gateway_config_key_preserves_existing_config(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    (tmp_path / "config.yaml").write_text(
        "model:\n  default: gpt-5.4\n",
        encoding="utf-8",
    )

    ok = gateway_run.GatewayRunner._save_gateway_config_key(
        "agent.reasoning_effort",
        "low",
    )

    saved = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert ok is True
    assert saved["model"]["default"] == "gpt-5.4"
    assert saved["agent"]["reasoning_effort"] == "low"


def test_save_gateway_config_key_creates_intermediate_dicts(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)

    ok = gateway_run.GatewayRunner._save_gateway_config_key(
        "display.platforms.telegram.show_reasoning",
        True,
    )

    saved = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert ok is True
    assert saved["display"]["platforms"]["telegram"]["show_reasoning"] is True


def test_save_gateway_config_updates_can_replace_and_delete_nested_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    (tmp_path / "config.yaml").write_text(
        "model:\n  default: old\n  provider: custom\n  base_url: https://stale.example/v1\nlogging:\n  level: info\n",
        encoding="utf-8",
    )

    ok = gateway_run.GatewayRunner._save_gateway_config_updates(
        {
            "model.default": "gpt-5.4",
            "model.provider": "openai",
        },
        delete_paths=["model.base_url"],
    )

    saved = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert ok is True
    assert saved["model"] == {"default": "gpt-5.4", "provider": "openai"}
    assert saved["logging"]["level"] == "info"


def test_save_gateway_config_key_returns_false_on_invalid_existing_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    config_path = tmp_path / "config.yaml"
    invalid_yaml = "model:\n  default: [unterminated\n"
    config_path.write_text(invalid_yaml, encoding="utf-8")

    ok = gateway_run.GatewayRunner._save_gateway_config_key("agent.reasoning_effort", "low")

    assert ok is False
    assert config_path.read_text(encoding="utf-8") == invalid_yaml
