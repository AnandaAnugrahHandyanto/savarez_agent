"""The preview builder must emit a safe ContextPack: no raw transcripts,
no absolute paths, no raw ids, and injection disabled by default."""

import pytest

from contextops_ese import (
    ContextPack,
    Observation,
    PreviewConfig,
    build_context_pack_preview,
)


def _pack_text(pack: ContextPack) -> str:
    return "\n".join((pack.id, *pack.restore, *pack.avoid, *pack.refs))


def test_injection_disabled_by_default():
    cfg = PreviewConfig()
    assert cfg.enabled is False
    assert cfg.preview is True
    assert cfg.inject is False


def test_pack_never_contains_raw_transcript():
    transcript = "USER: here is my entire secret diary, line one, line two, line three"
    obs = Observation(
        raw_id="msg-1",
        signal="user shared a diary; thread is about privacy boundaries",
        raw_text=transcript,
    )
    pack = build_context_pack_preview([obs])
    assert transcript not in _pack_text(pack)
    assert "secret diary" not in _pack_text(pack)


def test_pack_never_contains_raw_ids():
    obs = Observation(raw_id="hermes-msg-00042", signal="decision pending on rollout")
    pack = build_context_pack_preview([obs])
    assert "hermes-msg-00042" not in _pack_text(pack)
    assert safe_ref_present(pack)


def safe_ref_present(pack: ContextPack) -> bool:
    return all(ref.startswith("ref:") for ref in pack.refs) and len(pack.refs) > 0


def test_pack_rejects_absolute_posix_path_in_signal():
    obs = Observation(raw_id="msg-2", signal="operator pasted /home/op/.env into chat")
    with pytest.raises(ValueError, match="path"):
        build_context_pack_preview([obs])


def test_pack_rejects_absolute_windows_path_in_signal():
    # Filename deliberately free of secret-words so this isolates path detection.
    obs = Observation(raw_id="msg-3", signal=r"see C:\Users\op\report.txt for details")
    with pytest.raises(ValueError, match="path"):
        build_context_pack_preview([obs])


def test_pack_is_bounded_by_max_chars():
    cfg = PreviewConfig(max_context_pack_chars=120)
    obs = [
        Observation(raw_id=f"msg-{i}", signal=f"thread signal number {i} carries open tension")
        for i in range(50)
    ]
    pack = build_context_pack_preview(obs, cfg)
    assert len(_pack_text(pack)) <= cfg.max_context_pack_chars


def test_pack_requires_at_least_one_observation():
    with pytest.raises(ValueError):
        build_context_pack_preview([])
