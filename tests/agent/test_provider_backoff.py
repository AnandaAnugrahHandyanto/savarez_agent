from pathlib import Path

import pytest

from agent import provider_backoff as pb


def test_provider_backoff_trips_after_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "provider_backoff_dir", lambda: tmp_path)

    assert pb.record_provider_stall(
        "openai-codex", "gpt-5.5", now=1000, threshold=3, window_seconds=600, backoff_seconds=300
    ) == 0
    assert pb.record_provider_stall(
        "openai-codex", "gpt-5.5", now=1010, threshold=3, window_seconds=600, backoff_seconds=300
    ) == 0
    remaining = pb.record_provider_stall(
        "openai-codex", "gpt-5.5", now=1020, threshold=3, window_seconds=600, backoff_seconds=300
    )

    assert remaining == 300
    assert pb.provider_backoff_remaining("openai-codex", "gpt-5.5", now=1030) == 290
    assert pb.provider_backoff_remaining("openai-codex", "gpt-5.5", now=1321) == 0


def test_provider_backoff_is_model_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "provider_backoff_dir", lambda: tmp_path)

    pb.record_provider_stall("openai-codex", "gpt-5.5", now=1, threshold=1, backoff_seconds=60)

    assert pb.provider_backoff_remaining("openai-codex", "gpt-5.5", now=2) == 59
    assert pb.provider_backoff_remaining("openai-codex", "gpt-4.1", now=2) == 0
