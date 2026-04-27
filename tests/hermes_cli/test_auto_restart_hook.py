"""Tests for the auto-restart hook fired when sensitive config changes.

Covers:
- The sensitive-key regex matrix (positives + negatives).
- ``maybe_restart_gateway`` no-ops when the gateway is not running.
- ``maybe_restart_gateway`` triggers ``restart_gateway`` when running.
- ``HERMES_NO_AUTO_RESTART=1`` and ``no_restart=True`` opt-outs.
- Re-entrancy guard prevents recursion if the hook itself writes config.
- ``save_env_value`` invokes the hook for sensitive keys only.
- ``set_config_value`` invokes the hook for ``model.*`` / ``providers.*``.
- ``_wait_for_gateway_exit`` returns False when the PID never clears.
"""

import os
from unittest.mock import patch

import pytest

import hermes_cli.config as config
import hermes_cli.config_hooks as hooks
import hermes_cli.gateway as gateway


# ---------------------------------------------------------------------------
# Sensitive-key matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "key",
    [
        "LLM_MODEL",
        "HERMES_MODEL",
        "HERMES_INFERENCE_PROVIDER",
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_ALLOWED_USERS",
        "DISCORD_BOT_TOKEN",
        "SLACK_BOT_TOKEN",
        "MATRIX_ACCESS_TOKEN",
        "WHATSAPP_MODE",
        "WHATSAPP_ALLOWED_USERS",
        "GLM_API_KEY",
        "FIRECRAWL_API_KEY",
    ],
)
def test_sensitive_key_matches(key):
    assert hooks.is_sensitive_key(key) is True


@pytest.mark.parametrize(
    "key",
    [
        "THEME",
        "TERMINAL_BACKEND",
        "TERMINAL_DOCKER_IMAGE",
        "HERMES_HOME",
        "PATH",
        "RANDOM_VAR",
        "MODEL_NAME_BUT_NOT_SENSITIVE",  # only LLM_MODEL / HERMES_MODEL match
    ],
)
def test_non_sensitive_key_does_not_match(key):
    assert hooks.is_sensitive_key(key) is False


# ---------------------------------------------------------------------------
# maybe_restart_gateway behaviour
# ---------------------------------------------------------------------------

def test_no_op_when_gateway_not_running(capsys):
    with patch("gateway.status.get_running_pid", return_value=None):
        result = hooks.maybe_restart_gateway("LLM_MODEL changed")
    assert result == gateway.RestartResult.NOT_RUNNING


def test_triggers_restart_when_gateway_running():
    with patch("gateway.status.get_running_pid", return_value=4242):
        with patch.object(gateway, "restart_gateway", return_value=gateway.RestartResult.OK) as mock_restart:
            result = hooks.maybe_restart_gateway("LLM_MODEL changed")
    mock_restart.assert_called_once()
    assert mock_restart.call_args.kwargs["reason"] == "LLM_MODEL changed"
    assert result == gateway.RestartResult.OK


def test_explicit_no_restart_opts_out(capsys):
    with patch("gateway.status.get_running_pid", return_value=4242):
        with patch.object(gateway, "restart_gateway") as mock_restart:
            result = hooks.maybe_restart_gateway("LLM_MODEL changed", no_restart=True)
    mock_restart.assert_not_called()
    assert result is None
    captured = capsys.readouterr()
    assert "Auto-restart skipped" in captured.out


def test_env_var_opts_out(monkeypatch):
    monkeypatch.setenv("HERMES_NO_AUTO_RESTART", "1")
    with patch("gateway.status.get_running_pid", return_value=4242):
        with patch.object(gateway, "restart_gateway") as mock_restart:
            result = hooks.maybe_restart_gateway("LLM_MODEL changed", quiet=True)
    mock_restart.assert_not_called()
    assert result is None


def test_reentrancy_guard_blocks_nested_calls():
    """If the hook itself triggers another save_env_value, we must not recurse."""
    calls = []

    def fake_restart(reason, quiet=False):
        # Simulate a nested call into the hook from inside restart_gateway
        # (shouldn't happen in practice, but we want a safety net).
        nested = hooks.maybe_restart_gateway("nested call", quiet=True)
        calls.append(("nested_returned", nested))
        return gateway.RestartResult.OK

    with patch("gateway.status.get_running_pid", return_value=4242):
        with patch.object(gateway, "restart_gateway", side_effect=fake_restart):
            hooks.maybe_restart_gateway("outer call", quiet=True)

    assert calls == [("nested_returned", None)]


# ---------------------------------------------------------------------------
# save_env_value integration
# ---------------------------------------------------------------------------

