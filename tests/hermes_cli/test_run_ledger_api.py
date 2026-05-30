import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermes_cli import web_server


def _client() -> TestClient:
    return TestClient(web_server.app)


def _auth_headers() -> dict[str, str]:
    return {web_server._SESSION_HEADER_NAME: web_server._SESSION_TOKEN}


def _write_ledger(home: Path, project: str, rows: list[dict]) -> Path:
    ledger = home / ".claude" / "teams" / project / "runs" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return ledger


def test_runs_api_requires_session_token() -> None:
    response = _client().get("/api/runs?project=staam")

    assert response.status_code == 401


def test_runs_api_merges_filters_and_sorts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_server.Path, "home", staticmethod(lambda: tmp_path))
    _write_ledger(
        tmp_path,
        "staam",
        [
            {
                "event": "run_started",
                "run_id": "run_1",
                "task_id": "task_a",
                "agent_id": "claude",
                "run_type": "dispatch",
                "started_at": "2026-05-30T01:00:00+00:00",
                "command": "claude -p work",
            },
            {"not valid json": True},
            {
                "event": "run_finished",
                "run_id": "run_1",
                "task_id": "task_a",
                "agent_id": "claude",
                "run_type": "dispatch",
                "started_at": "2026-05-30T01:00:00+00:00",
                "finished_at": "2026-05-30T01:00:03+00:00",
                "duration_seconds": 3.25,
                "exit_code": 0,
                "classification": "ok",
                "stdout_tail": "done",
            },
            {
                "event": "run_finished",
                "run_id": "run_2",
                "task_id": "task_b",
                "agent_id": "deepseek",
                "run_type": "review",
                "started_at": "2026-05-30T02:00:00+00:00",
                "duration_seconds": 9,
                "exit_code": 1,
                "classification": "process_error",
                "stderr_tail": "failed",
            },
        ],
    )

    response = _client().get(
        "/api/runs?project=staam&classification=ok&limit=10",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["runs"][0]["run_id"] == "run_1"
    assert body["runs"][0]["command"] == "claude -p work"
    assert body["runs"][0]["classification"] == "ok"


def test_runs_summary_counts_and_duration(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_server.Path, "home", staticmethod(lambda: tmp_path))
    _write_ledger(
        tmp_path,
        "staam",
        [
            {
                "event": "run_finished",
                "run_id": "run_1",
                "started_at": "2026-05-30T01:00:00+00:00",
                "classification": "ok",
                "duration_seconds": 2,
            },
            {
                "event": "run_finished",
                "run_id": "run_2",
                "started_at": "2026-05-30T02:00:00+00:00",
                "classification": "timeout",
                "duration_seconds": 4,
            },
        ],
    )

    response = _client().get("/api/runs/summary?project=staam", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["classification_counts"] == {"ok": 1, "timeout": 1}
    assert body["avg_duration_seconds"] == 3
    assert [run["run_id"] for run in body["recent_runs"]] == ["run_2", "run_1"]


def test_runs_api_rejects_path_traversal_project(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(web_server.Path, "home", staticmethod(lambda: tmp_path))

    response = _client().get("/api/runs?project=../staam", headers=_auth_headers())

    assert response.status_code == 400
