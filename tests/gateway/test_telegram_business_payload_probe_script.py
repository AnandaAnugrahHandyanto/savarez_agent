import json
import sqlite3

from gateway.life_inbox_store import LifeInboxStore
from scripts import telegram_business_payload_probe as probe


def test_prepare_run_sheet_registers_probe_hashes_without_plaintext(tmp_path, capsys):
    db_path = tmp_path / "life_inbox.sqlite"
    run_id = "20260520T090000Z"

    exit_code = probe.main([
        "prepare",
        "--db",
        str(db_path),
        "--run-id",
        run_id,
        "--format",
        "json",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source_lane"] == "business_bot_probe"
    assert payload["run_id"] == run_id
    assert len(payload["scenarios"]) == 6
    assert payload["scenarios"][0] == {
        "scenario_id": "S1_contact_inbound",
        "alias": "CONTACT_1",
        "expected_direction": "incoming_to_owner",
        "instruction": "CONTACT_1 sends this exact code to Alen in Telegram.",
        "probe_text": "TBP-20260520T090000Z-S1_contact_inbound",
    }

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT scenario_id, probe_text_len, probe_text_sha256, status
            FROM business_payload_probe_scenarios
            ORDER BY id
            """
        ).fetchall()

    assert len(rows) == 6
    assert rows[0][0] == "S1_contact_inbound"
    assert rows[0][1] == len("TBP-20260520T090000Z-S1_contact_inbound")
    assert len(rows[0][2]) == 64
    assert rows[0][3] == "pending"
    assert f"TBP-{run_id}" not in db_path.read_bytes().decode("utf-8", errors="ignore")


def test_status_summarizes_probe_events_without_chat_or_sender_ids_by_default(tmp_path, capsys):
    db_path = tmp_path / "life_inbox.sqlite"
    run_id = "20260520T091500Z"
    probe_text = "TBP-20260520T091500Z-S2_contact_alen_manual_outbound"

    probe.main(["prepare", "--db", str(db_path), "--run-id", run_id, "--format", "json"])
    capsys.readouterr()

    store = LifeInboxStore(db_path)
    store.record_business_payload_probe_event(
        update_id=42,
        update_type="business_message",
        connection_id="private-connection-id",
        owner_user_chat_id="602562",
        chat_id="private-chat-id",
        message_id="private-message-id",
        sender_id="602562",
        text=probe_text,
        message_date="2026-05-20T09:15:00+00:00",
        field_availability={"message": {"has_text": True, "has_reply_to_message": False}},
        payload_shape={"message": {"keys": {"text": {"type": "str"}}}},
        media={},
        reply_context={},
    )

    exit_code = probe.main(["status", "--db", str(db_path), "--format", "json"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "private-chat-id" not in output
    assert "private-message-id" not in output
    assert "private-connection-id" not in output
    payload = json.loads(output)
    scenario = next(row for row in payload["scenarios"] if row["scenario_id"] == "S2_contact_alen_manual_outbound")
    assert scenario["status"] == "matched"
    assert scenario["event_count"] == 1
    assert scenario["event_update_types"] == ["business_message"]
    assert scenario["event_directions"] == ["outgoing_from_owner"]
    assert scenario["field_availability"]["message"]["has_text"] is True
    assert scenario["media_keys"] == []
    assert scenario["reply_present"] is False
