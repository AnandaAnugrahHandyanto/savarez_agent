"""Opt-in observability helpers for dashboard and agent flows.

This module intentionally imports PostHog and OpenTelemetry lazily. Hermes
core can import it on every startup without requiring the observability extra.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping

logger = logging.getLogger(__name__)

_STATE_LOCK = threading.Lock()
_INITIALIZED = False
_POSTHOG_CLIENT: Any = None
_TRACING_READY = False
_CONFIG: dict[str, Any] = {}

_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|token|authorization|api[_-]?key|apikey|secret|private[_-]?key|credential)",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"\+?[1-9]\d[\d .()/-]{6,}\d")
_ID_CARD_RE = re.compile(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b")
_MAX_PROPERTY_STRING = 2048


def _default_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "service": "hermes-agent",
        "env": os.getenv("HERMES_ENV", "local"),
        "version": "",
        "otlp_endpoint": "http://localhost:4317",
        "posthog_host": "https://us.i.posthog.com",
        "posthog_project_api_key": "",
        "analytics_enabled": False,
        "tracing_enabled": False,
        "structured_json_logs": False,
    }


def _load_config() -> dict[str, Any]:
    cfg = _default_config()
    try:
        from hermes_cli.config import load_config

        raw = load_config().get("observability", {})
        if isinstance(raw, Mapping):
            cfg.update({k: v for k, v in raw.items() if k in cfg})
    except Exception:
        pass

    env_map = {
        "enabled": "HERMES_OBSERVABILITY_ENABLED",
        "analytics_enabled": "HERMES_ANALYTICS_ENABLED",
        "tracing_enabled": "HERMES_TRACING_ENABLED",
        "structured_json_logs": "HERMES_STRUCTURED_JSON_LOGS",
        "service": "HERMES_OBSERVABILITY_SERVICE",
        "env": "HERMES_OBSERVABILITY_ENV",
        "version": "HERMES_OBSERVABILITY_VERSION",
        "otlp_endpoint": "OTEL_EXPORTER_OTLP_ENDPOINT",
        "posthog_host": "POSTHOG_HOST",
        "posthog_project_api_key": "POSTHOG_PROJECT_API_KEY",
    }
    for key, env_name in env_map.items():
        if env_name not in os.environ:
            continue
        value = os.environ[env_name]
        if isinstance(cfg.get(key), bool):
            cfg[key] = value.lower() in {"1", "true", "yes", "on"}
        else:
            cfg[key] = value
    return cfg


def get_config(*, reload: bool = False) -> dict[str, Any]:
    global _CONFIG
    if reload or not _CONFIG:
        _CONFIG = _load_config()
    return dict(_CONFIG)


def is_enabled() -> bool:
    cfg = get_config()
    return bool(cfg.get("enabled")) and (
        bool(cfg.get("analytics_enabled")) or bool(cfg.get("tracing_enabled"))
    )


def init_observability(app: Any | None = None, *, force: bool = False) -> bool:
    """Initialize optional analytics/tracing once.

    Returns True when at least one observability backend is active.
    """
    global _INITIALIZED, _POSTHOG_CLIENT, _TRACING_READY, _CONFIG
    with _STATE_LOCK:
        if _INITIALIZED and not force:
            return is_enabled()
        _INITIALIZED = True
        _POSTHOG_CLIENT = None
        _TRACING_READY = False
        _CONFIG = _load_config()
        cfg = _CONFIG

        if not cfg.get("enabled"):
            return False

        if cfg.get("analytics_enabled") and cfg.get("posthog_project_api_key"):
            try:
                import posthog

                posthog.project_api_key = str(cfg["posthog_project_api_key"])
                posthog.host = str(cfg.get("posthog_host") or "https://us.i.posthog.com")
                _POSTHOG_CLIENT = posthog
            except Exception as exc:
                logger.warning("PostHog observability disabled: %s", exc)

        if cfg.get("tracing_enabled"):
            try:
                from opentelemetry import trace
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
                from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
                from opentelemetry.instrumentation.requests import RequestsInstrumentor
                from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor

                if not getattr(trace.get_tracer_provider(), "_hermes_observability", False):
                    resource = Resource.create(
                        {
                            "service.name": str(cfg.get("service") or "hermes-agent"),
                            "deployment.environment": str(cfg.get("env") or "local"),
                            "service.version": str(cfg.get("version") or ""),
                        }
                    )
                    provider = TracerProvider(resource=resource)
                    provider._hermes_observability = True  # type: ignore[attr-defined]
                    endpoint = str(cfg.get("otlp_endpoint") or "http://localhost:4317")
                    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
                    trace.set_tracer_provider(provider)

                HTTPXClientInstrumentor().instrument()
                RequestsInstrumentor().instrument()
                SQLite3Instrumentor().instrument()
                if app is not None:
                    FastAPIInstrumentor.instrument_app(app)
                _TRACING_READY = True
            except Exception as exc:
                logger.warning("OpenTelemetry observability disabled: %s", exc)

        return bool(_POSTHOG_CLIENT or _TRACING_READY)


def current_trace_ids() -> tuple[str, str]:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and getattr(ctx, "is_valid", False):
            return (format(ctx.trace_id, "032x"), format(ctx.span_id, "016x"))
    except Exception:
        pass
    return ("", "")


@contextmanager
def span(name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[Any | None]:
    if not get_config().get("enabled"):
        yield None
        return
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("hermes-agent")
        with tracer.start_as_current_span(name, attributes=dict(attributes or {})) as active:
            yield active
    except Exception:
        yield None


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return redact_properties(value)
    if isinstance(value, list):
        return [_redact_value(v) for v in value[:50]]
    if isinstance(value, tuple):
        return [_redact_value(v) for v in value[:50]]
    if isinstance(value, str):
        text = _PHONE_RE.sub("[REDACTED]", value)
        text = _ID_CARD_RE.sub("[REDACTED]", text)
        if len(text) > _MAX_PROPERTY_STRING:
            text = text[:_MAX_PROPERTY_STRING] + "...[truncated]"
        return text
    return value


def redact_properties(properties: Mapping[str, Any] | None) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in dict(properties or {}).items():
        if _SENSITIVE_KEY_RE.search(str(key)):
            redacted[str(key)] = "[REDACTED]"
        else:
            redacted[str(key)] = _redact_value(value)
    return redacted


def build_event(
    event_name: str,
    *,
    user_id: str | None = None,
    properties: Mapping[str, Any] | None = None,
    source: str = "api",
) -> dict[str, Any]:
    cfg = get_config()
    trace_id, span_id = current_trace_ids()
    event_id = str(uuid.uuid4())
    return {
        "event_id": event_id,
        "event_name": event_name,
        "user_id": user_id or "anonymous",
        "trace_id": trace_id,
        "span_id": span_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "env": str(cfg.get("env") or "local"),
        "service": str(cfg.get("service") or "hermes-agent"),
        "version": str(cfg.get("version") or ""),
        "properties": redact_properties(properties),
        "source": source,
    }


def track(
    event_name: str,
    *,
    user_id: str | None = None,
    properties: Mapping[str, Any] | None = None,
    source: str = "api",
) -> dict[str, Any]:
    event = build_event(event_name, user_id=user_id, properties=properties, source=source)
    if not get_config().get("enabled"):
        return event
    if _POSTHOG_CLIENT is None:
        init_observability()
    if _POSTHOG_CLIENT is not None:
        try:
            _POSTHOG_CLIENT.capture(
                distinct_id=event["user_id"],
                event=event_name,
                properties={k: v for k, v in event.items() if k not in {"event_name", "user_id"}},
            )
        except Exception as exc:
            logger.debug("PostHog capture failed: %s", exc)
    logging.getLogger("agent.observability.events").info(
        json.dumps(event, sort_keys=True, ensure_ascii=False),
    )
    return event


def public_dashboard_config() -> dict[str, Any]:
    cfg = get_config(reload=True)
    return {
        "enabled": bool(cfg.get("enabled") and cfg.get("analytics_enabled") and cfg.get("posthog_project_api_key")),
        "posthog_host": str(cfg.get("posthog_host") or ""),
        "posthog_project_api_key": str(cfg.get("posthog_project_api_key") or ""),
        "env": str(cfg.get("env") or "local"),
        "service": str(cfg.get("service") or "hermes-agent"),
        "version": str(cfg.get("version") or ""),
    }
