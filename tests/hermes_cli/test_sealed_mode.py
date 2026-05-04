"""Tests for HERMES_SEALED env var support in profile management.

Sealed mode (HERMES_SEALED=true) locks the runtime to a single profile —
opt-in deployment posture for multi-tenant SaaS / sealed-image scenarios.
See hermes_constants.is_sealed and hermes_cli.profiles.SealedProfileError.
"""

from pathlib import Path

import pytest

from hermes_constants import is_sealed, get_sealed_profile_name
from hermes_cli.profiles import (
    SealedProfileError,
    create_profile,
    delete_profile,
    export_profile,
    import_profile,
    list_profiles,
    rename_profile,
    set_active_profile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sealed_env(tmp_path, monkeypatch):
    """Set up a sealed-mode test environment with one captain profile.

    Layout::

        tmp_path/
        └── .hermes/
            └── profiles/
                ├── captain/
                │   └── (one profile dir to pretend it's the sealed one)
                └── other/
                    └── (a sibling profile that should be hidden)

    Sealed mode is configured to pin the captain profile.
    """
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    profiles_root = tmp_path / ".hermes" / "profiles"
    (profiles_root / "captain").mkdir(parents=True)
    (profiles_root / "other").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(profiles_root / "captain"))
    monkeypatch.setenv("HERMES_SEALED", "true")
    monkeypatch.setenv("HERMES_PROFILE_NAME", "captain")
    return tmp_path


@pytest.fixture()
def unsealed_env(tmp_path, monkeypatch):
    """Same layout as sealed_env but without HERMES_SEALED set."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    profiles_root = tmp_path / ".hermes" / "profiles"
    (profiles_root / "captain").mkdir(parents=True)
    (profiles_root / "other").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.delenv("HERMES_SEALED", raising=False)
    monkeypatch.delenv("HERMES_PROFILE_NAME", raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# is_sealed()
# ---------------------------------------------------------------------------

class TestIsSealed:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "YES", "on", "ON"])
    def test_truthy_values_return_true(self, value, monkeypatch):
        monkeypatch.setenv("HERMES_SEALED", value)
        assert is_sealed() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "anything-else"])
    def test_non_truthy_values_return_false(self, value, monkeypatch):
        monkeypatch.setenv("HERMES_SEALED", value)
        assert is_sealed() is False

    def test_unset_returns_false(self, monkeypatch):
        monkeypatch.delenv("HERMES_SEALED", raising=False)
        assert is_sealed() is False

    def test_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("HERMES_SEALED", "  true  ")
        assert is_sealed() is True


# ---------------------------------------------------------------------------
# get_sealed_profile_name()
# ---------------------------------------------------------------------------

class TestGetSealedProfileName:
    def test_returns_none_when_not_sealed(self, monkeypatch):
        monkeypatch.delenv("HERMES_SEALED", raising=False)
        monkeypatch.setenv("HERMES_PROFILE_NAME", "captain")
        assert get_sealed_profile_name() is None

    def test_explicit_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("HERMES_SEALED", "true")
        monkeypatch.setenv("HERMES_PROFILE_NAME", "captain")
        monkeypatch.setenv("HERMES_HOME", "/opt/data/profiles/some-other-name")
        assert get_sealed_profile_name() == "captain"

    def test_inferred_from_hermes_home_path(self, monkeypatch):
        monkeypatch.setenv("HERMES_SEALED", "true")
        monkeypatch.delenv("HERMES_PROFILE_NAME", raising=False)
        monkeypatch.setenv("HERMES_HOME", "/opt/data/profiles/captain")
        assert get_sealed_profile_name() == "captain"

    def test_returns_none_when_cant_be_determined(self, monkeypatch):
        monkeypatch.setenv("HERMES_SEALED", "true")
        monkeypatch.delenv("HERMES_PROFILE_NAME", raising=False)
        monkeypatch.setenv("HERMES_HOME", "/opt/data")  # not under profiles/
        assert get_sealed_profile_name() is None


# ---------------------------------------------------------------------------
# list_profiles() filtering
# ---------------------------------------------------------------------------

class TestListProfilesSealed:
    def test_sealed_returns_only_configured_profile(self, sealed_env):
        profiles = list_profiles()
        names = [p.name for p in profiles]
        assert names == ["captain"]
        assert "other" not in names
        assert "default" not in names  # default profile not exposed in sealed mode

    def test_unsealed_returns_all_profiles(self, unsealed_env):
        profiles = list_profiles()
        names = sorted(p.name for p in profiles)
        # Order: default first, then sorted alphabetically
        assert "captain" in names
        assert "other" in names


# ---------------------------------------------------------------------------
# Mutation operations refused in sealed mode
# ---------------------------------------------------------------------------

class TestMutationsRefusedSealed:
    def test_create_profile_raises_in_sealed(self, sealed_env):
        with pytest.raises(SealedProfileError, match="create profile"):
            create_profile("anything-new")

    def test_delete_profile_raises_in_sealed(self, sealed_env):
        with pytest.raises(SealedProfileError, match="delete profile"):
            delete_profile("captain")

    def test_rename_profile_raises_in_sealed(self, sealed_env):
        with pytest.raises(SealedProfileError, match="rename profile"):
            rename_profile("captain", "captain-renamed")

    def test_export_profile_raises_in_sealed(self, sealed_env, tmp_path):
        with pytest.raises(SealedProfileError, match="export profile"):
            export_profile("captain", str(tmp_path / "out.tar.gz"))

    def test_import_profile_raises_in_sealed(self, sealed_env, tmp_path):
        # Pre-create a fake archive — the gate trips before file checks.
        archive = tmp_path / "fake.tar.gz"
        archive.write_bytes(b"")
        with pytest.raises(SealedProfileError, match="import profile"):
            import_profile(str(archive))

    def test_set_active_to_other_profile_raises(self, sealed_env):
        with pytest.raises(SealedProfileError, match="locked to profile 'captain'"):
            set_active_profile("other")

    def test_set_active_to_sealed_profile_is_noop(self, sealed_env):
        # Setting to the already-sealed profile should be a clean no-op
        # (no error, no state change required).
        set_active_profile("captain")  # should not raise


# ---------------------------------------------------------------------------
# Backward compatibility — unsealed mode unchanged
# ---------------------------------------------------------------------------

class TestUnsealedModeUnchanged:
    def test_create_profile_works_in_unsealed(self, unsealed_env):
        # Should not raise SealedProfileError; downstream logic is the
        # existing unchanged behavior (and may raise its own errors,
        # which is fine — we only care that the sealed gate is absent).
        path = create_profile("brand-new")
        assert path.is_dir()

    def test_set_active_profile_validates_normally_in_unsealed(self, unsealed_env):
        # Existing validation for non-existent profiles should fire.
        with pytest.raises(FileNotFoundError):
            set_active_profile("does-not-exist")
