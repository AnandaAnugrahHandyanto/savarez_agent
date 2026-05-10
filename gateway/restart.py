"""Shared gateway restart constants, parsing helpers, and safety gates."""

import os
import time
from pathlib import Path

from hermes_cli.config import DEFAULT_CONFIG, get_hermes_home

# EX_TEMPFAIL from sysexits.h — used to ask the service manager to restart
# the gateway after a graceful drain/reload path completes.
GATEWAY_SERVICE_RESTART_EXIT_CODE = 75

DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT = float(
    DEFAULT_CONFIG["agent"]["restart_drain_timeout"]
)

GATEWAY_RESTART_APPROVAL_REQUIRED_ENV = "HERMES_GATEWAY_RESTART_REQUIRES_APPROVAL"
GATEWAY_RESTART_APPROVED_ENV = "HERMES_GATEWAY_RESTART_APPROVED"
GATEWAY_RESTART_APPROVAL_REQUIRED_MARKER = ".gateway_restart_approval_required"
GATEWAY_RESTART_APPROVED_ONCE_MARKER = ".gateway_restart_approved_once"
GATEWAY_RESTART_APPROVED_ONCE_TTL_SECONDS = 120.0
GATEWAY_PROCESS_ENV = "HERMES_GATEWAY_PROCESS"
GATEWAY_INLINE_SERVICE_CONTROL_ENV = "HERMES_GATEWAY_INLINE_SERVICE_CONTROL"
GATEWAY_INLINE_SERVICE_CONTROL_COMMANDS = {
    "install",
    "uninstall",
    "start",
    "stop",
    "restart",
    "migrate-legacy",
}


def parse_restart_drain_timeout(raw: object) -> float:
    """Parse a configured drain timeout, falling back to the shared default."""
    try:
        value = float(raw) if str(raw or "").strip() else DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT
    except (TypeError, ValueError):
        return DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT
    return max(0.0, value)


def _truthy(raw: object) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on", "approved"}


def gateway_restart_approval_required(hermes_home: Path | None = None) -> bool:
    """Return True when local policy requires an explicit restart approval."""
    if _truthy(os.getenv(GATEWAY_RESTART_APPROVAL_REQUIRED_ENV)):
        return True
    try:
        home = hermes_home or get_hermes_home()
        return (Path(home) / GATEWAY_RESTART_APPROVAL_REQUIRED_MARKER).exists()
    except Exception:
        return False


def _approved_once_marker_path(hermes_home: Path | None = None) -> Path:
    home = hermes_home or get_hermes_home()
    return Path(home) / GATEWAY_RESTART_APPROVED_ONCE_MARKER


def mark_gateway_restart_approved_once(hermes_home: Path | None = None) -> None:
    """Create a short-lived approval marker for a service-delivered restart signal.

    CLI flags/env vars are visible to the `hermes gateway restart` process, but
    not to an already-running launchd/systemd gateway that receives SIGUSR1.
    This marker bridges that single approved command into the running process.
    """
    marker = _approved_once_marker_path(hermes_home)
    marker.write_text(str(time.time()), encoding="utf-8")


def _consume_gateway_restart_approved_once(hermes_home: Path | None = None) -> bool:
    try:
        marker = _approved_once_marker_path(hermes_home)
        raw = marker.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return False
    except Exception:
        return False

    try:
        approved_at = float(raw)
    except ValueError:
        approved_at = 0.0

    try:
        marker.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        # A stale marker should not permanently approve restarts.
        return False

    return (time.time() - approved_at) <= GATEWAY_RESTART_APPROVED_ONCE_TTL_SECONDS


def gateway_restart_approved(
    *,
    approved: bool = False,
    hermes_home: Path | None = None,
    consume_once: bool = False,
) -> bool:
    """Return True when this restart call carries an explicit approval override."""
    if bool(approved) or _truthy(os.getenv(GATEWAY_RESTART_APPROVED_ENV)):
        return True
    if consume_once:
        return _consume_gateway_restart_approved_once(hermes_home)
    return False


def gateway_restart_approval_message(source: str = "gateway restart") -> str:
    return (
        f"Refusing {source}: explicit approval is required by local policy. "
        "Ask the user for approval first, then rerun with --approved or set "
        f"{GATEWAY_RESTART_APPROVED_ENV}=1 for the single approved command. "
        "Emergency recovery can still bypass this by setting the same override."
    )


def gateway_inline_service_control_message(source: str = "gateway service control") -> str:
    return (
        f"Refusing {source}: gateway-origin sessions must not start, stop, "
        "restart, install, uninstall, or kickstart the gateway inline. "
        "Run the service-control command out-of-band after explicit operator "
        "approval so the active gateway session is not killed mid-turn."
    )


def is_gateway_origin_process() -> bool:
    """Return True inside the long-lived gateway or one of its subprocesses."""
    if _truthy(os.getenv(GATEWAY_PROCESS_ENV)):
        return True
    if _truthy(os.getenv(GATEWAY_INLINE_SERVICE_CONTROL_ENV)):
        return True
    if _truthy(os.getenv("HERMES_GATEWAY_SESSION")):
        return True
    try:
        from gateway.session_context import get_session_env

        platform = get_session_env("HERMES_SESSION_PLATFORM", "")
        return bool(platform and platform != "local")
    except Exception:
        return False


def require_no_gateway_inline_service_control(
    *,
    command: str | None = None,
    source: str = "gateway service control",
) -> None:
    """Reject gateway service-control from inside the gateway process tree."""
    if not command:
        command = source
    if is_gateway_origin_process():
        raise PermissionError(gateway_inline_service_control_message(command))


def require_gateway_restart_approval(
    *,
    source: str = "gateway restart",
    approved: bool = False,
    hermes_home: Path | None = None,
    consume_once: bool = False,
) -> None:
    """Raise PermissionError when restart policy requires approval and none was supplied."""
    if gateway_restart_approval_required(hermes_home) and not gateway_restart_approved(
        approved=approved,
        hermes_home=hermes_home,
        consume_once=consume_once,
    ):
        raise PermissionError(gateway_restart_approval_message(source))
