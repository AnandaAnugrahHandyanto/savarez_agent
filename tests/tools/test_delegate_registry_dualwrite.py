"""Phase 5 Step 2 — AgentTaskRegistry dual-write from tools/delegate_tool.py.

The registry is a parallel ledger next to the legacy ``_active_subagents``
dict (central-brain-openclaw.md §"Step 2"): ``_run_single_child`` registers an
``AgentTaskRecord`` right after ``_register_subagent`` and completes it in the
same ``finally`` that owns ``_unregister_subagent``.  These tests pin:

- register happens alongside _register_subagent (record present + RUNNING
  while the child runs, weakref agent_ref resolves to the child)
- complete on normal exit (terminal record mirroring the entry status,
  agent_ref dropped)
- complete(None) -> FAILED when the run dies without a result dict
  (BaseException / interrupt path)
- a broken registry can never break a real delegate run (guarded dual-write)
- the legacy result dict shape is unchanged (additive-only)
"""

from __future__ import annotations

import threading
import weakref
from unittest.mock import MagicMock

import pytest

from action_runtime.contract import ErrorType, Status
from action_runtime.task_registry import AgentTaskRegistry, TaskStatus
from tools.delegate_tool import _entry_to_execution_result, _run_single_child


@pytest.fixture(autouse=True)
def _reset_registry_singleton(monkeypatch):
    """get_registry() is a process singleton — never let tests share it."""
    import action_runtime.task_registry as task_registry

    monkeypatch.setattr(task_registry, "_instance", None)


@pytest.fixture
def registry(monkeypatch):
    """Fresh registry injected via the name delegate_tool actually calls."""
    from tools import delegate_tool

    reg = AgentTaskRegistry()
    monkeypatch.setattr(delegate_tool, "get_registry", lambda: reg)
    return reg


def _make_parent():
    parent = MagicMock()
    parent._delegate_depth = 0
    parent._active_children = []
    parent._active_children_lock = threading.Lock()
    parent._current_task_id = None
    parent.tool_progress_callback = None
    return parent


def _make_child(
    sid="sa-0-feedface",
    *,
    summary="all done",
    completed=True,
    interrupted=False,
):
    """Mock child with the string identity attrs the dual-write reads."""
    child = MagicMock()
    child._subagent_id = sid
    child._parent_subagent_id = None
    child._delegate_depth = 1
    child.model = "test/model"
    child._credential_pool = None
    child.run_conversation.return_value = {
        "final_response": summary,
        "completed": completed,
        "interrupted": interrupted,
        "api_calls": 1,
        "messages": [],
    }
    return child


# ── register alongside _register_subagent ──────────────────────────────


def test_record_registered_and_running_during_run(registry):
    from tools import delegate_tool

    sid = "sa-0-aaaa1111"
    child = _make_child(sid)
    seen = {}

    def _capture(user_message=None, task_id=None):
        # Runs on the child worker thread while the record must be live.
        rec = registry.get(sid)
        seen["status"] = rec.status if rec else None
        seen["goal"] = rec.goal if rec else None
        seen["intent"] = rec.intent if rec else None
        seen["depth"] = rec.depth if rec else None
        seen["model"] = rec.model if rec else None
        seen["parent_task_id"] = rec.parent_task_id if rec else "MISSING"
        seen["agent_ref"] = rec.agent_ref if rec else None
        seen["in_active"] = any(
            r["subagent_id"] == sid for r in delegate_tool.list_active_subagents()
        )
        return {
            "final_response": "done",
            "completed": True,
            "interrupted": False,
            "api_calls": 1,
            "messages": [],
        }

    child.run_conversation.side_effect = _capture
    result = _run_single_child(
        task_index=0, goal="dual write", child=child, parent_agent=_make_parent()
    )

    assert result["status"] == "completed"
    # Registered alongside the legacy dict, with _register_subagent's fields.
    assert seen["in_active"] is True
    assert seen["status"] is TaskStatus.RUNNING
    assert seen["goal"] == "dual write"
    assert seen["intent"] == "delegate"
    assert seen["depth"] == 0  # _delegate_depth=1 -> TUI depth 0
    assert seen["model"] == "test/model"
    assert seen["parent_task_id"] is None
    # agent_ref is a weakref that resolves to the live child.
    assert isinstance(seen["agent_ref"], weakref.ref)
    assert seen["agent_ref"]() is child


def test_no_registration_without_stable_subagent_id(registry):
    # MagicMock auto-attrs are not str -> the legacy path skips registration;
    # the dual-write must skip too.
    child = MagicMock()
    child._credential_pool = None
    child.run_conversation.return_value = {
        "final_response": "done",
        "completed": True,
        "interrupted": False,
        "api_calls": 1,
        "messages": [],
    }
    result = _run_single_child(
        task_index=0, goal="no id", child=child, parent_agent=_make_parent()
    )
    assert result["status"] == "completed"
    assert registry.list_active() == []


# ── complete on normal exit ─────────────────────────────────────────────


def test_complete_on_normal_exit_mirrors_status_and_drops_agent_ref(registry):
    sid = "sa-0-bbbb2222"
    child = _make_child(sid, summary="task finished")

    result = _run_single_child(
        task_index=0, goal="finish me", child=child, parent_agent=_make_parent()
    )

    assert result["status"] == "completed"
    rec = registry.get(sid)
    assert rec is not None
    assert rec.status is TaskStatus.SUCCEEDED
    assert rec.agent_ref is None
    assert rec.finished_at is not None
    assert rec.result is not None
    assert rec.result.status is Status.SUCCEEDED
    assert rec.result.outputs == {"summary": "task finished"}
    assert registry.list_active() == []


