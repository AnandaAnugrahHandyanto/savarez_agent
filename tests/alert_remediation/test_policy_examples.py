from pathlib import Path

import yaml


POLICY_PATH = Path("docs/alert-remediation/examples/hippo-host-policy.yaml")


def _load_policy():
    return yaml.safe_load(POLICY_PATH.read_text())


def test_hippo_host_policy_loads_with_expected_routes_and_rules():
    policy = _load_policy()

    assert policy["schema_version"] == "alert-remediation-policy/v1"
    assert policy["routes"]["routine_updates"] == "telegram:-1003939486586:4913"
    assert policy["routes"]["critical_alerts"] == "telegram:-1003939486586:7"
    assert policy["defaults"]["action"] == "triage_readonly"

    rules = policy["rules"]
    assert "wireguard_stale_handshake" in rules
    assert "db_backup_failed" in rules
    assert "gpu_transcoder_intake_failure" in rules
    assert "lvs_backend_unhealthy" in rules
    assert "disk_pressure_warning" in rules
    assert "disk_pressure_critical" in rules


def test_wireguard_stale_handshake_is_the_only_initial_auto_remediation():
    policy = _load_policy()
    rules = policy["rules"]

    assert rules["wireguard_stale_handshake"]["action"] == "auto_remediate"
    assert rules["wireguard_stale_handshake"]["allowed_runbooks"] == [
        "wireguard_restart_and_verify"
    ]

    auto_rules = {
        name: rule for name, rule in rules.items() if rule.get("action") == "auto_remediate"
    }
    assert set(auto_rules) == {"wireguard_stale_handshake"}


def test_mutation_heavy_incidents_are_readonly_or_approval_gated():
    policy = _load_policy()
    rules = policy["rules"]

    assert rules["db_backup_failed"]["action"] == "triage_readonly"
    assert rules["gpu_transcoder_intake_failure"]["action"] == "triage_readonly"
    assert "reboot" in rules["gpu_transcoder_intake_failure"]["forbidden_without_approval"]
    assert "kernel_or_driver_reload" in rules["gpu_transcoder_intake_failure"][
        "forbidden_without_approval"
    ]

    assert rules["lvs_backend_unhealthy"]["action"] == "triage_readonly"
    assert "dns_or_lvs_routing_change" in rules["lvs_backend_unhealthy"][
        "forbidden_without_approval"
    ]


def test_dangerous_actions_default_to_approval_required():
    policy = _load_policy()
    approval_required = set(policy["dangerous_actions"]["approval_required"])

    assert "reboot" in approval_required
    assert "database_restart" in approval_required
    assert "dns_or_lvs_routing_change" in approval_required
    assert "data_delete" in approval_required
    assert "package_upgrade" in approval_required
