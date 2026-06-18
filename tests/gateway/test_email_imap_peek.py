"""
Test that EmailAdapter respects the imap_peek config option.

Verifies the fetch command uses BODY.PEEK[] by default and RFC822 when
imap_peek is explicitly set to false.
"""

from unittest.mock import MagicMock, patch

from gateway.config import Platform, PlatformConfig
from gateway.platforms.email import EmailAdapter


def _make_adapter(extra: dict) -> EmailAdapter:
    config = MagicMock(spec=PlatformConfig)
    config.extra = extra
    return EmailAdapter(config)


def test_imap_peek_defaults_to_true():
    """Without explicit config, imap_peek should default to True (BODY.PEEK[])."""
    adapter = _make_adapter({})
    assert adapter._imap_peek is True


def test_imap_peek_false_restores_rfc822():
    """Setting imap_peek: false should disable PEEK and use RFC822."""
    adapter = _make_adapter({"imap_peek": False})
    assert adapter._imap_peek is False


def test_imap_peek_true_explicit():
    """Explicitly setting imap_peek: true should enable PEEK."""
    adapter = _make_adapter({"imap_peek": True})
    assert adapter._imap_peek is True


def test_imap_peek_string_false():
    """String 'false' should be coerced to bool False."""
    adapter = _make_adapter({"imap_peek": "false"})
    assert adapter._imap_peek is False


def test_imap_peek_string_true():
    """String 'true' should be coerced to bool True."""
    adapter = _make_adapter({"imap_peek": "true"})
    assert adapter._imap_peek is True