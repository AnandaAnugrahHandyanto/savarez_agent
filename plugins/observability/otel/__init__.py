"""otel — Hermes plugin for OpenTelemetry trace export.

Pushes session, model, tool, and cron spans to any OTLP/HTTP collector.
Fail-open: export errors are logged as warnings; agent runs are never
interrupted.

The plugin is opt-in. Enable it with ``hermes plugins enable
observability/otel`` and set ``otel.enabled: true`` (or
``HERMES_OTEL_ENABLED=1``); ``otel.endpoint`` and
``HERMES_OTEL_ENDPOINT`` configure the collector URL — ``/v1/traces`` is
appended when omitted.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# OTLP status + span-kind enums; tiny subset, kept here so the plugin
# stays zero-dep (no opentelemetry-sdk import).
STATUS_OK, STATUS_ERROR = 1, 2
KIND_INTERNAL, KIND_CLIENT = 1, 3

# One entry per (session_id|task_id|process); the sticky execution_id and
# resume lineage mean subsequent API/tool spans inherit continuity
# attributes without every call site having to pass them again.
_SESSIONS: dict[str, dict[str, Any]] = {}


def _now_ns() -> int:
    return time.time_ns()


def _id(n: int) -> str:
    return uuid.uuid4().hex[:n]


def _compact(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, "")}


def _json(value: Any, limit: int = 4096) -> str:
    # Coerce non-strings via JSON so attribute values stay valid OTLP
    # strings; fall back to repr when the payload isn't JSON-serializable.
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        except Exception:
            value = str(value)
    if len(value) <= limit:
        return value
    suffix = f"...[truncated {len(value) - limit} chars]"
    return value[: max(0, limit - len(suffix))] + suffix


def _attr(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": _json(value)}


def _attrs(d: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for k, v in d.items():
        if not k:
            continue
        av = _attr(v)
        if av is not None:
            out.append({"key": str(k), "value": av})
    return out


def _session(kwargs: dict[str, Any]) -> dict[str, Any]:
    key = str(kwargs.get("session_id") or kwargs.get("task_id") or f"thread:{os.getpid()}")
    state = _SESSIONS.get(key)
    if state is None:
        state = {
            "trace_id": _id(32),
            "execution_id": kwargs.get("execution_id") or _id(32),
            "start_ns": _now_ns(),
            "parent_session_id": kwargs.get("parent_session_id"),
            "resume_from": kwargs.get("resume_from") or kwargs.get("parent_session_id"),
        }
        _SESSIONS[key] = state
    return state


def _continuity(kwargs: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return _compact({
        "gen_ai.session.id": kwargs.get("session_id") or kwargs.get("task_id"),
        "gen_ai.agent.execution.id": kwargs.get("execution_id") or state["execution_id"],
        "hermes.resume_from": kwargs.get("resume_from") or kwargs.get("parent_session_id") or state.get("resume_from"),
        "hermes.cron.job.id": kwargs.get("cron_job_id") or os.environ.get("HERMES_CRON_JOB_ID", "").strip() or None,
    })


def _span(name: str, kwargs: dict[str, Any], attrs: dict[str, Any], *, kind: int = KIND_INTERNAL, status: int = STATUS_OK, duration_ns: int = 1_000_000, message: str = "") -> dict[str, Any]:
    # The post-event hooks don't carry an explicit start timestamp, so we
    # estimate backwards from the duration the hook payload already
    # supplies. Wall-clock position is approximate; the duration is exact.
    state = _session(kwargs)
    end = _now_ns()
    span: dict[str, Any] = {
        "traceId": state["trace_id"],
        "spanId": _id(16),
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(max(0, end - duration_ns)),
        "endTimeUnixNano": str(end),
        "attributes": _attrs({**_continuity(kwargs, state), **_compact(attrs)}),
        "status": {"code": status},
    }
    if message:
        span["status"]["message"] = _json(message, 512)
    return span


class _Exporter:
    def __init__(self, cfg: dict[str, Any]) -> None:
        endpoint = (
            os.environ.get("HERMES_OTEL_ENDPOINT")
            or cfg.get("endpoint")
            or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            or "http://localhost:4318/v1/traces"
        )
        endpoint = endpoint.rstrip("/")
        if not endpoint.endswith("/v1/traces"):
            endpoint += "/v1/traces"
        self.endpoint = endpoint

        # Headers can be a dict in config or a comma-list from env; we accept both.
        headers: dict[str, str] = dict(cfg.get("headers") or {})
        for part in (os.environ.get("HERMES_OTEL_HEADERS") or os.environ.get("OTEL_EXPORTER_OTLP_HEADERS") or "").split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                if k.strip():
                    headers[k.strip()] = v.strip()
        headers["Content-Type"] = "application/json"
        self.headers = headers

        self.service = os.environ.get("HERMES_OTEL_SERVICE_NAME") or cfg.get("service_name") or "hermes-agent"
        self.timeout = float(os.environ.get("HERMES_OTEL_TIMEOUT_SECONDS") or cfg.get("timeout_seconds") or 1.0)
        self.retry = float(os.environ.get("HERMES_OTEL_RETRY_INTERVAL_SECONDS") or cfg.get("retry_interval_seconds") or 30.0)
        # next_retry_at is wall-clock based so a long-lived process doesn't
        # hammer an unreachable collector; one failure silently backs off
        # for the configured interval before re-trying.
        self.next_retry_at = 0.0

    def export(self, spans: list[dict[str, Any]]) -> None:
        if not spans:
            return
        # Drop silently during backoff rather than raising — observer
        # hooks must never break the agent loop.
        if time.time() < self.next_retry_at:
            logger.warning("OTEL export skipped during retry backoff; dropping %d span(s)", len(spans))
            return
        payload = {
            "resourceSpans": [{
                "resource": {"attributes": _attrs({"service.name": self.service, "telemetry.sdk.language": "python"})},
                "scopeSpans": [{"scope": {"name": "hermes.observability.otel", "version": "1.0.0"}, "spans": spans}],
            }]
        }
        try:
            import urllib.request
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            req = urllib.request.Request(self.endpoint, data=data, headers=self.headers, method="POST")
            with urllib.request.urlopen(req, timeout=max(0.1, self.timeout)) as r:
                if r.status >= 400:
                    raise RuntimeError(f"HTTP {r.status}")
            self.next_retry_at = 0.0
        except Exception as exc:
            self.next_retry_at = time.time() + max(0.0, self.retry)
            logger.warning("OTEL export failed; dropping %d span(s) until retry window elapses: %s", len(spans), exc)


_EXPORTER: _Exporter | None = None


def _exporter() -> _Exporter | None:
    global _EXPORTER
    if _EXPORTER is not None:
        return _EXPORTER
    try:
        from hermes_cli.config import load_config
        cfg = load_config().get("otel") or {}
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    raw = os.environ.get("HERMES_OTEL_ENABLED", cfg.get("enabled", False))
    truthy = raw if isinstance(raw, bool) else str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if not truthy:
        return None
    _EXPORTER = _Exporter(cfg)
    return _EXPORTER


def _emit(name: str, kwargs: dict[str, Any], attrs: dict[str, Any], **kw: Any) -> None:
    try:
        ex = _exporter()
        if ex:
            ex.export([_span(name, kwargs, attrs, **kw)])
    except Exception:
        # Belt-and-suspenders: even if a hook callback catches nothing,
        # the agent loop must still be unaffected.
        logger.debug("OTEL hook failed", exc_info=True)


def on_session_start(**kwargs: Any) -> None:
    # Touch the session to seed trace_id / execution_id; the actual
    # session span is emitted on finalize so duration is real.
    state = _session(kwargs)
    state["attrs"] = _compact({
        **_continuity(kwargs, state),
        "hermes.platform": kwargs.get("platform"),
        "hermes.model": kwargs.get("model"),
        "hermes.provider": kwargs.get("provider"),
        "hermes.task_id": kwargs.get("task_id"),
    })


def on_session_finalize(**kwargs: Any) -> None:
    key = str(kwargs.get("session_id") or kwargs.get("task_id") or f"thread:{os.getpid()}")
    state = _SESSIONS.pop(key) or {}
    duration = max(1_000_000, _now_ns() - int(state.get("start_ns") or _now_ns()))
    _emit(
        "hermes.session", kwargs,
        {**(state.get("attrs") or {}), "hermes.finalize.reason": kwargs.get("reason")},
        duration_ns=duration,
    )


def on_session_reset(**kwargs: Any) -> None:
    # Reset re-uses the finalize path so the old session's span still
    # closes — otherwise long-lived profiles would leak trace rows.
    if old := kwargs.get("old_session_id") or kwargs.get("session_id"):
        on_session_finalize(**{**kwargs, "session_id": old, "reason": kwargs.get("reason") or "reset"})


def on_session_end(**kwargs: Any) -> None:
    return None  # Session span is owned by finalize; end is intentionally quiet.


def on_post_api_request(**kwargs: Any) -> None:
    raw = kwargs.get("usage")
    usage = raw if isinstance(raw, dict) else {}
    provider = kwargs.get("provider") or kwargs.get("gen_ai_system") or "llm"
    api_duration = kwargs.get("api_duration") or 0
    _emit(
        f"gen_ai.chat {provider}", kwargs,
        {
            "gen_ai.operation.name": "chat",
            "gen_ai.system": provider,
            "gen_ai.request.model": kwargs.get("model"),
            "gen_ai.response.model": kwargs.get("response_model") or kwargs.get("model"),
            "gen_ai.usage.input_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
            "gen_ai.usage.output_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
            "gen_ai.usage.total_tokens": usage.get("total_tokens"),
            "hermes.api_request_id": kwargs.get("api_request_id"),
            "hermes.turn_id": kwargs.get("turn_id"),
            "hermes.api_call_count": kwargs.get("api_call_count"),
            "hermes.provider": kwargs.get("provider"),
            "hermes.finish_reason": kwargs.get("finish_reason"),
        },
        kind=KIND_CLIENT,
        duration_ns=max(1_000_000, int(api_duration * 1_000_000_000)),
        message=kwargs.get("finish_reason") or "",
    )


def on_api_request_error(**kwargs: Any) -> None:
    error = kwargs.get("error")
    message = (error or {}).get("message") if isinstance(error, dict) else str(error or "")
    error_type = (error or {}).get("type") if isinstance(error, dict) else type(error).__name__
    provider = kwargs.get("provider") or "llm"
    _emit(
        f"gen_ai.chat {provider}", kwargs,
        {
            "gen_ai.operation.name": "chat",
            "gen_ai.system": provider,
            "gen_ai.request.model": kwargs.get("model"),
            "error.type": error_type,
            "hermes.error.message": message,
            "hermes.error.reason": kwargs.get("reason"),
            "hermes.retryable": kwargs.get("retryable"),
            "hermes.retry_count": kwargs.get("retry_count"),
        },
        status=STATUS_ERROR,
        kind=KIND_CLIENT,
        message=message,
    )


def on_post_tool_call(**kwargs: Any) -> None:
    status = (kwargs.get("status") or "ok").lower()
    tool = kwargs.get("tool_name") or "tool"
    duration_ms = kwargs.get("duration_ms")
    args = kwargs.get("args")
    result = kwargs.get("result")
    _emit(
        f"hermes.tool {tool}", kwargs,
        {
            "hermes.tool.name": tool,
            "gen_ai.tool.call.id": kwargs.get("tool_call_id"),
            "hermes.tool.status": status,
            "hermes.tool.duration_ms": duration_ms,
            "hermes.tool.args.size": len(_json(args)) if args is not None else 0,
            "hermes.tool.result.size": len(_json(result)) if result is not None else 0,
            "error.type": kwargs.get("error_type"),
            "hermes.error.message": kwargs.get("error_message"),
        },
        status=STATUS_OK if status == "ok" else STATUS_ERROR,
        duration_ns=int(duration_ms * 1_000_000) if duration_ms else 1_000_000,
        message=kwargs.get("error_message") or "",
    )


# Older plugin spikes exposed unprefixed names; keep them so existing
# importers/tests still resolve cleanly. The on_* spellings above are
# the canonical Phase 1 surface.
post_api_request = on_post_api_request
api_request_error = on_api_request_error
post_tool_call = on_post_tool_call


def register(ctx) -> None:
    for name, hook in {
        "on_session_start": on_session_start,
        "on_session_end": on_session_end,
        "on_session_finalize": on_session_finalize,
        "on_session_reset": on_session_reset,
        "post_api_request": on_post_api_request,
        "api_request_error": on_api_request_error,
        "post_tool_call": on_post_tool_call,
    }.items():
        ctx.register_hook(name, hook)


def _reset_for_tests() -> None:
    global _EXPORTER
    _SESSIONS.clear()
    _EXPORTER = None