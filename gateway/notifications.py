"""Generic proactive notification delivery for gateway-hosted features."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from hermes_constants import get_hermes_home

_runtime: Dict[str, Any] = {}


@dataclass(frozen=True)
class NotificationRequest:
    source: str
    content: str
    idempotency_key: str
    targets: List[Any]
    mirror: bool = True
    mirror_session_id: Optional[str] = None
    observation: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class NotificationResult:
    delivered: bool
    delivered_targets: List[Any] = field(default_factory=list)
    failed_targets: List[Any] = field(default_factory=list)
    mirrored_session_id: Optional[str] = None
    skipped_reason: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _dedup_path() -> Path:
    return get_hermes_home() / "notifications" / "delivery.db"


def _connect(path: Optional[Path] = None) -> sqlite3.Connection:
    resolved = path or _dedup_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved, timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deliveries (
            idempotency_key TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            delivered_at INTEGER NOT NULL,
            result_json TEXT NOT NULL
        )
        """
    )
    return conn


def _is_delivered(idempotency_key: str, path: Optional[Path] = None) -> bool:
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT 1 FROM deliveries WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
    return row is not None


def _record_delivery(
    request: NotificationRequest,
    result: NotificationResult,
    path: Optional[Path] = None,
    *,
    idempotency_key: Optional[str] = None,
) -> None:
    with _connect(path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO deliveries(
                idempotency_key, source, delivered_at, result_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                idempotency_key or request.idempotency_key,
                request.source,
                int(time.time()),
                json.dumps(result.to_dict(), sort_keys=True, default=str),
            ),
        )


def _target_to_deliver_value(target: Any) -> str:
    if isinstance(target, str):
        return target.strip()
    if not isinstance(target, dict):
        raise ValueError("notification target must be a string or mapping")
    platform = str(target.get("platform") or "").strip()
    chat_id = str(target.get("chat_id") or "").strip()
    thread_id = str(target.get("thread_id") or "").strip()
    if not platform:
        raise ValueError("notification target platform is required")
    if not chat_id:
        return platform
    if thread_id:
        return f"{platform}:{chat_id}:{thread_id}"
    return f"{platform}:{chat_id}"


def _target_idempotency_key(request: NotificationRequest, target: str) -> str:
    return f"{request.idempotency_key}|{target}"


def _target_details(target: Any) -> Optional[Dict[str, str]]:
    if isinstance(target, dict):
        platform = str(target.get("platform") or "").strip()
        chat_id = str(target.get("chat_id") or "").strip()
        thread_id = str(target.get("thread_id") or "").strip()
        user_id = str(target.get("user_id") or "").strip()
    elif isinstance(target, str):
        parts = target.strip().split(":")
        if len(parts) < 2:
            return None
        platform, chat_id = parts[0], parts[1]
        thread_id = ":".join(parts[2:]) if len(parts) > 2 else ""
        user_id = ""
    else:
        return None
    if not platform or not chat_id:
        return None
    return {
        "platform": platform,
        "chat_id": chat_id,
        "thread_id": thread_id,
        "user_id": user_id,
    }


def configure_notification_runtime(
    *,
    adapters: Optional[Dict[Any, Any]] = None,
    loop: Any = None,
    session_store: Any = None,
    memory_manager_resolver: Optional[Callable[[str], Any]] = None,
) -> None:
    """Bind optional gateway-owned services for background notification sends."""
    _runtime.clear()
    _runtime.update(
        {
            "adapters": adapters,
            "loop": loop,
            "session_store": session_store,
            "memory_manager_resolver": memory_manager_resolver,
        }
    )


def clear_notification_runtime() -> None:
    """Drop gateway-owned runtime bindings during shutdown."""
    _runtime.clear()


def deliver_notification(
    request: NotificationRequest,
    *,
    adapters: Optional[Dict[Any, Any]] = None,
    loop: Any = None,
    session_store: Any = None,
    memory_manager: Any = None,
    deliverer: Optional[Callable[..., Optional[str]]] = None,
    dedup_path: Optional[Path] = None,
) -> NotificationResult:
    """Deliver one proactive notification through the shared routing path.

    Transcript mirroring and external-memory observation ingest are best
    effort. They cannot change a successful user-facing delivery into failure.
    """
    if not request.idempotency_key:
        raise ValueError("notification idempotency_key is required")
    if adapters is None:
        adapters = _runtime.get("adapters")
    if loop is None:
        loop = _runtime.get("loop")
    if session_store is None:
        session_store = _runtime.get("session_store")

    target_pairs = [
        (item, _target_to_deliver_value(item))
        for item in request.targets
    ]
    target_pairs = [(item, target) for item, target in target_pairs if target]
    if not target_pairs:
        return NotificationResult(delivered=False, skipped_reason="no_targets")

    if deliverer is None:
        from cron.scheduler import _deliver_result
        deliverer = _deliver_result
    delivered_targets: List[Any] = []
    newly_delivered_targets: List[Any] = []
    failed_targets: List[Any] = []
    pending_count = 0
    for original_target, target in target_pairs:
        target_key = _target_idempotency_key(request, target)
        if _is_delivered(target_key, dedup_path):
            delivered_targets.append(original_target)
            continue
        pending_count += 1
        job = {
            "id": target_key,
            "name": request.source or "notification",
            "deliver": target,
            "_wrap_response": False,
        }
        error = deliverer(job, request.content, adapters=adapters, loop=loop)
        if error:
            failed_targets.append({"target": original_target, "error": str(error)})
            continue
        target_result = NotificationResult(
            delivered=True,
            delivered_targets=[original_target],
        )
        _record_delivery(request, target_result, dedup_path, idempotency_key=target_key)
        delivered_targets.append(original_target)
        newly_delivered_targets.append(original_target)

    if pending_count == 0:
        return NotificationResult(delivered=False, skipped_reason="duplicate")
    if not delivered_targets:
        return NotificationResult(
            delivered=False,
            failed_targets=failed_targets,
            error="; ".join(item["error"] for item in failed_targets),
        )

    target_session_id = request.mirror_session_id
    mirrored_session_id = None
    if request.mirror and target_session_id and session_store is not None:
        try:
            session_store.append_to_transcript(
                target_session_id,
                {"role": "assistant", "content": request.content},
            )
            mirrored_session_id = target_session_id
        except Exception:
            pass
    elif newly_delivered_targets:
        details = _target_details(newly_delivered_targets[0])
        if details:
            try:
                from gateway.mirror import _find_session_id, mirror_to_session

                target_session_id = _find_session_id(
                    details["platform"],
                    details["chat_id"],
                    thread_id=details["thread_id"] or None,
                    user_id=details["user_id"] or None,
                )
                if request.mirror and target_session_id:
                    mirror_to_session(
                        details["platform"],
                        details["chat_id"],
                        request.content,
                        source_label=request.source or "notification",
                        thread_id=details["thread_id"] or None,
                        user_id=details["user_id"] or None,
                    )
                    mirrored_session_id = target_session_id
            except Exception:
                target_session_id = None
    if memory_manager is None and target_session_id:
        resolver = _runtime.get("memory_manager_resolver")
        if callable(resolver):
            try:
                memory_manager = resolver(target_session_id)
            except Exception:
                memory_manager = None
    if newly_delivered_targets and request.observation and memory_manager is not None:
        try:
            memory_manager.on_observation(dict(request.observation))
        except Exception:
            pass

    result = NotificationResult(
        delivered=True,
        delivered_targets=delivered_targets,
        failed_targets=failed_targets,
        mirrored_session_id=mirrored_session_id,
    )
    return result
