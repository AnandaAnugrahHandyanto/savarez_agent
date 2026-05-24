"""Tests for the cmd.exe shim metacharacter detection helpers added
under #31419 (Windows ``.cmd`` / ``.bat`` argv re-parse hazard).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from hermes_cli._subprocess_compat import (
    CMD_METACHARS,
    arg_contains_cmd_metachars,
    is_windows_shim_target,
)


# ----------------------------------------------------------------------
# CMD_METACHARS
# ----------------------------------------------------------------------


def test_cmd_metachars_includes_core_shell_operators():
    """The default set must cover the operators that re-tokenize argv
    inside ``cmd.exe /c``. Without these, a .cmd shim mis-parses any
    argument containing them.
    """
    for ch in '|&<>^"':
        assert ch in CMD_METACHARS, f"missing metachar in default set: {ch!r}"


def test_cmd_metachars_is_immutable():
    """``CMD_METACHARS`` is a frozenset so callers can't accidentally
    mutate the shared default and leak state across modules.
    """
    assert isinstance(CMD_METACHARS, frozenset)


# ----------------------------------------------------------------------
# is_windows_shim_target
# ----------------------------------------------------------------------


def test_is_windows_shim_target_returns_false_off_windows():
    """Detection is a no-op on POSIX — there are no .cmd / .bat shims
    to worry about, and we don't want callers branching on platform.
    """
    with patch("hermes_cli._subprocess_compat.IS_WINDOWS", False):
        assert not is_windows_shim_target(r"C:\path\to\npm.cmd")
        assert not is_windows_shim_target(r"C:\path\to\foo.bat")
        assert not is_windows_shim_target("/usr/bin/npm")


def test_is_windows_shim_target_detects_cmd_and_bat_case_insensitive():
    """On Windows, both ``.cmd`` and ``.bat`` shims need protection,
    and the check is case-insensitive because paths round-trip through
    different cases regularly.
    """
    with patch("hermes_cli._subprocess_compat.IS_WINDOWS", True):
        assert is_windows_shim_target(r"C:\path\to\npm.cmd")
        assert is_windows_shim_target(r"C:\PATH\TO\NPM.CMD")
        assert is_windows_shim_target(r"foo.bat")
        assert is_windows_shim_target(r"FOO.Bat")
        # Negatives — .exe is not a shim
        assert not is_windows_shim_target(r"C:\path\to\python.exe")
        assert not is_windows_shim_target(r"C:\path\to\npm")
        assert not is_windows_shim_target("")
        assert not is_windows_shim_target(None)


# ----------------------------------------------------------------------
# arg_contains_cmd_metachars
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "arg",
    [
        "echo a | echo b",            # pipe — re-tokenizes argv
        "foo > out.txt",              # redirect — truncates a file
        "foo < in.txt",               # input redirect
        "a & b",                      # command sequencer
        "say \"hello\"",              # quote — affects cmd.exe tokenization
        "^echo",                      # cmd.exe escape character
        "mixed | content > here",
    ],
)
def test_arg_contains_cmd_metachars_detects_hazardous_argv(arg):
    """Any argv containing a default metacharacter is flagged. These are
    exactly the inputs that would be silently mis-parsed when passed
    through a ``.cmd`` / ``.bat`` shim.
    """
    assert arg_contains_cmd_metachars(arg), f"missed hazard: {arg!r}"


@pytest.mark.parametrize(
    "arg",
    [
        "",                           # empty — no hazard
        "plain-string-no-shell-ops",
        "a-b-c.d_e:f/g+h",            # punctuation that is NOT a cmd op
        "中文 emoji 🎉",                # non-ASCII passes through cleanly
        "/path/to/file.txt",
        "--flag=value",
    ],
)
def test_arg_contains_cmd_metachars_does_not_flag_safe_argv(arg):
    """The default character set is small and prefix-anchored to keep
    the false-positive rate low — common argv values must not trip.
    """
    assert not arg_contains_cmd_metachars(arg), f"false positive: {arg!r}"


def test_arg_contains_cmd_metachars_extra_extends_default_set():
    """Callers targeting a batch file (where ``%`` is also metachar)
    can extend the detected set per call.
    """
    arg = "echo %PATH%"
    assert not arg_contains_cmd_metachars(arg)  # % is NOT in default set
    assert arg_contains_cmd_metachars(arg, extra="%")  # explicit opt-in


def test_arg_contains_cmd_metachars_returns_false_for_empty_string():
    assert not arg_contains_cmd_metachars("")
