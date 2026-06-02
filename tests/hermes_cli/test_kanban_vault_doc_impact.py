"""Tests for automated Vault-V2 documentation-impact Kanban gates."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from hermes_cli import kanban as kc
from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb._INITIALIZED_PATHS.clear()
    kb.init_db()
    (home / "config.yaml").write_text(
        "kanban:\n"
        "  vault_doc_impact:\n"
        "    enabled: true\n"
        "    curator_assignee: vault-v2-curator\n"
        "    finalizer_step_keys: [finalizer, synthesizer]\n"
        "    finalizer_title_keywords: [finalizer, synthesizer]\n",
        encoding="utf-8",
    )
    return home


@pytest.fixture
def kb_conn(kanban_home):
    with kb.connect() as conn:
        yield conn


def _event_payloads(conn, task_id: str, kind: str = "vault_doc_impact") -> list:
    return [e.payload for e in kb.list_events(conn, task_id) if e.kind == kind]


def _curator_tasks(conn) -> list:
    return kb.list_tasks(conn, assignee="vault-v2-curator", include_archived=True)


def _get_task(conn, tid: str) -> kb.Task:
    t = kb.get_task(conn, tid)
    assert t is not None, f"task {tid} not found"
    return t


def test_gate_creation_inserts_curator_before_finalizer(kb_conn):
    from hermes_cli.kanban_vault_doc_impact import ensure_vault_doc_impact_for_task

    parent_a = kb.create_task(kb_conn, title="ship API", assignee="engineer")
    parent_b = kb.create_task(kb_conn, title="ship docs-sensitive UI", assignee="engineer")
    finalizer_id = kb.create_task(
        kb_conn,
        title="Workflow finalizer",
        assignee="orchestrator",
        parents=[parent_a, parent_b],
        workflow_key="wf-doc-impact",
        current_step_key="finalizer",
    )
    finalizer_task = _get_task(kb_conn, finalizer_id)

    result = ensure_vault_doc_impact_for_task(kb_conn, finalizer_task, source="unit-test")

    assert result["status"] == "gate_created"
    gate_id = result["gate_task_id"]
    gate = kb.get_task(kb_conn, gate_id)
    assert gate is not None
    assert gate.assignee == "vault-v2-curator"
    assert gate.workflow_key == "wf-doc-impact"
    assert gate.current_step_key == "vault_doc_impact"
    assert "Vault-V2 documentation impact" in gate.title
    assert "blindly mutate docs" in (gate.body or "").lower()
    assert finalizer_id in (gate.body or "")

    assert set(kb.parent_ids(kb_conn, gate_id)) == {parent_a, parent_b}
    assert kb.parent_ids(kb_conn, finalizer_id) == [gate_id]

    payloads = _event_payloads(kb_conn, finalizer_id)
    assert payloads[-1]["status"] == "gate_created"
    assert payloads[-1]["gate_task_id"] == gate_id
    assert payloads[-1]["source"] == "unit-test"


def test_explicit_skip_records_no_op_and_does_not_rewire(kb_conn):
    from hermes_cli.kanban_vault_doc_impact import ensure_vault_doc_impact_for_task

    parent = kb.create_task(kb_conn, title="implementation", assignee="engineer")
    finalizer_id = kb.create_task(
        kb_conn,
        title="Workflow finalizer",
        assignee="orchestrator",
        parents=[parent],
        workflow_key="wf-skip-doc-impact",
        current_step_key="finalizer",
    )
    finalizer_task = _get_task(kb_conn, finalizer_id)

    result = ensure_vault_doc_impact_for_task(
        kb_conn,
        finalizer_task,
        mode="skip",
        reason="README-only workflow already covered",
        source="unit-test",
    )

    assert result["status"] == "no_op"
    assert result["reason"] == "README-only workflow already covered"
    assert result.get("gate_task_id") is None
    assert _curator_tasks(kb_conn) == []
    assert kb.parent_ids(kb_conn, finalizer_id) == [parent]
    payloads = _event_payloads(kb_conn, finalizer_id)
    assert payloads[-1]["status"] == "no_op"
    assert payloads[-1]["reason"] == "README-only workflow already covered"


def test_gate_creation_is_idempotent_and_repairs_rewire(kb_conn):
    from hermes_cli.kanban_vault_doc_impact import ensure_vault_doc_impact_for_task

    parent = kb.create_task(kb_conn, title="implementation", assignee="engineer")
    finalizer_id = kb.create_task(
        kb_conn,
        title="Workflow finalizer",
        assignee="orchestrator",
        parents=[parent],
        workflow_key="wf-idempotent-doc-impact",
        current_step_key="finalizer",
    )
    finalizer_task = _get_task(kb_conn, finalizer_id)

    first = ensure_vault_doc_impact_for_task(kb_conn, finalizer_task, source="unit-test")
    gate_id = first["gate_task_id"]

    # Simulate a damaged graph: the finalizer was linked back to the original
    # implementation parent and the gate edge was lost. A retry/backstop must
    # repair this without creating a duplicate curator card.
    kb.unlink_tasks(kb_conn, gate_id, finalizer_id)
    kb.link_tasks(kb_conn, parent, finalizer_id)

    finalizer_task2 = _get_task(kb_conn, finalizer_id)
    second = ensure_vault_doc_impact_for_task(kb_conn, finalizer_task2, source="unit-test")

    assert second["status"] in {"gate_created", "already_recorded"}
    assert second["gate_task_id"] == gate_id
    assert [t.id for t in _curator_tasks(kb_conn)] == [gate_id]
    assert kb.parent_ids(kb_conn, finalizer_id) == [gate_id]
    assert kb.parent_ids(kb_conn, gate_id) == [parent]


def test_reconciler_creates_remediation_for_completed_finalizer_missing_record(kb_conn):
    from hermes_cli.kanban_vault_doc_impact import reconcile_vault_doc_impact

    parent = kb.create_task(kb_conn, title="implementation", assignee="engineer")
    kb.complete_task(kb_conn, parent, summary="implementation complete")
    finalizer_id = kb.create_task(
        kb_conn,
        title="Workflow finalizer",
        assignee="orchestrator",
        parents=[parent],
        workflow_key="wf-reconcile-doc-impact",
        current_step_key="finalizer",
    )
    kb.complete_task(kb_conn, finalizer_id, summary="workflow completed without gate")

    dry = reconcile_vault_doc_impact(kb_conn, dry_run=True, source="unit-test")
    assert dry["would_create"] == [finalizer_id]
    assert _curator_tasks(kb_conn) == []

    result = reconcile_vault_doc_impact(kb_conn, dry_run=False, source="unit-test")

    assert result["created"][0]["finalizer_task_id"] == finalizer_id
    assert result["created"][0]["status"] == "remediation_created"
    gate_id = result["created"][0]["gate_task_id"]
    gate = kb.get_task(kb_conn, gate_id)
    assert gate is not None
    assert gate.status == "ready"
    assert gate.assignee == "vault-v2-curator"
    assert kb.parent_ids(kb_conn, gate_id) == []
    payloads = _event_payloads(kb_conn, finalizer_id)
    assert payloads[-1]["status"] == "remediation_created"


def test_cli_create_triggers_doc_impact_gate(kanban_home):
    parent_out = kc.run_slash("create 'implementation' --assignee engineer")
    parent = re.search(r"(t_[a-f0-9]+)", parent_out).group(1)

    out = kc.run_slash(
        "create 'Workflow finalizer' --assignee orchestrator "
        f"--parent {parent} --workflow-key wf-cli-doc-impact "
        "--current-step-key finalizer"
    )

    finalizer = re.search(r"(t_[a-f0-9]+)", out).group(1)
    assert "Vault doc impact: gate_created" in out
    with kb.connect() as conn:
        gate_tasks = _curator_tasks(conn)
        assert len(gate_tasks) == 1
        gate = gate_tasks[0]
        assert kb.parent_ids(conn, finalizer) == [gate.id]
        assert kb.parent_ids(conn, gate.id) == [parent]


def test_native_kanban_create_tool_triggers_doc_impact_gate(kanban_home, monkeypatch):
    monkeypatch.setenv("HERMES_PROFILE", "orchestrator")
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_origin")
    from tools import kanban_tools as kt

    with kb.connect() as conn:
        parent = kb.create_task(conn, title="implementation", assignee="engineer")

    out = kt._handle_create({
        "title": "Workflow finalizer",
        "assignee": "orchestrator",
        "parents": [parent],
        "workflow_key": "wf-tool-doc-impact",
        "current_step_key": "finalizer",
    })
    data = json.loads(out)

    assert data["ok"] is True
    assert data["vault_doc_impact"]["status"] == "gate_created"
    gate_id = data["vault_doc_impact"]["gate_task_id"]
    with kb.connect() as conn:
        assert kb.parent_ids(conn, data["task_id"]) == [gate_id]
        assert kb.parent_ids(conn, gate_id) == [parent]
