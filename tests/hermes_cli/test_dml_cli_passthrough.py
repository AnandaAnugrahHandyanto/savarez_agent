import argparse
import importlib
import sys
import types

import pytest

hermes_main = importlib.import_module("hermes_cli.main")


def _install_fake_dml_cli(monkeypatch):
    calls = []
    package = types.ModuleType("daystrom_dml")
    provider_cli = types.ModuleType("daystrom_dml.provider_cli")

    def fake_main(argv=None):
        calls.append(argv)
        return 0

    setattr(provider_cli, "main", fake_main)
    setattr(package, "provider_cli", provider_cli)
    monkeypatch.setitem(sys.modules, "daystrom_dml", package)
    monkeypatch.setitem(sys.modules, "daystrom_dml.provider_cli", provider_cli)
    return calls


def test_cmd_dml_delegates_remaining_args(monkeypatch):
    calls = _install_fake_dml_cli(monkeypatch)
    args = argparse.Namespace(dml_args=["--base-url", "http://127.0.0.1:8796", "dcn", "eval-smoke"])

    with pytest.raises(SystemExit) as exc:
        hermes_main.cmd_dml(args)

    assert exc.value.code == 0
    assert calls == [["--base-url", "http://127.0.0.1:8796", "dcn", "eval-smoke"]]


def test_cmd_dml_forwards_help_to_dml_parser(monkeypatch):
    calls = _install_fake_dml_cli(monkeypatch)
    args = argparse.Namespace(dml_help=True, dml_args=[])

    with pytest.raises(SystemExit) as exc:
        hermes_main.cmd_dml(args)

    assert exc.value.code == 0
    assert calls == [["--help"]]


def test_split_dml_passthrough_preserves_dml_global_options():
    argv = ["dml", "--base-url", "http://127.0.0.1:8796", "status"]

    assert hermes_main._split_dml_passthrough_argv(argv) == [
        "--base-url",
        "http://127.0.0.1:8796",
        "status",
    ]


def test_split_dml_passthrough_does_not_steal_continue_session_name():
    assert hermes_main._split_dml_passthrough_argv(["--continue", "dml"]) is None
