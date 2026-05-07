"""Tests for Teams pipeline runtime wiring into the gateway."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from gateway.config import Platform, PlatformConfig
from gateway.run import GatewayRunner
from plugins.teams_pipeline.runtime import build_pipeline_runtime, build_pipeline_runtime_config


def test_gateway_runner_wires_teams_pipeline_runtime(monkeypatch):
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {Platform.MSGRAPH_WEBHOOK: object()}
    runner._teams_pipeline_runtime_error = None

    calls: list[object] = []

    def _bind(gateway_runner):
        calls.append(gateway_runner)
        return True

    monkeypatch.setattr("plugins.teams_pipeline.runtime.bind_gateway_runtime", _bind)

    GatewayRunner._wire_teams_pipeline_runtime(runner)

    assert calls == [runner]


def test_gateway_runner_skips_wiring_without_msgraph_adapter(monkeypatch):
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.adapters = {Platform.TELEGRAM: MagicMock()}
    runner._teams_pipeline_runtime_error = None

    called = False

    def _bind(_gateway_runner):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr("plugins.teams_pipeline.runtime.bind_gateway_runtime", _bind)

    GatewayRunner._wire_teams_pipeline_runtime(runner)

    assert called is False


def test_runtime_config_disables_teams_delivery_without_target():
    gateway_config = SimpleNamespace(
        platforms={
            Platform("teams"): PlatformConfig(enabled=True, extra={}),
        }
    )

    config = build_pipeline_runtime_config(gateway_config)

    assert "teams_delivery" not in config


def test_build_pipeline_runtime_only_wires_sender_when_delivery_configured(monkeypatch):
    gateway = SimpleNamespace(
        config=SimpleNamespace(
            platforms={
                Platform("teams"): PlatformConfig(enabled=True, extra={}),
            }
        )
    )

    monkeypatch.setattr(
        "plugins.teams_pipeline.runtime.build_graph_client",
        lambda: object(),
    )
    monkeypatch.setattr(
        "plugins.teams_pipeline.runtime.resolve_teams_pipeline_store_path",
        lambda: "/tmp/teams-pipeline-store.json",
    )
    monkeypatch.setattr(
        "plugins.teams_pipeline.runtime.TeamsPipelineStore",
        lambda path: {"path": path},
    )

    runtime = build_pipeline_runtime(gateway)

    assert runtime.teams_sender is None


def test_build_pipeline_runtime_wires_sender_for_graph_target(monkeypatch):
    gateway = SimpleNamespace(
        config=SimpleNamespace(
            platforms={
                Platform("teams"): PlatformConfig(
                    enabled=True,
                    extra={
                        "delivery_mode": "graph",
                        "team_id": "team-1",
                        "channel_id": "channel-1",
                    },
                ),
            }
        )
    )

    monkeypatch.setattr(
        "plugins.teams_pipeline.runtime.build_graph_client",
        lambda: object(),
    )
    monkeypatch.setattr(
        "plugins.teams_pipeline.runtime.resolve_teams_pipeline_store_path",
        lambda: "/tmp/teams-pipeline-store.json",
    )
    monkeypatch.setattr(
        "plugins.teams_pipeline.runtime.TeamsPipelineStore",
        lambda path: {"path": path},
    )

    runtime = build_pipeline_runtime(gateway)

    assert runtime.teams_sender is not None
