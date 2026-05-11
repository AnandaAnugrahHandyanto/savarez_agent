"""Test that ConnectError / TimeoutError trigger fallback provider resolution.

Regression test for M1 smoke finding (2026-05-11): fallback was gated on
AuthError only; a hard connection refusal (HTTP 000) left the gateway dark.

Covers:
  - gateway/run.py::_resolve_runtime_agent_kwargs
  - cli.py::ProviderSetup._resolve  (tested via the isinstance guard)
"""

from unittest.mock import patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# gateway/run.py — _resolve_runtime_agent_kwargs
# ---------------------------------------------------------------------------

class TestResolveRuntimeAgentKwargsNetworkFallback:
    """_resolve_runtime_agent_kwargs must fall back on network errors, not just AuthError."""

    def _make_fallback_config(self, tmp_path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "model:\n  provider: custom-local\n"
            "fallback_model:\n"
            "  - provider: openrouter\n"
            "    model: meta-llama/llama-4-maverick\n"
        )

    def _mock_resolve_factory(self, primary_exc):
        """Return a resolve_runtime_provider side_effect that raises on primary."""
        call_count = {"n": 0}

        def _mock(**kwargs):
            call_count["n"] += 1
            requested = (kwargs.get("requested") or "").lower()
            if "custom" in requested or call_count["n"] == 1:
                raise primary_exc
            return {
                "api_key": "fallback-key",
                "base_url": "https://openrouter.ai/api/v1",
                "provider": "openrouter",
                "api_mode": "openai_chat",
                "command": None,
                "args": None,
                "credential_pool": None,
            }

        return _mock, call_count

    @pytest.mark.parametrize("exc", [
        httpx.ConnectError("Connection refused"),
        httpx.ConnectTimeout("Connect timed out"),
        httpx.ReadTimeout("Read timed out"),
        ConnectionError("Network unreachable"),
    ])
    def test_network_error_tries_fallback(self, tmp_path, monkeypatch, exc):
        """Network errors on primary should trigger fallback, not hard failure."""
        self._make_fallback_config(tmp_path)
        monkeypatch.setattr("gateway.run._hermes_home", tmp_path)
        monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "custom-local")

        mock_fn, call_count = self._mock_resolve_factory(exc)

        with patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            side_effect=mock_fn,
        ):
            from gateway.run import _resolve_runtime_agent_kwargs
            result = _resolve_runtime_agent_kwargs()

        assert result["provider"] == "openrouter", (
            f"Expected fallback provider 'openrouter', got {result['provider']!r}"
        )
        assert call_count["n"] >= 2, "Expected at least primary + one fallback attempt"

    def test_connect_error_no_fallback_raises(self, tmp_path, monkeypatch):
        """When primary errors and no fallback is configured, RuntimeError is raised."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("model:\n  provider: custom-local\n")

        monkeypatch.setattr("gateway.run._hermes_home", tmp_path)
        monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "custom-local")

        with patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            from gateway.run import _resolve_runtime_agent_kwargs
            with pytest.raises(RuntimeError):
                _resolve_runtime_agent_kwargs()

    def test_auth_error_still_triggers_fallback(self, tmp_path, monkeypatch):
        """Existing AuthError behaviour must not regress."""
        from hermes_cli.auth import AuthError

        self._make_fallback_config(tmp_path)
        monkeypatch.setattr("gateway.run._hermes_home", tmp_path)
        monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "custom-local")

        mock_fn, call_count = self._mock_resolve_factory(AuthError("token expired"))

        with patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            side_effect=mock_fn,
        ):
            from gateway.run import _resolve_runtime_agent_kwargs
            result = _resolve_runtime_agent_kwargs()

        assert result["provider"] == "openrouter"
