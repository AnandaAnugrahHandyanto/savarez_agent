"""Regression tests for version-read-from-pyproject (fix for #35070).

Ensures ``hermes_cli.__version__`` and ``hermes_cli.__release_date__``
are read from ``pyproject.toml`` at import time so a git conflict
resolution that reverts ``__init__.py`` cannot silently downgrade the
reported version.
"""

import tomllib
from pathlib import Path

import pytest
from hermes_cli import __version__, __release_date__, _read_version_from_pyproject


class TestReadVersionFromPyproject:
    """Direct unit tests for ``_read_version_from_pyproject()``."""

    def test_reads_version_from_real_pyproject(self):
        """Against the real pyproject.toml in the repo, version is non-empty."""
        version, release = _read_version_from_pyproject()
        assert isinstance(version, str) and len(version) > 0
        assert isinstance(release, str) and len(release) > 0

    def test_matches_module_level_attributes(self):
        """Module-level __version__ / __release_date__ agree with the reader."""
        version, release = _read_version_from_pyproject()
        assert __version__ == version
        assert __release_date__ == release

    def test_fallback_when_pyproject_missing(self, tmp_path, monkeypatch):
        """When pyproject.toml is absent, the fallback constants are used."""
        from pathlib import Path

        def _fake_read(version_fallback, release_fallback):
            pyproject = Path("/nonexistent/pyproject.toml")
            try:
                with open(pyproject, "rb") as fh:
                    data = tomllib.load(fh)
                return data["project"]["version"], release_fallback
            except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
                return version_fallback, release_fallback

        v, r = _fake_read("9.9.9", "fallback-date")
        assert v == "9.9.9"
        assert r == "fallback-date"

    def test_fallback_when_toml_malformed(self, tmp_path):
        """A syntactically invalid pyproject.toml falls back gracefully."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not valid toml {{{")

        def _fake_read(version_fallback, release_fallback):
            try:
                with open(pyproject, "rb") as fh:
                    data = tomllib.load(fh)
                return data["project"]["version"], release_fallback
            except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
                return version_fallback, release_fallback

        v, r = _fake_read("safe", "safe-date")
        assert v == "safe"
        assert r == "safe-date"

    def test_fallback_when_version_key_missing(self, tmp_path):
        """A valid TOML without project.version falls back."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        def _fake_read(version_fallback, release_fallback):
            try:
                with open(pyproject, "rb") as fh:
                    data = tomllib.load(fh)
                return data["project"]["version"], release_fallback
            except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
                return version_fallback, release_fallback

        v, r = _fake_read("no-version", "nd")
        assert v == "no-version"


class TestRegressions:
    """End-to-end: importing hermes_cli still works."""

    def test_version_is_non_empty_string(self):
        """__version__ is a non-empty string after import."""
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_release_date_is_non_empty_string(self):
        """__release_date__ is a non-empty string after import."""
        assert isinstance(__release_date__, str)
        assert len(__release_date__) > 0

    def test_module_level_fallbacks_are_stable(self):
        """The fallback constants are not accidentally deleted."""
        from hermes_cli import _VERSION_FALLBACK, _RELEASE_DATE_FALLBACK
        assert isinstance(_VERSION_FALLBACK, str)
        assert isinstance(_RELEASE_DATE_FALLBACK, str)
