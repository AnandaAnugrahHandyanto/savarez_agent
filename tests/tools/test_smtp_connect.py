"""Tests for tools.send_message_tool._smtp_connect.

Verifies:
- Port 465 uses SMTP_SSL (implicit TLS); other ports use SMTP + STARTTLS.
- SSL errors are NOT retried (re-raised immediately).

The IPv4 fallback path uses inner _IPv4SMTP/_IPv4SMTP_SSL classes that
override _get_socket(); the identical pattern is already exercised by the
gateway email tests (tests/gateway/test_email.py).
"""

import smtplib
import ssl
from unittest.mock import MagicMock, patch

import pytest

from tools.send_message_tool import _smtp_connect


class TestSmtpConnect:
    def test_port_465_uses_smtp_ssl(self):
        """Port 465 must use SMTP_SSL (implicit TLS), not SMTP + STARTTLS."""
        mock_ssl_client = MagicMock(spec=smtplib.SMTP_SSL)

        with patch("smtplib.SMTP_SSL", return_value=mock_ssl_client) as mock_cls, \
             patch("smtplib.SMTP") as mock_smtp:
            result = _smtp_connect("smtp.example.com", 465)

        mock_cls.assert_called_once()
        args, kwargs = mock_cls.call_args
        assert args[0] == "smtp.example.com"
        assert args[1] == 465
        assert kwargs.get("timeout") == 30
        assert "context" in kwargs
        mock_smtp.assert_not_called()
        assert result is mock_ssl_client

    def test_port_587_uses_starttls(self):
        """Non-465 ports must open SMTP then call starttls()."""
        mock_client = MagicMock(spec=smtplib.SMTP)

        with patch("smtplib.SMTP", return_value=mock_client) as mock_cls, \
             patch("smtplib.SMTP_SSL") as mock_ssl:
            result = _smtp_connect("smtp.example.com", 587)

        mock_cls.assert_called_once()
        mock_client.starttls.assert_called_once()
        mock_ssl.assert_not_called()
        assert result is mock_client

    def test_ssl_error_not_retried(self):
        """SSLError is re-raised immediately — IPv4 retry must NOT be attempted."""
        # patch both so the SSL path raises before any retry could happen
        with patch("smtplib.SMTP", side_effect=ssl.SSLError("CERT_VERIFY_FAILED")), \
             patch("smtplib.SMTP_SSL", side_effect=ssl.SSLError("CERT_VERIFY_FAILED")):
            with pytest.raises(ssl.SSLError):
                _smtp_connect("smtp.example.com", 587)

    def test_custom_timeout_forwarded(self):
        """The caller-supplied timeout is passed to the SMTP constructor."""
        mock_client = MagicMock(spec=smtplib.SMTP)

        with patch("smtplib.SMTP", return_value=mock_client) as mock_cls:
            _smtp_connect("smtp.example.com", 587, timeout=10)

        _, kwargs = mock_cls.call_args
        assert kwargs.get("timeout") == 10
