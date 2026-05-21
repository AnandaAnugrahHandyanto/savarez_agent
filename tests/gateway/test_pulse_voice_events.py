import json

from gateway.pulse_voice_events import (
    completion_voice_text,
    publish_completion_voice_out,
    publish_voice_event,
    publish_voice_out,
    voice_events_path,
    voice_out_path,
    voice_safe_text,
)


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_voice_safe_text_removes_code_media_and_bounds_length():
    text = """
    Done. MEDIA:/tmp/audio.mp3

    ```python
    print('do not speak code')
    ```
    [[audio_as_voice]] Extra words that should not matter.
    """

    assert voice_safe_text(text) == "Done."


def test_publish_voice_out_writes_canonical_schema_and_legacy_mirror(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    publish_voice_out("ack", "Got it. I’ll wire the voice path.", session_id="s1", source_message_id="m1")

    canonical = _jsonl(voice_out_path())
    legacy = _jsonl(voice_events_path())
    assert canonical == legacy
    assert canonical[0]["kind"] == "ack"
    assert canonical[0]["text"] == "Got it."
    assert canonical[0]["max_seconds"] == 4
    assert canonical[0]["session_id"] == "s1"
    assert canonical[0]["source_message_id"] == "m1"


def test_legacy_delta_events_are_not_published(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    publish_voice_event("delta", "This raw token stream must not be spoken.")

    assert not voice_out_path().exists()
    assert not voice_events_path().exists()


def test_legacy_commentary_maps_to_progress(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    publish_voice_event("commentary", "I’ll inspect that now. More details follow later.")

    [event] = _jsonl(voice_out_path())
    assert event["kind"] == "progress"
    assert event["text"] == "I’ll inspect that now."


def test_completion_voice_text_summarizes_executor_output():
    kind, text = completion_voice_text("I updated the bridge and ran the tests. Full details are in Discord.")

    assert kind == "completion"
    assert text == "Done — I updated the bridge and ran the tests."


def test_publish_completion_voice_out_marks_questions(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    publish_completion_voice_out("Which profile should own the worker task?")

    [event] = _jsonl(voice_out_path())
    assert event["kind"] == "question"
    assert event["text"] == "Which profile should own the worker task?"
