"""Regression tests for Kanban gate_recipe deterministic verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    """Isolated HERMES_HOME with an empty kanban DB."""
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _events(conn, task_id: str) -> list[tuple[str, dict | None]]:
    rows = conn.execute(
        "SELECT kind, payload FROM task_events WHERE task_id = ? ORDER BY id",
        (task_id,),
    ).fetchall()
    out: list[tuple[str, dict | None]] = []
    for row in rows:
        out.append((row["kind"], json.loads(row["payload"]) if row["payload"] else None))
    return out


def _set_gate_recipe(conn, task_id: str, recipe) -> None:
    raw = recipe if isinstance(recipe, str) else json.dumps(recipe)
    conn.execute("UPDATE tasks SET gate_recipe = ? WHERE id = ?", (raw, task_id))
    conn.commit()


def _create_gate_task(conn, workspace: Path, *, recipe=None) -> str:
    workspace.mkdir(parents=True, exist_ok=True)
    tid = kb.create_task(
        conn,
        title="gated worker",
        assignee="default",
        workspace_kind="dir",
        workspace_path=str(workspace),
    )
    if recipe is not None:
        _set_gate_recipe(conn, tid, recipe)
    return tid


def test_complete_without_gate_recipe_still_done(kanban_home, tmp_path):
    with kb.connect() as conn:
        tid = _create_gate_task(conn, tmp_path / "workspace")

        assert kb.complete_task(conn, tid, result="ok") is True

        assert kb.get_task(conn, tid).status == "done"
        kinds = [kind for kind, _ in _events(conn, tid)]
        assert "verification_passed" not in kinds
        assert "verification_failed" not in kinds


def test_gate_recipe_all_checks_passes_and_records_event(kanban_home, tmp_path):
    workspace = tmp_path / "workspace"
    artifact = workspace / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    recipe = {
        "checks": [
            {"type": "artifact_exists", "path": "result.json"},
            {"type": "sha256_equals", "path": "result.json", "hex": artifact_hash},
            {"type": "result_field_equals", "file": "result.json", "key": "verdict", "expect": "PASS"},
            {"type": "worker_log_absent", "pattern": "FORBIDDEN"},
            {"type": "no_child_cards"},
        ]
    }
    with kb.connect() as conn:
        tid = _create_gate_task(conn, workspace, recipe=recipe)

        assert kb.complete_task(conn, tid, result="ok") is True

        assert kb.get_task(conn, tid).status == "done"
        passed = [payload for kind, payload in _events(conn, tid) if kind == "verification_passed"]
        assert len(passed) == 1
        assert all(item["ok"] for item in passed[0]["findings"])


def test_gate_recipe_sha256_mismatch_blocks_and_records_failed_event(kanban_home, tmp_path):
    workspace = tmp_path / "workspace"
    artifact = workspace / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
    recipe = {"checks": [{"type": "sha256_equals", "path": "result.json", "hex": "0" * 64}]}
    with kb.connect() as conn:
        tid = _create_gate_task(conn, workspace, recipe=recipe)

        with pytest.raises(kb.VerificationFailedError) as exc_info:
            kb.complete_task(conn, tid, result="claimed pass")

        assert exc_info.value.task_id == tid
        assert kb.get_task(conn, tid).status == "blocked"
        failed = [payload for kind, payload in _events(conn, tid) if kind == "verification_failed"]
        assert len(failed) == 1
        assert failed[0]["findings"][0]["type"] == "sha256_equals"
        assert failed[0]["findings"][0]["ok"] is False


def test_gate_recipe_missing_artifact_blocks(kanban_home, tmp_path):
    recipe = {"checks": [{"type": "artifact_exists", "path": "missing.json"}]}
    with kb.connect() as conn:
        tid = _create_gate_task(conn, tmp_path / "workspace", recipe=recipe)

        with pytest.raises(kb.VerificationFailedError):
            kb.complete_task(conn, tid, result="claimed pass")

        assert kb.get_task(conn, tid).status == "blocked"


def test_verification_failure_is_sticky_and_survives_recompute_ready(kanban_home, tmp_path):
    """A verification_failed block must be sticky (STEP5b2 respawn-loop regression).

    Without an explicit "blocked" event, _has_sticky_block returns False and
    recompute_ready's circuit-breaker auto-recovery promotes the parentless
    blocked card back to ready every dispatch tick -> the worker respawns
    forever. A deterministic verification failure is a deliberate stop; only an
    explicit unblock should re-dispatch it.
    """
    recipe = {"checks": [{"type": "artifact_exists", "path": "missing.json"}]}
    with kb.connect() as conn:
        tid = _create_gate_task(conn, tmp_path / "workspace", recipe=recipe)

        with pytest.raises(kb.VerificationFailedError):
            kb.complete_task(conn, tid, result="claimed pass")

        assert kb.get_task(conn, tid).status == "blocked"
        kinds = [kind for kind, _ in _events(conn, tid)]
        assert "verification_failed" in kinds
        # the sticky marker: a "blocked" event must accompany the failure
        assert "blocked" in kinds
        assert kb._has_sticky_block(conn, tid) is True

        # recompute_ready must NOT auto-promote it back to ready (respawn guard)
        kb.recompute_ready(conn)
        assert kb.get_task(conn, tid).status == "blocked"


@pytest.mark.parametrize("recipe", [{"checks": []}, "{not json"])
def test_gate_recipe_empty_or_unparseable_blocks(kanban_home, tmp_path, recipe):
    with kb.connect() as conn:
        tid = _create_gate_task(conn, tmp_path / "workspace", recipe=recipe)

        with pytest.raises(kb.VerificationFailedError):
            kb.complete_task(conn, tid, result="claimed pass")

        assert kb.get_task(conn, tid).status == "blocked"
        failed = [payload for kind, payload in _events(conn, tid) if kind == "verification_failed"]
        assert failed
        assert failed[-1]["findings"][0]["ok"] is False


def test_gate_recipe_worker_log_absent_blocks_when_pattern_exists(kanban_home, tmp_path):
    recipe = {"checks": [{"type": "worker_log_absent", "pattern": "FORBIDDEN_NETWORK"}]}
    with kb.connect() as conn:
        tid = _create_gate_task(conn, tmp_path / "workspace", recipe=recipe)
        log_path = kb.worker_log_path(tid)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("worker touched FORBIDDEN_NETWORK marker", encoding="utf-8")

        with pytest.raises(kb.VerificationFailedError):
            kb.complete_task(conn, tid, result="claimed pass")

        assert kb.get_task(conn, tid).status == "blocked"


def test_dispatch_skips_ready_task_with_unparseable_gate_recipe(kanban_home, tmp_path):
    with kb.connect() as conn:
        tid = _create_gate_task(conn, tmp_path / "workspace", recipe="{not json")
        spawned: list[str] = []

        result = kb.dispatch_once(
            conn,
            spawn_fn=lambda task, workspace: spawned.append(task.id),
            max_spawn=1,
        )

        assert spawned == []
        assert result.spawned == []
        assert result.skipped_gate_invalid == [tid]
        assert kb.get_task(conn, tid).status == "ready"
