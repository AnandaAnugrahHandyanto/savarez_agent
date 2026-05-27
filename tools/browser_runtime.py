"""Runtime contract for browser.read/browser.write style tools.

This module keeps policy (session write consent) separate from execution
(ActionBroker dispatch to the existing browser implementation).  The existing
browser_* tools remain as compatibility shims; the new contract routes through
these classes so read/write calls cannot bypass consent checks by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional


BROWSER_SESSION_CONSENTS: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class BrowserActionRequest:
    kind: str  # "read" | "write"
    action: str
    parameters: Dict[str, Any]
    task_id: Optional[str] = None


class BrowserSessionConsentStore:
    """In-process browser session consent registry keyed by task/session id."""

    @staticmethod
    def _key(task_id: Optional[str]) -> str:
        return task_id or "default"

    def status(self, task_id: Optional[str]) -> dict[str, Any]:
        key = self._key(task_id)
        entry = BROWSER_SESSION_CONSENTS.get(key) or {}
        return {
            "task_id": key,
            "write": bool(entry.get("write")),
            "granted_at": entry.get("granted_at"),
            "reason": entry.get("reason"),
        }

    def grant(self, task_id: Optional[str], *, reason: str = "") -> dict[str, Any]:
        key = self._key(task_id)
        BROWSER_SESSION_CONSENTS[key] = {
            "write": True,
            "granted_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason or None,
        }
        return self.status(key)

    def revoke(self, task_id: Optional[str]) -> dict[str, Any]:
        key = self._key(task_id)
        BROWSER_SESSION_CONSENTS.pop(key, None)
        return self.status(key)

    def has_write_consent(self, task_id: Optional[str]) -> bool:
        return self.status(task_id)["write"]


class ApprovalService:
    """Policy gate for browser actions.

    Read actions are always allowed. Write actions require explicit per-session
    browser consent granted through the public browser_session API.
    """

    def __init__(self, consent_store: BrowserSessionConsentStore | None = None):
        self.consent_store = consent_store or BrowserSessionConsentStore()

    def authorize(self, request: BrowserActionRequest) -> dict[str, Any]:
        if request.kind == "read":
            return {"approved": True}
        if request.kind != "write":
            return {"approved": False, "error": f"Unknown browser action kind: {request.kind}"}
        if self.consent_store.has_write_consent(request.task_id):
            return {"approved": True}
        return {
            "approved": False,
            "error_code": "browser_session_consent_required",
            "error": (
                "Browser write action requires session consent. Call "
                "browser_session(action='grant') after inspecting the session, "
                "or choose a read-only browser action."
            ),
            "consent": self.consent_store.status(request.task_id),
        }


class ActionBroker:
    """Dispatch browser read/write requests to the live browser runtime."""

    def execute(self, request: BrowserActionRequest) -> dict[str, Any]:
        import tools.browser_tool as bt

        params = dict(request.parameters or {})
        task_id = request.task_id

        if request.kind == "read":
            if request.action == "snapshot":
                return _loads(bt.browser_snapshot(
                    full=bool(params.get("full", False)),
                    task_id=task_id,
                    user_task=params.get("user_task"),
                ))
            if request.action == "console":
                if params.get("expression"):
                    return {
                        "success": False,
                        "error_code": "browser_read_expression_forbidden",
                        "error": (
                            "browser_read(action='console') can read buffered console messages only. "
                            "JavaScript expressions may mutate the page and are intentionally "
                            "not part of the read-only browser contract."
                        ),
                    }
                return _loads(bt.browser_console(
                    clear=bool(params.get("clear", False)),
                    expression=None,
                    task_id=task_id,
                ))
            if request.action == "images":
                return _loads(bt.browser_get_images(task_id=task_id))
            raise ValueError(f"Unsupported browser read action: {request.action}")

        if request.kind == "write":
            if request.action == "navigate":
                return _loads(bt.browser_navigate(url=str(params.get("url", "")), task_id=task_id))
            if request.action == "click":
                return _loads(bt.browser_click(ref=str(params.get("ref", "")), task_id=task_id))
            if request.action == "type":
                return _loads(bt.browser_type(
                    ref=str(params.get("ref", "")),
                    text=str(params.get("text", "")),
                    task_id=task_id,
                ))
            if request.action == "scroll":
                return _loads(bt.browser_scroll(direction=str(params.get("direction", "down")), task_id=task_id))
            if request.action == "back":
                return _loads(bt.browser_back(task_id=task_id))
            if request.action == "press":
                return _loads(bt.browser_press(key=str(params.get("key", "")), task_id=task_id))
            raise ValueError(f"Unsupported browser write action: {request.action}")

        raise ValueError(f"Unsupported browser action kind: {request.kind}")


def _loads(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {"success": True, "data": parsed}
    return {"success": True, "data": value}


def execute_browser_action(
    *,
    kind: str,
    action: str,
    parameters: Optional[Dict[str, Any]] = None,
    task_id: Optional[str] = None,
    approval_service: ApprovalService | None = None,
    broker: ActionBroker | None = None,
) -> dict[str, Any]:
    request = BrowserActionRequest(
        kind=kind,
        action=action,
        parameters=dict(parameters or {}),
        task_id=task_id,
    )
    approval = (approval_service or ApprovalService()).authorize(request)
    if not approval.get("approved"):
        return {"success": False, **approval}
    return (broker or ActionBroker()).execute(request)
