"""API tests for one-step resolver task creation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli import kanban_db as kb


def _load_plugin_router():
    repo_root = Path(__file__).resolve().parents[2]
    plugin_file = repo_root / "plugins" / "kanban" / "dashboard" / "plugin_api.py"
    mod_name = "hermes_dashboard_plugin_kanban_resolver_test"
    if mod_name in sys.modules:
        return sys.modules[mod_name].router
    spec = importlib.util.spec_from_file_location(mod_name, plugin_file)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod.router


@pytest.fixture
def kanban_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


@pytest.fixture
def client(kanban_home: Path) -> TestClient:
    app = FastAPI()
    app.include_router(_load_plugin_router(), prefix="/api/plugins/kanban")
    return TestClient(app)


def _blocked_task() -> str:
    conn = kb.connect()
    try:
        task_id = kb.create_task(conn, title="blocked", assignee="dev")
        kb.claim_task(conn, task_id)
        task = kb.get_task(conn, task_id)
        assert task is not None
        kb.block_task(
            conn,
            task_id,
            reason="waiting for resolver",
            expected_run_id=task.current_run_id,
        )
        return task_id
    finally:
        conn.close()


def test_post_task_resolver_creates_and_links_resolver(client: TestClient) -> None:
    blocked = _blocked_task()

    r = client.post(
        f"/api/plugins/kanban/tasks/{blocked}/resolver",
        json={
            "title": "repair dependency",
            "body": "Fix the dependency for the blocked card.",
            "assignee": "dev",
            "idempotency_key": "dep-fix",
        },
    )

    assert r.status_code == 200
    data = r.json()
    resolver_id = data["resolver_task"]["id"]
    assert data["blocked_task"]["id"] == blocked
    assert data["blocked_by"] == [resolver_id]
    assert data["auto_unblock_when_blockers_done"] is True
    assert data["resolver_dependency"]["blocked_by"] == [resolver_id]
    assert data["resolver_dependency"]["auto_unblock_when_blockers_done"] is True
    assert data["resolver_dependency"]["resolvers"] == [
        {
            "id": resolver_id,
            "title": "repair dependency",
            "status": "ready",
            "assignee": "dev",
            "auto_unblock_enabled": True,
            "terminal": False,
        }
    ]

    detail = client.get(f"/api/plugins/kanban/tasks/{blocked}")
    assert detail.status_code == 200
    assert detail.json()["resolver_dependency"]["resolvers"][0]["id"] == resolver_id

    conn = kb.connect()
    try:
        assert kb.parent_ids(conn, blocked) == [resolver_id]
    finally:
        conn.close()


def test_post_task_resolver_is_idempotent(client: TestClient) -> None:
    blocked = _blocked_task()
    payload = {
        "title": "same resolver",
        "assignee": "dev",
        "idempotency_key": "same-resolver",
    }

    first = client.post(f"/api/plugins/kanban/tasks/{blocked}/resolver", json=payload)
    second = client.post(f"/api/plugins/kanban/tasks/{blocked}/resolver", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["resolver_task"]["id"] == first.json()["resolver_task"]["id"]


def test_post_task_resolver_rejects_invalid_blocked_task(client: TestClient) -> None:
    conn = kb.connect()
    try:
        ready = kb.create_task(conn, title="ready", assignee="dev")
    finally:
        conn.close()

    missing = client.post(
        "/api/plugins/kanban/tasks/t_missing/resolver",
        json={"title": "resolver", "assignee": "dev"},
    )
    not_blocked = client.post(
        f"/api/plugins/kanban/tasks/{ready}/resolver",
        json={"title": "resolver", "assignee": "dev"},
    )

    assert missing.status_code == 404
    assert not_blocked.status_code == 400
    assert "expected 'blocked'" in not_blocked.json()["detail"]


def test_post_task_resolver_rejects_self_or_cycle_existing_idempotent_task(client: TestClient) -> None:
    blocked = _blocked_task()
    conn = kb.connect()
    try:
        child = kb.create_task(
            conn,
            title="already a child",
            assignee="dev",
            parents=[blocked],
            idempotency_key=f"resolver:{blocked}:cycle",
        )
        assert child in kb.child_ids(conn, blocked)
    finally:
        conn.close()

    r = client.post(
        f"/api/plugins/kanban/tasks/{blocked}/resolver",
        json={"title": "already a child", "assignee": "dev", "idempotency_key": "cycle"},
    )

    assert r.status_code == 400
    assert "would create a cycle" in r.json()["detail"]
