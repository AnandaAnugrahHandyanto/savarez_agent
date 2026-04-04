"""Tests for _apply_profile_override() in hermes_cli/main.py.

The function runs at module import time and mutates os.environ and sys.argv.
We test it by calling it directly with monkeypatched state.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch


# We can't import hermes_cli.main at module level because
# _apply_profile_override() fires on import.  Instead we import
# the function inside each test after setting up the environment.


def _get_override_fn():
    """Import _apply_profile_override without triggering it at module level."""
    import importlib
    spec = importlib.util.spec_from_file_location(
        "_main_override",
        Path(__file__).parent.parent.parent / "hermes_cli" / "main.py",
    )
    # We only need the function source, not the full module.
    # Read it and exec just the function.
    src = (Path(__file__).parent.parent.parent / "hermes_cli" / "main.py").read_text()

    # Extract the function + its imports
    import re
    fn_match = re.search(
        r"(def _apply_profile_override\(\).*?)(?=\n_apply_profile_override\(\)|\nclass |\ndef [a-z])",
        src, re.DOTALL,
    )
    assert fn_match, "Could not find _apply_profile_override in main.py"
    fn_source = fn_match.group(1)

    ns = {"os": os, "sys": sys, "Path": Path}
    exec(fn_source, ns)
    return ns["_apply_profile_override"]


@pytest.fixture
def active_profile_file(tmp_path, monkeypatch):
    """Create a fake active_profile file and point HOME at tmp_path."""
    hermes_dir = tmp_path / ".hermes"
    hermes_dir.mkdir()
    active = hermes_dir / "active_profile"

    # Also create the profiles dir so resolve_profile_env works
    profiles_dir = hermes_dir / "profiles"
    profiles_dir.mkdir()

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return active


class TestProfileOverride:
    """Tests for the HERMES_HOME / active_profile / -p priority chain."""

    def test_hermes_home_set_skips_active_profile(self, active_profile_file, monkeypatch):
        """When HERMES_HOME is already in env and no -p flag, active_profile is skipped."""
        active_profile_file.write_text("med")
        monkeypatch.setenv("HERMES_HOME", "/custom/hermes/path")
        monkeypatch.setattr(sys, "argv", ["hermes", "chat"])

        fn = _get_override_fn()
        fn()

        # HERMES_HOME should be unchanged — active_profile was not consulted
        assert os.environ["HERMES_HOME"] == "/custom/hermes/path"

    def test_explicit_p_flag_overrides_env(self, active_profile_file, monkeypatch):
        """The -p flag takes highest priority, even over a pre-set HERMES_HOME."""
        active_profile_file.write_text("ignored")
        # Create the target profile directory
        profile_dir = active_profile_file.parent / "profiles" / "coder"
        profile_dir.mkdir(parents=True)

        monkeypatch.setenv("HERMES_HOME", "/original/path")
        monkeypatch.setattr(sys, "argv", ["hermes", "-p", "coder", "chat"])

        fn = _get_override_fn()
        fn()

        # -p coder should override HERMES_HOME to the coder profile
        assert os.environ["HERMES_HOME"] == str(profile_dir)

    def test_empty_hermes_home_falls_through(self, active_profile_file, monkeypatch):
        """HERMES_HOME="" (empty) should NOT block active_profile lookup."""
        active_profile_file.write_text("med")
        # Create the med profile directory
        profile_dir = active_profile_file.parent / "profiles" / "med"
        profile_dir.mkdir(parents=True)

        monkeypatch.setenv("HERMES_HOME", "")
        monkeypatch.setattr(sys, "argv", ["hermes", "chat"])

        fn = _get_override_fn()
        fn()

        # Empty HERMES_HOME should fall through, active_profile "med" should be used
        assert os.environ["HERMES_HOME"] == str(profile_dir)

    def test_no_env_no_flag_uses_active_profile(self, active_profile_file, monkeypatch):
        """With no HERMES_HOME and no -p flag, active_profile is used."""
        active_profile_file.write_text("med")
        # Create the med profile directory
        profile_dir = active_profile_file.parent / "profiles" / "med"
        profile_dir.mkdir(parents=True)

        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setattr(sys, "argv", ["hermes", "chat"])

        fn = _get_override_fn()
        fn()

        # Should read active_profile and set HERMES_HOME to med
        assert os.environ["HERMES_HOME"] == str(profile_dir)

    def test_no_active_profile_file_no_change(self, active_profile_file, monkeypatch):
        """With no HERMES_HOME, no -p, and no active_profile file, nothing changes."""
        # Don't write active_profile file
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setattr(sys, "argv", ["hermes", "chat"])

        fn = _get_override_fn()
        fn()

        # HERMES_HOME should not be set
        assert "HERMES_HOME" not in os.environ or os.environ.get("HERMES_HOME") == ""
