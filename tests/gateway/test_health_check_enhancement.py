"""Tests for enhanced gateway health check endpoints.

The health check system now provides:
  - GET /health  — liveness probe with uptime and gateway state (backward-compat)
  - GET /ready   — readiness probe returning 503 when gateway is not running
  - GET /v1/status — comprehensive diagnostics (platforms, agents, config)
"""

import asyncio
import json
import time
from unittest.mock import patch, MagicMock

import pytest

from gateway.platforms.api_server import APIServerAdapter
from gateway.status import _build_runtime_status_record


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_mock_request():
    """Return a minimal aiohttp-like request object."""
    return MagicMock()


def _make_instance():
    """Create an APIServerAdapter instance with minimal state for testing."""
    instance = APIServerAdapter.__new__(APIServerAdapter)
    instance._start_time = time.monotonic()
    return instance


# ── /health tests ─────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Enhanced /health endpoint includes uptime and gateway state."""

    def test_health_returns_ok_status(self):
        instance = _make_instance()
        response = asyncio.run(instance._handle_health(_make_mock_request()))
        body = json.loads(response.text)
        assert body["status"] == "ok"
        assert "platform" in body

    def test_health_includes_uptime(self):
        instance = _make_instance()
        instance._start_time = time.monotonic() - 100  # Started 100s ago
        response = asyncio.run(instance._handle_health(_make_mock_request()))
        body = json.loads(response.text)
        assert "uptime_seconds" in body
        assert body["uptime_seconds"] >= 99  # Allow small timing variance

    def test_health_includes_gateway_state(self):
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "running"}
            response = asyncio.run(instance._handle_health(_make_mock_request()))
            body = json.loads(response.text)
            assert body.get("gateway_state") == "running"

    def test_health_returns_503_for_startup_failed(self):
        """Liveness probe must return 503 for terminal failure states."""
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "startup_failed"}
            response = asyncio.run(instance._handle_health(_make_mock_request()))
            assert response.status == 503
            body = json.loads(response.text)
            assert body["status"] == "error"
            assert body["gateway_state"] == "startup_failed"

    def test_health_returns_503_for_stopped(self):
        """Liveness probe must return 503 when gateway has stopped."""
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "stopped"}
            response = asyncio.run(instance._handle_health(_make_mock_request()))
            assert response.status == 503

    def test_health_returns_200_for_unknown_state(self):
        """Missing or unreadable status file must not trigger a restart."""
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status", return_value=None):
            response = asyncio.run(instance._handle_health(_make_mock_request()))
            assert response.status == 200

    def test_health_returns_200_for_draining(self):
        """Draining is a live transitional state — liveness probe stays green."""
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "draining"}
            response = asyncio.run(instance._handle_health(_make_mock_request()))
            assert response.status == 200


# ── /ready tests ──────────────────────────────────────────────────────────


class TestReadyEndpoint:
    """GET /ready returns 503 when gateway is not in 'running' state."""

    def test_ready_returns_200_when_running(self):
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "running"}
            response = asyncio.run(instance._handle_ready(_make_mock_request()))
            assert response.status == 200
            body = json.loads(response.text)
            assert body["ready"] is True

    def test_ready_returns_503_when_starting(self):
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "starting"}
            response = asyncio.run(instance._handle_ready(_make_mock_request()))
            assert response.status == 503
            body = json.loads(response.text)
            assert body["ready"] is False

    def test_ready_returns_503_when_draining(self):
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "draining"}
            response = asyncio.run(instance._handle_ready(_make_mock_request()))
            assert response.status == 503

    def test_ready_returns_503_when_no_status_file(self):
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = None
            response = asyncio.run(instance._handle_ready(_make_mock_request()))
            assert response.status == 503


# ── /v1/status tests ──────────────────────────────────────────────────────


class TestStatusEndpoint:
    """GET /v1/status returns comprehensive gateway diagnostics."""

    def test_status_includes_platforms(self):
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {
                "gateway_state": "running",
                "platforms": {
                    "telegram": {"state": "connected"},
                    "discord": {"state": "fatal", "error_code": "token_invalid"},
                },
                "active_agents": 3,
                "pid": 12345,
            }
            response = asyncio.run(instance._handle_status(_make_mock_request()))
            body = json.loads(response.text)
            assert "platforms" in body
            assert "telegram" in body["platforms"]
            assert "discord" in body["platforms"]

    def test_status_includes_active_agents_count(self):
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {
                "gateway_state": "running",
                "platforms": {},
                "active_agents": 5,
                "pid": 12345,
            }
            response = asyncio.run(instance._handle_status(_make_mock_request()))
            body = json.loads(response.text)
            assert body["active_agents"] == 5

    def test_status_includes_uptime(self):
        instance = _make_instance()
        instance._start_time = time.monotonic() - 200
        with patch("gateway.platforms.api_server.read_runtime_status") as mock_status:
            mock_status.return_value = {"gateway_state": "running", "platforms": {}, "pid": 12345}
            response = asyncio.run(instance._handle_status(_make_mock_request()))
            body = json.loads(response.text)
            assert "uptime_seconds" in body
            assert body["uptime_seconds"] >= 199

    def test_status_does_not_expose_pid_or_argv(self):
        """Sensitive process metadata must not appear in the /v1/status response."""
        instance = _make_instance()
        full_record = _build_runtime_status_record()
        full_record["gateway_state"] = "running"
        full_record["platforms"] = {}
        full_record["active_agents"] = 0
        with patch("gateway.platforms.api_server.read_runtime_status", return_value=full_record):
            response = asyncio.run(instance._handle_status(_make_mock_request()))
            body = json.loads(response.text)
            assert "pid" not in body
            assert "argv" not in body
            assert "exit_reason" not in body
            assert "restart_requested" not in body

    def test_status_returns_200_when_status_file_unreadable(self):
        """Status endpoint must degrade gracefully when status file is unavailable."""
        instance = _make_instance()
        with patch("gateway.platforms.api_server.read_runtime_status", side_effect=OSError("disk full")):
            response = asyncio.run(instance._handle_status(_make_mock_request()))
            assert response.status == 200
            body = json.loads(response.text)
            assert body["gateway_state"] == "unknown"
            assert body["active_agents"] == 0
