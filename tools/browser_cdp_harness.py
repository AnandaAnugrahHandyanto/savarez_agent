#!/usr/bin/env python3
"""Read-only Chrome DevTools Protocol harness.

This module exposes ``browser_cdp_harness``: a narrow, safe CDP adapter for
inspection-only browser workflows.  It intentionally does not accept arbitrary
CDP method names; mutating operations remain behind the lower-level
``browser_cdp`` escape hatch.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

READ_ONLY_ACTIONS = frozenset({"list_targets", "get_version", "evaluate"})
_MUTATING_EXPRESSION_PATTERN = re.compile(
    r"(\b(?:localStorage|sessionStorage)\.(?:setItem|removeItem|clear)\s*\(|"
    r"\b(?:document|window|location)\.(?:write|open|close|assign|replace|reload)\s*\(|"
    r"\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(|"
    r"\b(?:click|submit|focus|blur|remove|append|prepend|before|after|replaceWith)\s*\(|"
    r"\b(?:setAttribute|removeAttribute|classList\.(?:add|remove|toggle|replace))\s*\(|"
    r"\b(?:innerHTML|outerHTML|textContent|innerText|value|href|src|location)\s*=|"
    r"\b(?:delete|new\s+WebSocket)\b)",
    re.IGNORECASE,
)


def _resolve_cdp_endpoint() -> str:
    """Return the current CDP endpoint using the same precedence as browser_cdp."""
    try:
        from tools.browser_cdp_tool import _resolve_cdp_endpoint as _resolve

        return (_resolve() or "").strip()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("browser_cdp_harness: failed to resolve CDP endpoint: %s", exc)
        return ""


def _call_cdp(
    endpoint: str,
    method: str,
    params: Dict[str, Any],
    target_id: Optional[str],
    timeout: float,
) -> Dict[str, Any]:
    """Delegate a single CDP call to the raw CDP implementation."""
    from tools.browser_cdp_tool import _cdp_call, _run_async

    return _run_async(_cdp_call(endpoint, method, params, target_id, timeout))


def _safe_timeout(timeout: Any) -> float:
    try:
        value = float(timeout) if timeout is not None else 30.0
    except (TypeError, ValueError):
        value = 30.0
    return max(1.0, min(value, 120.0))


def _target_id_from_info(info: Dict[str, Any]) -> str:
    return str(info.get("targetId") or info.get("target_id") or "")


def _select_target_id(
    endpoint: str,
    target_url: Optional[str],
    target_title: Optional[str],
    timeout: float,
) -> tuple[Optional[str], Optional[str]]:
    """Resolve a target id from URL/title substring selectors."""
    selectors = [("url", target_url), ("title", target_title)]
    selectors = [(field, str(value)) for field, value in selectors if value]
    if not selectors:
        return None, "target_url or target_title is required when target_id is omitted."

    try:
        target_result = _call_cdp(endpoint, "Target.getTargets", {}, None, timeout)
    except Exception as exc:
        return None, f"Failed to list CDP targets for selector resolution: {exc}"

    targets = target_result.get("targetInfos") or []
    matches = []
    for target in targets:
        if target.get("type") not in (None, "page"):
            continue
        ok = True
        for field, needle in selectors:
            haystack = str(target.get(field) or "")
            if needle not in haystack:
                ok = False
                break
        if ok and _target_id_from_info(target):
            matches.append(target)

    selector_text = ", ".join(f"{field} contains {value!r}" for field, value in selectors)
    if not matches:
        return None, f"No CDP page target matched selector: {selector_text}."
    if len(matches) > 1:
        ids = ", ".join(_target_id_from_info(target) for target in matches[:5])
        return None, f"CDP target selector matched multiple targets ({ids}); pass target_id explicitly."
    return _target_id_from_info(matches[0]), None


def _expression_looks_mutating(expression: str) -> bool:
    """Cheap guardrail for obvious mutations before CDP evaluates code."""
    return bool(_MUTATING_EXPRESSION_PATTERN.search(expression))


def browser_cdp_harness(
    action: str,
    target_id: Optional[str] = None,
    target_url: Optional[str] = None,
    target_title: Optional[str] = None,
    expression: Optional[str] = None,
    timeout: float = 30.0,
) -> str:
    """Run a read-only CDP harness action.

    Supported actions:
    - ``list_targets``: call ``Target.getTargets``.
    - ``get_version``: call ``Browser.getVersion``.
    - ``evaluate``: run a side-effect-checked ``Runtime.evaluate`` expression
      in a specific target/tab. Requires ``target_id`` or a unique
      ``target_url`` / ``target_title`` selector, plus ``expression``.
    """
    safe_action = (action or "").strip()
    if safe_action not in READ_ONLY_ACTIONS:
        return tool_error(
            f"Unsupported read-only CDP harness action: {safe_action!r}. "
            f"Supported actions: {', '.join(sorted(READ_ONLY_ACTIONS))}."
        )

    endpoint = _resolve_cdp_endpoint()
    if not endpoint:
        return tool_error(
            "No CDP endpoint is available. Run '/browser connect' or set "
            "browser.cdp_url before using browser_cdp_harness."
        )
    if not endpoint.startswith(("ws://", "wss://")):
        return tool_error(f"CDP endpoint is not a WebSocket URL: {endpoint!r}")

    safe_timeout = _safe_timeout(timeout)

    method: str
    params: Dict[str, Any]
    call_target_id = target_id

    if safe_action == "list_targets":
        method = "Target.getTargets"
        params = {}
        call_target_id = None
    elif safe_action == "get_version":
        method = "Browser.getVersion"
        params = {}
        call_target_id = None
    else:  # evaluate
        if not expression or not isinstance(expression, str):
            return tool_error("action='evaluate' requires a JavaScript expression string.")
        if _expression_looks_mutating(expression):
            return tool_error(
                "Refusing mutating JavaScript expression in read-only CDP harness. "
                "Use side-effect-free inspection expressions only; route intentional mutations through browser_cdp."
            )
        if not target_id:
            target_id, selector_error = _select_target_id(endpoint, target_url, target_title, safe_timeout)
            if selector_error:
                return tool_error(selector_error, action=safe_action, method="Target.getTargets")
            call_target_id = target_id
        method = "Runtime.evaluate"
        params = {
            "expression": expression,
            "returnByValue": True,
            "throwOnSideEffect": True,
            "awaitPromise": False,
        }

    try:
        result = _call_cdp(endpoint, method, params, call_target_id, safe_timeout)
    except asyncio.TimeoutError as exc:
        return tool_error(f"CDP harness call timed out: {exc}", action=safe_action, method=method)
    except TimeoutError as exc:
        return tool_error(str(exc), action=safe_action, method=method)
    except RuntimeError as exc:
        return tool_error(str(exc), action=safe_action, method=method)
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("browser_cdp_harness unexpected error")
        return tool_error(
            f"Unexpected error: {type(exc).__name__}: {exc}",
            action=safe_action,
            method=method,
        )

    payload: Dict[str, Any] = {
        "success": True,
        "action": safe_action,
        "method": method,
        "result": result,
    }
    if call_target_id:
        payload["target_id"] = call_target_id
    return json.dumps(payload, ensure_ascii=False)


BROWSER_CDP_HARNESS_SCHEMA: Dict[str, Any] = {
    "name": "browser_cdp_harness",
    "description": (
        "Read-only Chrome DevTools Protocol harness for safe browser inspection. "
        "Supports only allowlisted actions: list_targets, get_version, and "
        "evaluate. Evaluation uses Runtime.evaluate with returnByValue=true and "
        "throwOnSideEffect=true, with an additional regex guardrail for obvious "
        "mutations. These checks reduce accidental side effects but are not a "
        "JavaScript sandbox and do not prove arbitrary expressions are pure. Use "
        "it for inspection expressions such as document.title, location.href, or "
        "DOM text extraction. Requires a reachable CDP endpoint from /browser "
        "connect or browser.cdp_url."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": sorted(READ_ONLY_ACTIONS),
                "description": "Read-only harness action to run.",
            },
            "target_id": {
                "type": "string",
                "description": "Target/tab id from action='list_targets'. Required for evaluate unless target_url or target_title uniquely selects a page.",
            },
            "target_url": {
                "type": "string",
                "description": "URL substring used to uniquely select a page target for action='evaluate'.",
            },
            "target_title": {
                "type": "string",
                "description": "Title substring used to uniquely select a page target for action='evaluate'.",
            },
            "expression": {
                "type": "string",
                "description": "JavaScript expression for action='evaluate'. Must be side-effect free.",
            },
            "timeout": {
                "type": "number",
                "description": "Timeout in seconds, clamped to 1..120.",
                "default": 30.0,
            },
        },
        "required": ["action"],
    },
}


def _browser_cdp_harness_check() -> bool:
    """Keep the harness visible; individual calls validate endpoint availability."""
    return True


registry.register(
    name="browser_cdp_harness",
    toolset="browser-cdp-harness",
    schema=BROWSER_CDP_HARNESS_SCHEMA,
    handler=lambda args, **kw: browser_cdp_harness(
        action=args.get("action", ""),
        target_id=args.get("target_id"),
        target_url=args.get("target_url"),
        target_title=args.get("target_title"),
        expression=args.get("expression"),
        timeout=args.get("timeout", 30.0),
    ),
    check_fn=_browser_cdp_harness_check,
    emoji="🔎",
)
