"""Tests for the Inworld TTS provider in tools/tts_tool.py."""

import base64
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in (
        "INWORLD_API_KEY",
        "INWORLD_BASE_URL",
        "HERMES_SESSION_PLATFORM",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def fake_pcm_bytes():
    # 0.1s of silence at 24kHz mono 16-bit = 4800 bytes
    return b"\x00" * 4800


@pytest.fixture
def mock_inworld_response(fake_pcm_bytes):
    """A successful Inworld /tts/v1/voice response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "audioContent": base64.b64encode(fake_pcm_bytes).decode(),
        "usage": {"processedCharactersCount": 5, "modelId": "inworld-tts-2"},
    }
    return resp


class TestGenerateInworldTts:
    def test_missing_api_key_raises_value_error(self, tmp_path):
        from tools.tts_tool import _generate_inworld_tts

        output_path = str(tmp_path / "test.wav")
        with pytest.raises(ValueError, match="INWORLD_API_KEY"):
            _generate_inworld_tts("Hello", output_path, {})

    def test_authorization_header_is_basic_verbatim(
        self, tmp_path, monkeypatch, mock_inworld_response
    ):
        """Portal key is already base64; we must NOT re-encode it."""
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "dGVzdC1rZXk6c2VjcmV0")  # arbitrary base64 from "test-key:secret"
        output_path = str(tmp_path / "test.wav")

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", output_path, {})

        headers = mock_post.call_args[1]["headers"]
        # Exact match: 'Basic ' + the key, byte-for-byte, no re-encoding.
        assert headers["Authorization"] == "Basic dGVzdC1rZXk6c2VjcmV0"
        assert headers["Content-Type"] == "application/json"

    def test_wav_output_fast_path(
        self, tmp_path, monkeypatch, mock_inworld_response, fake_pcm_bytes
    ):
        """`.wav` extension skips ffmpeg and writes RIFF directly."""
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        output_path = str(tmp_path / "test.wav")

        with patch("requests.post", return_value=mock_inworld_response), \
             patch("subprocess.run") as mock_run:
            result = _generate_inworld_tts("Hi", output_path, {})

        assert result == output_path
        mock_run.assert_not_called()
        data = (tmp_path / "test.wav").read_bytes()
        assert data[:4] == b"RIFF"
        assert data[8:12] == b"WAVE"
        # Audio payload should match the PCM we put in
        assert data[44:] == fake_pcm_bytes

    def test_default_voice_and_model(
        self, tmp_path, monkeypatch, mock_inworld_response
    ):
        from tools.tts_tool import (
            DEFAULT_INWORLD_TTS_MODEL,
            DEFAULT_INWORLD_TTS_VOICE,
            _generate_inworld_tts,
        )

        monkeypatch.setenv("INWORLD_API_KEY", "k")

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), {})

        payload = mock_post.call_args[1]["json"]
        assert payload["voiceId"] == DEFAULT_INWORLD_TTS_VOICE
        assert payload["modelId"] == DEFAULT_INWORLD_TTS_MODEL

    def test_custom_voice(self, tmp_path, monkeypatch, mock_inworld_response):
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        config = {"inworld": {"voice_id": "Anna"}}

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), config)

        assert mock_post.call_args[1]["json"]["voiceId"] == "Anna"

    def test_custom_model(self, tmp_path, monkeypatch, mock_inworld_response):
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        config = {"inworld": {"model": "inworld-tts-1.5-max"}}

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), config)

        assert mock_post.call_args[1]["json"]["modelId"] == "inworld-tts-1.5-max"

    @pytest.mark.parametrize(
        "ext,expected_encoding",
        [
            (".wav", "LINEAR16"),
            (".mp3", "MP3"),
            (".ogg", "OGG_OPUS"),
            (".opus", "OGG_OPUS"),
        ],
    )
    def test_audio_encoding_matches_output_ext(
        self, tmp_path, monkeypatch, mock_inworld_response, ext, expected_encoding
    ):
        """Inworld natively returns MP3 / OGG_OPUS / LINEAR16; pick from extension."""
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")

        # For .ogg/.mp3 native paths the mock 'PCM' bytes are written verbatim
        # to disk -- realistic enough for the encoding assertion.
        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", str(tmp_path / f"test{ext}"), {})

        audio_config = mock_post.call_args[1]["json"]["audioConfig"]
        assert audio_config["audioEncoding"] == expected_encoding
        assert audio_config["sampleRateHertz"] == 24000

    def test_mp3_output_skips_ffmpeg(
        self, tmp_path, monkeypatch, fake_pcm_bytes
    ):
        """Native MP3: API response bytes written verbatim, no ffmpeg call."""
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        fake_mp3 = b"\xff\xfb" + b"\x00" * 200  # MP3 sync word + filler
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"audioContent": base64.b64encode(fake_mp3).decode()}

        output_path = str(tmp_path / "test.mp3")
        with patch("requests.post", return_value=resp), \
             patch("subprocess.run") as mock_run:
            _generate_inworld_tts("Hi", output_path, {})

        mock_run.assert_not_called()
        assert (tmp_path / "test.mp3").read_bytes() == fake_mp3

    def test_ogg_output_skips_ffmpeg(self, tmp_path, monkeypatch):
        """Native OGG_OPUS: API response bytes written verbatim, no ffmpeg call."""
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        fake_opus = b"OggS" + b"\x00" * 200  # OGG container magic + filler
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"audioContent": base64.b64encode(fake_opus).decode()}

        output_path = str(tmp_path / "test.ogg")
        with patch("requests.post", return_value=resp), \
             patch("subprocess.run") as mock_run:
            _generate_inworld_tts("Hi", output_path, {})

        mock_run.assert_not_called()
        assert (tmp_path / "test.ogg").read_bytes() == fake_opus

    def test_text_is_truncated_at_2000_chars(
        self, tmp_path, monkeypatch, mock_inworld_response
    ):
        """API caps at 2000 chars; oversized input is sliced, not rejected."""
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        long_text = "a" * 5000

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts(long_text, str(tmp_path / "test.wav"), {})

        assert len(mock_post.call_args[1]["json"]["text"]) == 2000

    def test_endpoint_url(self, tmp_path, monkeypatch, mock_inworld_response):
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), {})

        assert mock_post.call_args[0][0] == "https://api.inworld.ai/tts/v1/voice"

    def test_http_error_raises_runtime_error(self, tmp_path, monkeypatch):
        """Inworld's typical 4xx response carries a `message` field."""
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        err_resp = MagicMock()
        err_resp.status_code = 400
        err_resp.json.return_value = {
            "code": 5,
            "message": "Unknown voice: John not found!",
        }

        with patch("requests.post", return_value=err_resp):
            with pytest.raises(RuntimeError, match="HTTP 400.*Unknown voice"):
                _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), {})

    def test_empty_audio_raises(self, tmp_path, monkeypatch):
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"audioContent": ""}

        with patch("requests.post", return_value=resp):
            with pytest.raises(RuntimeError, match="empty audio"):
                _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), {})

    def test_malformed_response_raises(self, tmp_path, monkeypatch):
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"usage": {}}  # no audioContent

        with patch("requests.post", return_value=resp):
            with pytest.raises(RuntimeError, match="malformed"):
                _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), {})

    def test_custom_base_url_via_config(
        self, tmp_path, monkeypatch, mock_inworld_response
    ):
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        config = {"inworld": {"base_url": "https://custom-inworld.example.com/tts/v1/voice"}}

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), config)

        assert mock_post.call_args[0][0] == "https://custom-inworld.example.com/tts/v1/voice"

    def test_custom_base_url_via_env(
        self, tmp_path, monkeypatch, mock_inworld_response
    ):
        from tools.tts_tool import _generate_inworld_tts

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        monkeypatch.setenv("INWORLD_BASE_URL", "https://env-inworld.example.com/tts/v1/voice")

        with patch("requests.post", return_value=mock_inworld_response) as mock_post:
            _generate_inworld_tts("Hi", str(tmp_path / "test.wav"), {})

        assert mock_post.call_args[0][0] == "https://env-inworld.example.com/tts/v1/voice"


