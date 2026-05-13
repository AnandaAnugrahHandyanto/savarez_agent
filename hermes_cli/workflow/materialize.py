"""Materialize persisted Hermes workflows into Kanban tasks."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
import time
from typing import Any

from hermes_cli import kanban_db

from .store import add_event, get_workflow


@dataclass(frozen=True)
class MaterializedTask:
    workflow_id: str
    node_id: str
    board: str
    task_id: str
    title: str
    assignee: str | None
    workspace_kind: str
    workspace_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "nodeId": self.node_id,
            "board": self.board,
            "taskId": self.task_id,
            "title": self.title,
            "assignee": self.assignee,
            "workspaceKind": self.workspace_kind,
            "workspacePath": self.workspace_path,
        }


@dataclass(frozen=True)
class MaterializationResult:
    workflow_id: str
    board: str
    status: str
    tasks: list[MaterializedTask]
    links_created: list[dict[str, str]]
    already_materialized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "board": self.board,
            "status": self.status,
            "tasks": [task.to_dict() for task in self.tasks],
            "linksCreated": self.links_created,
            "alreadyMaterialized": self.already_materialized,
        }


def materialize_workflow(
    workflow_conn: sqlite3.Connection,
    workflow_id: str,
    *,
    kanban_conn: sqlite3.Connection | None = None,
    actor_id: str = "system",
    now: float | None = None,
) -> MaterializationResult:
    """Materialize persisted workflow nodes and edges into Kanban tasks."""

    workflow = get_workflow(workflow_conn, workflow_id)
    if workflow is None:
        raise ValueError(f"workflow not found: {workflow_id}")
    if workflow.status not in {"dag_approved", "materialized"}:
        raise ValueError("workflow is not approved for materialization")

    nodes = workflow_conn.execute(
        "SELECT * FROM workflow_nodes WHERE workflow_id = ? ORDER BY created_at ASC, node_id ASC",
        (workflow_id,),
    ).fetchall()
    if not nodes:
        raise ValueError("workflow DAG has no persisted nodes")

    unresolved_gate = workflow_conn.execute(
        "SELECT 1 FROM workflow_gates WHERE workflow_id = ? AND status NOT IN ('approved', 'rejected', 'skipped') LIMIT 1",
        (workflow_id,),
    ).fetchone()
    if unresolved_gate is not None:
        raise ValueError("workflow has unresolved gates")

    board = workflow.board
    kconn = kanban_conn or kanban_db.connect(board=board)
    ts = time.time() if now is None else now
    existing = _existing_mappings(workflow_conn, workflow_id, board)
    edge_rows = _edge_rows(workflow_conn, workflow_id)
    ordered_nodes = _topological_nodes(nodes, edge_rows)
    node_ids = {node["node_id"] for node in nodes}
    existing = {
        node_id: task_id
        for node_id, task_id in existing.items()
        if node_id in node_ids and kanban_db.get_task(kconn, task_id) is not None
    }
    if set(existing) == node_ids:
        _repair_materialized_state(workflow_conn, workflow_id, existing, materialized_at=ts)
        links_created = _ensure_links(
            kconn,
            workflow_conn,
            workflow_id,
            board,
            existing,
            edge_rows=edge_rows,
            actor_id=actor_id,
            now=ts,
            emit_events=False,
        )
        return MaterializationResult(
            workflow_id=workflow_id,
            board=board,
            status="materialized",
            tasks=[_materialized_task_from_mapping(workflow_id, board, node, existing[node["node_id"]], kconn) for node in ordered_nodes],
            links_created=links_created,
            already_materialized=True,
        )

    add_event(
        workflow_conn,
        workflow_id=workflow_id,
        event_type="materialization_started",
        actor_type="workflow",
        actor_id=actor_id,
        data={"board": board},
        now=ts,
    )
    task_by_node: dict[str, str] = dict(existing)
    tasks: list[MaterializedTask] = []
    links_created: list[dict[str, str]] = []

    for node in ordered_nodes:
        node_id = node["node_id"]
        if node_id not in task_by_node:
            parent_task_ids = [task_by_node[edge["parent_node_id"]] for edge in edge_rows if edge["child_node_id"] == node_id and edge["parent_node_id"] in task_by_node]
            workspace_kind = "worktree" if node["worktree_path"] else "scratch"
            task_id = kanban_db.create_task(
                kconn,
                title=node["title"],
                body=_task_body(workflow_id, node),
                assignee=node["profile"],
                created_by=f"workflow:{actor_id}",
                workspace_kind=workspace_kind,
                workspace_path=node["worktree_path"],
                parents=parent_task_ids,
                idempotency_key=f"workflow:{workflow_id}:node:{node_id}",
            )
            _record_mapping(workflow_conn, workflow_id=workflow_id, node_id=node_id, board=board, task_id=task_id, materialized_at=ts)
            task_by_node[node_id] = task_id
            add_event(
                workflow_conn,
                workflow_id=workflow_id,
                node_id=node_id,
                event_type="kanban_task_created",
                actor_type="workflow",
                actor_id=actor_id,
                data={"board": board, "nodeId": node_id, "taskId": task_id},
                now=ts,
            )
        tasks.append(_materialized_task_from_mapping(workflow_id, board, node, task_by_node[node_id], kconn))

    links_created = _ensure_links(
        kconn,
        workflow_conn,
        workflow_id,
        board,
        task_by_node,
        edge_rows=edge_rows,
        actor_id=actor_id,
        now=ts,
        emit_events=True,
    )

    workflow_conn.execute("UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?", ("materialized", ts, workflow_id))
    add_event(
        workflow_conn,
        workflow_id=workflow_id,
        event_type="materialization_completed",
        actor_type="workflow",
        actor_id=actor_id,
        data={"board": board, "taskCount": len(tasks)},
        now=ts,
    )
    return MaterializationResult(workflow_id=workflow_id, board=board, status="materialized", tasks=tasks, links_created=links_created, already_materialized=False)


def _edge_rows(conn: sqlite3.Connection, workflow_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM workflow_edges WHERE workflow_id = ? ORDER BY parent_node_id ASC, child_node_id ASC",
        (workflow_id,),
    ).fetchall()


def _existing_mappings(conn: sqlite3.Connection, workflow_id: str, board: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT node_id, task_id FROM workflow_kanban_mappings WHERE workflow_id = ? AND board = ?",
        (workflow_id, board),
    ).fetchall()
    return {row["node_id"]: row["task_id"] for row in rows}


def _record_mapping(conn: sqlite3.Connection, *, workflow_id: str, node_id: str, board: str, task_id: str, materialized_at: float) -> None:
    conn.execute(
        """
        INSERT INTO workflow_kanban_mappings (workflow_id, node_id, board, task_id, materialized_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(workflow_id, node_id) DO UPDATE SET board = excluded.board, task_id = excluded.task_id, materialized_at = excluded.materialized_at
        """,
        (workflow_id, node_id, board, task_id, materialized_at),
    )
    conn.execute(
        "UPDATE workflow_nodes SET kanban_task_id = ?, updated_at = ? WHERE workflow_id = ? AND node_id = ?",
        (task_id, materialized_at, workflow_id, node_id),
    )
    conn.commit()


def _repair_materialized_state(conn: sqlite3.Connection, workflow_id: str, task_by_node: dict[str, str], *, materialized_at: float) -> None:
    for node_id, task_id in task_by_node.items():
        conn.execute(
            "UPDATE workflow_nodes SET kanban_task_id = ?, updated_at = ? WHERE workflow_id = ? AND node_id = ?",
            (task_id, materialized_at, workflow_id, node_id),
        )
    conn.execute(
        "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
        ("materialized", materialized_at, workflow_id),
    )
    conn.commit()


def _ensure_links(
    kconn: sqlite3.Connection,
    workflow_conn: sqlite3.Connection,
    workflow_id: str,
    board: str,
    task_by_node: dict[str, str],
    *,
    edge_rows: list[sqlite3.Row],
    actor_id: str,
    now: float,
    emit_events: bool,
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for edge in edge_rows:
        parent_task = task_by_node.get(edge["parent_node_id"])
        child_task = task_by_node.get(edge["child_node_id"])
        if not parent_task or not child_task:
            continue
        already = kconn.execute(
            "SELECT 1 FROM task_links WHERE parent_id = ? AND child_id = ?",
            (parent_task, child_task),
        ).fetchone()
        if already is None:
            kanban_db.link_tasks(kconn, parent_task, child_task)
        link = {"parentTaskId": parent_task, "childTaskId": child_task}
        links.append(link)
        if emit_events:
            add_event(
                workflow_conn,
                workflow_id=workflow_id,
                event_type="kanban_link_created",
                actor_type="workflow",
                actor_id=actor_id,
                data={
                    "board": board,
                    "parentNodeId": edge["parent_node_id"],
                    "childNodeId": edge["child_node_id"],
                    "parentTaskId": parent_task,
                    "childTaskId": child_task,
                },
                now=now,
            )
    return links


def _topological_nodes(nodes: list[sqlite3.Row], edges: list[sqlite3.Row]) -> list[sqlite3.Row]:
    by_id = {node["node_id"]: node for node in nodes}
    remaining = set(by_id)
    ordered: list[sqlite3.Row] = []
    while remaining:
        ready = sorted(
            node_id for node_id in remaining if all(edge["parent_node_id"] not in remaining for edge in edges if edge["child_node_id"] == node_id)
        )
        if not ready:
            return [by_id[node_id] for node_id in sorted(remaining)]
        for node_id in ready:
            ordered.append(by_id[node_id])
            remaining.remove(node_id)
    return ordered


def _materialized_task_from_mapping(workflow_id: str, board: str, node: sqlite3.Row, task_id: str, kconn: sqlite3.Connection) -> MaterializedTask:
    task = kanban_db.get_task(kconn, task_id)
    return MaterializedTask(
        workflow_id=workflow_id,
        node_id=node["node_id"],
        board=board,
        task_id=task_id,
        title=task.title if task else node["title"],
        assignee=task.assignee if task else node["profile"],
        workspace_kind=task.workspace_kind if task else ("worktree" if node["worktree_path"] else "scratch"),
        workspace_path=task.workspace_path if task else node["worktree_path"],
    )


def _task_body(workflow_id: str, node: sqlite3.Row) -> str:
    definition = _loads(node["definition_of_done_json"], [])
    scope = _loads(node["scope_json"], {})
    lines = [f"Workflow: {workflow_id}", f"Node: {node['node_id']}", "", f"Scope: {scope.get('summary', '')}", "", "Definition of done:"]
    lines.extend(f"- {item}" for item in definition)
    if node["branch"] or node["worktree_path"] or node["base_ref"]:
        lines.extend(["", "Workspace:"])
        if node["branch"]:
            lines.append(f"- Branch: {node['branch']}")
        if node["base_ref"]:
            lines.append(f"- Base ref: {node['base_ref']}")
        if node["worktree_path"]:
            lines.append(f"- Worktree: {node['worktree_path']}")
    return "\n".join(lines)


def _loads(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return fallback
