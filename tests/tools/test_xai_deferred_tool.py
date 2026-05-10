"""Unit tests for tools.xai_deferred_tool."""
from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest

from tools import xai_deferred_tool
from tools.xai_deferred_tool import (
    XaiDeferredError,
    XAI_DEFERRED_SCHEMA,
    check_xai_deferred_requirements,
    xai_deferred_chat,
)


# ---------------------------------------------------------------------------
# Helpers — minimal httpx mocking via monkeypatch
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


class _FakeHttp:
    """Capture submit + sequence of poll responses for one xai_deferred_chat call."""

    def __init__(self, submit: _FakeResponse, polls: List[_FakeResponse]):
        self.submit_resp = submit
        self.poll_responses = list(polls)
        self.submit_calls: List[Dict[str, Any]] = []
        self.poll_calls: List[Dict[str, Any]] = []

    def post(self, url: str, *, headers: Dict[str, str], json: Any, timeout: int):
        self.submit_calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.submit_resp

    def get(self, url: str, *, headers: Dict[str, str], timeout: int):
        self.poll_calls.append({"url": url, "headers": headers, "timeout": timeout})
        if not self.poll_responses:
            raise AssertionError("Test ran out of mocked poll responses")
        return self.poll_responses.pop(0)


@pytest.fixture
def fake_http(monkeypatch):
    """Install a stub for both httpx.post and httpx.get; tests mutate .next()."""
    holder: Dict[str, _FakeHttp] = {}

    def install(submit: _FakeResponse, polls: List[_FakeResponse]) -> _FakeHttp:
        fake = _FakeHttp(submit=submit, polls=polls)
        holder["fake"] = fake
        monkeypatch.setattr(xai_deferred_tool.httpx, "post", fake.post)
        monkeypatch.setattr(xai_deferred_tool.httpx, "get", fake.get)
        # No real sleeping in unit tests
        monkeypatch.setattr(xai_deferred_tool.time, "sleep", lambda _s: None)
        return fake

    return install


@pytest.fixture(autouse=True)
def _no_disk_config(monkeypatch):
    """Don't let load_config touch a real ~/.hermes/config.yaml during tests."""
    monkeypatch.setattr(xai_deferred_tool, "_config_section", lambda: {})


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "sk-test-deferred")


# ---------------------------------------------------------------------------
# check_xai_deferred_requirements / schema
# ---------------------------------------------------------------------------

class TestRequirements:
    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        assert check_xai_deferred_requirements() is False

    def test_unavailable_with_blank_key(self, monkeypatch):
        monkeypatch.setenv("XAI_API_KEY", "   ")
        assert check_xai_deferred_requirements() is False

    def test_available_with_key(self, monkeypatch):
        monkeypatch.setenv("XAI_API_KEY", "sk-x")
        assert check_xai_deferred_requirements() is True


class TestSchema:
    def test_schema_has_required_prompt(self):
        assert XAI_DEFERRED_SCHEMA["parameters"]["required"] == ["prompt"]

    def test_schema_advertises_optional_params(self):
        props = XAI_DEFERRED_SCHEMA["parameters"]["properties"]
        for key in ("prompt", "model", "system", "max_wait_seconds", "poll_interval_seconds"):
            assert key in props


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

class TestArgValidation:
    def test_empty_prompt_raises(self, api_key):
        with pytest.raises(ValueError):
            xai_deferred_chat("")

    def test_whitespace_prompt_raises(self, api_key):
        with pytest.raises(ValueError):
            xai_deferred_chat("   ")

    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        with pytest.raises(XaiDeferredError):
            xai_deferred_chat("hello")

    def test_negative_max_wait_raises(self, api_key):
        with pytest.raises(ValueError):
            xai_deferred_chat("hi", max_wait_seconds=-1)

    def test_negative_poll_interval_raises(self, api_key):
        with pytest.raises(ValueError):
            xai_deferred_chat("hi", poll_interval_seconds=-0.5)


# ---------------------------------------------------------------------------
# Submit semantics
# ---------------------------------------------------------------------------

