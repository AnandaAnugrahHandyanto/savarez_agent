from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def awareos_overlay_enabled() -> bool:
    return os.getenv("AWAREOS_OVERLAY_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def awareos_context_eval_enabled() -> bool:
    return os.getenv("AWAREOS_CONTEXT_EVAL_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def awareos_work_overlay_events_path() -> Path:
    raw = os.getenv("AWAREOS_WORK_OVERLAY_EVENTS_PATH", "").strip()
    if raw:
        return Path(raw)
    return get_hermes_home() / "state" / "awareos_work_overlay_events.jsonl"


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, ensure_ascii=False) + "\n")


def record_work_overlay_event(payload: dict[str, Any]) -> None:
    """Durably record an AwareOS work-overlay event for out-of-process ingest.

    This is intentionally schema-light: we persist stable references and
    compact summaries only (hashes, ids, counts). Do NOT include raw chat
    bodies/tool outputs in ``payload``.
    """
    if not awareos_overlay_enabled():
        return
    _append_jsonl(awareos_work_overlay_events_path(), payload)


def record_work_overlay_start(
    *,
    overlay_id: str,
    source: dict[str, Any],
    prompt_text: str | None = None,
    journal: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": "awareos.work_overlay_event.v1",
        "recorded_at": _now_iso(),
        "action": "start",
        "overlay_id": overlay_id,
        "source": dict(source or {}),
    }
    if prompt_text is not None:
        payload["prompt"] = {
            "sha256": _sha256_text(prompt_text),
            "length": len(prompt_text or ""),
        }
    if journal:
        payload["journal"] = dict(journal)
    record_work_overlay_event(payload)


def record_work_overlay_stop(
    *,
    overlay_id: str,
    source: dict[str, Any],
    result: dict[str, Any] | None = None,
    journal: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "schema_version": "awareos.work_overlay_event.v1",
        "recorded_at": _now_iso(),
        "action": "stop",
        "overlay_id": overlay_id,
        "source": dict(source or {}),
    }
    if result:
        payload["result"] = dict(result)
    if journal:
        payload["journal"] = dict(journal)
    record_work_overlay_event(payload)


_TIME_KEYWORDS = (
    "today",
    "tomorrow",
    "yesterday",
    "tonight",
    "this week",
    "next week",
    "schedule",
    "calendar",
    "meeting",
    "appointment",
    "free time",
    "availability",
    "time",
    "timezone",
)
_GOAL_KEYWORDS = (
    "goal",
    "goals",
    "plan",
    "plans",
    "roadmap",
    "milestone",
    "todo",
    "to-do",
    "task",
    "tasks",
)
_AWAREOS_KEYWORDS = ("awareos", "overlay", "contextual overlay", "work overlay")


def should_trigger_context_eval(message_text: str) -> bool:
    text = (message_text or "").strip().lower()
    if not text:
        return False
    if text.startswith("/"):
        return False
    return any(k in text for k in (*_TIME_KEYWORDS, *_GOAL_KEYWORDS, *_AWAREOS_KEYWORDS))


def context_eval_debounce_secs() -> int:
    raw = os.getenv("AWAREOS_CONTEXT_EVAL_DEBOUNCE_SECS", "").strip()
    try:
        return max(0, int(raw)) if raw else 900
    except Exception:
        return 900


@dataclass(frozen=True)
class ContextEvalResult:
    ok: bool
    snippet: str
    meta: dict[str, Any]


def _awareos_bearer_token() -> str:
    # Prefer a context-eval-specific env var, but support reusing the AwareOS
    # North Star token name for convenience in unified deployments.
    return (
        os.getenv("AWAREOS_CONTEXT_EVAL_BEARER_TOKEN", "").strip()
        or os.getenv("AWAREOS_MCP_SERVICE_TOKEN", "").strip()
    )


def _awareos_contextual_overlay_tz_offset_min() -> str | None:
    raw = (
        os.getenv("AWAREOS_CONTEXTUAL_OVERLAY_TZ_OFFSET_MIN", "").strip()
        or os.getenv("AWAREOS_CONTEXT_EVAL_TZ_OFFSET_MIN", "").strip()
    )
    if not raw:
        return None
    try:
        # Normalize to an int-like string; AwareOS clamps on its side.
        return str(int(float(raw)))
    except Exception:
        return None


def _looks_like_contextual_overlay_url(url: str) -> bool:
    # AwareOS canonical route: GET /api/kaze/contextual-overlay
    return "contextual-overlay" in (url or "")


