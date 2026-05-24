"""Teal shim tools — drive the deterministic Teal cash-flow engine over HTTP.

Teal is a separate FastAPI service that owns all financial state and math (see
the `teal` repo, ADR 0001/0002). These tools are thin HTTP shims: they never
compute anything, they fetch (or trigger) state the engine owns and hand the
result to the model as JSON. The engine recomputes the forecast deterministically
on approval; the model only narrates numbers a tool returned — never its own.

Base URL comes from ``TEAL_BASE_URL`` (default ``http://127.0.0.1:8420``).
"""

import logging
import os
from typing import Optional

import httpx

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:8420"


def _base_url() -> str:
    return os.environ.get("TEAL_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _call(method: str, path: str, json_body: Optional[dict] = None):
    """Call the Teal service. Returns (data, error_string) — exactly one is set."""
    url = f"{_base_url()}{path}"
    try:
        resp = httpx.request(method, url, json=json_body, timeout=10.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        return None, tool_error(
            f"The Teal engine is currently unreachable at {_base_url()}."
        )
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except ValueError:
            pass
        suffix = f": {detail}" if detail else ""
        return None, tool_error(
            f"Teal returned HTTP {exc.response.status_code} for {url}{suffix}"
        )
    except httpx.HTTPError as exc:
        return None, tool_error(f"Teal request failed: {exc}")

    try:
        return resp.json(), None
    except ValueError:
        return None, tool_error("Teal returned a non-JSON response")


# ---------------------------------------------------------------------------
# get_incident
# ---------------------------------------------------------------------------

GET_INCIDENT_SCHEMA = {
    "name": "get_incident",
    "description": (
        "Fetch the current cash-flow incident snapshot from the Teal engine: "
        "incident title and severity, projected balances, root-cause evidence, "
        "proposed actions and their deltas, approval status, and the "
        "reconciliation figures. Returns the engine's deterministic state as "
        "JSON. Call this whenever you need real numbers about the user's cash "
        "flow — never estimate them yourself."
    ),
    "parameters": {"type": "object", "properties": {}},
}


def _handle_get_incident(args: dict, **kwargs) -> str:
    data, err = _call("GET", "/api/incident")
    return err or tool_result(data)


# ---------------------------------------------------------------------------
# approve_actions
# ---------------------------------------------------------------------------

APPROVE_ACTIONS_SCHEMA = {
    "name": "approve_actions",
    "description": (
        "Approve proposed corrective actions in the Teal engine and return the "
        "recomputed incident snapshot (new projected balance, approved delta, "
        "updated action statuses, reconciliation). Approval triggers a "
        "deterministic forecast recompute server-side. Set approve_all=true to "
        "approve everything, or pass specific action_ids. This changes state — "
        "only call it once the user has explicitly approved the actions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific action IDs to approve. Omit when approve_all is true.",
            },
            "approve_all": {
                "type": "boolean",
                "description": "Approve all currently proposed actions.",
            },
        },
    },
}


def _handle_approve_actions(args: dict, **kwargs) -> str:
    action_ids = args.get("action_ids")
    approve_all = bool(args.get("approve_all", False))
    if not approve_all and not action_ids:
        return tool_error(
            "Nothing to approve: set approve_all=true or pass one or more action_ids."
        )
    data, err = _call(
        "POST",
        "/api/actions/approve",
        json_body={"action_ids": action_ids, "all": approve_all},
    )
    return err or tool_result(data)


# ---------------------------------------------------------------------------
# reset_demo
# ---------------------------------------------------------------------------

RESET_DEMO_SCHEMA = {
    "name": "reset_demo",
    "description": (
        "Reset the Teal engine to its seed scenario, discarding any approvals "
        "and restoring the original projected shortfall. Returns the fresh "
        "incident snapshot. Use this to restart the demo from a clean state."
    ),
    "parameters": {"type": "object", "properties": {}},
}


def _handle_reset_demo(args: dict, **kwargs) -> str:
    data, err = _call("POST", "/api/demo/reset")
    return err or tool_result(data)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="get_incident",
    toolset="teal",
    schema=GET_INCIDENT_SCHEMA,
    handler=_handle_get_incident,
    requires_env=[],
    is_async=False,
    description="Fetch the current Teal cash-flow incident snapshot",
    emoji="\U0001f9fe",
)

registry.register(
    name="approve_actions",
    toolset="teal",
    schema=APPROVE_ACTIONS_SCHEMA,
    handler=_handle_approve_actions,
    requires_env=[],
    is_async=False,
    description="Approve Teal corrective actions and recompute the forecast",
    emoji="✅",
)

registry.register(
    name="reset_demo",
    toolset="teal",
    schema=RESET_DEMO_SCHEMA,
    handler=_handle_reset_demo,
    requires_env=[],
    is_async=False,
    description="Reset the Teal engine to its seed scenario",
    emoji="\U0001f504",
)