class TestSubmit:
    def test_submit_sets_deferred_true_in_body(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "req-123"}),
            polls=[_FakeResponse(200, {"id": "cmpl-1", "choices": []})],
        )
        xai_deferred_chat("hi")
        assert fake.submit_calls[0]["json"]["deferred"] is True

    def test_submit_uses_default_model(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(200, {"id": "x", "choices": []})],
        )
        xai_deferred_chat("hi")
        assert fake.submit_calls[0]["json"]["model"] == "grok-4.3"

    def test_submit_passes_explicit_model(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(200, {"id": "x", "choices": []})],
        )
        xai_deferred_chat("hi", model="grok-4.20-multi-agent-0309")
        assert fake.submit_calls[0]["json"]["model"] == "grok-4.20-multi-agent-0309"

    def test_submit_includes_system_message(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(200, {"id": "x", "choices": []})],
        )
        xai_deferred_chat("user", system="be concise")
        msgs = fake.submit_calls[0]["json"]["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "be concise"
        assert msgs[-1]["content"] == "user"

    def test_submit_extra_body_cannot_override_deferred(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(200, {"id": "x", "choices": []})],
        )
        xai_deferred_chat("hi", extra_body={"deferred": False, "temperature": 0.2})
        assert fake.submit_calls[0]["json"]["deferred"] is True
        assert fake.submit_calls[0]["json"]["temperature"] == 0.2

    def test_submit_4xx_raises(self, api_key, fake_http):
        fake_http(
            submit=_FakeResponse(401, payload={"error": "bad key"}, text='{"error":"bad key"}'),
            polls=[],
        )
        with pytest.raises(XaiDeferredError) as exc:
            xai_deferred_chat("hi")
        assert "401" in str(exc.value)

    def test_submit_response_missing_request_id_raises(self, api_key, fake_http):
        fake_http(
            submit=_FakeResponse(200, {"unrelated": "field"}),
            polls=[],
        )
        with pytest.raises(XaiDeferredError) as exc:
            xai_deferred_chat("hi")
        assert "request_id" in str(exc.value)

    def test_submit_network_error_raises(self, api_key, monkeypatch):
        def _boom(*_a, **_kw):
            raise httpx.ConnectError("nope")
        monkeypatch.setattr(xai_deferred_tool.httpx, "post", _boom)
        with pytest.raises(XaiDeferredError) as exc:
            xai_deferred_chat("hi")
        assert "submit failed" in str(exc.value)


# ---------------------------------------------------------------------------
# Poll semantics
# ---------------------------------------------------------------------------

class TestPoll:
    def test_completes_on_first_200(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "abc"}),
            polls=[_FakeResponse(200, {"id": "cmpl", "choices": [{"message": {"role": "assistant", "content": "ok"}}]})],
        )
        result = xai_deferred_chat("hi")
        assert result["request_id"] == "abc"
        assert result["completion"]["choices"][0]["message"]["content"] == "ok"
        assert len(fake.poll_calls) == 1
        assert "deferred-completion/abc" in fake.poll_calls[0]["url"]

    def test_polls_until_ready(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[
                _FakeResponse(202),
                _FakeResponse(202),
                _FakeResponse(200, {"id": "cmpl", "choices": []}),
            ],
        )
        result = xai_deferred_chat("hi", poll_interval_seconds=0.01)
        assert len(fake.poll_calls) == 3
        assert result["completion"]["id"] == "cmpl"

    def test_poll_5xx_raises(self, api_key, fake_http):
        fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(500, text="upstream down")],
        )
        with pytest.raises(XaiDeferredError) as exc:
            xai_deferred_chat("hi", poll_interval_seconds=0.01)
        assert "500" in str(exc.value)

    def test_poll_timeout_raises(self, api_key, monkeypatch, fake_http):
        # Fake monotonic that jumps past max_wait on the second call.
        ticks = iter([0.0, 0.0, 9999.0])
        monkeypatch.setattr(xai_deferred_tool.time, "monotonic", lambda: next(ticks))
        fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(202)],
        )
        with pytest.raises(XaiDeferredError) as exc:
            xai_deferred_chat("hi", max_wait_seconds=10, poll_interval_seconds=0.01)
        assert "not ready after" in str(exc.value)


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

class TestHeaders:
    def test_authorization_bearer(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(200, {"id": "x", "choices": []})],
        )
        xai_deferred_chat("hi")
        assert fake.submit_calls[0]["headers"]["Authorization"] == "Bearer sk-test-deferred"
        assert fake.poll_calls[0]["headers"]["Authorization"] == "Bearer sk-test-deferred"

    def test_user_agent_present(self, api_key, fake_http):
        fake = fake_http(
            submit=_FakeResponse(200, {"request_id": "r"}),
            polls=[_FakeResponse(200, {"id": "x", "choices": []})],
        )
        xai_deferred_chat("hi")
        ua = fake.submit_calls[0]["headers"]["User-Agent"]
        assert ua.startswith("Hermes-Agent/")
