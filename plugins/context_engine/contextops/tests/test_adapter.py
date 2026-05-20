"""The thin Hermes ContextOps adapter must fail closed in every degraded
state and must never inject by default."""

from pathlib import Path

import pytest

from plugins.context_engine.contextops.adapter import ContextOpsAdapter, default_config


def _obs() -> list[dict]:
    return [
        {"raw_id": "hermes-msg-1", "signal": "rollout decision still open", "raw_text": "USER: ship it?"},
    ]


def test_default_config_is_fail_safe():
    cfg = default_config()
    assert cfg["enabled"] is False
    assert cfg["preview"] is True
    assert cfg["inject"] is False
    assert cfg["include_raw_transcript"] is False
    assert cfg["include_raw_ids"] is False
    assert cfg["include_paths"] is False


def test_adapter_inactive_by_default():
    adapter = ContextOpsAdapter()
    assert adapter.active is False
    assert adapter.build_preview(_obs()) is None


def test_adapter_never_injects_even_when_enabled():
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.should_inject is False


def test_adapter_fails_closed_when_core_missing(monkeypatch):
    import plugins.context_engine.contextops.adapter as mod

    monkeypatch.setattr(mod, "_import_core", lambda: None)
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.active is False
    assert adapter.build_preview(_obs()) is None


def test_adapter_builds_preview_when_enabled_and_core_present():
    adapter = ContextOpsAdapter({"enabled": True})
    pack = adapter.build_preview(_obs())
    assert pack is not None
    assert pack["preview"] is True
    assert pack["injected"] is False
    flat = "\n".join([pack["id"], *pack["restore"], *pack["avoid"], *pack["refs"]])
    assert "hermes-msg-1" not in flat
    assert "USER: ship it?" not in flat
    assert all(ref.startswith("ref:") for ref in pack["refs"])


def test_adapter_fails_closed_on_invalid_schema():
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview("not-a-list") is None
    assert adapter.build_preview([{"no_signal": "x"}]) is None
    assert adapter.build_preview([42]) is None


@pytest.mark.parametrize(
    "unsafe_signal",
    [
        "USER: please restore this raw chat turn",
        '{"messages": [{"role": "user", "content": "raw"}], "model": "claude"}',
        "operator pasted api_key for the rollout service",
        "token=" + "a" * 40,
        "restore message_id msg-00042 from session_id sess-9f3c",
        "operator pasted /home/op/.env",
    ],
)
def test_adapter_fails_closed_on_unsafe_signal(unsafe_signal):
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview([{"raw_id": "m1", "signal": unsafe_signal}]) is None


@pytest.mark.parametrize(
    "raw_refs",
    [
        ["/home/op/.env"],
        ['{"choices": [{"finish_reason": "stop"}]}'],
        ["token=" + "z" * 40],
        ["message_id"],
        ["msg-00042"],
    ],
)
def test_adapter_fails_closed_on_unsafe_raw_refs(raw_refs):
    adapter = ContextOpsAdapter({"enabled": True})
    obs = [{"raw_id": "m1", "signal": "rollout decision still open", "raw_refs": raw_refs}]
    assert adapter.build_preview(obs) is None


def test_adapter_fails_closed_on_core_regression_unsafe_pack(monkeypatch):
    import contextops_ese

    class PoisonedPack:
        id = "pack-contextops-ese"
        restore = ("USER: leaked raw transcript",)
        avoid = ("stay calm",)
        refs = ("ref:abc123abc123",)

    monkeypatch.setattr(contextops_ese, "build_context_pack_preview", lambda *_args, **_kw: PoisonedPack())
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview(_obs()) is None


def test_adapter_fails_closed_on_storage_error(monkeypatch):
    adapter = ContextOpsAdapter({"enabled": True, "storage_root": "/dev/null/nope"})
    # A broken storage root must not raise and must not produce a preview.
    assert adapter.build_preview(_obs()) is None


def test_adapter_does_not_import_gateway_or_prompt_builder():
    src = (Path(__file__).resolve().parents[1] / "adapter.py").read_text()
    assert "gateway.run" not in src
    assert "gateway/run.py" not in src
    assert "prompt_builder" not in src
