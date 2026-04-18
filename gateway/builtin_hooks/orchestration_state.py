"""Built-in orchestration-state hook.

Persists lightweight lifecycle state for gateway sessions so Pan can show the
current session status and delegated-child progress without parsing transcripts.
"""

from __future__ import annotations

from agent.orchestration_state import record_agent_end, record_agent_start, record_session_lifecycle


async def handle(event_type: str, context: dict) -> None:
    session_id = str((context or {}).get("session_id") or "").strip()
    if not session_id:
        return

    if event_type == "agent:start":
        record_agent_start(
            session_id,
            platform=(context or {}).get("platform"),
            user_id=(context or {}).get("user_id"),
            message=(context or {}).get("message"),
        )
        return

    if event_type == "agent:end":
        status = str((context or {}).get("status") or "").strip() or ""
        if not status:
            orchestration = (context or {}).get("orchestration") or {}
            if isinstance(orchestration, dict):
                status = str(orchestration.get("outcomeStatus") or "").strip()
        record_agent_end(
            session_id,
            status=status or "completed",
            response=(context or {}).get("response"),
        )
        return

    if event_type == "session:end":
        record_session_lifecycle(session_id, "ended")
        return

    if event_type == "session:reset":
        record_session_lifecycle(session_id, "reset")
