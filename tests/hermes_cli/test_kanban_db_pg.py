from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_db_pg as kb_pg


REPO_ROOT = Path(__file__).resolve().parents[2]
CALLERS = [
    REPO_ROOT / "hermes_cli/kanban.py",
    REPO_ROOT / "gateway/run.py",
    REPO_ROOT / "tools/kanban_tools.py",
]


def _required_surface() -> list[str]:
    names: set[str] = set()
    for path in CALLERS:
        tree = ast.parse(path.read_text(), filename=str(path))
        aliases = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "hermes_cli":
                for alias in node.names:
                    if alias.name == "kanban_db":
                        aliases.add(alias.asname or alias.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in aliases:
                    names.add(node.func.attr)
    return sorted(names)


def _normalized_runtime_signature(func) -> str:
    sig = inspect.signature(func)
    parts: list[str] = []
    for param in sig.parameters.values():
        text = param.name
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            parts.append(text)
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            parts.append(f"*{text}")
            continue
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            parts.append(f"**{text}")
            continue
        if param.kind is inspect.Parameter.KEYWORD_ONLY and "*" not in parts and not any(p.startswith("*") for p in parts):
            parts.append("*")
        if param.default is not inspect._empty:
            text = f"{text}={param.default!r}"
        parts.append(text)
    return f"{func.__name__}({', '.join(parts)})"


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


@pytest.fixture
def conn(kanban_home):
    with kb.connect() as conn:
        yield conn


def test_required_surface_signatures_match_sqlite_module():
    required = _required_surface()
    missing = [name for name in required if not hasattr(kb_pg, name)]
    assert not missing

    sqlite_path = REPO_ROOT / "hermes_cli/kanban_db.py"
    pg_path = REPO_ROOT / "hermes_cli/kanban_db_pg.py"
    mismatched = []
    for name in required:
        sqlite_sig = _normalized_runtime_signature(getattr(kb, name))
        pg_sig = _normalized_runtime_signature(getattr(kb_pg, name))
        if sqlite_sig != pg_sig:
            mismatched.append((name, sqlite_sig, pg_sig))
    assert not mismatched
    assert kb_pg.HallucinatedCardsError is kb.HallucinatedCardsError


def test_wrapper_create_complete_and_context_flow(conn):
    parent = kb_pg.create_task(conn, title="parent", assignee="worker")
    child = kb_pg.create_task(conn, title="child", parents=[parent], assignee="worker")

    child_task = kb_pg.get_task(conn, child)
    assert child_task is not None
    assert child_task.status == "todo"

    kb_pg.complete_task(conn, parent, result="done", summary="finished parent", metadata={"ok": True})

    child_task = kb_pg.get_task(conn, child)
    assert child_task is not None
    assert child_task.status == "ready"
    context = kb_pg.build_worker_context(conn, child)
    assert "finished parent" in context

    runs = kb_pg.list_runs(conn, parent)
    assert runs
    assert runs[-1].summary == "finished parent"


def test_wrapper_comments_links_block_unblock_and_lists(conn):
    parent = kb_pg.create_task(conn, title="a", assignee="worker")
    child = kb_pg.create_task(conn, title="b", assignee="worker")
    standalone = kb_pg.create_task(conn, title="c", assignee="worker")

    kb_pg.link_tasks(conn, parent, child)
    assert kb_pg.parent_ids(conn, child) == [parent]
    assert kb_pg.child_ids(conn, parent) == [child]

    comment_id = kb_pg.add_comment(conn, child, author="reviewer", body="needs eyes")
    comments = kb_pg.list_comments(conn, child)
    assert comments[-1].id == comment_id
    assert comments[-1].body == "needs eyes"

    assert kb_pg.claim_task(conn, standalone) is not None
    assert kb_pg.block_task(conn, standalone, reason="waiting") is True
    blocked = kb_pg.get_task(conn, standalone)
    assert blocked is not None and blocked.status == "blocked"

    assert kb_pg.unblock_task(conn, standalone) is True
    ready = kb_pg.get_task(conn, standalone)
    assert ready is not None and ready.status == "ready"

    kb_pg.complete_task(conn, parent, result="done")
    kb_pg.recompute_ready(conn)
    ready = kb_pg.get_task(conn, child)
    assert ready is not None and ready.status == "ready"


def test_wrapper_notify_cursor_flow(conn):
    tid = kb_pg.create_task(conn, title="notify me", assignee="worker")
    kb_pg.add_notify_sub(
        conn,
        task_id=tid,
        platform="telegram",
        chat_id="123",
        thread_id="456",
        user_id="u1",
        notifier_profile="worker",
    )

    kb_pg.add_comment(conn, tid, author="alice", body="hello")
    old_cursor, claimed_cursor, events = kb_pg.claim_unseen_events_for_sub(
        conn,
        task_id=tid,
        platform="telegram",
        chat_id="123",
        thread_id="456",
        kinds=None,
    )
    assert old_cursor == 0
    assert claimed_cursor >= 1
    assert events
    assert events[-1].task_id == tid

    kb_pg.rewind_notify_cursor(
        conn,
        task_id=tid,
        platform="telegram",
        chat_id="123",
        thread_id="456",
        claimed_cursor=claimed_cursor,
        old_cursor=old_cursor,
    )
    kb_pg.advance_notify_cursor(
        conn,
        task_id=tid,
        platform="telegram",
        chat_id="123",
        thread_id="456",
        new_cursor=claimed_cursor,
    )
    subs = kb_pg.list_notify_subs(conn, tid)
    assert len(subs) == 1
    assert subs[0]["last_event_id"] == claimed_cursor


def test_wrapper_dispatch_once_dry_run(conn, monkeypatch):
    created = kb_pg.create_task(conn, title="spawn me", assignee="worker")
    from hermes_cli import profiles

    monkeypatch.setattr(profiles, "profile_exists", lambda name: name == "worker")

    result = kb_pg.dispatch_once(conn, dry_run=True, max_spawn=1)

    assert isinstance(result, kb.DispatchResult)
    assert result.spawned
    assert result.spawned[0][0] == created


def test_pg_connect_without_driver_or_dsn_errors_cleanly(monkeypatch):
    monkeypatch.delenv("HERMES_KANBAN_POSTGRES_DSN", raising=False)
    with pytest.raises(RuntimeError, match="HERMES_KANBAN_POSTGRES_DSN"):
        kb_pg.connect(board="default")
