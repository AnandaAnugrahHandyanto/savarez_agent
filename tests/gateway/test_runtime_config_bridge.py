import json
import os
from pathlib import Path
from unittest.mock import patch


def test_load_gateway_startup_bridge_config_uses_shared_read_user_config(tmp_path):
    from gateway import runtime_config_bridge

    called = {}

    def fake_read_user_config(*, expand_env=True, merge_defaults=False, config_path=None):
        called["args"] = (expand_env, merge_defaults, config_path)
        return {"terminal": {"backend": "docker"}}

    with patch("hermes_cli.config.read_user_config", side_effect=fake_read_user_config):
        cfg = runtime_config_bridge.load_gateway_startup_bridge_config(tmp_path)

    assert cfg == {"terminal": {"backend": "docker"}}
    assert called["args"] == (True, False, tmp_path / "config.yaml")


def test_apply_gateway_startup_env_bridge_bridges_selected_settings(monkeypatch):
    from gateway import runtime_config_bridge

    for key in (
        "sample_flag",
        "TERMINAL_ENV",
        "TERMINAL_CWD",
        "TERMINAL_DOCKER_VOLUMES",
        "AUXILIARY_VISION_PROVIDER",
        "AUXILIARY_VISION_MODEL",
        "HERMES_MAX_ITERATIONS",
        "HERMES_AGENT_TIMEOUT",
        "HERMES_AGENT_TIMEOUT_WARNING",
        "HERMES_AGENT_NOTIFY_INTERVAL",
        "HERMES_RESTART_DRAIN_TIMEOUT",
        "HERMES_GATEWAY_BUSY_INPUT_MODE",
        "HERMES_TIMEZONE",
        "HERMES_REDACT_SECRETS",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("sample_flag", "from-env")
    monkeypatch.setenv("HERMES_AGENT_TIMEOUT", "99")

    cfg = {
        "sample_flag": "from-config",
        "terminal": {
            "backend": "docker",
            "cwd": ".",
            "docker_volumes": ["/host:/container"],
        },
        "auxiliary": {
            "vision": {
                "provider": "openrouter",
                "model": "openai/gpt-4o",
            },
            "web_extract": {"provider": "auto", "model": ""},
        },
        "agent": {
            "max_turns": 42,
            "gateway_timeout": 12,
            "gateway_timeout_warning": 5,
            "gateway_notify_interval": 3,
            "restart_drain_timeout": 7,
        },
        "display": {"busy_input_mode": "queue"},
        "timezone": "Asia/Tokyo",
        "security": {"redact_secrets": False},
    }

    runtime_config_bridge.apply_gateway_startup_env_bridge(cfg)

    assert os.environ.get("sample_flag") == "from-env"
    assert os.environ.get("TERMINAL_ENV") == "docker"
    assert os.environ.get("TERMINAL_CWD") is None
    assert json.loads(os.environ["TERMINAL_DOCKER_VOLUMES"]) == ["/host:/container"]
    assert os.environ.get("AUXILIARY_VISION_PROVIDER") == "openrouter"
    assert os.environ.get("AUXILIARY_VISION_MODEL") == "openai/gpt-4o"
    assert os.environ.get("HERMES_MAX_ITERATIONS") == "42"
    assert os.environ.get("HERMES_AGENT_TIMEOUT") == "99"
    assert os.environ.get("HERMES_AGENT_TIMEOUT_WARNING") == "5"
    assert os.environ.get("HERMES_AGENT_NOTIFY_INTERVAL") == "3"
    assert os.environ.get("HERMES_RESTART_DRAIN_TIMEOUT") == "7"
    assert os.environ.get("HERMES_GATEWAY_BUSY_INPUT_MODE") == "queue"
    assert os.environ.get("HERMES_TIMEZONE") == "Asia/Tokyo"
    assert os.environ.get("HERMES_REDACT_SECRETS") == "false"
