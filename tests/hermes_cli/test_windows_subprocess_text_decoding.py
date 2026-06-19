import subprocess
import sys

import hermes_cli


def test_windows_text_subprocess_defaults_to_lossy_utf8(monkeypatch):
    original_init = subprocess.Popen.__init__
    calls = []

    def fake_init(self, *args, **kwargs):
        calls.append(kwargs)
        return None

    try:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(subprocess.Popen, "__init__", fake_init)

        hermes_cli._ensure_windows_subprocess_text_decoding()
        subprocess.Popen.__init__(object(), ["cmd"], text=True)

        assert calls[-1]["encoding"] == "utf-8"
        assert calls[-1]["errors"] == "replace"
    finally:
        subprocess.Popen.__init__ = original_init


def test_windows_text_subprocess_preserves_explicit_decode_policy(monkeypatch):
    original_init = subprocess.Popen.__init__
    calls = []

    def fake_init(self, *args, **kwargs):
        calls.append(kwargs)
        return None

    try:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(subprocess.Popen, "__init__", fake_init)

        hermes_cli._ensure_windows_subprocess_text_decoding()
        subprocess.Popen.__init__(
            object(),
            ["cmd"],
            text=True,
            encoding="cp936",
            errors="surrogateescape",
        )

        assert calls[-1]["encoding"] == "cp936"
        assert calls[-1]["errors"] == "surrogateescape"
    finally:
        subprocess.Popen.__init__ = original_init


def test_windows_positional_universal_newlines_gets_lossy_utf8(monkeypatch):
    original_init = subprocess.Popen.__init__
    calls = []

    def fake_init(self, *args, **kwargs):
        calls.append((args, kwargs))
        return None

    try:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(subprocess.Popen, "__init__", fake_init)

        hermes_cli._ensure_windows_subprocess_text_decoding()
        # Popen.__init__ positional index 11 is universal_newlines.
        subprocess.Popen.__init__(
            object(),
            ["cmd"],
            -1,
            None,
            None,
            subprocess.PIPE,
            subprocess.PIPE,
            None,
            True,
            False,
            None,
            None,
            True,
        )

        assert calls[-1][1]["encoding"] == "utf-8"
        assert calls[-1][1]["errors"] == "replace"
    finally:
        subprocess.Popen.__init__ = original_init


def test_windows_encoding_only_text_mode_gets_replace_errors(monkeypatch):
    original_init = subprocess.Popen.__init__
    calls = []

    def fake_init(self, *args, **kwargs):
        calls.append(kwargs)
        return None

    try:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(subprocess.Popen, "__init__", fake_init)

        hermes_cli._ensure_windows_subprocess_text_decoding()
        subprocess.Popen.__init__(object(), ["cmd"], encoding="cp936")

        assert calls[-1]["encoding"] == "cp936"
        assert calls[-1]["errors"] == "replace"
    finally:
        subprocess.Popen.__init__ = original_init


def test_windows_errors_only_text_mode_gets_utf8_encoding(monkeypatch):
    original_init = subprocess.Popen.__init__
    calls = []

    def fake_init(self, *args, **kwargs):
        calls.append(kwargs)
        return None

    try:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(subprocess.Popen, "__init__", fake_init)

        hermes_cli._ensure_windows_subprocess_text_decoding()
        subprocess.Popen.__init__(object(), ["cmd"], errors="backslashreplace")

        assert calls[-1]["encoding"] == "utf-8"
        assert calls[-1]["errors"] == "backslashreplace"
    finally:
        subprocess.Popen.__init__ = original_init


def test_non_windows_subprocess_init_is_left_unchanged(monkeypatch):
    original_init = subprocess.Popen.__init__

    def fake_init(self, *args, **kwargs):
        return None

    try:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(subprocess.Popen, "__init__", fake_init)

        hermes_cli._ensure_windows_subprocess_text_decoding()

        assert subprocess.Popen.__init__ is fake_init
    finally:
        subprocess.Popen.__init__ = original_init
