"""Regression: local OpenAI-compatible streams must not inherit the 180s remote stale default."""

import os

import pytest

from agent.local_provider import compute_stream_stale_timeout


@pytest.mark.parametrize(
    "base_url",
    [
        "http://127.0.0.1:11434/v1",
        "http://192.168.0.5:8000/v1",
    ],
)
def test_local_stream_stale_wall_not_180_by_default(base_url, monkeypatch):
    monkeypatch.delenv("HERMES_LOCAL_STREAM_STALE_TIMEOUT", raising=False)
    monkeypatch.delenv("HERMES_FORCE_LOCAL_PROVIDER", raising=False)
    wall = compute_stream_stale_timeout(
        base_url=base_url,
        model_cfg=None,
        stream_stale_timeout_base=float(os.getenv("HERMES_STREAM_STALE_TIMEOUT", "180.0")),
        messages=[{"role": "user", "content": "warmup"}],
    )
    assert wall >= 3600.0


def test_local_stream_stale_respects_short_override(monkeypatch):
    monkeypatch.setenv("HERMES_LOCAL_STREAM_STALE_TIMEOUT", "900")
    wall = compute_stream_stale_timeout(
        base_url="http://localhost:11434/v1",
        model_cfg=None,
        stream_stale_timeout_base=180.0,
        messages=[{"role": "user", "content": "x"}],
    )
    assert wall == 900.0
