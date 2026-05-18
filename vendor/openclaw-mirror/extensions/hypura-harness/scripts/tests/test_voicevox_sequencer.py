# scripts/hypura/tests/test_voicevox_sequencer.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_speak_calls_voicevox_api() -> None:
    with (
        patch("voicevox_sequencer.httpx.AsyncClient") as MockHTTP,
        patch("voicevox_sequencer.sd") as _mock_sd,
    ):
        mock_client = AsyncMock()
        MockHTTP.return_value.__aenter__.return_value = mock_client
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={})
        resp.content = b"RIFF....WAV_DATA"
        mock_client.post = AsyncMock(return_value=resp)
        from voicevox_sequencer import VoicevoxSequencer

        seq = VoicevoxSequencer(voicevox_url="http://127.0.0.1:50021")
        try:
            await seq.speak("hello", emotion="neutral", speaker=8)
        except Exception:
            pass
        assert mock_client.post.called


@pytest.mark.asyncio
async def test_synthesize_returns_voicevox_wav_bytes() -> None:
    with patch("voicevox_sequencer.httpx.AsyncClient") as MockHTTP:
        mock_client = AsyncMock()
        MockHTTP.return_value.__aenter__.return_value = mock_client
        query_resp = MagicMock()
        query_resp.raise_for_status = MagicMock()
        query_resp.json = MagicMock(return_value={})
        synth_resp = MagicMock()
        synth_resp.raise_for_status = MagicMock()
        synth_resp.content = b"RIFF_WAV"
        mock_client.post = AsyncMock(side_effect=[query_resp, synth_resp])

        from voicevox_sequencer import VoicevoxSequencer

        seq = VoicevoxSequencer(voicevox_url="http://127.0.0.1:50021")
        assert await seq.synthesize("hello", speaker=3) == b"RIFF_WAV"


def test_play_wav_bytes_plays_multiple_output_devices() -> None:
    with (
        patch("voicevox_sequencer.sf.read", return_value=("audio", 24000)),
        patch("voicevox_sequencer.sd.play") as mock_play,
        patch("voicevox_sequencer.sd.wait"),
    ):
        from voicevox_sequencer import VoicevoxSequencer

        seq = VoicevoxSequencer()
        seq.play_wav_bytes(b"RIFF", output_devices=[5, 4])

        assert mock_play.call_count == 2
        assert {call.kwargs["device"] for call in mock_play.call_args_list} == {5, 4}


@pytest.mark.asyncio
async def test_emotion_maps_to_voice_params() -> None:
    from voicevox_sequencer import VoicevoxSequencer, load_param_map

    param_map = load_param_map()
    seq = VoicevoxSequencer()
    params = seq._emotion_to_voice_params("happy", param_map)
    assert params["speedScale"] > 1.0


@pytest.mark.asyncio
async def test_play_scene_processes_each_line() -> None:
    with (
        patch("voicevox_sequencer.httpx.AsyncClient") as MockHTTP,
        patch("voicevox_sequencer.sd"),
        patch("voicevox_sequencer.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        MockHTTP.return_value.__aenter__.return_value = mock_client
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={})
        resp.content = b"WAV"
        mock_client.post = AsyncMock(return_value=resp)
        from voicevox_sequencer import VoicevoxSequencer

        seq = VoicevoxSequencer()
        script = [
            {"text": "hello", "emotion": "happy", "pause_after": 0.1},
            {"text": "goodbye", "emotion": "sad", "pause_after": 0.1},
        ]
        await seq.play_scene(script, speaker=8)
        assert mock_client.post.call_count >= 2
