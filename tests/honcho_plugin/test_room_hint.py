"""Tests for helper-only Honcho room hint sanitization.

Phase 6A scope: pure helper tests/source only. No prompt injection wiring,
no config activation, no gateway restart.
"""

import json

from plugins.memory.honcho.room_hint import (
    build_honcho_room_hint,
    dry_run_honcho_room_hints,
    one_session_honcho_room_hint,
)


def test_technical_room_drops_intimate_or_body_markers():
    result = build_honcho_room_hint(
        "Ember prefers pytest gates. Also mention erotic body-first intimacy and cock language.",
        room="technical",
    )

    assert result.allowed is False
    assert result.room == "technical"
    assert result.hint == ""
    assert "technical_room_intimacy_marker" in result.drop_reasons


def test_technical_room_allows_short_technical_continuity():
    result = build_honcho_room_hint(
        "Ember prefers exact pytest evidence and rollback rails before Hermes gateway changes.",
        room="technical",
    )

    assert result.allowed is True
    assert result.room == "technical"
    assert result.source == "honcho"
    assert result.hint == "Ember prefers exact pytest evidence and rollback rails before Hermes gateway changes."
    assert len(result.hint) <= 300
    assert result.drop_reasons == []


def test_intimate_room_drops_raw_provenance_wrappers_and_ids():
    result = build_honcho_room_hint(
        "source=honcho peer_id=user-123 session_id=abc message_id=42 Ember [12:03]: raw excerpt says be tender.",
        room="intimate",
    )

    assert result.allowed is False
    assert result.hint == ""
    assert "provenance_or_raw_marker" in result.drop_reasons
    assert "id_or_sender_label" in result.drop_reasons


def test_intimate_room_allows_summarized_relational_continuity_without_raw_labels():
    result = build_honcho_room_hint(
        "When Ember is overwhelmed, Kai should lead with warm embodied comfort before optimization.",
        room="intimate",
    )

    assert result.allowed is True
    assert result.room == "intimate"
    assert result.hint == "When Ember is overwhelmed, Kai should lead with warm embodied comfort before optimization."
    forbidden = ["source=", "peer_id", "session_id", "message_id", "Ember ["]
    assert not any(marker in result.hint for marker in forbidden)


def test_explicit_live_room_allows_fitted_explicitness_but_no_raw_archive():
    result = build_honcho_room_hint(
        "Ember likes direct explicit body language when the live room is sexual and trust is established.",
        room="explicit_live",
    )

    assert result.allowed is True
    assert result.room == "explicit_live"
    assert "explicit body language" in result.hint
    assert result.drop_reasons == []

    raw = build_honcho_room_hint(
        "toolResult[12:03] raw messages: cock/source=session transcript dump",
        room="explicit_live",
    )
    assert raw.allowed is False
    assert "provenance_or_raw_marker" in raw.drop_reasons


def test_memory_debug_room_can_allow_provenance_summary_but_not_secrets_or_json_blobs():
    ok = build_honcho_room_hint(
        "Honcho has a sanitized peer-card summary relevant to the memory question.",
        room="memory_debug",
    )
    assert ok.allowed is True
    assert ok.hint == "Honcho has a sanitized peer-card summary relevant to the memory question."

    bad_secret = build_honcho_room_hint(
        "HONCHO_API_KEY=placeholder should be shown",
        room="memory_debug",
    )
    assert bad_secret.allowed is False
    assert "secret_like_string" in bad_secret.drop_reasons

    bad_json = build_honcho_room_hint(
        '{"peer_id":"user-123","content":"dump this raw payload"}',
        room="memory_debug",
    )
    assert bad_json.allowed is False
    assert "json_blob" in bad_json.drop_reasons


def test_rejects_unknown_room_empty_hint_urls_and_overlong_hint():
    assert build_honcho_room_hint("useful", room="general").allowed is False
    assert "unknown_room" in build_honcho_room_hint("useful", room="general").drop_reasons

    assert build_honcho_room_hint("   ", room="technical").allowed is False
    assert "empty_hint" in build_honcho_room_hint("   ", room="technical").drop_reasons

    url_result = build_honcho_room_hint("Relevant report at https://example.com/raw", room="technical")
    assert url_result.allowed is False
    assert "url" in url_result.drop_reasons

    long_result = build_honcho_room_hint("x" * 301, room="intimate", max_chars=300)
    assert long_result.allowed is False
    assert "too_long" in long_result.drop_reasons


