"""Tests for extracting Brian-grade goblin references from session history."""

from pathlib import Path

from agent.goblin_quotes import append_goblin_log, iter_goblin_quotes
from hermes_state import SessionDB


def _session_db(tmp_path: Path) -> SessionDB:
    return SessionDB(tmp_path / "state.db")


def test_iter_goblin_quotes_extracts_sentence_level_matches(tmp_path):
    db = _session_db(tmp_path)
    try:
        db.create_session("s-gob", source="slack")
        db.set_session_title("s-gob", "Goblin science")
        first_id = db.append_message(
            "s-gob",
            "assistant",
            "Normal setup. The goblin calibration rig is screaming again! Carry on.",
        )
        db.append_message("s-gob", "assistant", "No gremlins here, different creature.")

        quotes = list(iter_goblin_quotes(db))

        assert quotes == [
            {
                "session_id": "s-gob",
                "message_id": first_id,
                "role": "assistant",
                "source": "slack",
                "title": "Goblin science",
                "quote": "The goblin calibration rig is screaming again!",
            }
        ]
    finally:
        db.close()


def test_iter_goblin_quotes_handles_multimodal_text_parts_and_source_filter(tmp_path):
    db = _session_db(tmp_path)
    try:
        db.create_session("s-cli", source="cli")
        db.append_message("s-cli", "user", "CLI goblin should be ignored by source filter.")
        db.create_session("s-slack", source="slack")
        message_id = db.append_message(
            "s-slack",
            "user",
            [
                {"type": "text", "text": "Look at this goblin-shaped stack trace."},
                {"type": "image_url", "image_url": {"url": "https://example.test/goblin.png"}},
            ],
        )

        quotes = list(iter_goblin_quotes(db, source="slack"))

        assert len(quotes) == 1
        assert quotes[0]["session_id"] == "s-slack"
        assert quotes[0]["message_id"] == message_id
        assert quotes[0]["quote"] == "Look at this goblin-shaped stack trace."
    finally:
        db.close()


def test_append_goblin_log_is_markdown_and_dedupes_existing_entries(tmp_path):
    db = _session_db(tmp_path)
    try:
        db.create_session("s-gob", source="telegram")
        db.set_session_title("s-gob", "Lab notes")
        db.append_message("s-gob", "assistant", "Release the deployment goblins.")
        log_path = tmp_path / "goblin-quotes.md"

        first = append_goblin_log(db, log_path)
        second = append_goblin_log(db, log_path)

        text = log_path.read_text(encoding="utf-8")
        assert first["added"] == 1
        assert second["added"] == 0
        assert text.startswith("# Goblin Quote Log\n")
        assert text.count("Release the deployment goblins.") == 1
        assert "session: `s-gob`" in text
        assert "source: `telegram`" in text
    finally:
        db.close()
