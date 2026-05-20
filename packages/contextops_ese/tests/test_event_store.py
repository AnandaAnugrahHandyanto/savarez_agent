"""JSONL event store: contract, golden fixture, and leak gate.

These tests cover the ContextOps M1-A bounded slice: a minimal append-only
JSONL store that carries lane/kind/sanitized_payload/provenance rows under a
single schema version, and rejects unsafe content fail-closed at write time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contextops_ese import (
    SCHEMA_VERSION,
    ContextOpsEvent,
    JsonlEventStore,
    build_event,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "event_store_golden.jsonl"


# --- contract shape -------------------------------------------------------


def test_event_carries_lane_kind_payload_provenance_under_one_schema():
    event = build_event(
        lane="observation",
        kind="task_handoff_ack",
        sanitized_payload={"delegated": True},
        provenance={"source": "adapter.test"},
    )
    assert isinstance(event, ContextOpsEvent)
    row = event.to_dict()
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["lane"] == "observation"
    assert row["kind"] == "task_handoff_ack"
    assert row["sanitized_payload"] == {"delegated": True}
    assert row["provenance"] == {"source": "adapter.test"}


def test_event_to_dict_canonicalises_nested_mapping_keys():
    event = build_event(
        lane="context_pack",
        kind="preview_built",
        sanitized_payload={"restore_count": 2, "avoid_count": 1},
        provenance={"version": "0.0.1", "source": "adapter.test"},
    )
    row = event.to_dict()
    assert list(row["sanitized_payload"]) == ["avoid_count", "restore_count"]
    assert list(row["provenance"]) == ["source", "version"]


# --- append-only JSONL behaviour ------------------------------------------


def test_append_writes_one_jsonl_row_per_event(tmp_path: Path):
    store = JsonlEventStore(tmp_path / "events.jsonl")
    e1 = build_event(lane="observation", kind="signal_seen")
    e2 = build_event(lane="context_pack", kind="preview_built")
    store.append(e1)
    store.append(e2)

    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert [r["kind"] for r in parsed] == ["signal_seen", "preview_built"]


def test_append_is_strictly_append_only(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    store = JsonlEventStore(path)
    store.append(build_event(lane="observation", kind="first"))
    first = path.read_text()
    store.append(build_event(lane="observation", kind="second"))
    second = path.read_text()
    # The second write must extend, never rewrite, the file.
    assert second.startswith(first)
    assert second != first


def test_read_all_returns_rows_in_append_order(tmp_path: Path):
    store = JsonlEventStore(tmp_path / "events.jsonl")
    for kind in ("a", "b", "c"):
        store.append(build_event(lane="observation", kind=kind))
    rows = store.read_all()
    assert [r["kind"] for r in rows] == ["a", "b", "c"]


def test_read_all_on_missing_file_returns_empty(tmp_path: Path):
    store = JsonlEventStore(tmp_path / "missing.jsonl")
    # Constructor creates parent dir, not the file itself.
    assert store.read_all() == []


# --- golden fixture -------------------------------------------------------


def test_golden_jsonl_output_is_deterministic(tmp_path: Path):
    store = JsonlEventStore(tmp_path / "events.jsonl")
    store.append(
        build_event(
            lane="observation",
            kind="task_handoff_ack",
            sanitized_payload={
                "delegated": True,
                "completed": True,
                "restore_count": 2,
                "refs": ["ref:abcdef012345"],
            },
            provenance={"source": "adapter.test", "version": "0.0.1"},
        )
    )
    store.append(
        build_event(
            lane="context_pack",
            kind="preview_built",
            sanitized_payload={"avoid_count": 1, "restore_count": 2},
            provenance={"source": "adapter.test"},
        )
    )

    produced = (tmp_path / "events.jsonl").read_text()
    expected = GOLDEN.read_text()
    assert produced == expected


# --- leak gate: write-time fail-closed ------------------------------------


def test_build_event_rejects_unsafe_payload_string():
    with pytest.raises(ValueError):
        build_event(
            lane="observation",
            kind="signal_seen",
            sanitized_payload={"note": "USER: pasted full transcript"},
        )


def test_build_event_rejects_provider_json_in_nested_payload():
    with pytest.raises(ValueError):
        build_event(
            lane="observation",
            kind="signal_seen",
            sanitized_payload={"detail": {"dump": '{"choices": [{"role": "user"}]}'}},
        )


def test_build_event_rejects_secret_assignment_in_list_value():
    with pytest.raises(ValueError):
        build_event(
            lane="observation",
            kind="signal_seen",
            sanitized_payload={"notes": ["token=" + "a" * 40]},
        )


def test_build_event_rejects_path_in_provenance():
    with pytest.raises(ValueError):
        build_event(
            lane="observation",
            kind="signal_seen",
            provenance={"file": "/home/op/.env"},
        )


def test_build_event_rejects_raw_id_shape_in_provenance():
    with pytest.raises(ValueError):
        build_event(
            lane="observation",
            kind="signal_seen",
            provenance={"thread": "msg-00042"},
        )


def test_build_event_rejects_empty_lane_or_kind():
    with pytest.raises(ValueError):
        build_event(lane="", kind="signal_seen")
    with pytest.raises(ValueError):
        build_event(lane="observation", kind="   ")


def test_build_event_rejects_unsafe_lane_or_kind():
    with pytest.raises(ValueError):
        build_event(lane="USER: smuggled", kind="signal_seen")
    with pytest.raises(ValueError):
        build_event(lane="observation", kind="token=" + "x" * 40)


def test_build_event_rejects_unsupported_value_type():
    class Opaque:
        pass

    with pytest.raises(ValueError):
        build_event(
            lane="observation",
            kind="signal_seen",
            sanitized_payload={"obj": Opaque()},
        )


def test_payload_dict_key_named_payload_is_not_a_false_positive():
    # Structural key names that overlap with field labels must not trip the
    # leak gate (only *values* are scanned).
    event = build_event(
        lane="observation",
        kind="signal_seen",
        sanitized_payload={"payload": {"provenance": {"count": 1}}},
    )
    assert event.sanitized_payload == {"payload": {"provenance": {"count": 1}}}