def test_save_env_value_triggers_hook_for_sensitive_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    triggered = []

    def fake_hook(reason, quiet=False, no_restart=False):
        triggered.append(reason)

    monkeypatch.setattr("hermes_cli.config_hooks.maybe_restart_gateway", fake_hook)

    config.save_env_value("OPENROUTER_API_KEY", "sk-test-123")

    assert triggered == ["OPENROUTER_API_KEY changed"]


def test_save_env_value_does_not_trigger_hook_for_inert_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    triggered = []

    monkeypatch.setattr(
        "hermes_cli.config_hooks.maybe_restart_gateway",
        lambda *a, **kw: triggered.append(a),
    )

    config.save_env_value("TERMINAL_DOCKER_IMAGE", "ubuntu:22.04")

    assert triggered == []


# ---------------------------------------------------------------------------
# set_config_value integration
# ---------------------------------------------------------------------------

def test_set_config_value_triggers_hook_for_model(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    triggered = []

    monkeypatch.setattr(
        "hermes_cli.config_hooks.maybe_restart_gateway",
        lambda reason, quiet=False, no_restart=False: triggered.append(reason),
    )

    config.set_config_value("model.default", "anthropic/claude-sonnet-4-6")

    assert triggered == ["model.default changed"]


def test_set_config_value_does_not_trigger_for_unrelated_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    triggered = []

    monkeypatch.setattr(
        "hermes_cli.config_hooks.maybe_restart_gateway",
        lambda *a, **kw: triggered.append(a),
    )

    config.set_config_value("theme", "dark")

    assert triggered == []


# ---------------------------------------------------------------------------
# _wait_for_gateway_exit return contract
# ---------------------------------------------------------------------------

def test_wait_for_gateway_exit_returns_true_when_pid_clears():
    pids = iter([4242, None])  # first poll: alive, second: gone

    def fake_pid():
        try:
            return next(pids)
        except StopIteration:
            return None

    with patch("gateway.status.get_running_pid", side_effect=fake_pid):
        with patch("time.sleep"):
            assert gateway._wait_for_gateway_exit(timeout=2.0, force_after=10.0) is True


def test_wait_for_gateway_exit_returns_false_when_pid_persists(capsys):
    """Stuck PID must surface as False so callers abort the start path."""
    # Use a force_after greater than the timeout so the SIGKILL branch never
    # fires (signal.SIGKILL doesn't exist on Windows where this test runs in
    # CI) — the goal here is the timeout return contract, not the kill path.
    with patch("gateway.status.get_running_pid", return_value=4242):
        with patch("time.sleep"):
            result = gateway._wait_for_gateway_exit(timeout=0.05, force_after=10.0)
    assert result is False
    captured = capsys.readouterr()
    assert "refusing to start a colliding instance" in captured.out


# ---------------------------------------------------------------------------
# restart_gateway dispatch
# ---------------------------------------------------------------------------

def test_restart_gateway_no_op_when_not_running(capsys):
    with patch("gateway.status.get_running_pid", return_value=None):
        result = gateway.restart_gateway(reason="test")
    assert result == gateway.RestartResult.NOT_RUNNING


def test_restart_gateway_uses_systemd_when_unit_exists(tmp_path, monkeypatch):
    fake_unit = tmp_path / "hermes-gateway.service"
    fake_unit.write_text("[Unit]\n")

    monkeypatch.setattr(gateway, "is_linux", lambda: True)
    monkeypatch.setattr(gateway, "is_macos", lambda: False)
    monkeypatch.setattr(gateway, "get_systemd_unit_path", lambda system=False: fake_unit)

    with patch("gateway.status.get_running_pid", return_value=4242):
        with patch.object(gateway, "systemd_restart") as mock_systemd:
            result = gateway.restart_gateway(reason="model change", quiet=True)

    mock_systemd.assert_called_once_with(system=False)
    assert result == gateway.RestartResult.OK


def test_restart_gateway_returns_stop_timeout_in_manual_mode(tmp_path, monkeypatch):
    """Manual mode + stuck PID => STOP_TIMEOUT, no start attempted."""
    monkeypatch.setattr(gateway, "is_linux", lambda: False)
    monkeypatch.setattr(gateway, "is_macos", lambda: False)

    with patch("gateway.status.get_running_pid", return_value=4242):
        with patch("os.kill"):
            with patch.object(gateway, "_wait_for_gateway_exit", return_value=False):
                result = gateway.restart_gateway(reason="manual stuck", quiet=True)

    assert result == gateway.RestartResult.STOP_TIMEOUT
