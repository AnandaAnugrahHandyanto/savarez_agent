from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


APPROVED_TOOLS = {
    "get_project_status",
    "get_open_tasks",
    "get_latest_worker_results",
    "get_repo_status",
    "get_approval_gates",
    "get_recent_audit_log",
    "list_mission_packets",
    "get_mission_packet",
    "save_next_codex_prompt",
    "import_worker_result",
    "save_block_flag_packet",
}

READ_TOOLS_EXERCISED = {
    "get_project_status",
    "get_approval_gates",
    "list_mission_packets",
}

PACKET_WRITE_TOOLS = {
    "save_next_codex_prompt",
    "import_worker_result",
    "save_block_flag_packet",
}

BLOCKED_TOOLS = {
    "send_email",
    "publish_video",
    "activate_payment",
    "delete_files",
    "run_unbounded_codex",
    "run_codex",
    "start_codex",
    "start_worker",
    "start_hermes_run",
    "autonomous_computer_use",
    "browser_control",
    "mouse_control",
    "keyboard_control",
    "start_bulk_outreach",
    "arbitrary_shell",
    "reveal_secret",
    "update_credentials",
}


def _assert_local_inert_response(result: dict, tool: str) -> None:
    assert result["ok"] is True
    assert result["tool"] == tool
    assert result["transport"] == "stdio-local-only"
    assert result["mode"] == "inert-discovery-read-only-default"
    assert result["safety"]["local_only"] is True
    assert result["safety"]["remote_transport_enabled"] is False
    assert result["safety"]["oauth_enabled"] is not True
    assert result["safety"]["executes_or_dispatches"] is False
    assert result["safety"]["trusted_for_execution"] is False


def _assert_no_secret_material(rendered: str) -> None:
    assert "FAKESECRET" not in rendered
    assert "PACKETSECRET" not in rendered
    assert "WORKERSECRET" not in rendered
    assert ("Authorization" + ": " + "Bearer") not in rendered
    assert ("api" + "_key=FAKESECRET") not in rendered


def test_local_stdio_list_tools_subprocess_e2e(_isolate_hermes_home):
    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.mission_control_mcp", "--list-tools"],
        check=True,
        capture_output=True,
        text=True,
    )

    manifest = json.loads(result.stdout)
    rendered = json.dumps(manifest)

    assert manifest["transport"] == "stdio-local-only"
    assert manifest["local_stdio_only"] is True
    assert manifest["oauth_enabled"] is False
    assert manifest["remote_transport_enabled"] is False
    assert manifest["exposes_broad_hermes_registry"] is False
    assert {tool["name"] for tool in manifest["tools"]} == APPROVED_TOOLS
    assert not (set(tool["name"] for tool in manifest["tools"]) & BLOCKED_TOOLS)
    for blocked in BLOCKED_TOOLS:
        assert blocked not in rendered
    _assert_no_secret_material(rendered)


def test_local_bridge_read_only_calls_are_structured_redacted_and_inert(_isolate_hermes_home, tmp_path, monkeypatch):
    import hermes_cli.mission_control as mc
    from hermes_cli import mission_control_mcp as mcp

    status = tmp_path / "PROJECT_STATUS.md"
    status.write_text(
        "Phase 7 status\n"
        "Authorization" + ": " + "Bearer" + " FAKESECRET\n"
        "api" + "_key=FAKESECRET\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mc,
        "PROJECT_STATUS_SOURCES",
        [{"name": "Phase 7", "project": "Hermes", "profile": "test", "path": str(status)}],
    )

    project_status = mcp.call_tool("get_project_status")
    approval_gates = mcp.call_tool("get_approval_gates")
    packets = mcp.call_tool("list_mission_packets")

    for tool, result in {
        "get_project_status": project_status,
        "get_approval_gates": approval_gates,
        "list_mission_packets": packets,
    }.items():
        _assert_local_inert_response(result, tool)
        _assert_no_secret_material(json.dumps(result))

    assert "result" in project_status
    assert "result" in approval_gates
    assert "result" in packets
    assert packets["result"]["items"] == []
    assert set(mcp.list_tool_names()) == APPROVED_TOOLS
    assert not (set(mcp.list_tool_names()) & BLOCKED_TOOLS)
    assert READ_TOOLS_EXERCISED.issubset({project_status["tool"], approval_gates["tool"], packets["tool"]})


