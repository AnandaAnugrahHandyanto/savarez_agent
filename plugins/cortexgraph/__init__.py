"""CortexGraph connector plugin.

This plugin keeps the Hermes <-> CortexGraph connection reliable in two ways:

* a ``pre_llm_call`` hook injects a compact runtime contract on CortexGraph
  related turns, preserving the system-prompt cache while reminding the agent
  to heartbeat, resolve payloads, claim/checkpoint threads, answer questions,
  and verify delivery-to-completion rather than delivery-only.
* a ``transform_tool_result`` hook appends the same caution to webhook delivery
  inspection results so the agent does not overclaim autonomous wake success.

The plugin is deliberately side-effect-light: status/config tools read local
configuration and return redacted diagnostics; they do not mutate CortexGraph.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

try:  # PyYAML is present in normal Hermes installs, but keep import fail-safe.
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover
    def get_hermes_home() -> Path:
        return Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()


_RELEVANT_TERMS = (
    "cortexgraph",
    "workgraph",
    "gbrain",
    "company brain",
    "company-brain",
    "versatly",
    "question.asked",
    "thread.mention",
    "webhook.delivery",
)

_DELIVERY_TOOL_NAMES = {
    "mcp_cortexgraph_webhook_delivery_list",
    "mcp_cortexgraph_webhook_delivery_read",
    "mcp_cortexgraph_webhook_delivery_replay",
    "cortexgraph_webhook_delivery_list",
}

_SECRET_HEADER_RE = re.compile(r"authorization|token|secret|key|cookie", re.I)


RUNTIME_CONTRACT_TEMPLATE = """## CortexGraph runtime contract

Use CortexGraph as the durable runtime whenever this turn involves CortexGraph, WorkGraph/GBrain, Versatly/company-brain coordination, or CortexGraph webhook events.

Start of run:
1. Call `agent.heartbeat(status="working")` with display name, capabilities, current intent, and current thread if known.
2. Resolve the active question/thread from the webhook payload first. If the payload is partial, fall back to `question.inbox`, `ledger.recent`, and thread context.
3. Create or claim the relevant thread with `thread.create` / `thread.claim` and write an initial `thread.checkpoint` with scope, assumptions, payload evidence, and next action.

During run:
- Checkpoint meaningful milestones, blockers, decisions, external side effects, context sources/proposals, and answered/asked questions.
- If durable knowledge was learned, create `context.source.create` plus reviewed context proposals instead of leaving facts only in chat.
- For directed questions, close them with `question.answer`; do not only report to the user.

