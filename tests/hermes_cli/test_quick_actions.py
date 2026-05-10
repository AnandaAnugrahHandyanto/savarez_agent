"""Tests for Telegram Quick Actions local control plane."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone, timedelta

from hermes_cli.quick_actions import (
    cli_main,
    discard_candidate,
    execute_promotions,
    format_candidate_digest,
    list_candidates,
    promote_candidate,
    prune_active_actions,
)

def _qa_dir(tmp_path):
    path = tmp_path / "telegram_quick_actions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_candidate(tmp_path, **overrides):
    row = {
        "token": "tok123",
        "action": "save",
        "status": "candidate",
        "title": "Useful saved result",
        "content": "content",
        "recommended_targets": ["cortex_memory"],
        "captured_at": "2026-05-09T00:00:00+00:00",
    }
    row.update(overrides)
    with (_qa_dir(tmp_path) / "routing_candidates.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def test_list_candidates_filters_candidate_status(tmp_path):
    _write_candidate(tmp_path, token="a", status="candidate")
    _write_candidate(tmp_path, token="b", status="discarded")

    rows = list_candidates(home=tmp_path)

    assert [r["token"] for r in rows] == ["a"]


def test_format_candidate_digest_is_telegram_friendly(tmp_path):
    _write_candidate(
        tmp_path,
        token="tok123",
        action="todo",
        title="A very useful follow-up that should be short enough to scan in Telegram",
        recommended_targets=["cortex_todo", "kanban_candidate"],
    )

    rows = list_candidates(home=tmp_path)
    output = format_candidate_digest(rows, status="candidate", limit=5)

    assert "Quick Actions" in output
    assert "id\tstatus\taction" not in output
    assert "**todo** -> **todo** · `tok123`" in output
    assert "Tap a button" in output
    assert "state: candidate" not in output
    assert "/qa promote tok123 --to cortex_todo" not in output
    assert "/qa show <id>" in output


def test_cli_list_uses_chat_friendly_digest(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    _write_candidate(tmp_path, token="tok123", title="CLI digest candidate")

    rc = cli_main(["list", "--limit", "5"])

    assert rc == 0
    output = capsys.readouterr().out
    assert "Quick Actions" in output
    assert "**save** -> **memory** · `tok123`" in output
    assert "id\tstatus\taction" not in output


def test_promote_candidate_marks_row_and_appends_promotion(tmp_path):
    _write_candidate(tmp_path, token="tok123")

    updated = promote_candidate("tok123", target="cortex", home=tmp_path, actor="test")

    assert updated["status"] == "promoted"
    assert updated["promoted_to"] == "cortex"
    rows = [json.loads(line) for line in (_qa_dir(tmp_path) / "routing_candidates.jsonl").read_text().splitlines()]
    assert rows[0]["status"] == "promoted"
    events = [json.loads(line) for line in (_qa_dir(tmp_path) / "promotions.jsonl").read_text().splitlines()]
    assert events[0]["candidate_id"] == "tok123"
    assert events[0]["target"] == "cortex"
    assert events[0]["status"] == "pending_execution"


def test_discard_candidate_marks_row_and_appends_discard(tmp_path):
    _write_candidate(tmp_path, token="tok123")

    updated = discard_candidate("tok123", reason="noise", home=tmp_path, actor="test")

    assert updated["status"] == "discarded"
    assert updated["discard_reason"] == "noise"
    events = [json.loads(line) for line in (_qa_dir(tmp_path) / "discards.jsonl").read_text().splitlines()]
    assert events[0]["candidate_id"] == "tok123"
    assert events[0]["reason"] == "noise"


def test_execute_promotions_runs_cortex_todo_once_and_marks_executed(tmp_path):
    calls = []

    def runner(args):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="todo-id=42\n", stderr="")

    _write_candidate(
        tmp_path,
        token="tok123",
        action="todo",
        title="Follow up from cron",
        content="Investigate cron output",
        recommended_targets=["cortex_todo"],
        todo={"priority": "P1", "category": "ops", "project": "hermes", "source_type": "cron", "source_ref": "cron:daily"},
    )
    promote_candidate("tok123", target="cortex_todo", home=tmp_path, actor="test")

    result = execute_promotions(home=tmp_path, runner=runner)

    assert result["selected"] == 1
    assert result["executed"] == 1
    assert calls == [[
        "cmem",
        "todo-add",
        "--title",
        "Follow up from cron",
        "--content",
        "Investigate cron output",
        "--priority",
        "P1",
        "--category",
        "ops",
        "--project",
        "hermes",
        "--source-type",
        "cron",
        "--source-ref",
        "cron:daily",
    ]]
    promotions = [json.loads(line) for line in (_qa_dir(tmp_path) / "promotions.jsonl").read_text().splitlines()]
    assert promotions[0]["status"] == "executed"
    executions = [json.loads(line) for line in (_qa_dir(tmp_path) / "executions.jsonl").read_text().splitlines()]
    assert executions[0]["operation"] == "cmem_todo_add"
    assert executions[0]["stdout"] == "todo-id=42"

    second = execute_promotions(home=tmp_path, runner=runner)

    assert second["selected"] == 0
    assert len(calls) == 1


def test_execute_promotions_dry_run_does_not_mutate_ledgers(tmp_path):
    _write_candidate(tmp_path, token="tok123", recommended_targets=["cortex_memory"])
    promote_candidate("tok123", target="cortex_memory", home=tmp_path, actor="test")

    result = execute_promotions(home=tmp_path, dry_run=True)

    assert result["selected"] == 1
    assert result["dry_run"] == 1
    assert not (_qa_dir(tmp_path) / "executions.jsonl").exists()
    promotions = [json.loads(line) for line in (_qa_dir(tmp_path) / "promotions.jsonl").read_text().splitlines()]
    assert promotions[0]["status"] == "pending_execution"


def test_execute_promotions_writes_wiki_and_kanban_candidate_ledgers(tmp_path):
    _write_candidate(tmp_path, token="wiki1", title="Wiki item", recommended_targets=["brain_sync_wiki_candidate"])
    _write_candidate(tmp_path, token="kanban1", title="Kanban item", recommended_targets=["kanban_candidate"])
    promote_candidate("wiki1", target="brain_sync_wiki_candidate", home=tmp_path, actor="test")
    promote_candidate("kanban1", target="kanban_candidate", home=tmp_path, actor="test")

    result = execute_promotions(home=tmp_path)

    assert result["selected"] == 2
    assert result["executed"] == 2
    wiki_rows = [json.loads(line) for line in (_qa_dir(tmp_path) / "wiki_candidates.jsonl").read_text().splitlines()]
    kanban_rows = [json.loads(line) for line in (_qa_dir(tmp_path) / "kanban_candidates.jsonl").read_text().splitlines()]
    assert wiki_rows[0]["operation"] == "wiki_candidate"
    assert wiki_rows[0]["candidate"]["token"] == "wiki1"
    assert kanban_rows[0]["operation"] == "kanban_candidate"
    assert kanban_rows[0]["candidate"]["token"] == "kanban1"


def test_execute_promotions_keeps_failed_cortex_targets_retryable(tmp_path):
    calls = []

    def runner(args):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=2, stdout="", stderr="cmem unavailable")

    _write_candidate(tmp_path, token="tok123", recommended_targets=["cortex_memory"])
    promote_candidate("tok123", target="cortex_memory", home=tmp_path, actor="test")

    result = execute_promotions(home=tmp_path, runner=runner)

    assert result["selected"] == 1
    assert result["failed"] == 1
    promotions = [json.loads(line) for line in (_qa_dir(tmp_path) / "promotions.jsonl").read_text().splitlines()]
    assert promotions[0]["status"] == "pending_execution"
    assert promotions[0]["last_execution_status"] == "failed"
    executions = [json.loads(line) for line in (_qa_dir(tmp_path) / "executions.jsonl").read_text().splitlines()]
    assert executions[0]["stderr"] == "cmem unavailable"

    execute_promotions(home=tmp_path, runner=runner)

    assert len(calls) == 2


def test_prune_active_actions_removes_stale_and_can_drop_undated(tmp_path):
    now = datetime.now(timezone.utc)
    active = {
        "fresh": {"created_at": now.isoformat(), "content": "keep"},
        "old": {"created_at": (now - timedelta(days=30)).isoformat(), "content": "drop"},
        "legacy": {"content": "undated"},
    }
    (_qa_dir(tmp_path) / "active_actions.json").write_text(json.dumps(active), encoding="utf-8")

    result = prune_active_actions(older_than_days=14, drop_undated=False, home=tmp_path)

    assert result == {"kept": 2, "removed": 1, "total": 3}
    kept = json.loads((_qa_dir(tmp_path) / "active_actions.json").read_text())
    assert set(kept) == {"fresh", "legacy"}

    result = prune_active_actions(older_than_days=14, drop_undated=True, home=tmp_path)

    assert result == {"kept": 1, "removed": 1, "total": 2}
    kept = json.loads((_qa_dir(tmp_path) / "active_actions.json").read_text())
    assert set(kept) == {"fresh"}
