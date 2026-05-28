import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_session_audit_endpoint_returns_profile_scoped_context_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    (audit_dir / "2026-05-27.jsonl").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event": "turn_context_snapshot",
                "timestamp": "2026-05-27T12:00:00+00:00",
                "timestamp_unix": 1,
                "session_id": "visible-session",
                "profile": "builderwrx-eddie",
                "context": {"enabled_toolsets": ["safe"]},
                "tools": {"available": ["clarify"]},
                "tool_attempts": [],
            }
        )
        + "\n"
        + json.dumps({"session_id": "other-session", "event": "turn_context_snapshot"})
        + "\n",
        encoding="utf-8",
    )

    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    client = TestClient(app)
    client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    resp = client.get("/api/sessions/visible-session/audit")

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "visible-session"
    assert body["count"] == 1
    assert body["events"][0]["profile"] == "builderwrx-eddie"
