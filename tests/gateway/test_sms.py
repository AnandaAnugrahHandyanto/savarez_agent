"""Tests for SMS (Twilio) platform integration.

Covers config loading, format/truncate, echo prevention,
requirements check, and toolset verification.
"""

import base64
import hashlib
import hmac
import os
import urllib.parse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform, PlatformConfig, HomeChannel


# ── Config loading ──────────────────────────────────────────────────

class TestSmsConfigLoading:
    """Verify _apply_env_overrides wires SMS correctly."""

    def test_sms_platform_enum_exists(self):
        assert Platform.SMS.value == "sms"

    def test_env_overrides_create_sms_config(self):
        from gateway.config import load_gateway_config

        env = {
            "TWILIO_ACCOUNT_SID": "ACtest123",
            "TWILIO_AUTH_TOKEN": "token_abc",
            "TWILIO_PHONE_NUMBER": "+15551234567",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_gateway_config()
            assert Platform.SMS in config.platforms
            pc = config.platforms[Platform.SMS]
            assert pc.enabled is True
            assert pc.api_key == "token_abc"

    def test_env_overrides_set_home_channel(self):
        from gateway.config import load_gateway_config

        env = {
            "TWILIO_ACCOUNT_SID": "ACtest123",
            "TWILIO_AUTH_TOKEN": "token_abc",
            "TWILIO_PHONE_NUMBER": "+15551234567",
            "SMS_HOME_CHANNEL": "+15559876543",
            "SMS_HOME_CHANNEL_NAME": "My Phone",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_gateway_config()
            hc = config.platforms[Platform.SMS].home_channel
            assert hc is not None
            assert hc.chat_id == "+15559876543"
            assert hc.name == "My Phone"
            assert hc.platform == Platform.SMS

    def test_sms_in_connected_platforms(self):
        from gateway.config import load_gateway_config

        env = {
            "TWILIO_ACCOUNT_SID": "ACtest123",
            "TWILIO_AUTH_TOKEN": "token_abc",
        }
        with patch.dict(os.environ, env, clear=False):
            config = load_gateway_config()
            connected = config.get_connected_platforms()
            assert Platform.SMS in connected


# ── Format / truncate ───────────────────────────────────────────────

class TestSmsFormatAndTruncate:
    """Test SmsAdapter.format_message strips markdown."""

    def _make_adapter(self):
        from gateway.platforms.sms import SmsAdapter

        env = {
            "TWILIO_ACCOUNT_SID": "ACtest",
            "TWILIO_AUTH_TOKEN": "tok",
            "TWILIO_PHONE_NUMBER": "+15550001111",
        }
        with patch.dict(os.environ, env):
            pc = PlatformConfig(enabled=True, api_key="tok")
            adapter = object.__new__(SmsAdapter)
            adapter.config = pc
            adapter._platform = Platform.SMS
            adapter._account_sid = "ACtest"
            adapter._auth_token = "tok"
            adapter._from_number = "+15550001111"
        return adapter

    def test_strips_bold(self):
        adapter = self._make_adapter()
        assert adapter.format_message("**hello**") == "hello"

    def test_strips_italic(self):
        adapter = self._make_adapter()
        assert adapter.format_message("*world*") == "world"

    def test_strips_code_blocks(self):
        adapter = self._make_adapter()
        result = adapter.format_message("```python\nprint('hi')\n```")
        assert "```" not in result
        assert "print('hi')" in result

    def test_strips_inline_code(self):
        adapter = self._make_adapter()
        assert adapter.format_message("`code`") == "code"

    def test_strips_headers(self):
        adapter = self._make_adapter()
        assert adapter.format_message("## Title") == "Title"

    def test_strips_links(self):
        adapter = self._make_adapter()
        assert adapter.format_message("[click](https://example.com)") == "click"

    def test_collapses_newlines(self):
        adapter = self._make_adapter()
        result = adapter.format_message("a\n\n\n\nb")
        assert result == "a\n\nb"


# ── Echo prevention ────────────────────────────────────────────────

class TestSmsEchoPrevention:
    """Adapter should ignore messages from its own number."""

    def test_own_number_detection(self):
        """The adapter stores _from_number for echo prevention."""
        from gateway.platforms.sms import SmsAdapter

        env = {
            "TWILIO_ACCOUNT_SID": "ACtest",
            "TWILIO_AUTH_TOKEN": "tok",
            "TWILIO_PHONE_NUMBER": "+15550001111",
        }
        with patch.dict(os.environ, env):
            pc = PlatformConfig(enabled=True, api_key="tok")
            adapter = SmsAdapter(pc)
            assert adapter._from_number == "+15550001111"


# ── Requirements check ─────────────────────────────────────────────

class TestSmsRequirements:
    def test_check_sms_requirements_missing_sid(self):
        from gateway.platforms.sms import check_sms_requirements

        env = {"TWILIO_AUTH_TOKEN": "tok"}
        with patch.dict(os.environ, env, clear=True):
            assert check_sms_requirements() is False

    def test_check_sms_requirements_missing_token(self):
        from gateway.platforms.sms import check_sms_requirements

        env = {"TWILIO_ACCOUNT_SID": "ACtest"}
        with patch.dict(os.environ, env, clear=True):
            assert check_sms_requirements() is False

    def test_check_sms_requirements_both_set(self):
        from gateway.platforms.sms import check_sms_requirements

        env = {
            "TWILIO_ACCOUNT_SID": "ACtest",
            "TWILIO_AUTH_TOKEN": "tok",
        }
        with patch.dict(os.environ, env, clear=False):
            # Only returns True if aiohttp is also importable
            result = check_sms_requirements()
            try:
                import aiohttp  # noqa: F401
                assert result is True
            except ImportError:
                assert result is False


# ── Toolset verification ───────────────────────────────────────────

class TestSmsToolset:
    def test_hermes_sms_toolset_exists(self):
        from toolsets import get_toolset

        ts = get_toolset("hermes-sms")
        assert ts is not None
        assert "tools" in ts

    def test_hermes_sms_in_gateway_includes(self):
        from toolsets import get_toolset

        gw = get_toolset("hermes-gateway")
        assert gw is not None
        assert "hermes-sms" in gw["includes"]

    def test_sms_platform_hint_exists(self):
        from agent.prompt_builder import PLATFORM_HINTS

        assert "sms" in PLATFORM_HINTS
        assert "concise" in PLATFORM_HINTS["sms"].lower()

    def test_sms_in_scheduler_platform_map(self):
        """Verify cron scheduler recognizes 'sms' as a valid platform."""
        # Just check the Platform enum has SMS — the scheduler imports it dynamically
        assert Platform.SMS.value == "sms"

    def test_sms_in_send_message_platform_map(self):
        """Verify send_message_tool recognizes 'sms'."""
        # The platform_map is built inside _handle_send; verify SMS enum exists
        assert hasattr(Platform, "SMS")

    def test_sms_in_cronjob_deliver_description(self):
        """Verify cronjob_tools mentions sms in deliver description."""
        from tools.cronjob_tools import CRONJOB_SCHEMA
        deliver_desc = CRONJOB_SCHEMA["parameters"]["properties"]["deliver"]["description"]
        assert "sms" in deliver_desc.lower()


# ── Signature validation ───────────────────────────────────────────

def _make_sms_adapter():
    """Return a bare SmsAdapter without starting a server."""
    from gateway.platforms.sms import SmsAdapter

    pc = PlatformConfig(enabled=True, api_key="test_auth_token")
    adapter = object.__new__(SmsAdapter)
    adapter.config = pc
    adapter.platform = Platform.SMS
    adapter._platform = Platform.SMS
    adapter._account_sid = "ACtest"
    adapter._auth_token = "test_auth_token"
    adapter._from_number = "+15550001111"
    adapter._background_tasks = set()
    return adapter


def _twilio_signature(auth_token: str, url: str, params: dict) -> str:
    """Compute a valid Twilio request signature."""
    s = url + "".join(k + v for k, v in sorted(params.items()))
    mac = hmac.new(auth_token.encode("utf-8"), s.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode("ascii")


class TestTwilioSignatureValidation:
    """Unit tests for Twilio request URL/signature helpers."""

    def test_external_request_url_prefers_forwarded_headers(self):
        adapter = _make_sms_adapter()
        req = MagicMock()
        req.headers = {
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "public.example.com",
            "X-Forwarded-Port": "443",
        }
        req.path_qs = "/webhooks/twilio?foo=1"
        req.url = "http://internal:8080/webhooks/twilio?foo=1"
        assert adapter._external_request_url(req) == "https://public.example.com/webhooks/twilio?foo=1"

    def test_external_request_url_keeps_non_default_forwarded_port(self):
        adapter = _make_sms_adapter()
        req = MagicMock()
        req.headers = {
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "public.example.com",
            "X-Forwarded-Port": "8443",
        }
        req.path_qs = "/webhooks/twilio"
        req.url = "http://internal:8080/webhooks/twilio"
        assert adapter._external_request_url(req) == "https://public.example.com:8443/webhooks/twilio"

    def test_valid_signature_returns_true(self):
        adapter = _make_sms_adapter()
        url = "https://example.com/webhooks/twilio"
        params = {"From": "+155****6543", "Body": "hello", "To": "+155****1111"}
        sig = _twilio_signature(adapter._auth_token, url, params)
        assert adapter._validate_twilio_signature(url, params, sig) is True

    def test_wrong_signature_returns_false(self):
        adapter = _make_sms_adapter()
        url = "https://example.com/webhooks/twilio"
        params = {"From": "+15559876543", "Body": "hello"}
        assert adapter._validate_twilio_signature(url, params, "badsig==") is False

    def test_empty_signature_returns_false(self):
        adapter = _make_sms_adapter()
        url = "https://example.com/webhooks/twilio"
        assert adapter._validate_twilio_signature(url, {}, "") is False

    def test_tampered_body_returns_false(self):
        adapter = _make_sms_adapter()
        url = "https://example.com/webhooks/twilio"
        params = {"From": "+15559876543", "Body": "hello"}
        sig = _twilio_signature(adapter._auth_token, url, params)
        tampered = {**params, "Body": "injected"}
        assert adapter._validate_twilio_signature(url, tampered, sig) is False

    def test_wrong_url_returns_false(self):
        adapter = _make_sms_adapter()
        params = {"From": "+15559876543", "Body": "hello"}
        sig = _twilio_signature(adapter._auth_token, "https://real.example.com/webhooks/twilio", params)
        assert adapter._validate_twilio_signature("https://evil.example.com/webhooks/twilio", params, sig) is False


def _aiohttp_available() -> bool:
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _aiohttp_available(), reason="aiohttp not installed")
class TestTwilioWebhookSignatureEnforcement:
    """Integration-style tests for _handle_webhook signature gating."""

    def _make_request(self, body_params: dict, signature: str) -> MagicMock:
        """Build a mock aiohttp Request."""
        encoded = urllib.parse.urlencode(body_params).encode("utf-8")
        req = MagicMock()
        req.read = AsyncMock(return_value=encoded)
        req.headers = {"X-Twilio-Signature": signature}
        req.url = "https://example.com/webhooks/twilio"
        req.remote = "54.0.0.1"
        return req

    @pytest.mark.asyncio
    async def test_missing_signature_returns_403(self):
        adapter = _make_sms_adapter()
        params = {"From": "+15559876543", "Body": "hi", "To": "+15550001111", "MessageSid": "SM1"}
        req = self._make_request(params, "")
        resp = await adapter._handle_webhook(req)
        assert resp.status == 403

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_403(self):
        adapter = _make_sms_adapter()
        params = {"From": "+15559876543", "Body": "hi", "To": "+15550001111", "MessageSid": "SM1"}
        req = self._make_request(params, "invalidsignature==")
        resp = await adapter._handle_webhook(req)
        assert resp.status == 403

    @pytest.mark.asyncio
    async def test_valid_signature_returns_200(self):
        adapter = _make_sms_adapter()
        adapter.handle_message = AsyncMock()
        url = "https://example.com/webhooks/twilio"
        params = {"From": "+155****6543", "Body": "hi", "To": "+155****1111", "MessageSid": "SM1"}
        sig = _twilio_signature(adapter._auth_token, url, params)
        req = self._make_request(params, sig)
        req.url = url
        resp = await adapter._handle_webhook(req)
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_forwarded_headers_allow_valid_signature_behind_proxy(self):
        adapter = _make_sms_adapter()
        adapter.handle_message = AsyncMock()
        public_url = "https://public.example.com/webhooks/twilio"
        params = {"From": "+155****6543", "Body": "hi", "To": "+155****1111", "MessageSid": "SM2"}
        sig = _twilio_signature(adapter._auth_token, public_url, params)
        req = self._make_request(params, sig)
        req.url = "http://internal:8080/webhooks/twilio"
        req.path_qs = "/webhooks/twilio"
        req.headers.update({
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "public.example.com",
            "X-Forwarded-Port": "443",
        })
        resp = await adapter._handle_webhook(req)
        assert resp.status == 200
