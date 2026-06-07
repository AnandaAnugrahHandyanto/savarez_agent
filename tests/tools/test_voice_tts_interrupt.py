import subprocess
import sys
import threading
import time

import pytest

from tools import voice_mode


def test_stop_playback_interrupts_cross_process_player_from_another_cli(tmp_path, monkeypatch):
    """A new command in any desktop CLI should be able to cut off current TTS."""
    audio = tmp_path / "tts.mp3"
    audio.write_bytes(b"fake audio")
    sleeper = tmp_path / "fake_player.py"
    sleeper.write_text(
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, lambda signum, frame: raise SystemExit(0))\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(voice_mode.platform, "system", lambda: "Linux")
    monkeypatch.setattr(voice_mode.shutil, "which", lambda exe: sys.executable if exe == "ffplay" else None)
    monkeypatch.setattr(voice_mode, "_GLOBAL_TTS_LOCK_PATH", str(tmp_path / "tts_playback.lock"))
    real_popen = subprocess.Popen
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda cmd, stdout=None, stderr=None: real_popen(
            [sys.executable, str(sleeper)],
            stdout=stdout,
            stderr=stderr,
        ),
    )

    done = threading.Event()
    result = {}

    def play():
        result["played"] = voice_mode.play_audio_file(str(audio))
        done.set()

    thread = threading.Thread(target=play, daemon=True)
    thread.start()

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        with voice_mode._playback_lock:
            if voice_mode._active_playback is not None:
                break
        time.sleep(0.01)
    else:
        pytest.fail("player process did not start")

    voice_mode.stop_all_tts_playback()

    assert done.wait(3), "cross-process TTS stop marker should interrupt the current player"
    assert result.get("played") is False
    thread.join(timeout=1)


def test_handle_enter_does_not_request_tts_stop_before_queueing_new_input():
    """Source guard: typing a new command should not interrupt queued spoken output."""
    import inspect
    from cli import HermesCLI

    source = inspect.getsource(HermesCLI.run)
    normal_input_idx = source.index("# --- Normal input routing ---")
    queue_idx = source.index("self._pending_input.put(payload)", normal_input_idx)
    pre_queue_source = source[normal_input_idx:queue_idx]

    assert "stop_all_tts_playback" not in pre_queue_source
