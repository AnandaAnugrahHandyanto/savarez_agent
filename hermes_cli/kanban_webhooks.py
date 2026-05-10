"""Kanban webhook delivery — async outbound HTTP notifications.

Fired from kanban_db task-transition hooks after the DB transaction
commits.  Each delivery runs in a daemon ``threading.Thread`` so the
dispatcher / CLI never blocks on HTTP.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.request
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

_KANBAN_WEBHOOK_LOG = logging.getLogger("kanban_webhooks")


def _build_signature(payload_bytes: bytes, secret: Optional[str]) -> str:
    if not secret:
        return ""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def send_webhook_notification(
    url: str,
    secret: Optional[str],
    payload: dict[str, Any],
    *,
    max_retries: int = 3,
) -> bool:
    """Deliver a JSON webhook with HMAC-SHA256 signature.

    Retry up to ``max_retries`` times with exponential backoff
    (1 s, 2 s, 4 s).  Returns ``True`` on a 2xx response,
    ``False`` otherwise.  Logs failures to the
    ``kanban_webhooks`` logger.
    """
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    body_bytes = body.encode("utf-8")
    sig = _build_signature(body_bytes, secret)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Hermes-Kanban-Webhook/1.0",
    }
    if sig:
        headers["X-Kanban-Signature"] = f"sha256={sig}"

    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = 2 ** (attempt - 1)
            time.sleep(delay)
        try:
            req = urllib.request.Request(
                url,
                data=body_bytes,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if 200 <= resp.status < 300:
                    return True
                last_exc = RuntimeError(
                    f"HTTP {resp.status} from webhook {url}"
                )
        except Exception as exc:
            last_exc = exc

    # All retries exhausted
    err_msg = (
        f"Webhook delivery failed after {max_retries + 1} attempts: "
        f"url={url} event={payload.get('event')} "
        f"task={payload.get('task', {}).get('id')} error={last_exc}"
    )
    _KANBAN_WEBHOOK_LOG.warning(err_msg)
    logger.warning(err_msg)
    return False


def _fire_webhooks_async(
    webhooks: list[dict],
    payload: dict[str, Any],
) -> None:
    """Spawn a daemon thread to deliver ``payload`` to every webhook."""
    def _deliver() -> None:
        for wh in webhooks:
            try:
                send_webhook_notification(
                    url=wh["url"],
                    secret=wh.get("secret"),
                    payload=payload,
                )
            except Exception:
                logger.exception("Unhandled exception delivering webhook")

    t = threading.Thread(target=_deliver, daemon=True)
    t.start()


def build_payload(
    event: str,
    board: str,
    task: dict[str, Any],
    run_id: Optional[int] = None,
) -> dict[str, Any]:
    """Build the canonical Kanban webhook JSON payload."""
    return {
        "event": event,
        "board": board,
        "task": {
            "id": task.get("id"),
            "title": task.get("title"),
            "assignee": task.get("assignee"),
            "status": task.get("status"),
            "summary": task.get("summary"),
            "url": f"hermes://kanban/{board}/{task.get('id')}",
            "run_id": run_id,
        },
        "delivery_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
    }


def maybe_fire_webhooks(
    conn,
    event: str,
    board: str,
    task: dict[str, Any],
    run_id: Optional[int] = None,
) -> None:
    """Read matching webhooks from ``conn`` and fire them asynchronously.

    Safe to call inside or outside a write transaction — it only reads
    the webhook table and then spawns a thread.
    """
    from hermes_cli import kanban_db as kb

    webhooks = kb.get_webhooks_for_event(conn, event)
    if not webhooks:
        return
    payload = build_payload(event, board, task, run_id=run_id)
    _fire_webhooks_async(webhooks, payload)
