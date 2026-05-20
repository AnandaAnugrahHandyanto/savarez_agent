"""Mandatory leak safety gate.

A ContextPack is a restore/avoid contract — never a transcript, a provider
payload, a secret store, or an id dump. The preview builder must fail closed
(raise ``ValueError``) on any signal or ref that smells like one of those,
and every string field of the returned pack must pass the same gate.
"""

import pytest

from contextops_ese import Observation, build_context_pack_preview
from contextops_ese.safety import assert_pack_safe, scan_unsafe


def _build(signal: str, **kw):
    return build_context_pack_preview([Observation(raw_id="m1", signal=signal, **kw)])


# --- raw transcript / chat-turn markers -----------------------------------


def test_rejects_raw_transcript_turn_marker_in_signal():
    with pytest.raises(ValueError, match="transcript"):
        _build("USER: please restore my entire chat history right now")


def test_rejects_chat_turn_control_marker_in_signal():
    with pytest.raises(ValueError):
        _build("note about rollout <|im_start|>assistant smuggled turn")


# --- provider payload JSON shapes -----------------------------------------


def test_rejects_provider_request_payload_json_in_signal():
    with pytest.raises(ValueError, match="provider"):
        _build('payload {"messages": [{"role": "user"}], "model": "claude"}')


def test_rejects_provider_response_payload_json_in_signal():
    with pytest.raises(ValueError):
        _build('dump {"choices": [{"finish_reason": "stop"}], "usage": {}}')


# --- credential / secret-like material ------------------------------------


def test_rejects_secret_like_key_in_signal():
    with pytest.raises(ValueError):
        _build("operator pasted the api_key for the rollout service")


def test_rejects_token_assignment_in_signal():
    with pytest.raises(ValueError):
        _build("creds were token=" + "a" * 40 + " for the run")


def test_rejects_token_looking_value_in_signal():
    with pytest.raises(ValueError):
        _build("rollout key AKIA" + "Z" * 16 + " leaked into chat")


# --- raw message/session/id field names and id-shaped values --------------


def test_rejects_raw_id_field_name_in_signal():
    with pytest.raises(ValueError):
        _build("we should key restoration on the session_id field")


def test_rejects_raw_id_shaped_value_in_signal():
    with pytest.raises(ValueError):
        _build("restore the work around msg-00042 and sess-9f3c threads")


# --- disallowed refs / raw_refs -------------------------------------------


def test_rejects_path_like_raw_ref_on_observation():
    with pytest.raises(ValueError):
        _build("clean rollout decision is still open", raw_refs=("/home/op/.env",))


def test_rejects_provider_json_raw_ref_on_observation():
    with pytest.raises(ValueError):
        _build(
            "clean rollout decision is still open",
            raw_refs=('{"choices": [{"finish_reason": "stop"}]}',),
        )


def test_rejects_secret_like_raw_ref_on_observation():
    with pytest.raises(ValueError):
        _build("clean rollout decision is still open", raw_refs=("token=" + "z" * 40,))


# --- the final-pack gate is enforced over all string fields ---------------


def test_assert_pack_safe_rejects_pack_with_unsafe_restore():
    from contextops_ese.contracts import ContextPack

    poisoned = ContextPack(
        id="pack-contextops-ese",
        restore=("USER: leaked transcript turn",),
        avoid=("stay calm",),
        refs=("ref:abc123abc123",),
    )
    with pytest.raises(ValueError):
        assert_pack_safe(poisoned)


def test_assert_pack_safe_rejects_non_opaque_ref():
    from contextops_ese.contracts import ContextPack

    poisoned = ContextPack(
        id="pack-contextops-ese",
        restore=("clean restore line",),
        avoid=("stay calm",),
        refs=("msg-00042",),
    )
    with pytest.raises(ValueError):
        assert_pack_safe(poisoned)


# --- safe signals still build ---------------------------------------------


def test_scan_unsafe_passes_a_clean_signal():
    assert scan_unsafe("rollout decision still open; coupling tension unresolved") is None


def test_clean_signal_still_builds_a_pack():
    pack = _build("rollout decision still open; coupling tension unresolved")
    assert pack.restore
    assert all(ref.startswith("ref:") for ref in pack.refs)
