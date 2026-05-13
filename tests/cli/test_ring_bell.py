"""Tests for ``cli._ring_bell`` and the ``notify_on_interact`` plumbing.

The two-pronged paplay + ASCII BEL strategy is what makes the
notification land on Wayland-native terminals (Foot/Kitty/ghostty),
where the bare BEL is silently swallowed.  These tests make sure
the helper:

1. Always writes ASCII BEL ("\\a") and flushes stdout — keeps the
   classic over-SSH and tmux-passthrough paths working.
2. Spawns ``paplay`` when it is on PATH, with the freedesktop sound
   asset, in a detached process group so the agent thread never
   blocks on the audio backend.
3. Skips the spawn cleanly when ``paplay`` is not installed.
4. Never propagates errors from a missing binary, broken stdout, or
   sandboxed audio device — the bell is a UX nicety, not a load-
   bearing dependency.

It also pins the wire from the new ``display.notify_on_interact``
config flag through ``_maybe_ring_interact_bell`` in
``hermes_cli/callbacks`` to ``cli._ring_bell``.
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cli
from hermes_cli import callbacks


def test_ring_bell_writes_ascii_bel_and_flushes():
    """The ASCII BEL leg must always run regardless of paplay state."""
    fake_stdout = io.StringIO()
    flush = MagicMock()
    fake_stdout.flush = flush

    with patch.object(cli, "sys", SimpleNamespace(stdout=fake_stdout)), \
         patch.object(cli.shutil, "which", return_value=None):
        cli._ring_bell()

    assert fake_stdout.getvalue() == "\a"
    flush.assert_called_once()


def test_ring_bell_invokes_paplay_when_available():
    """When paplay is on PATH we fire it detached with the freedesktop sound."""
    fake_stdout = io.StringIO()
    fake_stdout.flush = MagicMock()
    popen = MagicMock()

    with patch.object(cli, "sys", SimpleNamespace(stdout=fake_stdout)), \
         patch.object(cli.shutil, "which", return_value="/usr/bin/paplay"), \
         patch("subprocess.Popen", popen):
        cli._ring_bell()

    popen.assert_called_once()
    args, kwargs = popen.call_args
    cmd = args[0]
    assert cmd[0] == "/usr/bin/paplay"
    assert cmd[1] == cli._BELL_SOUND_PATH
    # Detached + silenced I/O so the agent thread never blocks on PulseAudio.
    assert kwargs.get("start_new_session") is True
    assert "stdout" in kwargs and "stderr" in kwargs and "stdin" in kwargs


def test_ring_bell_skips_paplay_when_missing():
    """``shutil.which`` returning None must short-circuit the spawn."""
    fake_stdout = io.StringIO()
    fake_stdout.flush = MagicMock()
    popen = MagicMock()

    with patch.object(cli, "sys", SimpleNamespace(stdout=fake_stdout)), \
         patch.object(cli.shutil, "which", return_value=None), \
         patch("subprocess.Popen", popen):
        cli._ring_bell()

    popen.assert_not_called()


def test_ring_bell_swallows_paplay_failure():
    """A broken paplay binary must never crash the agent loop."""
    fake_stdout = io.StringIO()
    fake_stdout.flush = MagicMock()

    def boom(*_a, **_kw):
        raise OSError("audio device busy")

    with patch.object(cli, "sys", SimpleNamespace(stdout=fake_stdout)), \
         patch.object(cli.shutil, "which", return_value="/usr/bin/paplay"), \
         patch("subprocess.Popen", side_effect=boom):
        cli._ring_bell()

    assert fake_stdout.getvalue() == "\a"


def test_ring_bell_swallows_stdout_failure():
    """A closed stdout must not stop us from at least trying paplay."""
    bad_stdout = MagicMock()
    bad_stdout.write.side_effect = ValueError("I/O on closed file")
    popen = MagicMock()

    with patch.object(cli, "sys", SimpleNamespace(stdout=bad_stdout)), \
         patch.object(cli.shutil, "which", return_value="/usr/bin/paplay"), \
         patch("subprocess.Popen", popen):
        cli._ring_bell()

    popen.assert_called_once()


def test_maybe_ring_interact_bell_respects_config_flag():
    """``notify_on_interact = False`` must not invoke the bell helper at all."""
    cli_stub = SimpleNamespace(notify_on_interact=False)

    with patch.object(cli, "_ring_bell") as ring:
        callbacks._maybe_ring_interact_bell(cli_stub)

    ring.assert_not_called()


def test_maybe_ring_interact_bell_fires_when_enabled():
    """``notify_on_interact = True`` must reach ``cli._ring_bell``."""
    cli_stub = SimpleNamespace(notify_on_interact=True)

    with patch.object(cli, "_ring_bell") as ring:
        callbacks._maybe_ring_interact_bell(cli_stub)

    ring.assert_called_once_with()


def test_maybe_ring_interact_bell_handles_missing_attribute():
    """A CLI without the attribute (e.g. legacy stub) must not raise."""
    cli_stub = SimpleNamespace()  # no notify_on_interact

    with patch.object(cli, "_ring_bell") as ring:
        callbacks._maybe_ring_interact_bell(cli_stub)

    ring.assert_not_called()


def test_default_config_includes_notify_on_interact_off():
    """Documented default is False — opt-in only."""
    from hermes_cli.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["display"]["notify_on_interact"] is False
    # Sibling sanity — same default as bell_on_complete so users get a
    # consistent off-by-default experience for both audible cues.
    assert DEFAULT_CONFIG["display"]["bell_on_complete"] is False
