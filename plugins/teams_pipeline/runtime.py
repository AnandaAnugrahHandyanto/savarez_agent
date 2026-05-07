"""Gateway runtime wiring for the Teams meeting pipeline plugin."""

from __future__ import annotations

import logging
from typing import Any

from gateway.config import Platform
from plugins.teams_pipeline.pipeline import TeamsMeetingPipeline
from plugins.teams_pipeline.store import TeamsPipelineStore, resolve_teams_pipeline_store_path
from plugins.teams_pipeline.subscriptions import build_graph_client

logger = logging.getLogger(__name__)


def build_pipeline_runtime_config(gateway_config: Any) -> dict[str, Any]:
    """Build pipeline config from gateway platform config.

    Pipeline-specific knobs live under ``teams.extra.meeting_pipeline`` while
    Teams delivery continues to source its target details from the existing
    Teams platform config.
    """

    teams_config = gateway_config.platforms.get(Platform("teams"))
    teams_extra = dict((teams_config.extra or {}) if teams_config else {})
    pipeline_config = dict(teams_extra.get("meeting_pipeline") or {})

    if teams_config and teams_config.enabled:
        teams_delivery = dict(pipeline_config.get("teams_delivery") or {})
        teams_delivery.setdefault("enabled", True)

        delivery_mode = str(teams_extra.get("delivery_mode") or "").strip()
        if delivery_mode:
            teams_delivery["mode"] = delivery_mode

        for key in (
            "incoming_webhook_url",
            "access_token",
            "team_id",
            "channel_id",
            "chat_id",
        ):
            value = teams_extra.get(key)
            if value not in (None, ""):
                teams_delivery[key] = value

        if teams_delivery:
            pipeline_config["teams_delivery"] = teams_delivery

    return pipeline_config


def build_pipeline_runtime(gateway: Any) -> TeamsMeetingPipeline:
    return TeamsMeetingPipeline(
        graph_client=build_graph_client(),
        store=TeamsPipelineStore(resolve_teams_pipeline_store_path()),
        config=build_pipeline_runtime_config(gateway.config),
    )


def bind_gateway_runtime(gateway: Any) -> bool:
    """Attach the Teams pipeline runtime to the msgraph webhook adapter."""

    adapter = gateway.adapters.get(Platform.MSGRAPH_WEBHOOK)
    if adapter is None:
        return False

    if getattr(gateway, "_teams_pipeline_runtime", None) is not None:
        return True

    try:
        runtime = build_pipeline_runtime(gateway)
    except Exception as exc:
        error_message = str(exc)

        async def _drop_notification(
            notification: dict[str, Any],
            event: Any,
            *,
            _error_message: str = error_message,
        ) -> None:
            logger.warning(
                "Dropping Microsoft Graph notification because Teams pipeline runtime is unavailable: %s",
                _error_message,
            )

        adapter.set_notification_scheduler(_drop_notification)
        gateway._teams_pipeline_runtime_error = error_message
        return False

    async def _schedule(notification: dict[str, Any], event: Any) -> None:
        await runtime.run_notification(notification)

    adapter.set_notification_scheduler(_schedule)
    gateway._teams_pipeline_runtime = runtime
    gateway._teams_pipeline_runtime_error = None
    return True
