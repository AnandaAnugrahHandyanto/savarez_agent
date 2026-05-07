"""Tests for Teams pipeline runtime wiring into the gateway."""

from __future__ import annotations

from unittest.mock import MagicMock

from gateway.config import Platform
from gateway.run import GatewayRunner


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
