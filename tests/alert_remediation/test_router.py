from pathlib import Path

import pytest
import yaml

from alert_remediation.models import AlertEvent, AlertValidationError
from alert_remediation.router import route_event


POLICY_PATH = Path("docs/alert-remediation/examples/hippo-host-policy.yaml")


def load_policy():
    return yaml.safe_load(POLICY_PATH.read_text())


def test_alert_event_requires_core_fields():
    with pytest.raises(AlertValidationError, match="dedupe_key"):
        AlertEvent.from_mapping(
            {
                "schema_version": "alert.remediation/v1",
                "source": "unit-test",
                "severity": "critical",
                "service": "wireguard",
                "symptom": "peer handshake stale > 15m",
            }
        )


def test_wireguard_stale_handshake_routes_to_auto_remediation():
    event = AlertEvent.from_mapping(
        {
            "schema_version": "alert.remediation/v1",
            "source": "wireguard-watchdog",
            "dedupe_key": "wireguard:do-wireguard-01:stale-handshake",
            "severity": "critical",
            "service": "wireguard",
            "host": "do-wireguard-01",
            "symptom": "peer handshake stale > 15m",
            "evidence": [{"type": "text", "label": "wg show", "value": "stale"}],
        }
    )

    decision = route_event(event, load_policy())

    assert decision.action == "auto_remediate"
    assert decision.severity == "critical"
    assert decision.notify_target == "telegram:-1003939486586:7"
    assert decision.assignee == "sysadmin"
    assert decision.runbooks == ["wireguard_restart_and_verify"]
    assert decision.kanban_on_failure is True
    assert decision.matched_rule == "wireguard_stale_handshake"
    assert "wireguard_stale_handshake" in decision.reason


def test_gpu_transcoder_new_job_failure_routes_to_readonly_triage():
    event = AlertEvent.from_mapping(
        {
            "schema_version": "alert.remediation/v1",
            "source": "servermon",
            "dedupe_key": "gpu:gpu-5060-01:new-jobs-fail",
            "severity": "high",
            "service": "transcoder",
            "host": "gpu-5060-01",
            "tags": ["gpu", "transcode"],
            "symptom": "new jobs fail while existing jobs continue",
        }
    )

    decision = route_event(event, load_policy())

    assert decision.action == "triage_readonly"
    assert decision.severity == "high"
    assert decision.notify_target == "telegram:-1003939486586:7"
    assert decision.runbooks == [
        "inspect_supervisor_logs",
        "inspect_job_intake_state",
        "summarize_existing_vs_new_job_impact",
    ]
    assert "reboot" in decision.forbidden_without_approval
    assert "kernel_or_driver_reload" in decision.forbidden_without_approval
    assert decision.matched_rule == "gpu_transcoder_intake_failure"


def test_unmatched_event_uses_policy_defaults():
    event = AlertEvent.from_mapping(
        {
            "schema_version": "alert.remediation/v1",
            "source": "mystery-monitor",
            "dedupe_key": "unknown:host-01:oddness",
            "severity": "warning",
            "service": "unknown-service",
            "host": "host-01",
            "symptom": "odd but not matched",
        }
    )

    decision = route_event(event, load_policy())

    assert decision.action == "triage_readonly"
    assert decision.severity == "warning"
    assert decision.notify_target == "telegram:-1003939486586:7"
    assert decision.assignee == "sysadmin"
    assert decision.runbooks == []
    assert decision.kanban_on_failure is False
    assert decision.matched_rule is None
    assert "defaults" in decision.reason


def test_dangerous_suggested_action_is_downgraded_to_approval_required():
    event = AlertEvent.from_mapping(
        {
            "schema_version": "alert.remediation/v1",
            "source": "servermon",
            "dedupe_key": "host:web-01:reboot-required",
            "severity": "high",
            "service": "host",
            "host": "web-01",
            "symptom": "reboot required after kernel update",
            "suggested_action": "reboot",
        }
    )

    decision = route_event(event, load_policy())

    assert decision.action == "approval_required"
    assert decision.severity == "high"
    assert decision.notify_target == "telegram:-1003939486586:7"
    assert decision.kanban_on_failure is True
    assert "reboot" in decision.reason


def test_tags_all_and_tags_any_matching_are_supported():
    policy = {
        "schema_version": "alert-remediation-policy/v1",
        "routes": {"critical_alerts": "telegram:critical"},
        "defaults": {"action": "notify_only", "notify": "critical_alerts"},
        "rules": {
            "all_tags_rule": {
                "match": {"tags_all": ["origin", "flussonic"], "tags_any": ["edge", "origin"]},
                "action": "triage_readonly",
                "notify": "critical_alerts",
                "readonly_runbooks": ["collect_streaming_logs"],
            }
        },
    }
    event = AlertEvent.from_mapping(
        {
            "schema_version": "alert.remediation/v1",
            "source": "servermon",
            "dedupe_key": "stream:origin-01:flussonic-errors",
            "severity": "high",
            "service": "streaming",
            "tags": ["origin", "flussonic"],
            "symptom": "flussonic error rate high",
        }
    )

    decision = route_event(event, policy)

    assert decision.action == "triage_readonly"
    assert decision.runbooks == ["collect_streaming_logs"]
    assert decision.matched_rule == "all_tags_rule"
