"""Regression tests for gateway per-turn env reload preserving config authority.

Issue #19158: startup bridges config.yaml agent.max_turns into
HERMES_MAX_ITERATIONS, but a later per-turn load_dotenv(..., override=True)
can restore a stale .env HERMES_MAX_ITERATIONS value before the next turn.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from gateway import run as gateway_run


def test_reload_runtime_env_preserves_config_max_turns(tmp_path: Path, monkeypatch) -> None:
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"agent": {"max_turns": 9000}}),
        encoding="utf-8",
    )
    (hermes_home / ".env").write_text(
        "HERMES_MAX_ITERATIONS=90\nOPENROUTER_API_KEY=fresh-key\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setenv("HERMES_MAX_ITERATIONS", "9000")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    gateway_run._reload_runtime_env_preserving_config_authority()

    assert os.environ["OPENROUTER_API_KEY"] == "fresh-key"
    assert os.environ["HERMES_MAX_ITERATIONS"] == "9000"


def test_reload_runtime_env_keeps_env_max_iterations_when_config_omits_key(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(yaml.safe_dump({"agent": {}}), encoding="utf-8")
    (hermes_home / ".env").write_text("HERMES_MAX_ITERATIONS=123\n", encoding="utf-8")

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.delenv("HERMES_MAX_ITERATIONS", raising=False)

    gateway_run._reload_runtime_env_preserving_config_authority()

    assert os.environ["HERMES_MAX_ITERATIONS"] == "123"


def test_resolve_gateway_max_iterations_prefers_config_after_runtime_env_reload(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"agent": {"max_turns": 300}}),
        encoding="utf-8",
    )
    (hermes_home / ".env").write_text("HERMES_MAX_ITERATIONS=90\n", encoding="utf-8")

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setenv("HERMES_MAX_ITERATIONS", "90")

    max_iterations = gateway_run._resolve_gateway_max_iterations(reload_runtime_env=True)

    assert max_iterations == 300
    assert os.environ["HERMES_MAX_ITERATIONS"] == "300"


def test_api_server_agent_uses_config_authoritative_max_iterations(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump({"agent": {"max_turns": 300}, "platform_toolsets": {"api_server": []}}),
        encoding="utf-8",
    )
    (hermes_home / ".env").write_text("HERMES_MAX_ITERATIONS=90\n", encoding="utf-8")

    monkeypatch.setattr(gateway_run, "_hermes_home", hermes_home)
    monkeypatch.setenv("HERMES_MAX_ITERATIONS", "90")
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {})
    monkeypatch.setattr(gateway_run, "_resolve_gateway_model", lambda: "test-model")
    monkeypatch.setattr(gateway_run, "_load_gateway_config", lambda: {"platform_toolsets": {"api_server": []}})
    monkeypatch.setattr(gateway_run.GatewayRunner, "_load_reasoning_config", staticmethod(lambda: None))
    monkeypatch.setattr(gateway_run.GatewayRunner, "_load_fallback_model", staticmethod(lambda: None))

    import run_agent
    from gateway.config import PlatformConfig
    from gateway.platforms.api_server import APIServerAdapter

    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(run_agent, "AIAgent", FakeAgent)
    adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={}))
    monkeypatch.setattr(adapter, "_ensure_session_db", lambda: None)

    agent = adapter._create_agent(session_id="test-session")

    assert isinstance(agent, FakeAgent)
    assert captured["max_iterations"] == 300
    assert os.environ["HERMES_MAX_ITERATIONS"] == "300"
