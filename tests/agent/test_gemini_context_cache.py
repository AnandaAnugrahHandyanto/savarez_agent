"""Unit tests for Gemini server-side context caching (PR-2 of #29818).

`_ensure_gemini_cache()` creates or reuses a ``cachedContents`` resource for a
session's system instruction + tools. It must:
  - skip cleanly when there is no session / no system prompt,
  - reuse a still-fresh resource without an HTTP call,
  - refresh when the cached resource is near expiry,
  - never raise — an uncached request is the safe fallback on any error.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agent import conversation_loop
from agent.prompt_cache_strategy import GeminiResourceCacheStrategy


class _FakeDB:
    def __init__(self, meta=None):
        self._meta = dict(meta or {})
        self.set_calls = []

    def get_meta(self, key):
        return self._meta.get(key)

    def set_meta(self, key, value):
        self._meta[key] = value
        self.set_calls.append((key, value))


class _FakeResp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeHTTPClient:
    """Context-manager stand-in for httpx.Client that records POSTs."""

    def __init__(self, resp, calls):
        self._resp = resp
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, params=None, json=None, headers=None):
        self._calls.append({"url": url, "params": params, "json": json})
        return self._resp


def _agent(**overrides):
    base = dict(
        session_id="sess-1",
        _session_db=_FakeDB(),
        model="gemini-3.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key="AIza-test",
        tools=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_httpx(monkeypatch, resp):
    calls = []
    monkeypatch.setattr("httpx.Client", lambda *a, **k: _FakeHTTPClient(resp, calls))
    return calls


_SYS = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "hi"}]


def test_no_session_id_returns_none(monkeypatch):
    calls = _patch_httpx(monkeypatch, _FakeResp(payload={"name": "cachedContents/x"}))
    assert conversation_loop._ensure_gemini_cache(_agent(session_id=None), _SYS) is None
    assert calls == []  # never hits the network


def test_no_system_message_returns_none(monkeypatch):
    calls = _patch_httpx(monkeypatch, _FakeResp(payload={"name": "cachedContents/x"}))
    msgs = [{"role": "user", "content": "hi"}]
    assert conversation_loop._ensure_gemini_cache(_agent(), msgs) is None
    assert calls == []


def test_creates_and_stores_cache(monkeypatch):
    resp = _FakeResp(payload={"name": "cachedContents/abc123", "expireTime": "2099-01-01T00:00:00Z"})
    calls = _patch_httpx(monkeypatch, resp)
    agent = _agent()

    name = conversation_loop._ensure_gemini_cache(agent, _SYS)

    assert name == "cachedContents/abc123"
    # One POST to the cachedContents endpoint with the right shape.
    assert len(calls) == 1
    assert calls[0]["url"].endswith("/cachedContents")
    payload = calls[0]["json"]
    assert payload["model"] == "models/gemini-3.5-flash"  # prefixed
    assert payload["systemInstruction"]["parts"] == [{"text": "You are helpful."}]
    assert payload["ttl"] == "3600s"
    # Resource name persisted for cross-turn reuse.
    assert agent._session_db.set_calls
    key, stored = agent._session_db.set_calls[-1]
    assert key == "gemini_cache_sess-1"
    assert json.loads(stored)["name"] == "cachedContents/abc123"


def test_reuses_fresh_cache_without_http(monkeypatch):
    db = _FakeDB({"gemini_cache_sess-1": json.dumps({"name": "cachedContents/old", "expires_at": 9_999_999_999})})
    calls = _patch_httpx(monkeypatch, _FakeResp(status_code=500))  # would fail if used
    name = conversation_loop._ensure_gemini_cache(_agent(_session_db=db), _SYS)
    assert name == "cachedContents/old"
    assert calls == []  # fresh cache → no network call


def test_stale_cache_triggers_refresh(monkeypatch):
    db = _FakeDB({"gemini_cache_sess-1": json.dumps({"name": "cachedContents/old", "expires_at": 1})})
    resp = _FakeResp(payload={"name": "cachedContents/new"})
    calls = _patch_httpx(monkeypatch, resp)
    name = conversation_loop._ensure_gemini_cache(_agent(_session_db=db), _SYS)
    assert name == "cachedContents/new"
    assert len(calls) == 1  # near-expiry cache → re-created


def test_http_error_returns_none(monkeypatch):
    resp = _FakeResp(status_code=429, text="RESOURCE_EXHAUSTED")
    _patch_httpx(monkeypatch, resp)
    # Free-tier / quota errors must degrade to an uncached request, not raise.
    assert conversation_loop._ensure_gemini_cache(_agent(), _SYS) is None


def test_missing_name_in_response_returns_none(monkeypatch):
    _patch_httpx(monkeypatch, _FakeResp(payload={}))  # 200 but no name
    assert conversation_loop._ensure_gemini_cache(_agent(), _SYS) is None


def test_network_exception_is_swallowed(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("httpx.Client", _boom)
    assert conversation_loop._ensure_gemini_cache(_agent(), _SYS) is None


def test_strategy_apply_is_identity():
    """The marker strategy must not mutate messages — the work happens out of band."""
    strategy = GeminiResourceCacheStrategy()
    msgs = [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]
    from agent.prompt_cache_strategy import PromptCacheIntent

    out = strategy.apply(msgs, PromptCacheIntent(ttl="5m"))
    assert out == msgs
