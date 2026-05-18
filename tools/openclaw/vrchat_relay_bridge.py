"""Python bridge to hypura-harness VRChat relay endpoints (TS logic stays in vendor)."""

from __future__ import annotations

from typing import Any

from tools.openclaw.harness_client import call_harness, is_harness_running


def relay_available() -> bool:
    return is_harness_running()


def vrc_status() -> dict[str, Any]:
    if not is_harness_running():
        return _harness_offline("vrc/status")
    return call_harness("vrc/status", method="GET")


def vrc_channels_readiness() -> dict[str, Any]:
    if not is_harness_running():
        return _harness_offline("channels/readiness")
    return call_harness("channels/readiness", method="GET")


def vrc_chatbox(text: str, *, send_immediately: bool = True, notify: bool = False) -> dict[str, Any]:
    if not is_harness_running():
        return _harness_offline("vrc/chatbox")
    return call_harness(
        "vrc/chatbox",
        {"text": text, "send_immediately": send_immediately, "notify": notify},
    )


def vrc_parameter(name: str, value: float | int | bool | str) -> dict[str, Any]:
    if not is_harness_running():
        return _harness_offline("vrc/parameter")
    return call_harness("vrc/parameter", {"name": name, "value": value})


def auto_osc_status() -> dict[str, Any]:
    if not is_harness_running():
        return _harness_offline("auto_osc/status")
    return call_harness("auto_osc/status", method="GET")


def auto_osc_start() -> dict[str, Any]:
    if not is_harness_running():
        return _harness_offline("auto_osc/start")
    return call_harness("auto_osc/start", {})


def auto_osc_stop() -> dict[str, Any]:
    if not is_harness_running():
        return _harness_offline("auto_osc/stop")
    return call_harness("auto_osc/stop", {})


def _harness_offline(endpoint: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": "harness_offline",
        "endpoint": endpoint,
        "limitation": "vrchat-relay TypeScript runs inside hypura-harness; start with: hermes harness start",
        "recommendation": "hermes harness start",
    }
