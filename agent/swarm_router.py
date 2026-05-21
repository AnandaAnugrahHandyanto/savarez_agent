"""Deterministic first-pass router for the Jeeves swarm operator."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agent.swarm_state import PermissionGrant, RoutingPlan

_PERMISSION_WORDS = (
    "send", "email", "message", "post", "publish", "deploy", "restart", "delete", "remove",
    "drop", "destroy", "overwrite", "merge", "push", "charge", "buy", "purchase", "commit",
)
_PIPE_WORDS = ("n8n", "docker", "container", "compose", "workflow", "webhook")
_SWARM_WORDS = (
    "research", "review", "audit", "compare", "investigate", "lookup", "look up", "analyze",
    "code", "implement", "fix", "test", "summarize", "parallel", "subagent", "agents",
)
_PROCEDURAL_WORDS = (
    "then", "after that", "next", "finally", "validate", "verify", "check", "source of truth",
    "ground truth", "eval", "run", "collect", "parse", "extract",
)


def _count_steps(text: str) -> int:
    lowered = text.lower()
    numbered = len(re.findall(r"(?:^|[\n;])\s*(?:\d+\.|[-*])\s+", text))
    connectors = sum(lowered.count(word) for word in _PROCEDURAL_WORDS)
    # Explicit commas/semicolons with procedural verbs are a decent v1 signal.
    return max(numbered, connectors)


def _permission_requests(text: str) -> List[PermissionGrant]:
    lowered = text.lower()
    requests: List[PermissionGrant] = []
    for word in _PERMISSION_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            requests.append(
                PermissionGrant(
                    permission_id=f"perm_{word.replace(' ', '_')}",
                    description=f"Permission required before external/destructive action: {word}",
                    scope={"matched_word": word},
                )
            )
            break
    if any(word in lowered for word in _PIPE_WORDS):
        requests.append(
            PermissionGrant(
                permission_id="perm_pipe_execution",
                description="Permission required before invoking n8n/docker execution pipes",
                scope={"matched_pipe": True},
            )
        )
    return requests


def _suggested_tasks(text: str, mode: str) -> List[Dict[str, Any]]:
    if mode == "direct":
        return []
    chunks = [part.strip(" .") for part in re.split(r"\b(?:and|then|;|\n)\b", text, flags=re.IGNORECASE) if part.strip()]
    if len(chunks) < 2:
        chunks = [text.strip()]
    return [
        {"title": chunk[:80], "description": chunk, "mode": mode}
        for chunk in chunks[:6]
    ]


def route_request(
    text: str,
    platform_context: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> RoutingPlan:
    """Classify a request without LLM calls.

    Modes are conservative candidates: ``direct``, ``swarm``, ``script``, or
    ``pipe``. Permission requests are advisory and default-deny downstream work.
    """

    del platform_context, config  # reserved for later live policy inputs
    raw_text = text or ""
    lowered = raw_text.lower()
    permissions = _permission_requests(raw_text)
    step_count = _count_steps(raw_text)

    if any(word in lowered for word in _PIPE_WORDS):
        mode = "pipe"
        reason = "Request mentions n8n/docker-style execution pipes."
    elif step_count > 3:
        mode = "script"
        reason = "Request appears to have more than three procedural/validation steps."
    elif (
        sum(1 for word in _SWARM_WORDS if word in lowered) >= 2
        or (" and " in lowered and any(word in lowered for word in _SWARM_WORDS))
        or re.search(r"\b(a|b|c)\b.*\b(a|b|c)\b", lowered)
    ):
        mode = "swarm"
        reason = "Request contains multiple independent research/code/review signals."
    else:
        mode = "direct"
        reason = "Simple prompt suitable for direct handling."

    verification_required = mode in {"swarm", "script", "pipe"} or bool(permissions) or any(
        word in lowered for word in ("verify", "validate", "test", "check")
    )
    return RoutingPlan(
        mode=mode,
        reason=reason,
        suggested_tasks=_suggested_tasks(raw_text, mode),
        permission_requests=permissions,
        verification_required=verification_required,
        metadata={"step_count": step_count, "permission_required": bool(permissions)},
    )


__all__ = ["route_request"]
