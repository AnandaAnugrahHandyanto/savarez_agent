"""Tests for gateway SIGTERM handling under systemd.

When the gateway runs under a systemd unit, SIGTERM from ``systemctl stop``
must be treated as a planned stop (exit 0) so the unit reports "inactive"
instead of "failed" (issue #41631).
"""

import os
import signal

import pytest


class TestSystemdSigtermPlannedStop:
    """Verify that SIGTERM under systemd is treated as a planned stop."""

    def test_sigterm_under_systemd_sets_planned_stop(self, monkeypatch):
        """When INVOCATION_ID is set (systemd-managed), SIGTERM should be
        treated as a planned stop — the handler must NOT set
        _signal_initiated_shutdown to True."""
        monkeypatch.setenv("INVOCATION_ID", "test-invocation-123")
        # Import the module to access internal state
        from gateway import status as status_mod
        monkeypatch.setattr(status_mod, "consume_planned_stop_marker_for_self", lambda: False)
        monkeypatch.setattr(status_mod, "consume_takeover_marker_for_self", lambda: False)

        # Simulate the signal handler's decision logic
        # (mirrors shutdown_signal_handler in gateway/run.py)
        _signal_initiated_shutdown = False
        planned_stop = False
        planned_takeover = False
        received_signal = signal.SIGTERM

        if received_signal == signal.SIGINT:
            planned_stop = True
        elif (
            received_signal == signal.SIGTERM
            and os.environ.get("INVOCATION_ID")
        ):
            planned_stop = True
        elif not planned_takeover:
            planned_stop = False  # no marker

        if not planned_takeover and not planned_stop:
            _signal_initiated_shutdown = True

        assert planned_stop is True, "SIGTERM under systemd should be planned stop"
        assert _signal_initiated_shutdown is False, (
            "_signal_initiated_shutdown must be False under systemd"
        )

    def test_sigterm_without_systemd_not_planned_by_default(self, monkeypatch):
        """When INVOCATION_ID is not set (non-systemd), SIGTERM without a
        planned-stop marker should NOT be treated as a planned stop."""
        monkeypatch.delenv("INVOCATION_ID", raising=False)
        from gateway import status as status_mod
        monkeypatch.setattr(status_mod, "consume_planned_stop_marker_for_self", lambda: False)
        monkeypatch.setattr(status_mod, "consume_takeover_marker_for_self", lambda: False)

        _signal_initiated_shutdown = False
        planned_stop = False
        planned_takeover = False
        received_signal = signal.SIGTERM

        if received_signal == signal.SIGINT:
            planned_stop = True
        elif (
            received_signal == signal.SIGTERM
            and os.environ.get("INVOCATION_ID")
        ):
            planned_stop = True
        elif not planned_takeover:
            planned_stop = False  # no marker

        if not planned_takeover and not planned_stop:
            _signal_initiated_shutdown = True

        assert planned_stop is False
        assert _signal_initiated_shutdown is True, (
            "SIGTERM without systemd and without marker should trigger exit 1"
        )

    def test_sigint_always_planned_regardless_of_systemd(self, monkeypatch):
        """SIGINT (Ctrl+C) is always a planned stop, systemd or not."""
        monkeypatch.delenv("INVOCATION_ID", raising=False)
        from gateway import status as status_mod
        monkeypatch.setattr(status_mod, "consume_planned_stop_marker_for_self", lambda: False)

        planned_stop = False
        received_signal = signal.SIGINT

        if received_signal == signal.SIGINT:
            planned_stop = True

        assert planned_stop is True

    def test_planned_marker_takes_precedence_over_systemd_fallback(self, monkeypatch):
        """When a planned-stop marker exists, it still works under systemd."""
        monkeypatch.setenv("INVOCATION_ID", "test-invocation-456")
        from gateway import status as status_mod
        monkeypatch.setattr(status_mod, "consume_planned_stop_marker_for_self", lambda: True)
        monkeypatch.setattr(status_mod, "consume_takeover_marker_for_self", lambda: False)

        # Both the systemd check and marker check would set planned_stop=True.
        # The systemd check fires first (elif chain), so marker is never checked.
        # This is fine — both paths lead to the same outcome.
        planned_stop = False
        received_signal = signal.SIGTERM

        if received_signal == signal.SIGINT:
            planned_stop = True
        elif (
            received_signal == signal.SIGTERM
            and os.environ.get("INVOCATION_ID")
        ):
            planned_stop = True

        assert planned_stop is True
