"""Defence-in-depth: the adapter must independently re-validate core output.

Even if the ``contextops_ese`` package leak gate regresses, an unsafe pack
(raw transcript, provider payload, secret, raw id, non-opaque ref) must never
reach Hermes — the adapter re-checks the serialized dict and fails closed.
"""

import pytest

from plugins.context_engine.contextops.adapter import ContextOpsAdapter


def _obs() -> list[dict]:
    return [{"raw_id": "hermes-msg-1", "signal": "rollout decision still open"}]


@pytest.mark.parametrize(
    "signal",
    [
        "USER: here is the full transcript line",
        '{"role": "user", "content": "secret payload"}',
        "operator shared api_key=hunter2 in chat",
        "value sk-ABCDEFGHIJKLMNOPQRST0123 leaked",
        "look at msg-00042 above for context",
        "operator pasted /home/op/.env into chat",
    ],
)
def test_adapter_fails_closed_on_unsafe_signal(signal):
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview([{"raw_id": "m1", "signal": signal}]) is None


def _patch_core_build(monkeypatch, pack):
    """Force the core builder to emit ``pack``, simulating a regressed gate."""

    import contextops_ese

    monkeypatch.setattr(
        contextops_ese, "build_context_pack_preview", lambda *a, **k: pack
    )


class _Pack:
    def __init__(self, restore, avoid, refs, id="pack-contextops-ese"):
        self.id = id
        self.restore = tuple(restore)
        self.avoid = tuple(avoid)
        self.refs = tuple(refs)


def test_adapter_rejects_unsafe_restore_even_if_core_regresses(monkeypatch):
    _patch_core_build(
        monkeypatch,
        _Pack(
            restore=("USER: leaked raw transcript line",),
            avoid=("do not restore stale threads",),
            refs=("ref:abcdef012345",),
        ),
    )
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview(_obs()) is None


def test_adapter_rejects_secret_in_avoid_even_if_core_regresses(monkeypatch):
    _patch_core_build(
        monkeypatch,
        _Pack(
            restore=("rollout decision still open",),
            avoid=("never echo the api_key value",),
            refs=("ref:abcdef012345",),
        ),
    )
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview(_obs()) is None


def test_adapter_rejects_non_opaque_ref_even_if_core_regresses(monkeypatch):
    _patch_core_build(
        monkeypatch,
        _Pack(
            restore=("rollout decision still open",),
            avoid=("do not restore stale threads",),
            refs=("session-abc-99",),
        ),
    )
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview(_obs()) is None


def test_adapter_rejects_unsafe_output_even_if_core_validator_regresses(monkeypatch):
    """Hard case: BOTH the builder and every core leak validator regress.

    The adapter's own gate must not depend on ``contextops_ese`` — unsafe
    output must still fail closed at the Hermes boundary.
    """

    import contextops_ese

    _patch_core_build(
        monkeypatch,
        _Pack(
            restore=("USER: leaked raw transcript line",),
            avoid=("do not restore stale threads",),
            refs=("ref:abcdef012345",),
        ),
    )
    # Simulate a fully regressed package leak gate (every validator neutered).
    monkeypatch.setattr(contextops_ese, "assert_pack_safe", lambda p: p, raising=False)
    monkeypatch.setattr(contextops_ese, "scan_unsafe", lambda t: None, raising=False)
    monkeypatch.setattr(
        contextops_ese, "assert_ref_safe", lambda r, *a, **k: r, raising=False
    )
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview(_obs()) is None


def test_adapter_rejects_non_opaque_ref_even_if_core_validator_regresses(monkeypatch):
    import contextops_ese

    _patch_core_build(
        monkeypatch,
        _Pack(
            restore=("rollout decision still open",),
            avoid=("do not restore stale threads",),
            refs=("session-abc-99",),
        ),
    )
    monkeypatch.setattr(contextops_ese, "assert_pack_safe", lambda p: p, raising=False)
    monkeypatch.setattr(contextops_ese, "scan_unsafe", lambda t: None, raising=False)
    monkeypatch.setattr(
        contextops_ese, "assert_ref_safe", lambda r, *a, **k: r, raising=False
    )
    adapter = ContextOpsAdapter({"enabled": True})
    assert adapter.build_preview(_obs()) is None


def test_adapter_still_builds_a_genuinely_safe_pack():
    adapter = ContextOpsAdapter({"enabled": True})
    pack = adapter.build_preview(_obs())
    assert pack is not None
    assert all(ref.startswith("ref:") for ref in pack["refs"])
