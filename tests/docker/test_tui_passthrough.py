"""Harness: interactive TUI TTY passthrough.

Uses ``script -qc`` on the host to allocate a PTY for the docker client,
which then allocates a container-side PTY via ``-t``. The probe inside
the container echoes ``$COLUMNS`` (injected via ``-e COLUMNS=123``), which
is a reliable way to confirm the Docker env var reached the container
process. A positive value confirms end-to-end env + TTY passthrough.

``tput cols`` was used previously but is fragile: on a 0×0 script PTY
(common in CI) it reads TIOCGWINSZ and returns 0, and the ``script``
output also begins with a stray ``^@`` sequence that confuses simple
digit-only token matching. Using an explicit ``$COLUMNS`` probe removes
both sources of flakiness.

These tests MUST pass on the current tini-based image AND continue to
pass after the Phase 2 s6 migration. Any drift is a regression.
"""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("script") is None,
    reason="`script` command not available on this host",
)


def test_tty_passthrough_to_container(built_image: str) -> None:
    """``docker run -t`` must deliver a real TTY to the container process."""
    # Use echo $COLUMNS rather than tput cols: tput reads TIOCGWINSZ which
    # is 0 when script -qc creates a 0×0 PTY (always the case in CI), while
    # $COLUMNS reflects the explicit -e COLUMNS=123 we passed to docker run.
    probe = "if [ -t 1 ]; then echo $COLUMNS; else echo NO_TTY; fi"
    cmd = (
        f"docker run --rm -t -e COLUMNS=123 {built_image} "
        f"sh -c {shlex.quote(probe)}"
    )
    r = subprocess.run(
        ["script", "-qc", cmd, "/dev/null"],
        capture_output=True, text=True, timeout=120,
    )
    output = r.stdout.strip()
    assert "NO_TTY" not in output, f"TTY passthrough failed: {output!r}"
    # script -qc prepends a stray '^@' (two literal chars) or NUL byte to
    # its first line of output on Linux (util-linux script).  Use re.findall
    # to extract digit sequences regardless of leading non-digit characters.
    numeric_lines = [int(m) for m in re.findall(r"\d+", output) if int(m) > 0]
    assert numeric_lines, f"No positive numeric width in output: {output!r}"


def test_tui_flag_recognized(built_image: str) -> None:
    """``docker run -it <image> --help`` should run without crashing."""
    cmd = f"docker run --rm -t {built_image} --help"
    r = subprocess.run(
        ["script", "-qc", cmd, "/dev/null"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0