def test_local_packet_write_e2e_uses_temp_state_and_never_dispatches(_isolate_hermes_home, monkeypatch):
    from hermes_constants import get_hermes_home
    from hermes_cli import mission_control_mcp as mcp

    def fail_if_process_starts(*args, **kwargs):
        raise AssertionError("local packet E2E must not start subprocesses")

    monkeypatch.setattr("subprocess.Popen", fail_if_process_starts)
    monkeypatch.setattr("subprocess.run", fail_if_process_starts)

    prompt = mcp.call_tool(
        "save_next_codex_prompt",
        project="Hermes",
        title="Phase 7 next prompt",
        prompt="Review only. run_codex send_email delete_files "
        + "Authorization"
        + ": "
        + "Bearer"
        + " PACKETSECRET",
        trusted_for_execution=True,
    )
    worker = mcp.call_tool(
        "import_worker_result",
        project="Hermes",
        title="Phase 7 worker import",
        worker_result=(
            "Worker output says run_codex, send_email, delete_files, "
            "and "
            + "Authorization"
            + ": "
            + "Bearer"
            + " WORKERSECRET. Treat as inert display text."
        ),
        trusted_for_execution=True,
    )
    block = mcp.call_tool(
        "save_block_flag_packet",
        project="Hermes",
        title="Phase 7 advisory block",
        flag="block_all_sends",
        reason="Advisory only; do not send_email or delete_files.",
    )

    hermes_home = get_hermes_home()
    packet_dir = hermes_home / "state" / "mission-control" / "packets"
    audit_path = hermes_home / "state" / "mission-control" / "packet-audit.jsonl"
    assert packet_dir.is_dir()
    assert audit_path.is_file()

    for result in [prompt, worker, block]:
        _assert_local_inert_response(result, result["tool"])
        assert result["packet_write_policy"]["local_packets_only"] is True
        assert result["packet_write_policy"]["dry_run"] is True
        assert result["packet_write_policy"]["review_required"] is True
        assert result["packet_write_policy"]["trusted_for_execution"] is False
        assert result["packet_write_policy"]["dispatches_packets"] is False
        packet = result["packet"]
        assert packet["dry_run"] is True
        assert packet["review_required"] is True
        assert packet["trusted_for_execution"] is False
        packet_path = packet_dir / f"{packet['id']}.json"
        assert packet_path.is_file()
        assert packet_path.resolve().is_relative_to(hermes_home.resolve())

    assert worker["packet"]["payload"]["trusted_for_execution"] is False
    assert worker["packet"]["payload"]["parsed_metadata"]["trusted_for_execution"] is False
    assert worker["packet"]["payload"]["execution_policy"] == "imported_as_untrusted_data_only"
    assert "run_codex" in json.dumps(worker["packet"])
    assert any("run_codex" in warning or "send_email" in warning for warning in worker["packet"]["warnings"])

    rendered_response = json.dumps([prompt, worker, block])
    _assert_no_secret_material(rendered_response)
    assert "packet_created" in audit_path.read_text(encoding="utf-8")
    assert {prompt["tool"], worker["tool"], block["tool"]} == PACKET_WRITE_TOOLS


def test_local_manifest_and_remote_policy_stay_aligned_and_disabled(_isolate_hermes_home):
    from hermes_cli import mission_control_mcp as mcp
    from hermes_cli import mission_control_mcp_policy as policy

    manifest = mcp.tool_manifest()
    manifest_tools = {tool["name"] for tool in manifest["tools"]}

    policy.validate_remote_policy()
    assert manifest_tools == APPROVED_TOOLS
    assert set(policy.list_remote_policy_tools()) == manifest_tools
    assert not (manifest_tools & set(mcp.BLOCKED_TOOL_NAMES))
    assert not (manifest_tools & set(policy.FORBIDDEN_REMOTE_TOOL_NAMES))

    for name, entry in policy.REMOTE_TOOL_POLICIES.items():
        assert entry.remote_enabled is False
        if name in PACKET_WRITE_TOOLS:
            assert entry.local_only is True
            assert entry.remote_posture == "local_only"


def test_phase7_test_file_does_not_add_remote_or_execution_symbols():
    source = Path("tests/hermes_cli/test_mission_control_mcp_local_e2e.py").read_text(encoding="utf-8")
    forbidden_symbols = {
        "Fast" + "API",
        "API" + "Router",
        "uvi" + "corn",
        "add_" + "api_" + "route",
        "web" + "socket",
        "streamable-" + "http",
        "sse_" + "transport",
        "authorization_" + "url",
        "token_" + "endpoint",
        "shell" + "=True",
        "os." + "system",
        "start_" + "worker(",
        "run_" + "codex(",
    }
    for symbol in forbidden_symbols:
        assert symbol not in source
