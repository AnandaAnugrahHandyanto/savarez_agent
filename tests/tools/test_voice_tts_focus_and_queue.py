"""Regression tests for TTS playback foreground/focus and queue semantics."""

import inspect

from cli import HermesCLI
from tools import voice_mode


def test_playback_after_waiting_lock_is_not_skipped_by_prior_stop_marker(tmp_path, monkeypatch):
    """A stop marker should cut off active audio, not cancel later queued TTS."""
    audio = tmp_path / "queued.mp3"
    audio.write_bytes(b"fake audio")
    stop_marker = tmp_path / "tts.stop"
    calls = []

    class FakeLock:
        def __enter__(self):
            voice_mode.request_global_tts_stop(str(stop_marker))
            calls.append("lock-enter")

        def __exit__(self, exc_type, exc, tb):
            calls.append("lock-exit")

    class FakeProc:
        def __init__(self):
            self._polled = False

        def poll(self):
            if self._polled:
                return 0
            self._polled = True
            return None

        def wait(self, timeout=None):
            calls.append("wait")
            return 0

    monkeypatch.setattr(voice_mode, "_GLOBAL_TTS_STOP_PATH", str(stop_marker))
    monkeypatch.setattr(voice_mode, "global_tts_playback_lock", lambda: FakeLock())
    monkeypatch.setattr(voice_mode.shutil, "which", lambda name: "/usr/bin/ffplay" if name == "ffplay" else None)
    monkeypatch.setattr(voice_mode.subprocess, "Popen", lambda *args, **kwargs: FakeProc())

    assert voice_mode.play_audio_file(str(audio)) is True
    assert calls == ["lock-enter", "wait", "lock-exit"]


def test_classic_cli_tts_focuses_window_before_playback():
    """Source guard: each spoken reply should foreground its CLI window first."""
    source = inspect.getsource(HermesCLI._voice_speak_response)
    focus_idx = source.index("_focus_window_on_complete")
    play_idx = source.rindex("play_audio_file")
    assert focus_idx < play_idx


def test_normal_enter_does_not_globally_stop_queued_tts():
    """Typing a new message should not kill active/queued completion speech."""
    with open("/home/david/.hermes/hermes-agent/cli.py", "r", encoding="utf-8") as f:
        source = f.read()
    normal_input_idx = source.index("# --- Normal input routing ---")
    model_inline_idx = source.index("# Handle /model directly", normal_input_idx)
    normal_input_prelude = source[normal_input_idx:model_inline_idx]
    assert "stop_all_tts_playback" not in normal_input_prelude


def test_focus_helper_uses_target_pid_when_available(tmp_path, monkeypatch):
    """The CLI should invoke the local helper with a sanitized task preview."""
    import cli as cli_module

    cli = HermesCLI.__new__(HermesCLI)
    cli.focus_window_on_complete = True
    cli._current_user_task_preview = ""

    helper = tmp_path / ".local" / "bin" / "hermes-cli-focus-window"
    helper.parent.mkdir(parents=True)
    helper.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    captured = {}

    class _DummyProc:
        pass

    monkeypatch.setattr(cli_module.Path, "home", classmethod(lambda cls: tmp_path))

    def _fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return _DummyProc()

    monkeypatch.setattr("subprocess.Popen", _fake_popen)

    cli._focus_window_on_complete("  任务\n标题  ")

    assert captured["args"] == [str(helper), "任务 标题"]
