"""Tests for dashboard data helpers (model switch + context)."""

import yaml

from hermes_constants import get_hermes_home


def _write_config(cfg: dict) -> None:
    path = get_hermes_home() / "config.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def test_resolve_dashboard_context_input_empty_and_numeric():
    _write_config({
        "custom_providers": [{
            "name": "p1",
            "base_url": "http://localhost:1234/v1",
            "models": {"m1": {"context_length": 65536}},
        }],
    })
    from hermes_cli.dashboard.data import resolve_dashboard_context_input

    assert resolve_dashboard_context_input("", "p1", "m1") == (65536, None)
    assert resolve_dashboard_context_input("", "p1", "new-model") == (32768, None)
    assert resolve_dashboard_context_input("131072", "p1", "x") == (131072, None)
    assert resolve_dashboard_context_input("128k", "p1", "x") == (131072, None)
    assert resolve_dashboard_context_input("131_072", "p1", "x") == (131072, None)
    assert resolve_dashboard_context_input("0", "p1", "x")[1] is not None
    assert resolve_dashboard_context_input("bad", "p1", "x")[1] is not None


def test_ensure_provider_has_model_updates_existing_context():
    _write_config({
        "custom_providers": [{
            "name": "p1",
            "base_url": "http://localhost:1234/v1",
            "models": {"m1": {"context_length": 4096}},
        }],
    })
    from hermes_cli.dashboard.data import ensure_provider_has_model

    assert ensure_provider_has_model("p1", "m1", 131072) is True
    cfg = yaml.safe_load((get_hermes_home() / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["custom_providers"][0]["models"]["m1"]["context_length"] == 131072