def _build_overlay_snippet(payload: Any) -> str:
    """Convert the AwareOS contextual overlay response to a compact snippet."""
    if not isinstance(payload, dict):
        return ""
    prompts = payload.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        return ""

    lines: list[str] = []
    for prompt in prompts[:6]:
        if not isinstance(prompt, dict):
            continue
        kind = str(prompt.get("kind") or "").strip()
        priority = str(prompt.get("priority") or "").strip()
        reason = str(prompt.get("reason") or "").strip()
        suggested = str(prompt.get("suggested_action") or "").strip()
        if not (kind or reason or suggested):
            continue

        head_parts: list[str] = []
        if priority:
            head_parts.append(f"[{priority}]")
        if kind:
            head_parts.append(kind)
        head = " ".join(head_parts).strip()

        if head and reason:
            lines.append(f"- {head}: {reason}")
        elif head:
            lines.append(f"- {head}")
        elif reason:
            lines.append(f"- {reason}")
        else:
            lines.append("-")

        if suggested:
            lines.append(f"  suggested: {suggested}")

    snippet = "\n".join(lines).strip()
    return snippet[:1500].rstrip()


def _run_contextual_overlay_eval(*, url: str, message_text: str) -> ContextEvalResult:
    started = time.time()
    token = _awareos_bearer_token()
    if not token:
        return ContextEvalResult(
            ok=False,
            snippet="",
            meta={"mode": "contextual_overlay_get", "error": "missing_bearer_token"},
        )

    tz_offset_min = _awareos_contextual_overlay_tz_offset_min()
    calendar_prep_needed = (
        "1"
        if any(k in (message_text or "").lower() for k in ("calendar", "meeting", "appointment"))
        else "0"
    )

    parsed = urllib.parse.urlparse(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if tz_offset_min is not None and "tz_offset_min" not in query:
        query["tz_offset_min"] = tz_offset_min
    if "calendar_prep_needed" not in query:
        query["calendar_prep_needed"] = calendar_prep_needed
    new_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))

    req = urllib.request.Request(
        new_url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw else {}
        snippet = _build_overlay_snippet(payload)
        return ContextEvalResult(
            ok=bool(snippet),
            snippet=snippet,
            meta={
                "mode": "contextual_overlay_get",
                "latency_ms": int((time.time() - started) * 1000),
                "response_keys": sorted(list(payload.keys())) if isinstance(payload, dict) else [],
                "prompt_count": len(payload.get("prompts") or []) if isinstance(payload, dict) else 0,
            },
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        return ContextEvalResult(
            ok=False,
            snippet="",
            meta={
                "mode": "contextual_overlay_get",
                "error": str(exc),
                "latency_ms": int((time.time() - started) * 1000),
            },
        )
    except Exception as exc:
        return ContextEvalResult(
            ok=False,
            snippet="",
            meta={
                "mode": "contextual_overlay_get",
                "error": str(exc),
                "latency_ms": int((time.time() - started) * 1000),
            },
        )

def run_context_eval(
    *,
    message_text: str,
    session_key: str,
    platform: str,
    chat_id: str,
    user_id: str | None,
) -> ContextEvalResult | None:
    """Optional sparse AwareOS contextual-evaluator call.

    If configured via ``AWAREOS_CONTEXT_EVAL_URL``, makes a best-effort HTTP call.

    Two endpoint shapes are supported:

    - AwareOS contextual overlay (preferred): when the URL points at the AwareOS
      route ``/api/kaze/contextual-overlay`` this function issues a GET request
      and converts the returned prompts into a compact snippet. No raw chat body
      is sent.
    - Legacy evaluator: POST JSON and expect a ``snippet``/``context`` field.
    """
    if not awareos_context_eval_enabled():
        return None
    url = os.getenv("AWAREOS_CONTEXT_EVAL_URL", "").strip()
    if not url:
        return None

    if _looks_like_contextual_overlay_url(url):
        return _run_contextual_overlay_eval(url=url, message_text=message_text)

    body = {
        "schema_version": "awareos.context_eval_request.v1",
        "requested_at": _now_iso(),
        "platform": platform,
        "chat_id": chat_id,
        "user_id": user_id or "",
        "session_key": session_key,
        "text": message_text or "",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw) if raw else {}
        snippet = str(parsed.get("snippet") or parsed.get("context") or "").strip()
        if not snippet:
            return ContextEvalResult(
                ok=False,
                snippet="",
                meta={"error": "empty_response", "latency_ms": int((time.time() - started) * 1000)},
            )
        # Hard cap; keep prompt caching impact bounded.
        snippet = snippet[:1500].rstrip()
        return ContextEvalResult(
            ok=True,
            snippet=snippet,
            meta={
                "latency_ms": int((time.time() - started) * 1000),
                "response_keys": sorted(list(parsed.keys())) if isinstance(parsed, dict) else [],
            },
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        return ContextEvalResult(
            ok=False,
            snippet="",
            meta={"error": str(exc), "latency_ms": int((time.time() - started) * 1000)},
        )
    except Exception as exc:
        return ContextEvalResult(
            ok=False,
            snippet="",
            meta={"error": str(exc), "latency_ms": int((time.time() - started) * 1000)},
        )
