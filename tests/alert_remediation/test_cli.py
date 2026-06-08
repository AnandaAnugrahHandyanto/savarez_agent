import json
import subprocess
import sys
from pathlib import Path


POLICY_PATH = Path("docs/alert-remediation/examples/hippo-host-policy.yaml")


def _wireguard_event():
    return {
        "schema_version": "alert.remediation/v1",
        "source": "wireguard-watchdog",
        "dedupe_key": "wireguard:do-wireguard-01:stale-handshake",
        "severity": "critical",
        "service": "wireguard",
        "host": "do-wireguard-01",
        "symptom": "peer handshake stale > 15m",
    }


def test_route_command_outputs_json_decision_for_event_file(tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_wireguard_event()))

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alert_remediation.cli",
            "route",
            "--policy",
            str(POLICY_PATH),
            "--event",
            str(event_path),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["action"] == "auto_remediate"
    assert decision["severity"] == "critical"
    assert decision["notify_target"] == "telegram:-1003939486586:7"
    assert decision["assignee"] == "sysadmin"
    assert decision["runbooks"] == ["wireguard_restart_and_verify"]
    assert decision["kanban_on_failure"] is True
    assert decision["matched_rule"] == "wireguard_stale_handshake"


def test_route_command_reads_event_from_stdin_when_event_is_dash():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alert_remediation.cli",
            "route",
            "--policy",
            str(POLICY_PATH),
            "--event",
            "-",
            "--json",
        ],
        input=json.dumps(_wireguard_event()),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)
    assert decision["action"] == "auto_remediate"
    assert decision["matched_rule"] == "wireguard_stale_handshake"


def test_route_command_exits_nonzero_for_malformed_alert(tmp_path):
    event_path = tmp_path / "bad-event.json"
    event_path.write_text(json.dumps({"schema_version": "alert.remediation/v1"}))

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alert_remediation.cli",
            "route",
            "--policy",
            str(POLICY_PATH),
            "--event",
            str(event_path),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "missing required alert field" in result.stderr
    assert result.stdout == ""


def test_route_command_plain_text_summary(tmp_path):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_wireguard_event()))

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alert_remediation.cli",
            "route",
            "--policy",
            str(POLICY_PATH),
            "--event",
            str(event_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "action: auto_remediate" in result.stdout
    assert "matched_rule: wireguard_stale_handshake" in result.stdout
    assert "notify_target: telegram:-1003939486586:7" in result.stdout
