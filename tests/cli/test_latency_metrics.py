import json


def test_latency_metrics_summary_groups_by_arm_and_class(tmp_path):
    from hermes_cli.latency_metrics import (
        LatencyMetricRow,
        append_latency_metric,
        format_latency_summary,
        latency_metric_from_hook_payload,
        summarize_latency_metrics,
    )

    metrics_path = tmp_path / "latency.jsonl"
    rows = [
        LatencyMetricRow(
            arm="control",
            turn_class="short_chat",
            latency_ms=100.0,
            cache_hit=True,
            input_tokens=10,
            estimated_cost_usd=0.10,
            model="anthropic/claude-opus-4.7",
            error=False,
            tool_calls=0,
        ),
        LatencyMetricRow(
            arm="control",
            turn_class="short_chat",
            latency_ms=200.0,
            cache_hit=False,
            input_tokens=20,
            estimated_cost_usd=0.20,
            model="anthropic/claude-opus-4.7",
            error=True,
            tool_calls=2,
        ),
        LatencyMetricRow(
            arm="treatment",
            turn_class="short_chat",
            latency_ms=50.0,
            cache_hit=True,
            input_tokens=5,
            estimated_cost_usd=0.02,
            model="anthropic/claude-sonnet-4.6",
            error=False,
            tool_calls=1,
        ),
    ]

    for row in rows:
        append_latency_metric(metrics_path, row)

    raw_line = metrics_path.read_text(encoding="utf-8").splitlines()[0]
    assert "thanks" not in raw_line
    assert "user_message" not in json.loads(raw_line)

    summary = summarize_latency_metrics(metrics_path)
    control = summary[("control", "short_chat")]
    treatment = summary[("treatment", "short_chat")]

    assert control.count == 2
    assert control.p50_latency_ms == 150.0
    assert control.p90_latency_ms == 190.0
    assert control.p99_latency_ms == 199.0
    assert control.cache_hit_percent == 50.0
    assert control.mean_input_tokens == 15.0
    assert control.estimated_cost_usd == 0.30
    assert control.opus_percent == 100.0
    assert control.error_rate_percent == 50.0
    assert control.tool_call_rate_percent == 50.0

    assert treatment.opus_percent == 0.0
    table = format_latency_summary(summary)
    assert "control" in table
    assert "treatment" in table


def test_latency_metric_from_hook_payload_sanitizes_text_fields():
    from hermes_cli.latency_metrics import latency_metric_from_hook_payload

    row = latency_metric_from_hook_payload(
        {
            "session_id": "s1",
            "platform": "slack",
            "model": "anthropic/claude-opus-4.7",
            "api_duration": 1.25,
            "ended_at": 123.0,
            "assistant_tool_call_count": 2,
            "user_message": "do not store this raw text",
            "request": {"body": {"messages": [{"content": "secret-ish text"}]}},
            "routing_decision": {
                "enabled": True,
                "arm": "treatment",
                "class": "short_chat",
                "effective_model": "anthropic/claude-sonnet-4.6",
            },
            "usage": {
                "input_tokens": 100,
                "output_tokens": 5,
                "cache_read_tokens": 90,
                "cache_write_tokens": 10,
            },
        }
    )

    assert row is not None
    assert row.session_id == "s1"
    assert row.platform == "slack"
    assert row.latency_ms == 1250.0
    assert row.cache_hit is True
    assert row.input_tokens == 100
    assert row.output_tokens == 5
    assert row.cache_read_tokens == 90
    assert row.cache_write_tokens == 10
    assert row.tool_calls == 2
    assert "raw text" not in repr(row)