class TestInworldInCheckRequirements:
    def test_inworld_api_key_satisfies_requirements(self, monkeypatch):
        from tools.tts_tool import check_tts_requirements

        # Strip everything else
        for key in (
            "ELEVENLABS_API_KEY",
            "OPENAI_API_KEY",
            "VOICE_TOOLS_OPENAI_KEY",
            "MINIMAX_API_KEY",
            "XAI_API_KEY",
            "MISTRAL_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        ):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("INWORLD_API_KEY", "k")

        # Force edge_tts import to fail so we actually hit the inworld check
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "edge_tts":
                raise ImportError("simulated")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            assert check_tts_requirements() is True


class TestDispatcher:
    def test_dispatcher_routes_inworld(self, monkeypatch, tmp_path):
        """Top-level text_to_speech_tool routes provider='inworld' correctly."""
        from tools import tts_tool

        monkeypatch.setenv("INWORLD_API_KEY", "k")
        called = {}

        def fake_inworld(text, file_str, tts_config):
            called["text"] = text
            called["path"] = file_str
            called["cfg"] = tts_config
            # Create an empty file so downstream "file exists" checks pass.
            open(file_str, "wb").close()
            return file_str

        # Patch the provider function and the on-disk config loader so the
        # dispatcher sees `provider: inworld` without touching ~/.hermes/.
        monkeypatch.setattr(tts_tool, "_generate_inworld_tts", fake_inworld)
        monkeypatch.setattr(
            tts_tool,
            "_load_tts_config",
            lambda: {"provider": "inworld", "inworld": {"voice_id": "Sarah"}},
        )

        out_path = str(tmp_path / "out.wav")
        tts_tool.text_to_speech_tool(
            text="Hello from Inworld",
            output_path=out_path,
        )

        assert called.get("text") == "Hello from Inworld"
        assert called.get("cfg", {}).get("provider") == "inworld"
