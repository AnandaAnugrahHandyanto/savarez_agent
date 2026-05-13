from __future__ import annotations

import pytest

from hermes_cli import kanban_db
from hermes_cli.workflow import MaterializationResult, materialize_workflow
from hermes_cli.workflow.store import add_gate, connect, create_workflow, list_events, save_dag


def _dag() -> dict:
    return {
        "workflow_id": "wf_mat",
        "nodes": [
            {
                "id": "backend-api",
                "title": "Implement backend API",
                "role": "engineer",
                "profile": "engineer",
                "status": "waiting",
                "gate_level": 1,
                "definition_of_done": ["API tests pass."],
                "scope": {"summary": "Build API."},
                "workspace": {
                    "kind": "worktree",
                    "branch": "workflow/wf_mat/backend-api",
                    "worktree_path": "/tmp/wf_mat-backend-api",
                    "base_ref": "origin/main",
                },
            },
            {
                "id": "integration",
                "title": "Integrate API",
                "role": "integrator",
                "profile": "integrator",
                "status": "waiting",
                "gate_level": 2,
                "parents": ["backend-api"],
                "definition_of_done": ["Integration passes."],
                "scope": {"summary": "Wire API into system."},
            },
        ],
        "edges": [{"source": "backend-api", "target": "integration", "kind": "depends_on"}],
    }


def _create_approved_workflow(conn):
    create_workflow(conn, workflow_id="wf_mat", title="Materialize", board="core", status="dag_approved", now=1.0)
    save_dag(conn, workflow_id="wf_mat", normalized_dag=_dag(), now=2.0)


def test_public_workflow_package_exports_materializer():
    assert MaterializationResult.__name__ == "MaterializationResult"
    assert callable(materialize_workflow)


def test_materialize_rejects_missing_or_unready_workflow(tmp_path):
    with connect(tmp_path / "workflow.db") as workflow_conn:
        with pytest.raises(ValueError, match="workflow not found: wf_missing"):
            materialize_workflow(workflow_conn, "wf_missing", kanban_conn=kanban_db.connect(tmp_path / "kanban.db"))

        create_workflow(workflow_conn, workflow_id="wf_empty", title="Empty", status="dag_approved")
        with pytest.raises(ValueError, match="workflow DAG has no persisted nodes"):
            materialize_workflow(workflow_conn, "wf_empty", kanban_conn=kanban_db.connect(tmp_path / "kanban.db"))

        create_workflow(workflow_conn, workflow_id="wf_unapproved", title="Unapproved", status="dag_validated")
        save_dag(workflow_conn, workflow_id="wf_unapproved", normalized_dag={**_dag(), "workflow_id": "wf_unapproved"})
        with pytest.raises(ValueError, match="workflow is not approved for materialization"):
            materialize_workflow(workflow_conn, "wf_unapproved", kanban_conn=kanban_db.connect(tmp_path / "kanban.db"))


def test_materialize_rejects_unresolved_gates(tmp_path):
    with connect(tmp_path / "workflow.db") as workflow_conn:
        _create_approved_workflow(workflow_conn)
        add_gate(workflow_conn, workflow_id="wf_mat", gate_type="dag_review", level=1, required_actor="human")

        with pytest.raises(ValueError, match="workflow has unresolved gates"):
            materialize_workflow(workflow_conn, "wf_mat", kanban_conn=kanban_db.connect(tmp_path / "kanban.db"))


def test_materialize_creates_kanban_tasks_mappings_edges_and_events(tmp_path):
    with connect(tmp_path / "workflow.db") as workflow_conn:
        kanban_conn = kanban_db.connect(tmp_path / "kanban.db")
        _create_approved_workflow(workflow_conn)

        result = materialize_workflow(workflow_conn, "wf_mat", kanban_conn=kanban_conn, actor_id="publisher", now=12.0)
        tasks = {task.title: task for task in kanban_db.list_tasks(kanban_conn, include_archived=True)}
        mapping_rows = workflow_conn.execute(
            "SELECT * FROM workflow_kanban_mappings WHERE workflow_id = ? ORDER BY node_id",
            ("wf_mat",),
        ).fetchall()
        node_rows = workflow_conn.execute("SELECT node_id, kanban_task_id FROM workflow_nodes WHERE workflow_id = ?", ("wf_mat",)).fetchall()
        workflow = workflow_conn.execute("SELECT status FROM workflows WHERE id = ?", ("wf_mat",)).fetchone()
        events = [event.event_type for event in list_events(workflow_conn, "wf_mat")]

    assert result.to_dict()["status"] == "materialized"
    assert result.workflow_id == "wf_mat"
    assert result.board == "core"
    assert result.already_materialized is False
    assert set(tasks) == {"Implement backend API", "Integrate API"}
    assert tasks["Implement backend API"].assignee == "engineer"
    assert tasks["Implement backend API"].workspace_kind == "worktree"
    assert tasks["Implement backend API"].workspace_path == "/tmp/wf_mat-backend-api"
    assert "Workflow: wf_mat" in (tasks["Implement backend API"].body or "")
    assert "- API tests pass." in (tasks["Implement backend API"].body or "")
    assert tasks["Integrate API"].status == "todo"
    assert [row["board"] for row in mapping_rows] == ["core", "core"]
    assert all(row["task_id"] for row in mapping_rows)
    assert all(row["kanban_task_id"] for row in node_rows)
    assert workflow["status"] == "materialized"
    assert events == [
        "materialization_started",
        "kanban_task_created",
        "kanban_task_created",
        "kanban_link_created",
        "materialization_completed",
    ]


