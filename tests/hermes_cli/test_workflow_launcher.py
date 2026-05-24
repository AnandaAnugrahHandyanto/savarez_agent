from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from hermes_cli.workflow_launcher import (
    STATE_FILENAME,
    WORKFLOW_DIRNAME,
    advance_workflow_gate,
    init_workflow,
    inspect_workflow,
    inventory_artifact_repository,
    load_workflow_state,
    record_verification,
    workflow_status,
)


def _write_artifact(root: Path, slug: str, files: dict[str, str]) -> Path:
    artifact_dir = root / "artifacts" / slug
    artifact_dir.mkdir(parents=True)
    for name, content in files.items():
        (artifact_dir / name).write_text(content, encoding="utf-8")
    return artifact_dir


def test_inventory_artifact_repository_counts_required_files(tmp_path):
    _write_artifact(
        tmp_path,
        "complete",
        {
            "metadata.json": '{"title":"Complete Artifact","updated_at":"2026-05-20"}',
            "preview.html": "<html></html>",
            "artifact.md": "# Artifact",
            "notes.md": "Notes",
            "thumbnail.png": "fake",
            "source.jsx": "export default function App() { return null }",
        },
    )
    _write_artifact(
        tmp_path,
        "missing-source",
        {
            "metadata.json": '{"title":"Missing Source"}',
            "preview.html": "<html></html>",
            "artifact.md": "# Artifact",
            "notes.md": "Notes",
        },
    )

    inventory = inventory_artifact_repository(tmp_path)

    assert inventory.total == 2
    assert inventory.with_preview == 2
    assert inventory.with_thumbnail == 1
    assert inventory.missing_required_count == 1
    missing = next(record for record in inventory.records if record.slug == "missing-source")
    assert "thumbnail.png" in missing.missing
    assert "source.html|source.jsx" in missing.missing


def test_init_workflow_dry_run_does_not_write(tmp_path):
    writes = init_workflow(tmp_path, workflow_name="Artifact Repo", dry_run=True)

    assert writes
    assert all(write.action in {"create", "write", "exists"} for write in writes)
    assert not (tmp_path / WORKFLOW_DIRNAME).exists()


def test_init_workflow_writes_and_refuses_overwrite_without_force(tmp_path):
    init_workflow(tmp_path, workflow_name="Artifact Repo")
    state_file = tmp_path / WORKFLOW_DIRNAME / "WORKFLOW_STATE.md"
    state_file.write_text("custom state\n", encoding="utf-8")

    writes = init_workflow(tmp_path, workflow_name="Artifact Repo")

    assert state_file.read_text(encoding="utf-8") == "custom state\n"
    assert any(write.path == state_file and write.action == "exists" for write in writes)


def test_init_workflow_writes_machine_readable_state(tmp_path):
    init_workflow(
        tmp_path,
        workflow_name="Artifact Repo",
        linear_issue="PB-1",
        linear_project="Operator Lab",
    )

    state = load_workflow_state(tmp_path)

    assert state is not None
    assert state.workflow_name == "Artifact Repo"
    assert state.linear_issue == "PB-1"
    assert state.linear_project == "Operator Lab"
    assert (tmp_path / WORKFLOW_DIRNAME / STATE_FILENAME).exists()
    scope_gate = next(gate for gate in state.gates if gate.key == "scope_packet")
    assert scope_gate.status == "ready"


def test_inspect_workflow_reports_inventory(tmp_path):
    _write_artifact(
        tmp_path,
        "one",
        {
            "metadata.json": '{"title":"One"}',
            "preview.html": "<html></html>",
            "artifact.md": "# Artifact",
            "notes.md": "Notes",
            "thumbnail.png": "fake",
            "source.html": "<html></html>",
        },
    )

    output = inspect_workflow(tmp_path)

    assert "Artifacts: 1" in output
    assert "With preview: 1" in output
    assert "`one`" in output


def test_workflow_status_reports_gate_state(tmp_path):
    init_workflow(tmp_path, workflow_name="Artifact Repo")

    output = workflow_status(tmp_path)

    assert "Workflow name: `Artifact Repo`" in output
    assert "| scope_packet | Scope packet | Codex | ready | ARCHITECT_PACK.md |" in output
    assert "No verification records yet." in output


def test_advance_workflow_gate_updates_state_and_markdown(tmp_path):
    init_workflow(tmp_path, workflow_name="Artifact Repo")

    state = advance_workflow_gate(
        tmp_path,
        "claude_review",
        "blocked",
        evidence="CLAUDE_CRITIQUE.md",
        note="Claude auth returned 401.",
    )

    gate = next(gate for gate in state.gates if gate.key == "claude_review")
    assert gate.status == "blocked"
    assert gate.note == "Claude auth returned 401."
    markdown = (tmp_path / WORKFLOW_DIRNAME / "WORKFLOW_STATE.md").read_text(
        encoding="utf-8"
    )
    assert "Claude auth returned 401." in markdown


def test_record_verification_appends_log_and_updates_gate(tmp_path):
    init_workflow(tmp_path, workflow_name="Artifact Repo")

    state = record_verification(
        tmp_path,
        command="pytest tests/hermes_cli/test_workflow_launcher.py",
        result="passed",
        note="workflow tests passed",
    )

    assert state.verifications[-1].result == "passed"
    gate = next(gate for gate in state.gates if gate.key == "verification")
    assert gate.status == "done"
    assert gate.note == "workflow tests passed"


def test_advance_workflow_gate_rejects_unknown_gate(tmp_path):
    init_workflow(tmp_path, workflow_name="Artifact Repo")

    try:
        advance_workflow_gate(tmp_path, "missing", "done")
    except ValueError as exc:
        assert "Unknown gate" in str(exc)
    else:
        raise AssertionError("Expected unknown gate to raise")


def test_parallel_workflow_writes_keep_state_json_valid(tmp_path):
    init_workflow(tmp_path, workflow_name="Artifact Repo")

    def advance() -> None:
        advance_workflow_gate(
            tmp_path,
            "claude_review",
            "blocked",
            note="Claude auth returned 401.",
        )

    def verify() -> None:
        record_verification(
            tmp_path,
            command="workflow-smoke",
            result="passed",
            note="workflow tests passed",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(advance), executor.submit(verify)]
        for future in futures:
            future.result()

    state = load_workflow_state(tmp_path)

    assert state is not None
    assert state.workflow_name == "Artifact Repo"
    gates = {gate.key: gate for gate in state.gates}
    assert gates["claude_review"].status == "blocked"
    assert gates["claude_review"].note == "Claude auth returned 401."
    assert gates["verification"].status == "done"
    assert state.verifications[-1].command == "workflow-smoke"
