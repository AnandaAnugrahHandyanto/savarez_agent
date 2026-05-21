"""Regression tests for #29760 — Feishu doc/drive tools must reach the gateway-
built lark client in DM / group-chat agent threads, where the comment-handler
thread-local was never populated."""

from __future__ import annotations

import threading
from unittest import mock

import pytest

from tools import feishu_doc_tool, feishu_drive_tool


@pytest.fixture(autouse=True)
def _reset_clients():
    """Reset both per-thread and process-wide client state on every test."""
    for mod in (feishu_doc_tool, feishu_drive_tool):
        if hasattr(mod._local, "client"):
            del mod._local.client
        mod._default_client = None
    yield
    for mod in (feishu_doc_tool, feishu_drive_tool):
        if hasattr(mod._local, "client"):
            del mod._local.client
        mod._default_client = None


@pytest.mark.parametrize("mod", [feishu_doc_tool, feishu_drive_tool])
def test_get_client_returns_none_without_any_injection(mod):
    assert mod.get_client() is None


@pytest.mark.parametrize("mod", [feishu_doc_tool, feishu_drive_tool])
def test_default_client_visible_when_thread_local_unset(mod):
    """The gateway-wide default must be returned when no thread-local exists.

    This is the #29760 path: the gateway adapter registers the lark client
    once at connect time; an AIAgent later spawned in a worker thread for a
    DM / group chat must inherit it without further plumbing."""
    sentinel = object()
    mod.set_default_client(sentinel)
    assert mod.get_client() is sentinel


@pytest.mark.parametrize("mod", [feishu_doc_tool, feishu_drive_tool])
def test_thread_local_wins_over_default(mod):
    """The comment-handler thread-local (set_client) must take precedence."""
    default = object()
    scoped = object()
    mod.set_default_client(default)
    mod.set_client(scoped)
    assert mod.get_client() is scoped


@pytest.mark.parametrize("mod", [feishu_doc_tool, feishu_drive_tool])
def test_default_client_is_visible_across_threads(mod):
    """A worker thread that never called set_client must still see the default.

    This is the literal failure mode in #29760: the gateway adapter creates
    the lark client on the asyncio thread, but AIAgent runs Feishu tool
    invocations in a different worker thread where set_client was never
    called."""
    sentinel = object()
    mod.set_default_client(sentinel)

    seen: list = []

    def _worker():
        seen.append(mod.get_client())

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    assert seen == [sentinel]


@pytest.mark.parametrize("mod", [feishu_doc_tool, feishu_drive_tool])
def test_thread_local_does_not_leak_to_default(mod):
    """set_client on one thread must not become the process-wide default."""
    scoped = object()
    mod.set_client(scoped)

    seen: list = []

    def _worker():
        seen.append(mod.get_client())

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    assert seen == [None]


def test_gateway_build_lark_client_registers_default(monkeypatch):
    """FeishuAdapter._build_lark_client must register the new client as the
    process-wide default for both tool modules. This is the actual wiring
    point that resolves #29760 — without it, the DM path's worker thread
    returns ``None`` from get_client() even though the gateway has a live
    client."""
    from gateway.platforms import feishu as feishu_mod

    sentinel = object()

    class _FakeBuilder:
        def app_id(self, *_):
            return self
        def app_secret(self, *_):
            return self
        def domain(self, *_):
            return self
        def log_level(self, *_):
            return self
        def build(self):
            return sentinel

    class _FakeClient:
        @staticmethod
        def builder():
            return _FakeBuilder()

    class _FakeLark:
        class LogLevel:
            WARNING = 0
        Client = _FakeClient

    monkeypatch.setattr(feishu_mod, "lark", _FakeLark, raising=False)

    # Call _build_lark_client through an instance bound only enough to
    # satisfy the method — we sidestep the full FeishuAdapter __init__ to
    # keep this test scoped to the wiring behavior, not the adapter's
    # config loading.
    adapter = feishu_mod.FeishuAdapter.__new__(feishu_mod.FeishuAdapter)
    adapter._app_id = "test-app-id"
    adapter._app_secret = "test-app-secret"
    built = feishu_mod.FeishuAdapter._build_lark_client(adapter, domain=mock.Mock())

    assert built is sentinel
    assert feishu_doc_tool._default_client is sentinel
    assert feishu_drive_tool._default_client is sentinel
