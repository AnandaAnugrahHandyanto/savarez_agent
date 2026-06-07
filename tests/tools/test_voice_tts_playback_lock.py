"""Regression tests for cross-process voice TTS serialization."""

import multiprocessing as mp
import time
from pathlib import Path


def _worker(lock_path: str, hold_seconds: float, queue) -> None:
    from tools.voice_mode import global_tts_playback_lock

    start = time.monotonic()
    with global_tts_playback_lock(lock_path=lock_path, timeout=5):
        acquired = time.monotonic()
        queue.put(("acquired", acquired - start))
        time.sleep(hold_seconds)
    queue.put(("released", time.monotonic() - start))


def test_global_tts_playback_lock_serializes_across_processes(tmp_path):
    """Two independent Hermes CLI processes must not play TTS at the same time.

    The second process should block on the shared lock until the first process
    finishes playback, preserving task-completion order without overlapping
    speaker output.
    """
    lock_path = str(tmp_path / "hermes-tts.lock")
    queue = mp.Queue()

    first = mp.Process(target=_worker, args=(lock_path, 0.35, queue))
    second = mp.Process(target=_worker, args=(lock_path, 0.01, queue))

    first.start()
    first_acquired = queue.get(timeout=2)
    assert first_acquired[0] == "acquired"
    assert first_acquired[1] < 0.2

    second.start()
    second_event = queue.get(timeout=3)

    first.join(timeout=3)
    second.join(timeout=3)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert second_event[0] == "released"
    assert second_event[1] >= 0.35


def test_play_audio_file_uses_global_tts_playback_lock(monkeypatch, tmp_path):
    import tools.voice_mode as voice_mode

    audio_path = tmp_path / "reply.mp3"
    audio_path.write_bytes(b"fake audio")
    calls = []

    class FakeLock:
        def __enter__(self):
            calls.append("enter")

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")

    class FakeProc:
        def __init__(self):
            self._polled = False

        def poll(self):
            if self._polled:
                return 0
            self._polled = True
            return None

        def wait(self, timeout=None):
            calls.append(("wait", calls.copy()))
            return 0

    monkeypatch.setattr(voice_mode, "global_tts_playback_lock", lambda: FakeLock())
    monkeypatch.setattr(voice_mode.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "ffplay" else None)
    monkeypatch.setattr(voice_mode.subprocess, "Popen", lambda *args, **kwargs: FakeProc())

    assert voice_mode.play_audio_file(str(audio_path)) is True
    assert calls[0] == "enter"
    assert calls[-1] == "exit"
    wait_calls = [c for c in calls if isinstance(c, tuple) and c[0] == "wait"]
    assert wait_calls
    assert "enter" in wait_calls[0][1]
    assert "exit" not in wait_calls[0][1]
