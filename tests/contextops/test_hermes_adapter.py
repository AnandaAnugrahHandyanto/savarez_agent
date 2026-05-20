from __future__ import annotations

import copy

import pytest

from plugins.context_engine.contextops.hermes_record_adapter import (
    TRANSCRIPT_REF_PREFIX,
    hermes_record_to_event,
    hermes_records_to_events,
)
from contextops.models import Event


def test_adapter_keeps_short_text_intact_and_does_not_mutate_input() -> None:
    record = {"id": "msg-7", "source": "Devhub/#contextops", "text": "short operator note", "refs": ["#contextops"], "channel": "#contextops"}
    original = copy.deepcopy(record)
    event = hermes_record_to_event(record)
    assert isinstance(event, Event)
    assert event.id == "msg-7"
    assert event.text == "short operator note"
    assert "#contextops" in event.refs
    assert event.metadata["channel"] == "#contextops"
    assert record == original


def test_adapter_uses_safe_ref_instead_of_injecting_giant_transcript() -> None:
    giant = "operator said many things in this turn. " * 300
    event = hermes_record_to_event({"id": "msg-501", "source": "Devhub/#contextops", "text": giant})
    transcript_ref = f"{TRANSCRIPT_REF_PREFIX}msg-501"
    assert transcript_ref in event.refs
    assert len(event.text) < len(giant)
    assert giant.strip() not in event.text
    assert event.metadata["transcript_truncated"] is True
    assert event.metadata["transcript_chars"] == len(giant)


def test_adapter_rejects_record_without_id() -> None:
    with pytest.raises(ValueError):
        hermes_record_to_event({"source": "x", "text": "y"})


def test_adapter_builds_safe_refs_from_session_event_like_record_without_raw_metadata() -> None:
    event = hermes_record_to_event({"message_id": "msg-abc/123", "platform": "discord", "channel": "#contextops", "session_id": "sess-42", "role": "user", "content": "operator reactivated the unresolved coupling anomaly", "metadata": {"transcript": "must not leak", "safe_label": "fixture"}})
    assert event.id == "msg-abc/123"
    assert event.source == "discord/#contextops"
    assert "message:msg-abc/123" in event.refs
    assert "session:sess-42" in event.refs
    assert "channel:#contextops" in event.refs
    assert event.metadata == {"role": "user", "channel": "#contextops", "safe_label": "fixture"}


def test_adapter_maps_many_records_preserving_order() -> None:
    rows = [{"id": f"m{i}", "source": "fixture", "text": f"message {i}"} for i in range(3)]
    assert [event.id for event in hermes_records_to_events(rows)] == ["m0", "m1", "m2"]


def test_adapter_drops_raw_transcript_like_caller_refs() -> None:
    leak = "operator said many sensitive things in this turn"
    event = hermes_record_to_event({"id": "msg-9", "source": "x", "text": "note", "refs": [leak]})
    assert leak not in event.refs
    assert all(not any(ch.isspace() for ch in ref) for ref in event.refs)


def test_adapter_drops_absolute_path_caller_refs() -> None:
    paths = ["/etc/passwd", "/home/op/.ssh/id_rsa", "C:\\Users\\op\\secrets.txt", "~/.aws/credentials"]
    event = hermes_record_to_event({"id": "msg-10", "source": "x", "text": "note", "refs": paths})
    for bad in paths:
        assert bad not in event.refs


def test_adapter_drops_token_and_secret_like_caller_refs() -> None:
    secrets = ["token=" + "a" * 40, "AKIA" + "Z" * 16, "deadbeef" * 8, "channel:bearer-" + "f" * 40]
    event = hermes_record_to_event({"id": "msg-11", "source": "x", "text": "note", "refs": secrets})
    for bad in secrets:
        assert bad not in event.refs


