"""Regression tests for unique CLI voice TTS temp paths."""

from pathlib import Path


def test_create_tts_output_path_is_unique_even_within_same_second(tmp_path):
    from tools.voice_mode import create_tts_output_path

    first = create_tts_output_path(temp_dir=str(tmp_path))
    second = create_tts_output_path(temp_dir=str(tmp_path))

    assert first != second
    assert Path(first).parent == tmp_path
    assert Path(second).parent == tmp_path
    assert first.endswith(".mp3")
    assert second.endswith(".mp3")
    assert "%f" not in first
    assert "%f" not in second


def test_create_tts_output_path_reserves_file_atomically(tmp_path):
    from tools.voice_mode import create_tts_output_path

    output_path = create_tts_output_path(temp_dir=str(tmp_path))

    assert Path(output_path).is_file()
    assert Path(output_path).stat().st_size == 0
