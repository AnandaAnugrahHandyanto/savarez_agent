import asyncio
import json
from pathlib import Path

import pytest
import yaml
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.platforms.api_server import APIServerAdapter, cors_middleware, security_headers_middleware
from gateway.config import PlatformConfig
from hermes_state import SessionDB


def _make_adapter(api_key: str = "") -> APIServerAdapter:
    extra = {}
    if api_key:
        extra["key"] = api_key
    return APIServerAdapter(PlatformConfig(enabled=True, extra=extra))


def _create_app(adapter: APIServerAdapter) -> web.Application:
    mws = [mw for mw in (cors_middleware, security_headers_middleware) if mw is not None]
    app = web.Application(middlewares=mws)
    app["api_server_adapter"] = adapter
    app.router.add_get("/api/authority/snapshot", adapter._handle_authority_snapshot)
    return app


def _seed_profile(profile_root: Path, *, session_id: str = "session-123") -> None:
    profile_root.mkdir(parents=True, exist_ok=True)
    (profile_root / "workspace").mkdir(parents=True, exist_ok=True)
    (profile_root / "runtime" / "orchestration").mkdir(parents=True, exist_ok=True)
    (profile_root / "runtime" / "runs").mkdir(parents=True, exist_ok=True)

    config = {
        "model": {
            "default": "glm-5.1",
            "provider": "zai",
            "base_url": "https://api.z.ai/api/coding/paas/v4",
        },
        "agent": {
            "max_turns": 42,
            "reasoning_effort": "high",
            "tool_use_enforcement": "required",
        },
        "ui_policy_preset": "full-power",
        "toolsets": ["terminal", "file"],
        "terminal": {
            "backend": "local",
            "timeout": 180,
            "cwd": str(profile_root / "workspace"),
        },
        "memory": {
            "memory_enabled": True,
            "user_profile_enabled": True,
        },
        "compression": {
            "enabled": True,
            "threshold": 0.5,
        },
    }
    (profile_root / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    (profile_root / "SOUL.md").write_text("You are Hermes.\n", encoding="utf-8")

    db = SessionDB(profile_root / "state.db")
    db.create_session(
        session_id,
        source="webui",
        model="glm-5.1",
        model_config={
            "provider": "zai",
            "policyPreset": "full-power",
            "memoryMode": "standard",
            "loadedSkillIds": ["skill-authoring"],
            "pinned": True,
        },
    )
    db.append_message(session_id, "user", "Hello gateway authority")
    db.append_message(session_id, "assistant", "Hi from Hermes authority")
    db.close()

    runs_payload = {
        "runs": [
            {
                "id": "run-123",
                "session_id": session_id,
                "status": "completed",
                "source": "webui-stream",
                "started_at": "2026-04-17T00:00:00Z",
                "updated_at": "2026-04-17T00:00:05Z",
                "finished_at": "2026-04-17T00:00:05Z",
                "last_error": None,
            }
        ]
    }
    (profile_root / "runtime" / "runs" / "index.json").write_text(json.dumps(runs_payload), encoding="utf-8")

    continuations_payload = {
        "items": [
            {
                "sessionId": session_id,
                "status": "pending",
                "reason": "needs follow-up",
                "responsePreview": "Hi from Hermes authority",
                "openTodos": [{"id": "todo-1", "content": "Finish review", "status": "pending"}],
                "createdAt": "2026-04-17T00:00:00Z",
                "updatedAt": "2026-04-17T00:00:05Z",
                "attemptCount": 1,
                "events": [{"type": "pending_created", "timestamp": "2026-04-17T00:00:00Z", "message": "Created"}],
            },
            {
                "sessionId": "session-history",
                "status": "resolved",
                "reason": "done",
                "responsePreview": "Completed",
                "openTodos": [],
                "createdAt": "2026-04-16T00:00:00Z",
                "updatedAt": "2026-04-16T00:00:05Z",
                "attemptCount": 0,
                "events": [{"type": "resolved", "timestamp": "2026-04-16T00:00:05Z", "message": "Resolved"}],
            },
        ]
    }
    (profile_root / "runtime" / "orchestration" / "continuations.json").write_text(
        json.dumps(continuations_payload),
        encoding="utf-8",
    )


class TestAuthoritySnapshotEndpoint:
    def test_returns_profile_scoped_authority_snapshot(self, tmp_path, monkeypatch):
        async def _scenario():
            monkeypatch.setenv("HERMES_HOME", str(tmp_path))
            profile_root = tmp_path / "profiles" / "generic-core"
            _seed_profile(profile_root)

            adapter = _make_adapter()
            app = _create_app(adapter)

            async with TestClient(TestServer(app)) as cli:
                resp = await cli.get("/api/authority/snapshot?profile_id=generic-core&search=gateway&session_id=session-123")
                assert resp.status == 200
                payload = await resp.json()

            assert payload["profileId"] == "generic-core"
            assert payload["config"]["modelDefault"] == "glm-5.1"
            assert payload["config"]["policyPreset"] == "full-power"
            assert len(payload["profiles"]) >= 1
            assert any(profile["id"] == "generic-core" for profile in payload["profiles"])
            assert len(payload["sessions"]) == 1
            assert payload["sessions"][0]["id"] == "session-123"
            assert payload["sessions"][0]["pinned"] is True
            assert payload["session"]["id"] == "session-123"
            assert payload["session"]["pinned"] is True
            assert payload["session"]["messages"][0]["content"] == "Hello gateway authority"
            assert payload["runs"][0]["id"] == "run-123"
            assert len(payload["continuations"]) == 1
            assert len(payload["history"]) == 1
            assert payload["workspaces"]["current"]["path"] == str(profile_root / "workspace")

        asyncio.run(_scenario())

    def test_requires_auth_when_api_key_is_configured(self, tmp_path, monkeypatch):
        async def _scenario():
            monkeypatch.setenv("HERMES_HOME", str(tmp_path))
            _seed_profile(tmp_path / "profiles" / "generic-core")

            adapter = _make_adapter(api_key="sk-secret")
            app = _create_app(adapter)

            async with TestClient(TestServer(app)) as cli:
                denied = await cli.get("/api/authority/snapshot?profile_id=generic-core")
                assert denied.status == 401

                allowed = await cli.get(
                    "/api/authority/snapshot?profile_id=generic-core",
                    headers={"Authorization": "Bearer sk-secret"},
                )
                assert allowed.status == 200
                payload = await allowed.json()
                assert payload["profileId"] == "generic-core"

        asyncio.run(_scenario())
