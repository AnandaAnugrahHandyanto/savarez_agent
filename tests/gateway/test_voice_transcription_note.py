"""Tests for the voice-transcription enrichment note helper."""

from gateway.run import _voice_transcription_note


def test_non_empty_transcript_is_quoted():
    note = _voice_transcription_note({"success": True, "transcript": "hello there"})

    assert 'Here\'s what they said: "hello there"' in note
    assert "empty or inaudible" not in note


def test_empty_transcript_uses_sentinel_note():
    note = _voice_transcription_note({"success": True, "transcript": ""})

    assert "empty or inaudible" in note
    assert 'they said: ""' not in note


def test_whitespace_only_transcript_uses_sentinel_note():
    note = _voice_transcription_note({"success": True, "transcript": "   \n\t"})

    assert "empty or inaudible" in note
    assert "Do not guess" in note


def test_missing_transcript_key_uses_sentinel_note():
    note = _voice_transcription_note({"success": True})

    assert "empty or inaudible" in note
