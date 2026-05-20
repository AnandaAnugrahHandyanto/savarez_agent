"""Adversarial negative tests for the fail-closed output safety gate.

Every unsafe shape — raw transcript / chat-turn markers, provider-payload JSON,
credential/secret-like keys, token-like values, raw message/session/id shapes,
absolute paths, and non-opaque refs — must be rejected (fail closed) rather
than silently redacted into accepted ContextPack output.
"""

import pytest

from contextops_ese import Observation, PreviewConfig, build_context_pack_preview
from contextops_ese.contracts import ContextPack
from contextops_ese.safety import (
    assert_pack_safe,
    assert_ref_safe,
    assert_text_safe,
    scan_unsafe,
)


def _pack_text(pack: ContextPack) -> str:
    return "\n".join((pack.id, *pack.restore, *pack.avoid, *pack.refs))


# --- scan_unsafe / assert_text_safe: direct adversarial cases -------------


@pytest.mark.parametrize(
    "unsafe",
    [
        "USER: here is my whole pasted message",
        "  assistant: sure, here is the transcript",
        '{"role": "user", "content": "secret payload"}',
        'thread carried "messages": [ ... ] verbatim',
        "operator shared api_key in chat",
        "the client_secret was discussed openly",
        "token = hunter2supersecret was set",
        "value sk-ABCDEFGHIJKLMNOPQRST0123 leaked",
        "aws key AKIAIOSFODNN7EXAMPLE pasted",
        "see message_id in the open thread",
        "look at msg-00042 above for context",
        "operator pasted /home/op/.env into chat",
        r"see C:\Users\op\secrets.txt for details",
    ],
)
def test_scan_unsafe_flags_every_leak_shape(unsafe):
    assert scan_unsafe(unsafe) is not None
    with pytest.raises(ValueError):
        assert_text_safe(unsafe, "signal")


def test_scan_unsafe_passes_already_safe_signal():
    assert scan_unsafe("rollout decision still open") is None
    assert assert_text_safe("rollout decision still open", "signal")


# --- assert_ref_safe: opaque-ref enforcement ------------------------------


def test_assert_ref_safe_accepts_opaque_token():
    assert assert_ref_safe("ref:abcdef012345") == "ref:abcdef012345"


def test_assert_ref_safe_rejects_raw_id_shapes():
    for bad in ("hermes-msg-00042", "session-abc-99", "message_id=42", "", "ref:NOTHEX"):
        with pytest.raises(ValueError):
            assert_ref_safe(bad)


# --- assert_pack_safe: whole-pack gate ------------------------------------


def test_assert_pack_safe_rejects_unsafe_restore_line():
    bad = ContextPack(
        id="pack-contextops-ese",
        restore=("USER: leaked transcript line",),
        avoid=("do not restore stale threads",),
        refs=("ref:abcdef012345",),
    )
    with pytest.raises(ValueError):
        assert_pack_safe(bad)


def test_assert_pack_safe_rejects_non_opaque_ref():
    bad = ContextPack(
        id="pack-contextops-ese",
        restore=("rollout decision still open",),
        avoid=("do not restore stale threads",),
        refs=("session-abc-99",),
    )
    with pytest.raises(ValueError):
        assert_pack_safe(bad)


# --- build_context_pack_preview: fails closed end-to-end ------------------


@pytest.mark.parametrize(
    "signal",
    [
        "USER: here is the full transcript line",
        '{"role": "user", "content": "secret payload"}',
        "operator shared api_key=hunter2 in chat",
        "value sk-ABCDEFGHIJKLMNOPQRST0123 leaked",
        "look at msg-00042 above for context",
    ],
)
def test_preview_fails_closed_on_unsafe_signal(signal):
    obs = Observation(raw_id="m1", signal=signal)
    with pytest.raises(ValueError):
        build_context_pack_preview([obs])


def test_preview_fails_closed_on_unsafe_avoid_signal():
    cfg = PreviewConfig(avoid_signals=("USER: do not avoid this transcript",))
    obs = Observation(raw_id="m1", signal="rollout decision still open")
    with pytest.raises(ValueError):
        build_context_pack_preview([obs], cfg)


@pytest.mark.parametrize(
    "raw_ref",
    [
        "/home/op/.env",
        '{"role": "user", "content": "x"}',
        "USER: pasted transcript fragment",
        "message_id=42",
        "operator api_key value",
    ],
)
def test_preview_fails_closed_on_unsafe_raw_ref(raw_ref):
    obs = Observation(
        raw_id="m1", signal="rollout decision still open", raw_refs=(raw_ref,)
    )
    with pytest.raises(ValueError):
        build_context_pack_preview([obs])


def test_preview_keeps_refs_opaque_and_drops_safe_raw_refs():
    obs = Observation(
        raw_id="hermes-msg-1",
        signal="rollout decision still open",
        raw_refs=("thread-rollout",),
    )
    pack = build_context_pack_preview([obs])
    # Raw input ids/refs never appear verbatim; only opaque tokens leave.
    assert "hermes-msg-1" not in _pack_text(pack)
    assert "thread-rollout" not in _pack_text(pack)
    assert pack.refs and all(ref.startswith("ref:") for ref in pack.refs)
