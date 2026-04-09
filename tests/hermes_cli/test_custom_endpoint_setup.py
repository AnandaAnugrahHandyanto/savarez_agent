from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from hermes_cli.main import _is_valid_http_endpoint_url, _model_flow_custom


def test_valid_http_endpoint_url_rejects_malformed_port_suffix():
    assert _is_valid_http_endpoint_url("https://api.example.com/v1") is True
    assert _is_valid_http_endpoint_url("http://127.0.0.1:6153/v1") is True
    assert _is_valid_http_endpoint_url("http://127.0.0.1:6153export") is False
    assert _is_valid_http_endpoint_url("https://") is False


def test_model_flow_custom_refuses_invalid_saved_current_url(tmp_path, monkeypatch, capsys):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:6153export")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config_path = hermes_home / "config.yaml"
    config_path.write_text("model: gpt-5\n_config_version: 12\n", encoding="utf-8")

    config = {"model": "gpt-5", "_config_version": 12}

    with patch("builtins.input", side_effect=[""]), patch("getpass.getpass", return_value="test-key"):
        _model_flow_custom(config)

    out = capsys.readouterr().out
    assert "Invalid current custom endpoint URL" in out

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["model"] == "gpt-5"
    assert not saved.get("custom_providers")


def test_model_flow_custom_accepts_valid_user_entered_url(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config_path = hermes_home / "config.yaml"
    config_path.write_text("model: gpt-5\n_config_version: 12\n", encoding="utf-8")

    config = {"model": "gpt-5", "_config_version": 12}

    with patch("builtins.input", side_effect=["http://127.0.0.1:6153/v1", "gpt-5.4", ""]), \
         patch("getpass.getpass", return_value="test-key"), \
         patch("hermes_cli.models.probe_api_models", return_value={"models": None, "probed_url": "http://127.0.0.1:6153/v1", "suggested_base_url": None}):
        _model_flow_custom(config)

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["model"]["provider"] == "custom"
    assert saved["model"]["base_url"] == "http://127.0.0.1:6153/v1"
    assert saved["model"]["api_key"] == "test-key"
    assert saved["model"]["default"] == "gpt-5.4"
