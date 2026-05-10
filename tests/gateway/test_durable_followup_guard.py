"""Regression tests for queued follow-up durable guards.

A 2026-05-09 gateway patch added a rare queued-follow-up wrapper that touched
``_DURABLE_AVAILABLE`` / ``_durable`` directly. When those sentinels were not
present at module scope, the branch raised ``NameError`` only for users who hit
queued follow-up recursion, which made the failure look intermittent.
"""

import gateway.run as gateway_run


def test_get_durable_runtime_treats_missing_sentinels_as_unavailable(monkeypatch):
    """Missing sentinels must degrade to "durable unavailable", not NameError."""

    monkeypatch.delattr(gateway_run, "_DURABLE_AVAILABLE", raising=False)
    monkeypatch.delattr(gateway_run, "_durable", raising=False)

    assert gateway_run._get_durable_runtime() is None


def test_get_durable_runtime_requires_enabled_flag(monkeypatch):
    durable_stub = object()

    monkeypatch.setattr(gateway_run, "_DURABLE_AVAILABLE", False, raising=False)
    monkeypatch.setattr(gateway_run, "_durable", durable_stub, raising=False)

    assert gateway_run._get_durable_runtime() is None


def test_get_durable_runtime_returns_module_when_enabled(monkeypatch):
    durable_stub = object()

    monkeypatch.setattr(gateway_run, "_DURABLE_AVAILABLE", True, raising=False)
    monkeypatch.setattr(gateway_run, "_durable", durable_stub, raising=False)

    assert gateway_run._get_durable_runtime() is durable_stub
