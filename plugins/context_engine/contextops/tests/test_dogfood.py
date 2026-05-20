"""Fixture-only read-only Hermes dogfood detector tests."""

import json

import pytest

from contextops_ese import SCHEMA_VERSION
from contextops_ese.safety import scan_unsafe
from plugins.context_engine.contextops.dogfood import (
    export_hermes_dogfood_observations,
    run_hermes_dogfood,
)


def _fixture():
    return {
        "runtime_events": [{"id": "evt-raw-1", "kind": "kanban_completed"}],
        "messages": [
            {
                "message_id": "msg-raw-1",
                "session_id": "sess-raw-1",
                "role": "assistant",
                "summary": "handoff summary ready",
                "content": "USER: raw transcript must not leak",
            }
        ],
        "tasks": [
            {
                "id": "t_raw_ack_missing",
                "origin": "#contextops",
                "return_to": "#contextops",
                "delegated": True,
                "status": "done",
                "origin_ack_observed": False,
                "delivery_mode": "passive",
                "trigger_agent": False,
                "operator_expected_active_wake": True,
                "remediation_group": "fix-review-loop-1",
                "pair_role": "fix",
            },
            {
                "id": "t_raw_review_dup",
                "origin": "#contextops",
                "delegated": True,
                "status": "done",
                "origin_ack_observed": True,
                "remediation_group": "fix-review-loop-1",
                "pair_role": "review",
            },
        ],
    }


def _all_strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _all_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _all_strings(v)
    elif isinstance(value, str):
        yield value


def test_export_maps_hermes_like_dicts_to_versioned_opaque_dtos():
    exported = export_hermes_dogfood_observations(_fixture())
    assert exported["runtime_events"][0]["schema_version"] == SCHEMA_VERSION
    assert exported["messages"][0]["message_ref"].startswith("ref:")
    assert exported["messages"][0]["session_ref"].startswith("ref:")
    assert exported["tasks"][0]["task_ref"].startswith("ref:")
    flattened = json.dumps(exported)
    assert "msg-raw-1" not in flattened
    assert "sess-raw-1" not in flattened
    assert "t_raw_ack_missing" not in flattened
    assert "#contextops" not in flattened
    assert "USER:" not in flattened


def test_detectors_emit_three_suggestion_only_findings():
    report = run_hermes_dogfood(_fixture())
    kinds = {finding["kind"] for finding in report["findings"]}
    assert kinds == {
        "missing_origin_ack",
        "passive_delivery_mistaken_for_active_wake",
        "duplicate_remediation_loop",
    }
    for finding in report["findings"]:
        assert finding["recommendation"]["routing_category"] == "contextops_backlog"
        assert finding["safety_decision"]["policy_mode"] == "suggestion_only"
        assert finding["safety_decision"]["mutation_allowed"] is False
        assert finding["safety_decision"]["dispatch_allowed"] is False
        assert finding["evidence"]["evidence_refs"]
        assert all(ref.startswith("ref:") for ref in finding["evidence"]["evidence_refs"])


def test_report_strings_pass_leak_probe():
    report = run_hermes_dogfood(_fixture())
    raw = json.dumps(report)
    for forbidden in ("msg-raw-1", "sess-raw-1", "t_raw", "#contextops", "USER:", "/home/"):
        assert forbidden not in raw
    for text in _all_strings(report):
        if text.startswith("ref:"):
            continue
        assert scan_unsafe(text) is None


def test_unsafe_summary_fails_closed():
    fixture = _fixture()
    fixture["messages"][0]["summary"] = "operator pasted /home/op/.env"
    try:
        export_hermes_dogfood_observations(fixture)
    except ValueError as exc:
        assert "absolute filesystem path" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unsafe summary should fail closed")


def test_unsupported_runtime_event_type_fails_closed():
    fixture = _fixture()
    fixture["runtime_events"][0]["kind"] = "totally_unknown_event"
    with pytest.raises(ValueError, match="unsupported runtime event type"):
        export_hermes_dogfood_observations(fixture)


def test_unsupported_task_delivery_mode_fails_closed():
    fixture = _fixture()
    fixture["tasks"][0]["delivery_mode"] = "telepathic"
    with pytest.raises(ValueError, match="unsupported task delivery_mode"):
        export_hermes_dogfood_observations(fixture)


def test_unsupported_task_pair_role_fails_closed():
    fixture = _fixture()
    fixture["tasks"][0]["pair_role"] = "saboteur"
    with pytest.raises(ValueError, match="unsupported task pair_role"):
        export_hermes_dogfood_observations(fixture)


def test_unsupported_task_action_type_fails_closed():
    fixture = _fixture()
    fixture["tasks"][0]["action_type"] = "mutate_gateway"
    with pytest.raises(ValueError, match="unsupported task action type"):
        export_hermes_dogfood_observations(fixture)


def test_unsupported_task_status_fails_closed():
    fixture = _fixture()
    fixture["tasks"][0]["status"] = "teleported"
    with pytest.raises(ValueError, match="unsupported task status"):
        export_hermes_dogfood_observations(fixture)


def test_unsupported_type_produces_no_report_or_findings():
    fixture = _fixture()
    fixture["runtime_events"][0]["kind"] = "unknown_kind"
    with pytest.raises(ValueError):
        run_hermes_dogfood(fixture)
