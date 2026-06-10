"""Monica mobile bug agent plugin.

Monica is intentionally mention-gated and loop-driven: the Slack mention wakes
the agentic workflow, then the workflow decides the next useful step.
"""

from __future__ import annotations

import logging
import re
import threading
from functools import lru_cache
from typing import Any

from gateway.config import Platform

from .config import load_monica_config, runtime_root
from .cli import mobile_bug_agent_command, register_cli
from .loop import MonicaLoop
from .skills import DefaultMonicaSkills
from .slack_flow import MonicaSlackFlow
from .state import MonicaState

logger = logging.getLogger(__name__)
_SLACK_MENTION_RE = re.compile(r"<@([A-Z0-9_]+)(?:\|[^>]+)?>")


@lru_cache(maxsize=1)
def _runtime() -> MonicaSlackFlow:
    config = load_monica_config()
    state_path = runtime_root(config) / "state.sqlite"
    state = MonicaState.open(state_path)
    skills = DefaultMonicaSkills(config=config, state=state)
    loop = MonicaLoop(config=config, state=state, skills=skills)

    def launch(run_id: str) -> None:
        thread = threading.Thread(
            target=_run_loop_safely,
            args=(loop, run_id),
            name=f"monica-loop-{run_id[:8]}",
            daemon=True,
        )
        thread.start()

    return MonicaSlackFlow(config=config, state=state, loop_launcher=launch)


def _run_loop_safely(loop: MonicaLoop, run_id: str) -> None:
    try:
        loop.run(run_id)
    except Exception as exc:  # pragma: no cover - defensive gateway isolation
        logger.warning("Monica loop %s failed: %s", run_id, exc, exc_info=True)
        try:
            loop.state.update_run(run_id, status="failed", failure_reason=str(exc))
        except Exception:
            logger.debug("Failed to mark Monica run %s failed", run_id, exc_info=True)


def _on_pre_gateway_dispatch(event: Any, gateway: Any = None, **_: Any) -> dict[str, Any] | None:
    try:
        return _runtime().handle_gateway_event(event)
    except Exception as exc:  # pragma: no cover - defensive gateway isolation
        _runtime.cache_clear()
        logger.warning("Monica gateway hook unavailable: %s", exc, exc_info=True)
        if _is_slack_monica_mention_fallback(event):
            return {
                "action": "skip_reply",
                "reason": "monica_runtime_unavailable",
                "text": (
                    "Monica could not start because her runtime is not configured correctly. "
                    "Run `hermes mobile-bug-agent doctor` on the host for details."
                ),
            }
        return None


def _is_slack_monica_mention_fallback(event: Any) -> bool:
    source = getattr(event, "source", None)
    if getattr(source, "platform", None) != Platform.SLACK:
        return False
    raw = getattr(event, "raw_message", None)
    if _is_slack_direct_message_fallback(event):
        return True
    text = str(raw.get("text") if isinstance(raw, dict) else getattr(event, "text", "") or "")
    mentioned_ids = set(_SLACK_MENTION_RE.findall(text))
    is_app_mention = isinstance(raw, dict) and str(raw.get("type") or "") == "app_mention"
    try:
        config = load_monica_config()
    except Exception:
        return bool(is_app_mention)
    configured_ids = set(config.slack.bot_user_ids)
    if configured_ids:
        return bool(configured_ids & mentioned_ids)
    return bool(is_app_mention)


def _is_slack_direct_message_fallback(event: Any) -> bool:
    source = getattr(event, "source", None)
    raw = getattr(event, "raw_message", None)
    if isinstance(raw, dict):
        channel_type = str(raw.get("channel_type") or "")
        if channel_type == "im":
            return True
        if channel_type == "mpim":
            return False

    channel_id = str(getattr(source, "chat_id", "") or "")
    chat_type = str(getattr(source, "chat_type", "") or "")
    return chat_type == "dm" and channel_id.startswith("D")


def register(ctx) -> None:
    ctx.register_cli_command(
        name="mobile-bug-agent",
        help="Inspect and operate Monica mobile bug loops",
        setup_fn=register_cli,
        handler_fn=mobile_bug_agent_command,
        description="Operator CLI for Monica Slack-to-Linear mobile bug loops.",
    )
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