def test_complete_on_interrupted_child_maps_transport_failed(registry):
    sid = "sa-0-cccc3333"
    child = _make_child(sid, summary="partial", completed=False, interrupted=True)

    result = _run_single_child(
        task_index=0, goal="stop me", child=child, parent_agent=_make_parent()
    )

    assert result["status"] == "interrupted"
    rec = registry.get(sid)
    assert rec.status is TaskStatus.FAILED
    assert rec.result.status is Status.FAILED
    assert rec.result.error.type is ErrorType.TRANSPORT
    assert rec.result.error.message == "interrupted"
    assert rec.result.error.retryable is False


def test_complete_on_child_exception_maps_internal_failed(registry):
    sid = "sa-0-dddd4444"
    child = _make_child(sid)
    child.run_conversation.side_effect = RuntimeError("boom")

    result = _run_single_child(
        task_index=0, goal="blow up", child=child, parent_agent=_make_parent()
    )

    assert result["status"] == "error"
    rec = registry.get(sid)
    assert rec.status is TaskStatus.FAILED
    assert rec.result.error.type is ErrorType.INTERNAL
    assert "boom" in rec.result.error.message
    assert rec.agent_ref is None


# ── session_id threading + _tasks.jsonl persistence (Step 6a) ───────────


def test_dual_write_carries_parent_session_id_and_persists(
    registry, tmp_path, monkeypatch
):
    """A parent agent with a string session_id ties the child record to that
    session, so complete() appends the snapshot to the session's
    _tasks.jsonl (end-to-end through the real registry persist path)."""
    import json

    import hermes_constants

    monkeypatch.setattr(hermes_constants, "get_hermes_home", lambda: tmp_path)
    parent = _make_parent()
    parent.session_id = "sess-dw"
    sid = "sa-0-9999aaaa"
    child = _make_child(sid, summary="persisted")

    result = _run_single_child(
        task_index=0, goal="persist me", child=child, parent_agent=parent
    )

    assert result["status"] == "completed"
    assert registry.get(sid).session_id == "sess-dw"
    lines = (
        (tmp_path / "spawn-trees" / "sess-dw" / "_tasks.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["task_id"] == sid
    assert entry["session_id"] == "sess-dw"
    assert entry["status"] == "succeeded"


def test_dual_write_skips_non_string_parent_session_id(registry):
    """Test doubles (MagicMock attrs) must not leak a non-string session_id
    into the record — no session, no persistence."""
    sid = "sa-0-8888bbbb"
    child = _make_child(sid)

    result = _run_single_child(
        task_index=0, goal="no session", child=child, parent_agent=_make_parent()
    )

    assert result["status"] == "completed"
    assert registry.get(sid).session_id is None


# ── complete(None) -> FAILED on the interrupt path ──────────────────────


def test_run_killed_without_entry_completes_failed_with_none_result(registry):
    # BaseException escapes every except-Exception handler, so the finally
    # sees entry=None -> complete(sid, None) -> FAILED with no result.
    sid = "sa-0-eeee5555"
    child = _make_child(sid)
    child.run_conversation.side_effect = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        _run_single_child(
            task_index=0, goal="hard kill", child=child, parent_agent=_make_parent()
        )

    rec = registry.get(sid)
    assert rec is not None
    assert rec.status is TaskStatus.FAILED
    assert rec.result is None
    assert rec.agent_ref is None
    assert registry.list_active() == []


# ── a broken registry never breaks the run ──────────────────────────────


def test_registry_failure_does_not_break_delegate_run(monkeypatch):
    from tools import delegate_tool

    def _boom():
        raise RuntimeError("registry down")

    monkeypatch.setattr(delegate_tool, "get_registry", _boom)
    sid = "sa-0-ffff6666"
    child = _make_child(sid)

    result = _run_single_child(
        task_index=0, goal="survive", child=child, parent_agent=_make_parent()
    )

    # Legacy result shape and cleanup are untouched by the registry failure.
    assert result["status"] == "completed"
    assert result["summary"] == "all done"
    assert all(
        r["subagent_id"] != sid for r in delegate_tool.list_active_subagents()
    )


# ── _entry_to_execution_result mapping pins ─────────────────────────────


def test_entry_mapping_terminal_rules():
    res = _entry_to_execution_result({"status": "completed", "summary": "ok"})
    assert res.status is Status.SUCCEEDED
    assert res.outputs == {"summary": "ok"}
    assert res.error is None

    res = _entry_to_execution_result({"status": "failed", "error": "no output"})
    assert res.status is Status.FAILED
    assert res.error.type is ErrorType.PROVIDER_ERROR
    assert res.error.message == "no output"
    assert res.error.retryable is False

    res = _entry_to_execution_result({"status": "error", "error": "boom"})
    assert res.error.type is ErrorType.INTERNAL

    res = _entry_to_execution_result({"status": "timeout", "error": "slow"})
    assert res.error.type is ErrorType.TRANSPORT
    assert res.error.message == "timeout"

    # Missing/unknown entries yield None -> registry maps to FAILED.
    assert _entry_to_execution_result(None) is None
    assert _entry_to_execution_result({"status": "wat"}) is None