def test_materialize_repairs_links_when_kanban_idempotency_returns_existing_tasks(tmp_path):
    with connect(tmp_path / "workflow.db") as workflow_conn:
        kanban_conn = kanban_db.connect(tmp_path / "kanban.db")
        _create_approved_workflow(workflow_conn)
        parent = kanban_db.create_task(kanban_conn, title="Existing parent", idempotency_key="workflow:wf_mat:node:backend-api")
        child = kanban_db.create_task(kanban_conn, title="Existing child", idempotency_key="workflow:wf_mat:node:integration")

        materialize_workflow(workflow_conn, "wf_mat", kanban_conn=kanban_conn, now=12.0)
        links = kanban_conn.execute("SELECT parent_id, child_id FROM task_links").fetchall()

    assert [(row["parent_id"], row["child_id"]) for row in links] == [(parent, child)]


def test_materialize_does_not_treat_stale_mapping_count_as_complete(tmp_path):
    with connect(tmp_path / "workflow.db") as workflow_conn:
        kanban_conn = kanban_db.connect(tmp_path / "kanban.db")
        _create_approved_workflow(workflow_conn)
        stale_task = kanban_db.create_task(kanban_conn, title="Stale")
        stale_task_2 = kanban_db.create_task(kanban_conn, title="Stale 2")
        workflow_conn.execute(
            "INSERT INTO workflow_kanban_mappings (workflow_id, node_id, board, task_id, materialized_at) VALUES (?, ?, ?, ?, ?)",
            ("wf_mat", "old-node", "core", stale_task, 9.0),
        )
        workflow_conn.execute(
            "INSERT INTO workflow_kanban_mappings (workflow_id, node_id, board, task_id, materialized_at) VALUES (?, ?, ?, ?, ?)",
            ("wf_mat", "another-old-node", "core", stale_task_2, 9.0),
        )
        workflow_conn.commit()

        result = materialize_workflow(workflow_conn, "wf_mat", kanban_conn=kanban_conn, now=12.0)

    assert result.already_materialized is False
    assert {task.node_id for task in result.tasks} == {"backend-api", "integration"}


def test_materialize_repairs_authoritative_state_when_mappings_already_exist(tmp_path):
    with connect(tmp_path / "workflow.db") as workflow_conn:
        kanban_conn = kanban_db.connect(tmp_path / "kanban.db")
        _create_approved_workflow(workflow_conn)
        parent = kanban_db.create_task(kanban_conn, title="Existing parent")
        child = kanban_db.create_task(kanban_conn, title="Existing child")
        workflow_conn.execute(
            "INSERT INTO workflow_kanban_mappings (workflow_id, node_id, board, task_id, materialized_at) VALUES (?, ?, ?, ?, ?)",
            ("wf_mat", "backend-api", "core", parent, 9.0),
        )
        workflow_conn.execute(
            "INSERT INTO workflow_kanban_mappings (workflow_id, node_id, board, task_id, materialized_at) VALUES (?, ?, ?, ?, ?)",
            ("wf_mat", "integration", "core", child, 9.0),
        )
        workflow_conn.commit()

        result = materialize_workflow(workflow_conn, "wf_mat", kanban_conn=kanban_conn, now=14.0)
        workflow = workflow_conn.execute("SELECT status, updated_at FROM workflows WHERE id = ?", ("wf_mat",)).fetchone()
        nodes = workflow_conn.execute(
            "SELECT node_id, kanban_task_id FROM workflow_nodes WHERE workflow_id = ? ORDER BY node_id",
            ("wf_mat",),
        ).fetchall()

    assert result.already_materialized is True
    assert workflow["status"] == "materialized"
    assert workflow["updated_at"] == 14.0
    assert [(row["node_id"], row["kanban_task_id"]) for row in nodes] == [("backend-api", parent), ("integration", child)]


def test_materialize_is_idempotent(tmp_path):
    with connect(tmp_path / "workflow.db") as workflow_conn:
        kanban_conn = kanban_db.connect(tmp_path / "kanban.db")
        _create_approved_workflow(workflow_conn)

        first = materialize_workflow(workflow_conn, "wf_mat", kanban_conn=kanban_conn, now=12.0)
        second = materialize_workflow(workflow_conn, "wf_mat", kanban_conn=kanban_conn, now=13.0)
        tasks = kanban_db.list_tasks(kanban_conn, include_archived=True)

    assert first.already_materialized is False
    assert second.already_materialized is True
    assert [task.task_id for task in second.tasks] == [task.task_id for task in first.tasks]
    assert len(tasks) == 2
