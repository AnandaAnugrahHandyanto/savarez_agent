from pathlib import Path

import yaml

from alert_remediation.kanban import format_kanban_card
from alert_remediation.models import AlertEvent
from alert_remediation.router import route_event


POLICY_PATH = Path("docs/alert-remediation/examples/hippo-host-policy.yaml")


def load_policy():
    return yaml.safe_load(POLICY_PATH.read_text())


def test_wireguard_failure_card_draft_contains_operational_context():
    event = AlertEvent.from_mapping(
        {
            "schema_version": "alert.remediation/v1",
            "source": "wireguard-watchdog",
            "dedupe_key": "wireguard:do-wireguard-01:stale-handshake",
            "severity": "critical",
            "service": "wireguard",
            "host": "do-wireguard-01",
            "symptom": "peer handshake stale > 15m",
            "evidence": [
                {"type": "text", "label": "wg show", "value": "latest handshake: 21 minutes ago"}
            ],
            "links": [
                {"label": "ServerMon node", "url": "https://servermon.example/nodes/do-wireguard-01"}
            ],
        }
    )
    decision = route_event(event, load_policy())

    draft = format_kanban_card(event, decision, outcome="remediation_failed")

    assert "[critical] wireguard on do-wireguard-01" in draft.title
    assert "peer handshake stale > 15m" in draft.title
    assert draft.assignee == "sysadmin"
    assert draft.idempotency_key == "alert:wireguard:do-wireguard-01:stale-handshake"
    assert draft.initial_status == "running"
    assert "Detected alert" in draft.body
    assert "Source: wireguard-watchdog" in draft.body
    assert "Dedupe key: wireguard:do-wireguard-01:stale-handshake" in draft.body
    assert "Action decision: auto_remediate" in draft.body
    assert "Matched rule: wireguard_stale_handshake" in draft.body
    assert "Runbooks: wireguard_restart_and_verify" in draft.body
    assert "wg show" in draft.body
    assert "latest handshake: 21 minutes ago" in draft.body
    assert "ServerMon node: https://servermon.example/nodes/do-wireguard-01" in draft.body
    assert "Requested outcome" in draft.body
    assert "restore service or document why approval is required" in draft.body


def test_approval_required_card_starts_blocked_and_requests_human_decision():
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

    draft = format_kanban_card(event, decision)

    assert draft.initial_status == "blocked"
    assert draft.assignee == "sysadmin"
    assert draft.idempotency_key == "alert:host:web-01:reboot-required"
    assert "[high] host on web-01" in draft.title
    assert "Human approval required" in draft.body
    assert "Suggested action requires approval" in draft.body
    assert "active workload/job count" in draft.body


def test_card_formatter_handles_unmatched_event_without_runbooks_or_links():
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

    draft = format_kanban_card(event, decision)

    assert draft.title == "[warning] unknown-service on host-01: odd but not matched"
    assert draft.assignee == "sysadmin"
    assert draft.initial_status == "running"
    assert "Matched rule: none" in draft.body
    assert "Runbooks: none" in draft.body
    assert "Evidence: none supplied" in draft.body
    assert "Links: none supplied" in draft.body


def test_card_title_is_truncated_for_long_symptoms():
    long_symptom = "x" * 220
    event = AlertEvent.from_mapping(
        {
            "schema_version": "alert.remediation/v1",
            "source": "unit-test",
            "dedupe_key": "service:host:long",
            "severity": "high",
            "service": "service",
            "host": "host",
            "symptom": long_symptom,
        }
    )
    decision = route_event(event, load_policy())

    draft = format_kanban_card(event, decision)

    assert len(draft.title) <= 120
    assert draft.title.endswith("…")
