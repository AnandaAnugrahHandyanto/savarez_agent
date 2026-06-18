"""Tests for the bundled XMemo memory provider."""

from __future__ import annotations

import httpx
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest


def _load_provider(tmp_path: Path):
    """Load the bundled XMemo provider into a temp HERMES_HOME."""
    from plugins.memory import load_memory_provider

    os.environ["HERMES_HOME"] = str(tmp_path)
    provider = load_memory_provider("xmemo")
    assert provider is not None
    return provider


@pytest.fixture
def provider(tmp_path):
    provider = _load_provider(tmp_path)
    provider.initialize("test-session")
    return provider


class FakeClient:
    def __init__(self, search_results=None, recall_context=None):
        self.search_results = search_results or []
        self.recall_context_response = recall_context or {}
        self.calls: List[Dict[str, Any]] = []

    def _record(self, method, **kwargs):
        self.calls.append({"method": method, **kwargs})

    def health(self):
        self._record("health")
        return {"status": "ok"}

    def validate_token(self):
        self._record("validate_token")
        return {"status": "valid"}

    def recall_context(self, **kwargs):
        self._record("recall_context", **kwargs)
        return self.recall_context_response

    def search(self, **kwargs):
        self._record("search", **kwargs)
        return self.search_results

    def remember(self, **kwargs):
        self._record("remember", **kwargs)
        return {"id": "mem-123"}

    def update_state(self, **kwargs):
        self._record("update_state", **kwargs)
        return {"id": "state-123"}

    def record_event(self, **kwargs):
        self._record("record_event", **kwargs)
        return {"id": "event-123"}

    def create_reminder(self, **kwargs):
        self._record("create_reminder", **kwargs)
        return {"id": "reminder-123"}

    def list_reminders(self, **kwargs):
        self._record("list_reminders", **kwargs)
        return []

    def complete_reminder(self, **kwargs):
        self._record("complete_reminder", **kwargs)
        return {"id": kwargs.get("todo_id", "reminder-123")}

    def mark_used(self, **kwargs):
        self._record("mark_used", **kwargs)
        if "bucket" in kwargs or "scope" in kwargs:
            raise ValueError("MemoryUsageRequest does not accept bucket/scope")
        return {"id": kwargs.get("memory_id", "mem-123")}

    def forget(self, **kwargs):
        self._record("forget", **kwargs)
        return {"id": kwargs.get("memory_id", "mem-123")}

    def create_restart_snapshot(self, **kwargs):
        self._record("create_restart_snapshot", **kwargs)
        return {"id": "snapshot-123"}

    def close(self):
        self._record("close")


def test_external_load(provider):
    assert provider.name == "xmemo"


def test_default_tool_schemas(provider):
    names = {s["name"] for s in provider.get_tool_schemas()}
    assert names == {
        "xmemo_recall_context",
        "xmemo_search",
        "xmemo_remember",
        "xmemo_update_state",
    }


