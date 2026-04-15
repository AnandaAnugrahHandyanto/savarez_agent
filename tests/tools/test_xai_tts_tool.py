import pytest


class _FakeResponse:
    def __init__(self, *, content=b""):
        self.content = content

    def raise_for_status(self):
        return None


def test_generate_xai_tts_writes_audio_file(monkeypatch, tmp_path):
    from hermes_cli import __version__
    from tools.tts_tool import _generate_xai_tts

    captured = {}
    output_path = tmp_path / "speech.mp3"

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(content=b"fake-mp3-bytes")

    monkeypatch.setenv("XAI_API_KEY", "xai-test-key")
    monkeypatch.setattr("requests.post", _fake_post)

    result = _generate_xai_tts("hello world", str(output_path), {"xai": {"voice_id": "eve"}})

    assert result == str(output_path)
    assert output_path.read_bytes() == b"fake-mp3-bytes"
    assert captured["url"] == "https://api.x.ai/v1/tts"
    assert captured["headers"]["User-Agent"] == f"Hermes-Agent/{__version__}"
    assert captured["json"]["text"] == "hello world"
    assert captured["json"]["voice_id"] == "eve"
    assert captured["json"]["language"] == "en"
    assert "output_format" not in captured["json"]


def test_generate_xai_tts_includes_output_format_for_non_default_overrides(monkeypatch, tmp_path):
    from tools.tts_tool import _generate_xai_tts

    captured = {}
    output_path = tmp_path / "speech.wav"

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(content=b"fake-wav-bytes")

    monkeypatch.setenv("XAI_API_KEY", "xai-test-key")
    monkeypatch.setattr("requests.post", _fake_post)

    result = _generate_xai_tts(
        "hello world",
        str(output_path),
        {"xai": {"voice_id": "eve", "language": "en", "sample_rate": 44100}},
    )

    assert result == str(output_path)
    assert captured["json"]["output_format"]["codec"] == "wav"
    assert captured["json"]["output_format"]["sample_rate"] == 44100


def test_generate_xai_tts_missing_key_raises_value_error(monkeypatch, tmp_path):
    from tools.tts_tool import _generate_xai_tts

    monkeypatch.delenv("XAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="XAI_API_KEY"):
        _generate_xai_tts("hello world", str(tmp_path / "speech.mp3"), {"xai": {"voice_id": "eve"}})
