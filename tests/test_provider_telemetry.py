from __future__ import annotations

import json
from pathlib import Path

from agent import provider_telemetry as telemetry
from agent.provider_telemetry import (
    CANONICAL_SCHEMA,
    REQUIRED_FIELDS,
    append_provider_event,
    redact_value,
    sanitize_event,
)


def test_redact_value_masks_common_secret_shapes() -> None:
    raw = {
        "headers": "Authorization: Bearer tokenabc123 Authorization: Bearer sk-test-placeholder api_key=abc123 password=hunter2 token=tok_456",
        "nested": ["secret=keep-out", "x" * 120],
    }

    redacted = redact_value(raw)
    joined = json.dumps(redacted)

    assert "tokenabc123" not in joined
    assert "sk-test-placeholder" not in joined
    assert "abc123" not in joined
    assert "hunter2" not in joined
    assert "tok_456" not in joined
    assert "[REDACTED]" in joined
    assert "[REDACTED_LONG_TOKEN]" in joined


def test_sanitize_event_populates_canonical_schema_and_compat_failure_kind() -> None:
    event = sanitize_event(
        {
            "event": "fallback_activated",
            "platform": "cli",
            "provider": "openai-codex",
            "model": "gpt-5.5",
            "failure_kind": "quota",
            "fallback": {"provider": "opencode-go", "model": "kimi-k2.6"},
            "input_tokens": "10",
            "output_tokens": "20",
            "notes": "bearer secret-token-here",
            "status_code": 429,
        }
    )

    assert all(field in event for field in REQUIRED_FIELDS)
    assert event["schema"] == CANONICAL_SCHEMA
    assert event["status"] == "completed"
    assert event["resolution"] == "pass"
    assert event["failure_kind"] == "rate_limit"
    assert event["input_tokens"] == 10
    assert event["output_tokens"] == 20
    assert event["status_code"] == 429
    assert "secret-token-here" not in event["notes"]


def test_sanitize_event_preserves_fallback_status_and_redacts_nested_fallback() -> None:
    event = sanitize_event(
        {
            "event": "fallback_activated",
            "status": "fallback_activated",
            "resolution": "fallback",
            "failure_kind": "billing",
            "fallback": {
                "provider": "custom",
                "model": "fallback-model",
                "base_url": "https://example.test/v1?api_key=fake-key-123",
            },
        }
    )

    assert event["status"] == "fallback_activated"
    assert event["resolution"] == "fallback"
    assert event["failure_kind"] == "billing"
    assert "fake-key-123" not in json.dumps(event["fallback"])


def test_default_log_path_uses_hermes_home(monkeypatch, tmp_path) -> None:
    import hermes_constants

    monkeypatch.setattr(hermes_constants, "get_hermes_home", lambda: str(tmp_path))

    assert telemetry._default_log_path() == Path(tmp_path) / "logs" / "provider-failover.log"


def test_append_provider_event_writes_jsonl(tmp_path) -> None:
    log_path = tmp_path / "provider-failover.log"

    append_provider_event(
        {
            "event": "provider_request_end",
            "provider": "fixture",
            "model": "unit-test",
            "latency_ms": 12,
        },
        path=log_path,
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["schema"] == CANONICAL_SCHEMA
    assert event["provider"] == "fixture"
    assert event["latency_ms"] == 12


def test_append_provider_event_never_raises_for_unwritable_path(tmp_path) -> None:
    directory = tmp_path / "is-a-directory"
    directory.mkdir()

    append_provider_event({"event": "provider_request_error"}, path=directory)
