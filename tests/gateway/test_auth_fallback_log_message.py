"""When the primary provider's credential pool is rate-limited, the gateway
should log an actionable "rate-limited (resets in X)" line instead of the
misleading "No Codex credentials stored" message that the legacy
``_read_codex_tokens`` path used to emit.
"""

from __future__ import annotations

import logging
import time
from unittest.mock import patch


def _write_config_with_openrouter_fallback(tmp_path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "model:\n"
        "  provider: openai-codex\n"
        "fallback_model:\n"
        "  provider: openrouter\n"
        "  model: meta-llama/llama-4-maverick\n",
        encoding="utf-8",
    )


def test_rate_limit_authError_produces_actionable_warning(tmp_path, monkeypatch, caplog):
    """Gateway warning should name the provider and the reset window."""
    from hermes_cli.auth import AuthError

    _write_config_with_openrouter_fallback(tmp_path)
    monkeypatch.setattr("gateway.run._hermes_home", tmp_path)
    monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "openai-codex")

    reset_at = time.time() + 4320  # 1h 12m
    rate_limit_summary = {
        "kind": "rate_limit",
        "label": "rate-limited",
        "provider": "openai-codex",
        "soonest_reset_at": reset_at,
        "soonest_remaining_seconds": 4320,
        "last_error_reason": "usage_limit_reached",
        "last_error_code": 429,
        "entry_count": 1,
    }
    primary_exc = AuthError.from_pool_exhaustion("openai-codex", rate_limit_summary)

    def _mock_resolve(**kwargs):
        requested = kwargs.get("requested", "")
        if requested and "codex" in str(requested).lower():
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

    with patch(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        side_effect=_mock_resolve,
    ):
        with caplog.at_level(logging.WARNING, logger="gateway.run"):
            from gateway.run import _resolve_runtime_agent_kwargs

            result = _resolve_runtime_agent_kwargs()

    # Fallback still works.
    assert result["provider"] == "openrouter"

    # The warning must describe what actually happened: rate-limit, provider
    # name, reset window. The pre-fix misleading text must be gone.
    warnings = "\n".join(rec.getMessage() for rec in caplog.records if rec.levelno >= logging.WARNING)
    assert "rate-limited" in warnings
    assert "openai-codex" in warnings
    assert "1h 11m" in warnings or "1h 12m" in warnings
    assert "trying fallback" in warnings
    assert "No Codex credentials stored" not in warnings


def test_plain_authError_still_logs_generic_message(tmp_path, monkeypatch, caplog):
    """Unstructured AuthError (no ``kind``) should keep the legacy log shape."""
    from hermes_cli.auth import AuthError

    _write_config_with_openrouter_fallback(tmp_path)
    monkeypatch.setattr("gateway.run._hermes_home", tmp_path)
    monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "openai-codex")

    def _mock_resolve(**kwargs):
        requested = kwargs.get("requested", "")
        if requested and "codex" in str(requested).lower():
            raise AuthError("token refresh failed")
        return {
            "api_key": "fallback-key",
            "base_url": "https://openrouter.ai/api/v1",
            "provider": "openrouter",
            "api_mode": "openai_chat",
            "command": None,
            "args": None,
            "credential_pool": None,
        }

    with patch(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        side_effect=_mock_resolve,
    ):
        with caplog.at_level(logging.WARNING, logger="gateway.run"):
            from gateway.run import _resolve_runtime_agent_kwargs

            _resolve_runtime_agent_kwargs()

    warnings = "\n".join(rec.getMessage() for rec in caplog.records if rec.levelno >= logging.WARNING)
    assert "primary provider auth failed" in warnings.lower()
    assert "token refresh failed" in warnings