Autonomous wake verification:
- delivery != completion. A webhook delivery row or HTTP 200 only proves transport.
- Success requires target-agent evidence: fresh heartbeat/checkpoint and `question.answer` or thread progress for the same question/thread id.
- Maintain wake plumbing with `webhook.endpoint.update/disable/delete` and `trigger.update/disable/delete`; prefer narrow `question.asked` and `thread.mention` triggers over recursive lifecycle triggers.
""".strip()


CORTEXGRAPH_CONFIG_STATUS = {
    "name": "cortexgraph_config_status",
    "description": (
        "Inspect Hermes' CortexGraph bridge configuration without printing secrets. "
        "Reports whether mcp_servers.cortexgraph is configured and redacts auth headers."
    ),
    "parameters": {"type": "object", "properties": {}},
}

CORTEXGRAPH_RUNTIME_CONTRACT = {
    "name": "cortexgraph_runtime_contract",
    "description": (
        "Return the CortexGraph runtime contract Hermes should follow for autonomous "
        "wake runs: heartbeat, thread claim/checkpoint, question answer, and delivery-to-completion verification."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_message": {
                "type": "string",
                "description": "Optional user/webhook message to extract question/thread/event ids from.",
            }
        },
    },
}


def _disabled() -> bool:
    return os.environ.get("HERMES_CORTEXGRAPH_DISABLE", "").lower() in {"1", "true", "yes", "on"}


def _always() -> bool:
    return os.environ.get("HERMES_CORTEXGRAPH_ALWAYS", "").lower() in {"1", "true", "yes", "on"}


def _config_path() -> Path:
    return get_hermes_home() / "config.yaml"


def _load_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _redact(value: Any, *, key: str = "") -> Any:
    if isinstance(value, dict):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, key=key) for v in value]
    if _SECRET_HEADER_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, str) and re.search(r"bearer\s+|token[_:= -]|secret[_:= -]", value, re.I):
        return "[REDACTED]"
    return value


def _extract_payload_facts(user_message: str | None) -> dict[str, Any]:
    if not user_message:
        return {}
    text = user_message.strip()
    facts: dict[str, Any] = {}
    try:
        payload = json.loads(text)
    except Exception:
        payload = None
    if isinstance(payload, dict):
        for key in ("event", "eventName", "questionId", "threadId", "deliveryId", "triggerId"):
            value = payload.get(key)
            if value is not None:
                facts[key] = value
        nested = payload.get("payload")
        if isinstance(nested, dict):
            for key in ("event", "eventName", "questionId", "threadId", "deliveryId", "triggerId"):
                value = nested.get(key)
                if value is not None and key not in facts:
                    facts[key] = value
    else:
        for key, pattern in {
            "questionId": r"q_[A-Za-z0-9_-]+",
            "threadId": r"thread_[A-Za-z0-9_-]+",
            "deliveryId": r"(?:del|delivery)_[A-Za-z0-9_-]+",
        }.items():
            match = re.search(pattern, text)
            if match:
                facts[key] = match.group(0)
    return facts


def _is_relevant(user_message: str | None, platform: str | None = None) -> bool:
    if _disabled():
        return False
    if _always():
        return True
    text = (user_message or "").lower()
    if platform == "webhook" and "cortex" in text:
        return True
    return any(term in text for term in _RELEVANT_TERMS)


def _build_runtime_context(user_message: str | None = None) -> str:
    facts = _extract_payload_facts(user_message)
    if not facts:
        return RUNTIME_CONTRACT_TEMPLATE
    lines = [RUNTIME_CONTRACT_TEMPLATE, "", "Payload hints detected by cortexgraph plugin:"]
    for key in sorted(facts):
        lines.append(f"- {key}: `{facts[key]}`")
    lines.append("- Resolve the active question/thread from these ids before doing work.")
    return "\n".join(lines)


def _tool_runtime_contract(args: dict[str, Any] | None = None, **_: Any) -> str:
    args = args or {}
    return json.dumps({"context": _build_runtime_context(args.get("user_message"))})


def _tool_config_status(args: dict[str, Any] | None = None, **_: Any) -> str:
    cfg = _load_config()
    mcp_servers = cfg.get("mcp_servers") if isinstance(cfg, dict) else None
    server = mcp_servers.get("cortexgraph") if isinstance(mcp_servers, dict) else None
    webhook_subs = get_hermes_home() / "webhook_subscriptions.json"
    payload = {
        "configured": isinstance(server, dict),
        "mcp_server": _redact(server or {}),
        "webhook_subscriptions_file": str(webhook_subs),
        "webhook_subscriptions_file_exists": webhook_subs.exists(),
        "advice": (
            "Restart Hermes/gateway after MCP config changes. For autonomous wake, verify delivery -> "
            "gateway accepted -> heartbeat/checkpoint -> question.answer/thread progress."
        ),
    }
    return json.dumps(payload, sort_keys=True)


def _on_pre_llm_call(**kwargs: Any) -> dict[str, str] | None:
    user_message = kwargs.get("user_message")
    platform = kwargs.get("platform")
    if not _is_relevant(str(user_message or ""), str(platform or "")):
        return None
    return {"context": _build_runtime_context(str(user_message or ""))}


def _result_mentions_delivered(result: str) -> bool:
    text = result.lower()
    return "delivered" in text or "webhook.delivery" in text or "delivery" in text


def _on_transform_tool_result(tool_name: str, args: Any, result: str, **kwargs: Any) -> str | None:
    if _disabled() or tool_name not in _DELIVERY_TOOL_NAMES:
        return None
    if not isinstance(result, str) or not _result_mentions_delivered(result):
        return None
    warning = (
        "\n\n---\n"
        "CortexGraph wake verification reminder: delivery != completion. "
        "Before reporting autonomous wake success, verify a target-agent heartbeat/checkpoint "
        "and `question.answer` or `thread.checkpoint`/thread progress for the same event."
    )
    return result + warning


def register(ctx: Any) -> None:
    """Register plugin tools, hooks, and skill."""
    plugin_dir = Path(__file__).resolve().parent
    ctx.register_tool(
        name="cortexgraph_config_status",
        toolset="cortexgraph",
        schema=CORTEXGRAPH_CONFIG_STATUS,
        handler=_tool_config_status,
        description="Inspect redacted CortexGraph MCP/webhook config status.",
        emoji="🧠",
    )
    ctx.register_tool(
        name="cortexgraph_runtime_contract",
        toolset="cortexgraph",
        schema=CORTEXGRAPH_RUNTIME_CONTRACT,
        handler=_tool_runtime_contract,
        description="Return the CortexGraph runtime/wake verification contract.",
        emoji="🧠",
    )
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("transform_tool_result", _on_transform_tool_result)
    ctx.register_skill(
        "cortexgraph-connector",
        plugin_dir / "skills" / "cortexgraph-connector" / "SKILL.md",
        description="Operate the Hermes ↔ CortexGraph connector plugin.",
    )
