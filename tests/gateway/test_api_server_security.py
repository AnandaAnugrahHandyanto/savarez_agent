"""Tests for API server security hardening.

1. Timing-safe API key comparison (hmac.compare_digest)
2. Error responses do not leak exception details to callers
"""

import hmac
from unittest.mock import MagicMock, patch
import pytest


class TestTimingSafeAuth:
    """API key comparison must use hmac.compare_digest, not ==."""

    def test_compare_digest_used_in_source(self):
        """Verify the auth method uses hmac.compare_digest."""
        import inspect
        from gateway.platforms.api_server import APIServerAdapter

        source = inspect.getsource(APIServerAdapter._check_auth)
        assert "compare_digest" in source
        assert "token ==" not in source


class TestErrorSanitization:
    """Error responses must not leak internal exception details."""

    def test_openai_error_helper_no_exception_interpolation(self):
        """_openai_error should not be called with f-string exception details."""
        import inspect
        from gateway.platforms import api_server

        source = inspect.getsource(api_server)
        # No f-string interpolation of exceptions in _openai_error calls
        assert '_openai_error(f"Internal server error: {e}"' not in source
        assert '_openai_error(f"Internal server error: {' not in source

    def test_cron_endpoints_do_not_return_raw_exception(self):
        """Cron error handlers must not return str(e) to callers."""
        import inspect
        from gateway.platforms import api_server

        source = inspect.getsource(api_server)
        # No raw str(e) in JSON responses
        assert '{"error": str(e)}' not in source
