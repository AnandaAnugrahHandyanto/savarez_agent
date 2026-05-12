"""RED-phase parametrized tests for the shell/interpreter ``-c`` hardline bypass.

The hardline floor (``tools.approval.detect_hardline_command``) currently
scans the raw command string for catastrophic patterns -- ``rm -rf /``,
``mkfs``, ``shutdown``, fork bombs, ``kill -1``, etc. -- but it does not
look inside the payload of a shell or interpreter ``-c`` flag. That means
an attacker (or a confused LLM) can smuggle a hardline command past the
floor simply by wrapping it in ``bash -c '...'``, ``zsh -ic '...'``, or
``python -c "..."``.

These tests pin the desired behavior: ``detect_hardline_command`` must
catch the catastrophic payload even when it is nested inside an ``-c``
argument, while still leaving harmless ``print``/``echo`` lines that only
*mention* the dangerous words untouched.

This file is RED-only. The production fix lives in ``tools/approval.py``
and is deferred to the GREEN commit.
"""

import pytest

from tools.approval import detect_hardline_command


# -------------------------------------------------------------------------
# Positive cases -- catastrophic commands hidden inside an ``-c`` payload.
# All of these MUST be hardline-blocked once the floor learns to inspect
# shell/interpreter ``-c`` arguments.
# -------------------------------------------------------------------------
_SHELL_PAYLOAD_HARDLINE_CASES = [
    # bash -lc: login shell, single-quoted catastrophic rm -rf /
    "bash -lc 'rm -rf /'",
    # sh -c with double-quoted mkfs against a raw block device
    'sh -c "mkfs.ext4 /dev/sda"',
    # zsh -ic: interactive shell smuggling shutdown
    "zsh -ic 'shutdown -h now'",
    # python3 -c invoking os.system on rm -rf /
    "python3 -c 'import os; os.system(\"rm -rf /\")'",
    # python -c using __import__ to reach os.system with a mkfs payload
    "python -c \"__import__('os').system('mkfs.ext4 /dev/sda')\"",
]


# -------------------------------------------------------------------------
# Negative cases -- ``-c`` payloads that only *mention* the dangerous
# words as string literals. These must NOT trip the hardline floor.
# -------------------------------------------------------------------------
_SHELL_PAYLOAD_NEGATIVE_CASES = [
    # print() of a literal string that happens to contain "rm -rf /"
    "python -c \"print('rm -rf / as text')\"",
    # echo of the literal word "reboot" -- nothing is actually being rebooted
    "bash -c 'echo reboot'",
]


@pytest.mark.parametrize("command", _SHELL_PAYLOAD_HARDLINE_CASES)
def test_shell_payload_is_hardline(command):
    """Catastrophic payloads hidden in ``-c`` arguments are hardline matches.

    The exact description string is intentionally not pinned: the GREEN
    implementation is free to choose its phrasing (e.g. "rm -rf root via
    bash -c", "mkfs filesystem via interpreter -c", etc.). We only require
    that *some* non-empty description accompanies the True flag so callers
    can build a meaningful block message.
    """
    is_hardline, description = detect_hardline_command(command)
    assert is_hardline is True, (
        f"shell/interpreter -c payload should be hardline-blocked, "
        f"but detect_hardline_command returned False for: {command!r}"
    )
    assert isinstance(description, str) and description.strip(), (
        f"hardline match must include a non-empty description; got "
        f"{description!r} for {command!r}"
    )


@pytest.mark.parametrize("command", _SHELL_PAYLOAD_NEGATIVE_CASES)
def test_shell_payload_negative_is_not_hardline(command):
    """Benign ``-c`` payloads that only mention the words must pass.

    These commands are not actually invoking ``rm``/``reboot`` -- they are
    string literals fed to ``print`` or ``echo``. The hardline floor must
    not return a false positive on them, otherwise harmless logging and
    documentation snippets would be unconditionally blocked.
    """
    assert detect_hardline_command(command) == (False, None), (
        f"benign -c payload was unexpectedly hardline-blocked: {command!r}"
    )
