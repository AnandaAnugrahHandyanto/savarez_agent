"""Unit tests for the SSL CA certificate diagnostic guard.

These tests exercise the ``check_ssl_ca_bundle()`` pre-flight in
in isolation — no HTTP requests are made.
"""

from pathlib import Path
from typing import Generator
from types import ModuleType
from unittest.mock import patch

import pytest

from agent.errors import SSLConfigurationError
from agent.ssl_guard import check_ssl_ca_bundle


# Helpers -----------------------------------------------------------------


def _make_bogus_certifi(path: Path) -> ModuleType:
    """Build a minimal fake ``certifi`` module whose ``where()`` points
to *path*."""
    import types
    mod = types.ModuleType("certifi")
    setattr(mod, "where", lambda: str(path))
    return mod


@pytest.fixture
def fake_ca_file(tmp_path: Path) -> Path:
    ca = tmp_path / "cacert.pem"
    ca.write_text("BOGUS PEM\n")
    return ca


# Baseline success --------------------------------------------------------


def test_check_ssl_ok(fake_ca_file: Path) -> None:
    """When the CA bundle exists and is non-empty, check_ssl_ca_bundle
passes without raising."""
    bogus = _make_bogus_certifi(fake_ca_file)
    with patch.dict(
        "sys.modules",
        {"certifi": bogus},
    ), patch("agent.ssl_guard.ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value.get_ca_certs.return_value = ["cert"]
        check_ssl_ca_bundle()
    mock_ctx.assert_called_once_with(cafile=str(fake_ca_file))


# Import-failure paths ----------------------------------------------------


def test_check_ssl_missing_certifi_package() -> None:
    """Missing ``certifi`` raises SSLConfigurationError with a clear hint."""
    with patch.dict("sys.modules", {"certifi": None}):
        with pytest.raises(SSLConfigurationError) as exc_info:
            check_ssl_ca_bundle()
    err = str(exc_info.value)
    assert "certifi" in err or "not installed" in err


# Bundle-missing / empty paths ------------------------------------------


def test_check_ssl_missing_bundle_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pem"
    bogus = _make_bogus_certifi(missing)
    with patch.dict("sys.modules", {"certifi": bogus}):
        with pytest.raises(SSLConfigurationError) as exc_info:
            check_ssl_ca_bundle()
    assert "missing" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()


def test_check_ssl_empty_bundle_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.pem"
    empty.write_text("")
    bogus = _make_bogus_certifi(empty)
    with patch.dict("sys.modules", {"certifi": bogus}):
        with pytest.raises(SSLConfigurationError) as exc_info:
            check_ssl_ca_bundle()
    assert "empty" in str(exc_info.value).lower()


# Load failure — corrupted PEM ------------------------------------------


def test_check_ssl_corrupt_bundle_load(tmp_path: Path) -> None:
    corrupt = tmp_path / "bad.pem"
    corrupt.write_text("nope")
    bogus = _make_bogus_certifi(corrupt)
    with patch.dict("sys.modules", {"certifi": bogus}), \
         patch("agent.ssl_guard.ssl.create_default_context") as mock_ctx:
        mock_ctx.side_effect = RuntimeError("can't load")
        with pytest.raises(SSLConfigurationError) as exc_info:
            check_ssl_ca_bundle()
    err = str(exc_info.value)
    assert "cannot be loaded" in err.lower()


# System-store fallback (macOS Keychain etc.) -----------------------------


def test_check_ssl_empty_bundle_but_system_store_ok(tmp_path: Path) -> None:
    """If certifi returns an empty bundle but the system trust store works,
we DON'T raise — we just log and return."""
    empty = tmp_path / "empty.pem"
    empty.write_text("not-a-cert")
    bogus = _make_bogus_certifi(empty)

    def _fake_create_ctx(**kw):
        class _Ctx:
            def get_ca_certs(self):
                if kw.get("cafile"):
                    return []  # certifi empty
                return ["system-cert"]  # fallback ok
        return _Ctx()

    with patch.dict("sys.modules", {"certifi": bogus}):
        with patch("agent.ssl_guard.ssl.create_default_context", _fake_create_ctx):
            check_ssl_ca_bundle()  # should not raise


def test_check_ssl_empty_bundle_and_system_store_also_empty(tmp_path: Path) -> None:
    """If both certifi and the system store are empty, we DO raise."""
    empty = tmp_path / "empty.pem"
    empty.write_text("")
    bogus = _make_bogus_certifi(empty)

    def _fake_create_ctx(**kw):
        class _Ctx:
            def get_ca_certs(self):
                return []
        return _Ctx()

    with patch.dict("sys.modules", {"certifi": bogus}):
        with patch("agent.ssl_guard.ssl.create_default_context", _fake_create_ctx), \
             pytest.raises(SSLConfigurationError) as exc_info:
            check_ssl_ca_bundle()
    assert "missing" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()