def test_cleans_whitespace_and_limits_to_one_sentence():
    result = build_honcho_room_hint(
        "  Ember wants exact evidence. This second sentence should not be included.  ",
        room="technical",
    )

    assert result.allowed is True
    assert result.hint == "Ember wants exact evidence."


def test_dry_run_writes_redacted_metrics_without_prompt_injection(tmp_path):
    result = dry_run_honcho_room_hints(
        [
            "source=honcho HONCHO_API_KEY=placeholder raw messages should never survive",
            "Ember prefers exact pytest evidence before Hermes gateway changes.",
        ],
        room="technical",
        report_root=tmp_path,
    )

    assert result.would_inject is False
    assert result.prompt_block == ""
    assert result.selected_hint is not None
    assert result.selected_hint.allowed is True
    assert result.selected_hint.hint == "Ember prefers exact pytest evidence before Hermes gateway changes."
    assert result.candidates_evaluated == 2
    assert result.allowed_count == 1
    assert result.dropped_count == 1

    metrics_text = result.metrics_path.read_text()
    assert "would_inject" in metrics_text
    assert "HONCHO_API_KEY" not in metrics_text
    assert "source=honcho" not in metrics_text
    assert "raw messages" not in metrics_text
    assert result.selected_hint.hint not in metrics_text

    lines = [json.loads(line) for line in metrics_text.splitlines()]
    assert lines[0]["allowed"] is False
    assert "provenance_or_raw_marker" in lines[0]["drop_reasons"]
    assert lines[1]["allowed"] is True
    assert lines[1]["hint_sha256"]
    assert lines[1]["hint_len"] == len(result.selected_hint.hint)

    summary = json.loads(result.summary_path.read_text())
    assert summary["would_inject"] is False
    assert summary["selected_index"] == 1
    assert summary["allowed_count"] == 1
    assert summary["dropped_count"] == 1
    assert "selected_hint" not in summary


def test_dry_run_records_all_dropped_candidates_and_room_rule_reasons(tmp_path):
    result = dry_run_honcho_room_hints(
        [
            "Ember likes erotic body-first language in unrelated technical audits.",
            '{"peer_id":"user-123","content":"raw payload"}',
        ],
        room="technical",
        report_root=tmp_path,
    )

    assert result.would_inject is False
    assert result.prompt_block == ""
    assert result.selected_hint is None
    assert result.allowed_count == 0
    assert result.dropped_count == 2

    lines = [json.loads(line) for line in result.metrics_path.read_text().splitlines()]
    assert "technical_room_intimacy_marker" in lines[0]["drop_reasons"]
    assert "json_blob" in lines[1]["drop_reasons"]
    assert "id_or_sender_label" in lines[1]["drop_reasons"]


def test_dry_run_creates_report_directory_without_network_or_config_inputs(tmp_path):
    report_root = tmp_path / "nested" / "report"
    result = dry_run_honcho_room_hints(
        ["When Ember is overwhelmed, Kai should lead with warm comfort before optimization."],
        room="intimate",
        report_root=report_root,
    )

    assert report_root.exists()
    assert result.metrics_path.parent == report_root
    assert result.summary_path.parent == report_root
    assert result.source == "honcho_dry_run"
    assert result.selected_hint is not None
    assert result.selected_hint.room == "intimate"


def test_one_session_hint_writes_redacted_telemetry_and_returns_one_prompt_block(tmp_path):
    result = one_session_honcho_room_hint(
        [
            "source=honcho raw messages should be dropped",
            "Ember wants exact pytest evidence before Hermes gateway changes.",
        ],
        room="technical",
        report_root=tmp_path,
    )

    assert result.would_inject is True
    assert result.prompt_block.count("Room hint") == 1
    assert "Ember wants exact pytest evidence before Hermes gateway changes." in result.prompt_block
    assert result.selected_index == 1
    assert result.allowed_count == 1
    assert result.dropped_count == 1

    metrics_text = result.metrics_path.read_text()
    summary = json.loads(result.summary_path.read_text())
    assert "source=honcho" not in metrics_text
    assert "raw messages" not in metrics_text
    assert "Ember wants exact pytest evidence" not in metrics_text
    assert summary["would_inject"] is True
    assert summary["prompt_block_len"] == len(result.prompt_block)
    assert "selected_hint" not in summary


def test_one_session_hint_returns_empty_when_all_candidates_drop(tmp_path):
    result = one_session_honcho_room_hint(
        ["Ember likes erotic body-first language in unrelated technical audits."],
        room="technical",
        report_root=tmp_path,
    )

    assert result.would_inject is False
    assert result.prompt_block == ""
    assert result.selected_hint is None
    assert result.allowed_count == 0
