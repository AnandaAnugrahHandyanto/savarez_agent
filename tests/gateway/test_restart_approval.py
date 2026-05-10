import pytest

from gateway.restart import (
    GATEWAY_RESTART_APPROVAL_REQUIRED_ENV,
    GATEWAY_RESTART_APPROVED_ENV,
    GATEWAY_RESTART_APPROVAL_REQUIRED_MARKER,
    GATEWAY_RESTART_APPROVED_ONCE_MARKER,
    gateway_restart_approval_required,
    mark_gateway_restart_approved_once,
    require_gateway_restart_approval,
)


def test_restart_approval_not_required_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV, raising=False)
    monkeypatch.delenv(GATEWAY_RESTART_APPROVED_ENV, raising=False)

    assert gateway_restart_approval_required(tmp_path) is False
    require_gateway_restart_approval(hermes_home=tmp_path)


def test_restart_approval_required_by_env_blocks_without_override(tmp_path, monkeypatch):
    monkeypatch.setenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV, "1")
    monkeypatch.delenv(GATEWAY_RESTART_APPROVED_ENV, raising=False)

    with pytest.raises(PermissionError, match="explicit approval is required"):
        require_gateway_restart_approval(source="test restart", hermes_home=tmp_path)


def test_restart_approval_required_by_marker_blocks_without_override(tmp_path, monkeypatch):
    monkeypatch.delenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV, raising=False)
    monkeypatch.delenv(GATEWAY_RESTART_APPROVED_ENV, raising=False)
    (tmp_path / GATEWAY_RESTART_APPROVAL_REQUIRED_MARKER).write_text("1")

    with pytest.raises(PermissionError, match="Refusing test restart"):
        require_gateway_restart_approval(source="test restart", hermes_home=tmp_path)


def test_restart_approval_accepts_explicit_argument(tmp_path, monkeypatch):
    monkeypatch.setenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV, "1")
    monkeypatch.delenv(GATEWAY_RESTART_APPROVED_ENV, raising=False)

    require_gateway_restart_approval(approved=True, hermes_home=tmp_path)


def test_restart_approval_accepts_single_command_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV, "1")
    monkeypatch.setenv(GATEWAY_RESTART_APPROVED_ENV, "1")

    require_gateway_restart_approval(hermes_home=tmp_path)


def test_restart_approval_once_marker_bridges_service_signal_and_is_consumed(tmp_path, monkeypatch):
    monkeypatch.setenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV, "1")
    monkeypatch.delenv(GATEWAY_RESTART_APPROVED_ENV, raising=False)

    mark_gateway_restart_approved_once(tmp_path)
    marker = tmp_path / GATEWAY_RESTART_APPROVED_ONCE_MARKER
    assert marker.exists()

    require_gateway_restart_approval(hermes_home=tmp_path, consume_once=True)
    assert not marker.exists()

    with pytest.raises(PermissionError, match="explicit approval is required"):
        require_gateway_restart_approval(hermes_home=tmp_path, consume_once=True)


def test_restart_approval_once_marker_expires(tmp_path, monkeypatch):
    monkeypatch.setenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV, "1")
    monkeypatch.delenv(GATEWAY_RESTART_APPROVED_ENV, raising=False)
    marker = tmp_path / GATEWAY_RESTART_APPROVED_ONCE_MARKER
    marker.write_text(str(0.0), encoding="utf-8")

    with pytest.raises(PermissionError, match="explicit approval is required"):
        require_gateway_restart_approval(hermes_home=tmp_path, consume_once=True)
    assert not marker.exists()