def test_adapter_drops_namespaced_secret_like_caller_refs() -> None:
    secrets = ["message:AKIA" + "Z" * 16, "session:eyJhbGciOiJIUzI1NiJ9.payload.signature"]
    event = hermes_record_to_event({"id": "msg-11b", "source": "x", "text": "note", "refs": secrets})
    for bad in secrets:
        assert bad not in event.refs


def test_adapter_drops_oversized_caller_refs() -> None:
    huge = "channel:" + "x" * 5000
    event = hermes_record_to_event({"id": "msg-12", "source": "x", "text": "note", "refs": [huge]})
    assert huge not in event.refs
    assert all(len(ref) <= 256 for ref in event.refs)


def test_adapter_preserves_derived_and_benign_safe_refs_only() -> None:
    record = {
        "id": "msg-13",
        "source": "x",
        "text": "note",
        "session_id": "sess-1",
        "channel": "#contextops",
        "refs": ["#contextops", "/etc/passwd", "raw transcript leak text"],
    }
    event = hermes_record_to_event(record)
    assert "message:msg-13" in event.refs
    assert "session:sess-1" in event.refs
    assert "channel:#contextops" in event.refs
    assert "#contextops" in event.refs
    assert "/etc/passwd" not in event.refs
    assert "raw transcript leak text" not in event.refs


def test_adapter_redacts_unsafe_metadata_safe_label() -> None:
    raw = "operator pasted /home/op/.env and token=" + "b" * 50 + " into the channel"
    event = hermes_record_to_event({"id": "msg-14", "source": "x", "text": "note", "metadata": {"safe_label": raw}})
    smuggled = str(event.metadata.get("safe_label", ""))
    assert smuggled != raw
    assert "token=" not in smuggled
    assert "/home/op/.env" not in smuggled


def test_adapter_redacts_oversized_metadata_value() -> None:
    event = hermes_record_to_event({"id": "msg-15", "source": "x", "text": "note", "metadata": {"safe_label": "leak " * 400}})
    assert len(str(event.metadata.get("safe_label", ""))) < 100


def test_adapter_redacts_short_raw_phrase_metadata_value() -> None:
    raw = "operator said sensitive things"
    event = hermes_record_to_event({"id": "msg-16", "source": "x", "text": "note", "metadata": {"safe_label": raw}})
    assert event.metadata.get("safe_label") != raw
    assert event.metadata.get("safe_label") == "[redacted]"


def test_adapter_redacts_embedded_path_metadata_value_without_token_hint() -> None:
    raw = "operator pasted /home/op/.env"
    event = hermes_record_to_event({"id": "msg-17", "source": "x", "text": "note", "metadata": {"safe_label": raw}})
    smuggled = str(event.metadata.get("safe_label", ""))
    assert smuggled != raw
    assert "/home/op/.env" not in smuggled


def test_adapter_preserves_benign_identifier_metadata_values() -> None:
    event = hermes_record_to_event({
        "id": "msg-18",
        "source": "x",
        "text": "note",
        "role": "user",
        "channel": "#contextops",
        "metadata": {"safe_label": "fixture", "message_type": "status-update"},
    })
    assert event.metadata["role"] == "user"
    assert event.metadata["channel"] == "#contextops"
    assert event.metadata["safe_label"] == "fixture"
    assert event.metadata["message_type"] == "status-update"


def test_adapter_redacts_secret_like_metadata_tokens() -> None:
    for raw in ("AKIA" + "Z" * 16, "eyJhbGciOiJIUzI1NiJ9.payload.signature"):
        event = hermes_record_to_event({"id": f"msg-{raw[:4]}", "source": "x", "text": "note", "metadata": {"safe_label": raw}})
        assert event.metadata["safe_label"] == "[redacted]"


def test_top_level_contextops_does_not_export_hermes_adapter_api() -> None:
    import contextops

    assert not hasattr(contextops, "hermes_record_to_event")
    assert not hasattr(contextops, "hermes_records_to_events")
