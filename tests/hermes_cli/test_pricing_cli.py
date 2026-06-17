from __future__ import annotations

import argparse
import json

import yaml

from hermes_cli.pricing_cli import pricing_command, register_pricing_subparser


def _parse(argv: list[str]):
    parser = argparse.ArgumentParser(prog="hermes")
    subparsers = parser.add_subparsers(dest="command")
    register_pricing_subparser(subparsers)
    return parser.parse_args(argv)


def test_pricing_set_and_remove_model_override(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    args = _parse(
        [
            "pricing",
            "set",
            "--provider",
            "custom",
            "--model",
            "llama3.3:70b",
            "--input",
            "1.2",
            "--output",
            "4.8",
        ]
    )
    pricing_command(args)

    config = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    models = config["pricing"]["custom_overrides"]["providers"][0]["models"]
    assert models[0]["model"] == "llama3.3:70b"
    assert models[0]["input_cost_per_million"] == 1.2
    assert models[0]["output_cost_per_million"] == 4.8

    remove_args = _parse(
        [
            "pricing",
            "remove",
            "--provider",
            "custom",
            "--model",
            "llama3.3:70b",
        ]
    )
    pricing_command(remove_args)

    config = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert config["pricing"]["custom_overrides"]["providers"] == []

    out = capsys.readouterr().out
    assert "Saved pricing override" in out
    assert "Removed pricing override" in out


def test_pricing_set_provider_default_and_activate_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    args = _parse(
        [
            "pricing",
            "set",
            "--provider",
            "custom",
            "--plan",
            "enterprise-2026",
            "--activate-plan",
            "--input",
            "0.7",
            "--output",
            "2.1",
            "--billing-mode",
            "custom_contract",
        ]
    )
    pricing_command(args)

    config = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    overrides = config["pricing"]["custom_overrides"]
    assert overrides["active_plans"]["custom"] == "enterprise-2026"
    bucket = overrides["providers"][0]
    assert bucket["billing_mode"] == "custom_contract"
    assert bucket["default"]["input_cost_per_million"] == 0.7
    assert bucket["default"]["output_cost_per_million"] == 2.1


def test_pricing_import_replaces_custom_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    import_path = tmp_path / "pricing.json"
    import_path.write_text(
        json.dumps(
            {
                "pricing": {
                    "custom_overrides": {
                        "enabled": True,
                        "providers": [
                            {
                                "provider": "openrouter",
                                "models": [
                                    {
                                        "model": "anthropic/claude-opus-4.6",
                                        "input_cost_per_million": 9.0,
                                        "output_cost_per_million": 33.0,
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    args = _parse(["pricing", "import", "--file", str(import_path)])
    pricing_command(args)

    config = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    models = config["pricing"]["custom_overrides"]["providers"][0]["models"]
    assert models[0]["model"] == "anthropic/claude-opus-4.6"
    assert models[0]["input_cost_per_million"] == 9.0
    assert models[0]["output_cost_per_million"] == 33.0


def test_pricing_list_default_subcommand(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "pricing": {
                    "custom_overrides": {
                        "enabled": True,
                        "currency": "USD",
                        "active_plans": {"custom": "enterprise-2026"},
                        "providers": [
                            {
                                "provider": "custom",
                                "plan": "enterprise-2026",
                                "billing_mode": "custom_contract",
                                "default": {
                                    "input_cost_per_million": 0.7,
                                    "output_cost_per_million": 2.1,
                                },
                            }
                        ],
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    args = _parse(["pricing", "list"])
    pricing_command(args)

    out = capsys.readouterr().out
    assert "Custom pricing overrides: enabled" in out
    assert "provider: custom [plan=enterprise-2026] (active)" in out
    assert "billing_mode: custom_contract" in out


def test_pricing_set_refuses_to_overwrite_unparseable_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    config_path = tmp_path / "config.yaml"
    original = "\tbroken tab indent:\n"
    config_path.write_text(original, encoding="utf-8")

    args = _parse(
        [
            "pricing",
            "set",
            "--provider",
            "custom",
            "--model",
            "llama3.3:70b",
            "--input",
            "1.2",
        ]
    )

    try:
        pricing_command(args)
        raised = False
    except SystemExit as exc:
        raised = True
        assert "Could not parse existing config.yaml" in str(exc)

    assert raised is True
    assert config_path.read_text(encoding="utf-8") == original
