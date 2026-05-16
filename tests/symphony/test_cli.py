import json
import subprocess
import sys
from types import SimpleNamespace

from symphony import cli as symphony_cli


def test_symphony_help_lists_validate():
    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "validate" in result.stdout
    assert "run" in result.stdout
    assert "state" in result.stdout


def test_symphony_validate_help():
    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "validate", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "WORKFLOW.md" in result.stdout
    assert "--json" in result.stdout


def test_symphony_validate_missing_workflow_json(tmp_path):
    missing = tmp_path / "missing-WORKFLOW.md"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hermes_cli.main",
            "symphony",
            "validate",
            str(missing),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "missing_workflow_file"
    assert str(missing) in payload["error"]["message"]


def test_symphony_validate_valid_workflow_json(tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text(
        "---\n"
        "agent:\n"
        "  runner: hermes\n"
        "workspace:\n"
        "  root: ./workspaces\n"
        "---\n"
        "Work on {{ issue.identifier }} attempt {{ attempt }}.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "validate", str(workflow), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["workflow"] == str(workflow)
    assert payload["agent"]["runner"] == "hermes"
    assert payload["hermes"]["mode"] == "subprocess"


def test_symphony_state_json_returns_empty_snapshot():
    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "state", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["snapshot"]["counts"]["running"] == 0


def test_symphony_run_once_json_validates_and_reports_no_dispatch(tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text("---\nworkspace:\n  root: ./workspaces\n---\nWork on {{ issue.identifier }}.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "run", str(workflow), "--once", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "once"
    assert payload["dispatched"] == 0


def test_symphony_run_loop_json_supports_bounded_cycles_for_smoke(tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text(
        "---\npolling:\n  interval_ms: 1\nworkspace:\n  root: ./workspaces\n---\nWork on {{ issue.identifier }}.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "run", str(workflow), "--max-cycles", "2", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "loop"
    assert payload["cycles"] == 2
    assert payload["dispatched"] == 0


def test_run_loop_reuses_orchestrator_state_between_cycles(monkeypatch, tmp_path):
    seen_state_ids = []
    wait_flags = []

    def fake_run_once_payload(config, workflow_prompt_template, workflow_path, *, state=None, wait_for_completion=True):
        seen_state_ids.append(id(state))
        wait_flags.append(wait_for_completion)
        state.retries[str(len(seen_state_ids))] = SimpleNamespace(attempt=len(seen_state_ids), retry_after_ms=0)
        return {"ok": True, "mode": "once", "dispatched": 0, "snapshot": {}}

    monkeypatch.setattr(symphony_cli, "_run_once_payload", fake_run_once_payload)

    payload = symphony_cli._run_loop_payload(
        SimpleNamespace(polling=SimpleNamespace(interval_ms=0), agent=SimpleNamespace(runner="hermes")),
        "Prompt",
        tmp_path / "WORKFLOW.md",
        max_cycles=2,
    )

    assert payload["cycles"] == 2
    assert len(set(seen_state_ids)) == 1
    assert wait_flags == [False, False]


def test_symphony_state_json_reads_persisted_workflow_state(tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text(
        "---\nworkspace:\n  root: ./workspaces\n---\nWork on {{ issue.identifier }}.\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "workspaces" / ".symphony" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"counts": {"running": 1}, "running": ["issue-id"]}), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "state", str(workflow), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["snapshot"]["counts"]["running"] == 1
    assert payload["snapshot"]["running"] == ["issue-id"]


def test_run_loop_survives_one_run_once_exception(monkeypatch, tmp_path):
    calls = {"count": 0}

    def flaky_run_once_payload(config, workflow_prompt_template, workflow_path, *, state=None, wait_for_completion=True):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("linear temporarily down")
        return {"ok": True, "mode": "once", "dispatched": 1, "snapshot": {"counts": {"running": 0}}}

    monkeypatch.setattr(symphony_cli, "_run_once_payload", flaky_run_once_payload)

    payload = symphony_cli._run_loop_payload(
        SimpleNamespace(
            polling=SimpleNamespace(interval_ms=0),
            agent=SimpleNamespace(runner="hermes"),
            workspace=SimpleNamespace(root=tmp_path / "workspaces"),
        ),
        "Prompt",
        tmp_path / "WORKFLOW.md",
        max_cycles=2,
    )

    assert calls["count"] == 2
    assert payload["cycles"] == 2
    assert payload["dispatched"] == 1
    assert payload["last"]["ok"] is True


def test_symphony_run_port_returns_explicit_unimplemented_error(tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text(
        "---\nworkspace:\n  root: ./workspaces\n---\nWork on {{ issue.identifier }}.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "run", str(workflow), "--port", "3987", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "unsupported_status_server"


def test_run_loop_survives_state_persist_failure(monkeypatch, tmp_path):
    def flaky_run_once_payload(config, workflow_prompt_template, workflow_path, *, state=None, wait_for_completion=True):
        raise RuntimeError("linear down")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(symphony_cli, "_run_once_payload", flaky_run_once_payload)
    monkeypatch.setattr(symphony_cli, "_persist_state_snapshot", boom)

    payload = symphony_cli._run_loop_payload(
        SimpleNamespace(
            polling=SimpleNamespace(interval_ms=0),
            agent=SimpleNamespace(runner="hermes"),
            workspace=SimpleNamespace(root=tmp_path / "workspaces"),
        ),
        "Prompt",
        tmp_path / "WORKFLOW.md",
        max_cycles=1,
    )

    assert payload["cycles"] == 1
    assert payload["last"]["ok"] is False


def test_symphony_state_json_uses_default_workflow_when_present(tmp_path):
    workflow = tmp_path / "WORKFLOW.md"
    workflow.write_text(
        "---\nworkspace:\n  root: ./workspaces\n---\nWork on {{ issue.identifier }}.\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "workspaces" / ".symphony" / "state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"counts": {"running": 2}, "running": ["a", "b"]}), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "state", "--json"],
        text=True,
        capture_output=True,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["snapshot"]["counts"]["running"] == 2


def test_try_persist_state_snapshot_marks_snapshot_on_failure(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise OSError("disk full")

    snapshot = {"counts": {"running": 0}}
    config = SimpleNamespace(workspace=SimpleNamespace(root=tmp_path / "workspaces"))
    monkeypatch.setattr(symphony_cli, "_persist_state_snapshot", boom)

    assert symphony_cli._try_persist_state_snapshot(config, snapshot) is False
    assert snapshot["state_persisted"] is False
