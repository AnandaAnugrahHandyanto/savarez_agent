"""Tests for read-only config fast paths (load_config_readonly, read_raw_config_readonly)."""

from __future__ import annotations

import textwrap

import pytest


def _write_config(tmp_path, body: str) -> None:
    (tmp_path / "config.yaml").write_text(textwrap.dedent(body), encoding="utf-8")


def test_read_raw_config_readonly_returns_cached_object(monkeypatch, tmp_path):
    """Cache hits return the same view object — callers must not mutate."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, "model:\n  default: alpha\n")

    from hermes_cli.config import read_raw_config_readonly

    first = read_raw_config_readonly()
    second = read_raw_config_readonly()
    assert first is second
    assert first["model"]["default"] == "alpha"


def test_read_raw_config_readonly_rejects_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, "model:\n  default: alpha\n")

    from hermes_cli.config import read_raw_config_readonly

    cfg = read_raw_config_readonly()
    with pytest.raises(TypeError):
        cfg["model"] = {}
    with pytest.raises(TypeError):
        cfg["model"]["default"] = "mutated"


def test_read_raw_config_returns_defensive_copy(monkeypatch, tmp_path):
    """Mutating read_raw_config() must not affect read_raw_config_readonly() cache."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(tmp_path, "model:\n  default: alpha\n")

    from hermes_cli.config import read_raw_config, read_raw_config_readonly

    cached = read_raw_config_readonly()
    mutable = read_raw_config()
    mutable["model"]["default"] = "mutated"

    assert read_raw_config_readonly()["model"]["default"] == "alpha"
    assert cached["model"]["default"] == "alpha"


def test_load_config_readonly_matches_load_config_values(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        """\
        agent:
          max_turns: 42
        """,
    )

    from hermes_cli.config import load_config, load_config_readonly

    assert load_config_readonly()["agent"]["max_turns"] == load_config()["agent"]["max_turns"]


def test_load_config_readonly_rejects_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        """\
        agent:
          max_turns: 42
        """,
    )

    from hermes_cli.config import load_config_readonly

    cfg = load_config_readonly()
    with pytest.raises(TypeError):
        cfg["agent"]["max_turns"] = 99


def test_readonly_views_pass_isinstance_dict_checks(monkeypatch, tmp_path):
    """Readonly config must satisfy existing isinstance(cfg, dict) guards."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        """\
        providers:
          openrouter:
            request_timeout_seconds: 120
            models:
              test-model:
                timeout_seconds: 90
        agent:
          max_turns: 42
        """,
    )

    from hermes_cli.config import load_config_readonly
    from hermes_cli.timeouts import get_provider_request_timeout

    cfg = load_config_readonly()
    assert isinstance(cfg, dict)
    assert isinstance(cfg.get("providers"), dict)
    assert get_provider_request_timeout("openrouter", "test-model") == 90.0
