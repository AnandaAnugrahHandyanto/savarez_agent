"""Opt-in live frontdesk pre-dispatch helpers."""

from __future__ import annotations

from typing import Any, Callable

from utils import is_truthy_value


def frontdesk_live_enabled(owner: Any, *, session: dict | None = None) -> bool:
    """Return whether live frontdesk interception is explicitly enabled."""
    for carrier in (session, owner):
        if not carrier:
            continue
        if isinstance(carrier, dict):
            if "frontdesk_live_enabled" in carrier:
                return bool(carrier.get("frontdesk_live_enabled"))
            cfg = carrier.get("config")
        else:
            if hasattr(carrier, "frontdesk_live_enabled"):
                return bool(getattr(carrier, "frontdesk_live_enabled"))
            if hasattr(carrier, "_frontdesk_live_enabled"):
                return bool(getattr(carrier, "_frontdesk_live_enabled"))
            cfg = getattr(carrier, "config", None)
        if isinstance(cfg, dict):
            orchestration = cfg.get("orchestration") or {}
            if isinstance(orchestration, dict):
                raw = orchestration.get("frontdesk_live_enabled")
                if raw is not None:
                    return is_truthy_value(raw, default=False)
    return False


def handle_frontdesk_live_input(
    owner: Any,
    request_text: Any,
    *,
    session: dict | None = None,
    session_key: str | None = None,
    source_surface: str,
    main_in_flight: bool = False,
    steer_callback: Callable[[str], Any] | None = None,
    cancel_callback: Callable[[str], Any] | None = None,
):
    """Run the frontdesk control gate and return a consumed result or ``None``.

    ``None`` means the caller should continue its existing main-model path.
    Every non-``None`` result is a local control response and must not be
    enqueued, replayed, or sent to the main model.
    """
    if not frontdesk_live_enabled(owner, session=session):
        return None
    if not isinstance(request_text, str) or not request_text.strip():
        return None

    from agent.orchestration_runtime import (
        OrchestrationRuntime,
        get_or_create_orchestration_runtime,
    )

    runtime_owner = session if session is not None else owner
    if isinstance(runtime_owner, dict):
        runtime = runtime_owner.get("_orchestration_runtime")
        if not isinstance(runtime, OrchestrationRuntime):
            runtime = OrchestrationRuntime.create()
            runtime_owner["_orchestration_runtime"] = runtime
    else:
        runtime = get_or_create_orchestration_runtime(runtime_owner)
    result = runtime.handle_frontdesk_input(
        request_text,
        frontdesk_mode_active=True,
        session_key=session_key,
        source_surface=source_surface,
        main_in_flight=main_in_flight,
        steer_callback=steer_callback,
    )
    if result.action == "main":
        return None
    if result.action == "stopped" and cancel_callback is not None:
        cancel_callback(request_text)
    return result
