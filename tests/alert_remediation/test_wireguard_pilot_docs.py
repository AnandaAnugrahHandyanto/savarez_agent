from __future__ import annotations

import json
from pathlib import Path

import yaml

from alert_remediation.models import AlertEvent
from alert_remediation.router import route_event


DOC_PATH = Path("docs/alert-remediation/pilots/wireguard.md")
FIXTURE_PATH = Path("docs/alert-remediation/fixtures/wireguard-stale.json")
POLICY_PATH = Path("docs/alert-remediation/examples/hippo-host-policy.yaml")


def test_wireguard_pilot_doc_captures_dry_run_and_safety_gates() -> None:
    text = DOC_PATH.read_text()

    assert "# WireGuard Alert Remediation Pilot" in text
    assert "dry-run" in text
    assert "scripts/alert_remediation_router.py" in text
    assert "wireguard-stale.json" in text
    assert "No live mutation is enabled by this document" in text
    assert "systemctl restart wg-quick@" in text
    assert "not raw wg-quick down/up" in text
    assert "telegram:-1003939486586:7" in text


def test_wireguard_pilot_doc_lists_required_pre_and_post_checks() -> None:
    text = DOC_PATH.read_text()

    for required in [
        "wg show",
        "systemctl status wg-quick@",
        "ip rule show",
        "ip route get 8.8.8.8",
        "latest-handshakes",
        "peer reachable",
        "service active",
        "policy routing selects the expected exit interface",
    ]:
        assert required in text


def test_wireguard_stale_fixture_routes_to_auto_remediate_policy() -> None:
    event_data = json.loads(FIXTURE_PATH.read_text())
    policy = yaml.safe_load(POLICY_PATH.read_text())

    event = AlertEvent.from_mapping(event_data)
    decision = route_event(event, policy)

    assert event.dedupe_key == "wireguard:do-wireguard-01:stale-handshake"
    assert decision.action == "auto_remediate"
    assert decision.matched_rule == "wireguard_stale_handshake"
    assert decision.notify_target == "telegram:-1003939486586:7"
    assert decision.runbooks == ["wireguard_restart_and_verify"]