def test_remember_routes_to_api(provider, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(provider, "_get_client", lambda: fake)

    result = json.loads(
        provider.handle_tool_call(
            "xmemo_remember",
            {"content": "user likes small PRs", "path": "hermes/preferences"},
        )
    )
    assert result["result"] == "Saved to XMemo."
    assert fake.calls[0]["method"] == "remember"


def test_mark_used_payload_no_bucket_scope(provider, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(provider, "_get_client", lambda: fake)

    result = json.loads(
        provider.handle_tool_call(
            "xmemo_mark_used",
            {"memory_id": "mem-456", "context": "used in answer"},
        )
    )
    assert result["result"] == "Memory usage recorded in XMemo."
    assert fake.calls[0]["method"] == "mark_used"
    assert "bucket" not in fake.calls[0]
    assert "scope" not in fake.calls[0]


def test_capture_timeline_false_no_auto_write(provider, monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(provider, "_get_client", lambda: fake)

    provider.sync_turn("remember that I prefer small PRs", "got it")
    assert fake.calls == []


def test_redaction_replaces_token(provider, monkeypatch, tmp_path):
    from plugins.memory.xmemo.config import save_config

    os.environ["HERMES_HOME"] = str(tmp_path)
    save_config({"capture_timeline": True}, str(tmp_path))

    # Re-load plugin with capture_timeline enabled
    provider2 = _load_provider(tmp_path)
    provider2.initialize("test-session")
    provider2._config["api_key"] = "test-key"

    fake = FakeClient()
    monkeypatch.setattr(provider2, "_get_client", lambda: fake)

    secret = "sk-" + "a" * 50
    provider2.sync_turn(f"remember this token {secret}", "ok")
    assert len(fake.calls) == 1
    assert fake.calls[0]["method"] == "record_event"
    content = fake.calls[0]["content"]
    assert secret not in content
    assert "[REDACTED]" in content


def test_rest_mark_used_usage_endpoint():
    from plugins.memory.xmemo.client import XMemoClient

    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "mem-123"})

    client = XMemoClient(
        base_url="https://xmemo.dev",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    client.mark_used("mem-123", context="used in answer")
    client.close()

    assert len(requests) == 1
    assert requests[0].url.path == "/v1/memories/mem-123/usage"
    body = json.loads(requests[0].content)
    assert body["action"] == "used"
    assert "bucket" not in body
    assert "scope" not in body


def test_team_id_passed_to_api_calls(provider, monkeypatch):
    provider._config["team_id"] = "team-abc"
    fake = FakeClient()
    monkeypatch.setattr(provider, "_get_client", lambda: fake)

    provider.handle_tool_call(
        "xmemo_remember",
        {"content": "team note", "path": "hermes/team-note"},
    )
    remember_call = fake.calls[0]
    assert remember_call["team_id"] == "team-abc"


def test_setup_required_409_does_not_crash_initialize(tmp_path, monkeypatch):
    from plugins.memory.xmemo.client import XMemoClientError

    os.environ["HERMES_HOME"] = str(tmp_path)
    os.environ["XMEMO_KEY"] = "test-key"
    provider = _load_provider(tmp_path)

    calls = []

    class FailingValidationClient:
        def validate_token(self):
            calls.append("validate_token")
            raise XMemoClientError("setup required", status_code=409)

        def close(self):
            pass

    monkeypatch.setattr(provider, "_get_client", lambda: FailingValidationClient())

    provider.initialize("test-session")
    assert calls == ["validate_token"]


def test_validate_api_key_ok():
    from plugins.memory.xmemo.cli import _validate_api_key
    from plugins.memory.xmemo.client import XMemoClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/auth/token/validate"
        return httpx.Response(200, json={"status": "ok"})

    client = XMemoClient(
        base_url="https://xmemo.dev",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    ok, msg = _validate_api_key("https://xmemo.dev", "test-key", client=client)
    assert ok is True
    assert msg == ""


def test_validate_api_key_setup_required():
    from plugins.memory.xmemo.cli import _validate_api_key
    from plugins.memory.xmemo.client import XMemoClient

    client = XMemoClient(
        base_url="https://xmemo.dev",
        api_key="test-key",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(409, json={"setup_state": "setup_required"})
        ),
    )
    ok, msg = _validate_api_key("https://xmemo.dev", "test-key", client=client)
    assert ok is False
    assert "setup is required" in msg


def test_device_login_setup_required_fails_fast(monkeypatch):
    from plugins.memory.xmemo.cli import _run_device_login
    import time

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/start"):
            return httpx.Response(
                200,
                json={
                    "device_code": "dev-setup",
                    "user_code": "USER-CODE",
                    "verification_uri": "https://xmemo.dev/device-login",
                    "verification_uri_complete": "https://xmemo.dev/device-login?user_code=USER-CODE",
                    "expires_in": 600,
                    "interval": 1,
                },
            )
        return httpx.Response(
            400,
            json={
                "error": "setup_required",
                "error_description": "Complete XMemo onboarding before authorizing device login",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="onboarding"):
        _run_device_login("https://xmemo.dev", timeout_seconds=10.0, client=client)


def test_device_login_returns_token(monkeypatch):
    from plugins.memory.xmemo.cli import _run_device_login
    import time

    responses = {
        "start": httpx.Response(
            200,
            json={
                "device_code": "dev-123",
                "user_code": "USER-CODE",
                "verification_uri": "https://xmemo.dev/device-login",
                "verification_uri_complete": "https://xmemo.dev/device-login?user_code=USER-CODE",
                "expires_in": 600,
                "interval": 1,
            },
        ),
        "pending": httpx.Response(
            400,
            json={"error": "authorization_pending"},
        ),
        "token": httpx.Response(
            200,
            json={"access_token": "tok_abc:secret", "token_type": "Bearer"},
        ),
    }
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/start"):
            return responses["start"]
        call_count["n"] += 1
        if call_count["n"] == 1:
            return responses["pending"]
        return responses["token"]

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    token = _run_device_login("https://xmemo.dev", timeout_seconds=10.0, client=client)
    assert token == "tok_abc:secret"
