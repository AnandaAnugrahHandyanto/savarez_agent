from __future__ import annotations

import logging
import os
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from hermes_cli.profiles import get_active_profile_name

if TYPE_CHECKING:
    from cli import HermesCLI

logger = logging.getLogger(__name__)


@dataclass
class LiveRuntimeState:
    thread: Optional[threading.Thread] = None
    stop_event: Optional[threading.Event] = None
    registered_session_id: Optional[str] = None


def _display_name(cli: "HermesCLI") -> str:
    title = None
    try:
        if getattr(cli, "_session_db", None):
            title = cli._session_db.get_session_title(cli.session_id)
    except Exception:
        title = None
    if title:
        return title
    role = getattr(cli, "_live_role", None)
    if role:
        return role
    return cli.session_id


def _build_payload(cli: "HermesCLI") -> dict:
    cwd = os.getenv("TERMINAL_CWD") or os.getcwd()
    provider = getattr(cli, "provider", None) or getattr(cli, "requested_provider", None) or "auto"
    return {
        "session_id": cli.session_id,
        "source": "cli",
        "display_name": _display_name(cli),
        "role": getattr(cli, "_live_role", None),
        "model": getattr(cli, "model", None),
        "provider": provider,
        "profile": get_active_profile_name(),
        "cwd": cwd,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "agent_running": bool(getattr(cli, "_agent_running", False)),
        "accepts_messages": True,
        "started_at": getattr(cli, "session_start", None).timestamp() if getattr(cli, "session_start", None) else time.time(),
    }


def refresh_live_registration(cli: "HermesCLI") -> None:
    db = getattr(cli, "_session_db", None)
    state = getattr(cli, "_live_runtime", None)
    if not db or not state:
        return

    payload = _build_payload(cli)
    current_session_id = payload["session_id"]
    previous = state.registered_session_id
    if previous and previous != current_session_id:
        try:
            db.remove_live_session(previous)
        except Exception:
            logger.debug("Failed removing old live session row for %s", previous, exc_info=True)
    db.upsert_live_session(**payload)
    state.registered_session_id = current_session_id
    try:
        db.prune_live_sessions()
    except Exception:
        logger.debug("Live session prune failed", exc_info=True)


def stop_live_runtime(cli: "HermesCLI") -> None:
    state = getattr(cli, "_live_runtime", None)
    db = getattr(cli, "_session_db", None)
    if state and state.stop_event:
        state.stop_event.set()
    if state and state.thread and state.thread.is_alive():
        state.thread.join(timeout=1.5)
    if db and state and state.registered_session_id:
        try:
            db.remove_live_session(state.registered_session_id)
        except Exception:
            logger.debug("Failed removing live session row during shutdown", exc_info=True)
    if state:
        state.registered_session_id = None


def start_live_runtime(cli: "HermesCLI", *, interval_seconds: float = 0.75) -> None:
    state = getattr(cli, "_live_runtime", None)
    if not state or not getattr(cli, "_session_db", None):
        return
    if state.thread and state.thread.is_alive():
        return

    stop_event = threading.Event()
    state.stop_event = stop_event

    def _loop() -> None:
        while not stop_event.is_set() and not getattr(cli, "_should_exit", False):
            try:
                refresh_live_registration(cli)
                cli._drain_live_session_messages()
            except Exception:
                logger.debug("Live CLI heartbeat loop error", exc_info=True)
            stop_event.wait(interval_seconds)

    state.thread = threading.Thread(target=_loop, daemon=True, name="hermes-live-sessions")
    state.thread.start()
