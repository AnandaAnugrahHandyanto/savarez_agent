"""Regression tests for numbered fallbacks when TerminalMenu cannot initialize."""

import subprocess
import sys
import types

from hermes_cli.config import load_config, save_config


class _BrokenTerminalMenu:
    def __init__(self, *args, **kwargs):
        raise subprocess.CalledProcessError(2, ["tput", "clear"])


def test_prompt_model_selection_falls_back_on_terminalmenu_runtime_error(monkeypatch):
    from hermes_cli.auth import _prompt_model_selection

    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )
    responses = iter(["2"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    selected = _prompt_model_selection(["model-a", "model-b"])

    assert selected == "model-b"


def test_prompt_reasoning_effort_falls_back_on_terminalmenu_runtime_error(monkeypatch):
    from hermes_cli.main import _prompt_reasoning_effort_selection

    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )
    responses = iter(["3"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    selected = _prompt_reasoning_effort_selection(["low", "medium", "high"], current_effort="")

    assert selected == "high"


def test_remove_custom_provider_falls_back_on_terminalmenu_runtime_error(tmp_path, monkeypatch):
    from hermes_cli.main import _remove_custom_provider

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )

    cfg = load_config()
    cfg["custom_providers"] = [
        {"name": "Local A", "base_url": "http://localhost:8001/v1"},
        {"name": "Local B", "base_url": "http://localhost:8002/v1"},
    ]
    save_config(cfg)

    responses = iter(["1"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    _remove_custom_provider(cfg)

    reloaded = load_config()
    assert reloaded["custom_providers"] == [
        {"name": "Local B", "base_url": "http://localhost:8002/v1"},
    ]


def test_edit_custom_provider_falls_back_on_terminalmenu_runtime_error(tmp_path, monkeypatch):
    from hermes_cli.main import _edit_custom_provider

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )

    cfg = load_config()
    cfg["custom_providers"] = [
        {"name": "Local A", "base_url": "http://localhost:8001/v1", "model": "old-model"},
        {"name": "Local B", "base_url": "http://localhost:8002/v1"},
    ]
    save_config(cfg)

    input_responses = iter(["1", "Renamed A", "", "new-model", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(input_responses))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "")

    _edit_custom_provider(cfg)

    reloaded = load_config()
    edited = reloaded["custom_providers"][0]
    assert edited["name"] == "Renamed A"
    assert edited["base_url"] == "http://localhost:8001/v1"
    assert edited["model"] == "new-model"


def test_edit_custom_provider_reprobes_on_url_change(tmp_path, monkeypatch):
    from hermes_cli.main import _edit_custom_provider

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )

    probe_calls = []

    def mock_probe(api_key, base_url, timeout=5.0):
        probe_calls.append((api_key, base_url))
        return {
            "models": ["test-model"],
            "probed_url": base_url + "/models",
            "resolved_base_url": base_url,
            "used_fallback": False,
            "suggested_base_url": None,
        }

    monkeypatch.setattr("hermes_cli.models.probe_api_models", mock_probe)

    cfg = load_config()
    cfg["custom_providers"] = [
        {"name": "Old", "base_url": "http://localhost:8001/v1", "model": "m1"},
    ]
    save_config(cfg)

    input_responses = iter(["1", "", "http://localhost:9999/v1", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(input_responses))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "")

    _edit_custom_provider(cfg)

    assert len(probe_calls) == 1
    assert probe_calls[0][1] == "http://localhost:9999/v1"
    reloaded = load_config()
    assert reloaded["custom_providers"][0]["base_url"] == "http://localhost:9999/v1"


def test_edit_custom_provider_cancel_selection(tmp_path, monkeypatch, capsys):
    from hermes_cli.main import _edit_custom_provider

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )

    cfg = load_config()
    cfg["custom_providers"] = [
        {"name": "Local A", "base_url": "http://localhost:8001/v1"},
    ]
    save_config(cfg)

    input_responses = iter(["2"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(input_responses))

    _edit_custom_provider(cfg)

    captured = capsys.readouterr()
    assert "No change." in captured.out
    reloaded = load_config()
    assert reloaded["custom_providers"][0]["name"] == "Local A"


def test_edit_custom_provider_updates_context_length(tmp_path, monkeypatch):
    from hermes_cli.main import _edit_custom_provider

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )

    cfg = load_config()
    cfg["custom_providers"] = [
        {
            "name": "Local",
            "base_url": "http://localhost:8001/v1",
            "model": "qwen",
            "models": {"qwen": {"context_length": 32768}},
        },
    ]
    save_config(cfg)

    input_responses = iter(["1", "", "", "", "128k"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(input_responses))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "")

    _edit_custom_provider(cfg)

    reloaded = load_config()
    assert reloaded["custom_providers"][0]["models"]["qwen"]["context_length"] == 128000


def test_edit_custom_provider_no_providers(tmp_path, monkeypatch, capsys):
    from hermes_cli.main import _edit_custom_provider

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    cfg = load_config()
    cfg["custom_providers"] = []
    save_config(cfg)

    _edit_custom_provider(cfg)

    captured = capsys.readouterr()
    assert "No custom providers configured." in captured.out


def test_named_custom_provider_model_picker_falls_back_on_terminalmenu_runtime_error(tmp_path, monkeypatch):
    from hermes_cli.main import _model_flow_named_custom

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setitem(
        sys.modules,
        "simple_term_menu",
        types.SimpleNamespace(TerminalMenu=_BrokenTerminalMenu),
    )
    monkeypatch.setattr("hermes_cli.models.fetch_api_models", lambda *args, **kwargs: ["model-a", "model-b"])
    monkeypatch.setattr("hermes_cli.auth.deactivate_provider", lambda: None)

    cfg = load_config()
    save_config(cfg)

    responses = iter(["2"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    _model_flow_named_custom(
        cfg,
        {
            "name": "Local",
            "base_url": "http://localhost:8000/v1",
            "api_key": "",
            "model": "",
        },
    )

    reloaded = load_config()
    assert reloaded["model"]["provider"] == "custom"
    assert reloaded["model"]["base_url"] == "http://localhost:8000/v1"
    assert reloaded["model"]["default"] == "model-b"
