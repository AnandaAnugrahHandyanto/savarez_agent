"""Tests for report-only safe orchestration verifier."""

import pytest

from agent.verifier import ToolCallRecord, evaluate_turn


def finding_codes(report):
    return {finding.code for finding in report.findings}


def test_clean_turn_has_no_findings():
    report = evaluate_turn([
        ToolCallRecord(name="read_file", args={"path": "agent/prompt_builder.py"}),
        ToolCallRecord(name="search_files", args={"pattern": "Safe orchestration"}),
    ])

    assert report.enabled is True
    assert report.findings == ()


@pytest.mark.parametrize(
    ("command", "expected_code"),
    [
        ("systemctl restart hermes-gateway", "gateway_restart_command"),
        ("hermes gateway run --replace", "gateway_restart_command"),
        ("pkill -f hermes", "hermes_process_kill_command"),
        ("claude update", "self_update_command"),
    ],
)
def test_terminal_dangerous_commands_are_reported_without_blocking(command, expected_code):
    report = evaluate_turn([
        ToolCallRecord(name="terminal", args={"command": command}),
    ])

    assert expected_code in finding_codes(report)
    assert all(finding.severity == "warning" for finding in report.findings)


@pytest.mark.parametrize(
    ("path", "expected_code"),
    [
        ("config.yaml", "sensitive_config_write"),
        (".env", "sensitive_config_write"),
        (".env.local", "sensitive_config_write"),
        ("key.pem", "sensitive_config_write"),
        ("gateway/slack_adapter.py", "gateway_adapter_write"),
    ],
)
def test_file_mutation_dangerous_paths_are_reported(path, expected_code):
    report = evaluate_turn([
        ToolCallRecord(name="write_file", args={"path": path, "content": "placeholder"}),
    ])

    assert expected_code in finding_codes(report)


def test_patch_dangerous_path_is_reported():
    report = evaluate_turn([
        ToolCallRecord(name="patch", args={"path": "gateway/slack_adapter.py"}),
    ])

    assert "gateway_adapter_write" in finding_codes(report)


def test_findings_are_aggregated_across_multiple_records():
    report = evaluate_turn([
        ToolCallRecord(name="terminal", args={"command": "pkill -f hermes"}),
        ToolCallRecord(name="write_file", args={"path": ".env.production", "content": "x"}),
    ])

    assert finding_codes(report) == {
        "hermes_process_kill_command",
        "sensitive_config_write",
    }


def test_gateway_adapter_detection_is_segment_aware():
    report = evaluate_turn([
        ToolCallRecord(name="write_file", args={"path": "gateway/slacktivity/example.py"}),
    ])

    assert "gateway_adapter_write" not in finding_codes(report)


def test_report_only_verifier_does_not_raise_for_malformed_records():
    report = evaluate_turn([
        ToolCallRecord(name="terminal", args={"command": None}),
        ToolCallRecord(name="write_file", args={"path": None}),
        ToolCallRecord(name="unknown", args={}),
    ])

    assert report.enabled is True
    assert isinstance(report.findings, tuple)
