"""SMS (Twilio) platform adapter.

Connects to the Twilio REST API for outbound SMS and runs an aiohttp
webhook server to receive inbound messages.

Shares credentials with the optional telephony skill — same env vars:
  - TWILIO_ACCOUNT_SID
  - TWILIO_AUTH_TOKEN
  - TWILIO_PHONE_NUMBER  (E.164 from-number, e.g. +15551234567)

Gateway-specific env vars:
  - SMS_WEBHOOK_PORT     (default 8080)
  - SMS_ALLOWED_USERS    (comma-separated E.164 phone numbers)
  - SMS_ALLOW_ALL_USERS  (true/false)
  - SMS_HOME_CHANNEL     (phone number for cron delivery)
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import re
import urllib.parse
from typing import Any, Dict, Optional

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01/Accounts"
MAX_SMS_LENGTH = 1600  # ~10 SMS segments
DEFAULT_WEBHOOK_PORT = 8080

# E.164 phone number pattern for redaction
_PHONE_RE = re.compile(r"\+[1-9]\d{6,14}")
_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def _redact_phone(phone: str) -> str:
    """Redact a phone number for logging: +15551234567 -> +1555***4567."""
    if not phone:
        return "<none>"
    if len(phone) <= 8:
        return phone[:2] + "***" + phone[-2:] if len(phone) > 4 else "****"
    return phone[:5] + "***" + phone[-4:]


def _empty_twiml_response(web, status: int = 200):
    """Return an empty TwiML response with the requested status code."""
    return web.Response(
        text=_EMPTY_TWIML,
        content_type="application/xml",
        status=status,
    )


def check_sms_requirements() -> bool:
    """Check if SMS adapter dependencies are available."""
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))


class SmsAdapter(BasePlatformAdapter):
    """
    Twilio SMS <-> Hermes gateway adapter.

    Each inbound phone number gets its own Hermes session (multi-tenant).
    Replies are always sent from the configured TWILIO_PHONE_NUMBER.
    """

    MAX_MESSAGE_LENGTH = MAX_SMS_LENGTH

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.SMS)
        self._account_sid: str = os.environ["TWILIO_ACCOUNT_SID"]
        self._auth_token: str = os.environ["TWILIO_AUTH_TOKEN"]
        self._from_number: str = os.getenv("TWILIO_PHONE_NUMBER", "")
        self._webhook_port: int = int(
            os.getenv("SMS_WEBHOOK_PORT", str(DEFAULT_WEBHOOK_PORT))
        )
        self._runner = None
        self._http_session: Optional["aiohttp.ClientSession"] = None

    def _basic_auth_header(self) -> str:
        """Build HTTP Basic auth header value for Twilio."""
        creds = f"{self._account_sid}:{self._auth_token}"
        encoded = base64.b64encode(creds.encode("ascii")).decode("ascii")
        return f"Basic {encoded}"

    def _validation_urls(self, request) -> list[str]:
        """Build candidate public URLs for Twilio signature validation."""
        raw_path = getattr(request, "raw_path", None) or getattr(
            request, "path_qs", ""
        )

        def _add_candidate(candidates: list[str], value: str) -> None:
            value = (value or "").strip()
            if not value:
                return
            parsed = urllib.parse.urlsplit(value)
            if parsed.scheme and parsed.netloc:
                netloc = parsed.netloc.rsplit("@", 1)[-1]
                value = urllib.parse.urlunsplit(
                    (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
                )
            if value not in candidates:
                candidates.append(value)

        def _first_header(name: str) -> str:
            raw = request.headers.get(name, "")
            return raw.split(",", 1)[0].strip()

        candidates: list[str] = []

        forwarded_proto = ""
        forwarded_host = ""
        forwarded_header = request.headers.get("Forwarded", "")
        if forwarded_header:
            for item in forwarded_header.split(",", 1)[0].split(";"):
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                value = value.strip().strip('"')
                key = key.strip().lower()
                if key == "proto" and value and not forwarded_proto:
                    forwarded_proto = value
                elif key == "host" and value and not forwarded_host:
                    forwarded_host = value

        host = (
            forwarded_host
            or _first_header("X-Original-Host")
            or _first_header("X-Forwarded-Host")
            or request.headers.get("Host", "").strip()
            or getattr(request, "host", "")
        )
        forwarded_port = _first_header("X-Forwarded-Port")
        host_candidates = [host] if host else []
        if (
            host
            and forwarded_port
            and ":" not in host.rsplit("@", 1)[-1]
            and f"{host}:{forwarded_port}" not in host_candidates
        ):
            host_candidates.append(f"{host}:{forwarded_port}")

        scheme = (
            forwarded_proto
            or _first_header("X-Forwarded-Proto")
            or getattr(request, "scheme", "")
        )
        if scheme:
            for host_value in host_candidates:
                _add_candidate(candidates, f"{scheme}://{host_value}{raw_path}")

        if host_candidates and not forwarded_proto:
            # TLS is commonly terminated before aiohttp, so try both public schemes.
            for host_value in host_candidates:
                _add_candidate(candidates, f"https://{host_value}{raw_path}")
                _add_candidate(candidates, f"http://{host_value}{raw_path}")

        try:
            _add_candidate(candidates, str(request.url))
        except Exception:
            pass

        return candidates

    def _validate_twilio_signature(
        self, request, form_pairs: list[tuple[str, str]]
    ) -> bool:
        """Validate the inbound Twilio webhook signature."""
        signature = (
            request.headers.get("X-Twilio-Signature", "")
            or request.headers.get("x-twilio-signature", "")
        ).strip()
        if not signature:
            return False

        sorted_pairs = sorted(form_pairs, key=lambda item: item[0])
        for url in self._validation_urls(request):
            payload = url + "".join(f"{name}{value}" for name, value in sorted_pairs)
            digest = hmac.new(
                self._auth_token.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha1,
            ).digest()
            expected = base64.b64encode(digest).decode("ascii")
            if hmac.compare_digest(signature, expected):
                return True
        return False

    # ------------------------------------------------------------------
    # Required abstract methods
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        import aiohttp
        from aiohttp import web

        if not self._from_number:
            logger.error("[sms] TWILIO_PHONE_NUMBER not set — cannot send replies")
            return False

        app = web.Application()
        app.router.add_post("/webhooks/twilio", self._handle_webhook)
        app.router.add_get("/health", lambda _: web.Response(text="ok"))

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._webhook_port)
        await site.start()
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
        )
        self._running = True

        logger.info(
            "[sms] Twilio webhook server listening on port %d, from: %s",
            self._webhook_port,
            _redact_phone(self._from_number),
        )
        return True

    async def disconnect(self) -> None:
        if self._http_session:
            await self._http_session.close()
            self._http_session = None
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._running = False
        logger.info("[sms] Disconnected")

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        import aiohttp

        formatted = self.format_message(content)
        chunks = self.truncate_message(formatted)
        last_result = SendResult(success=True)

        url = f"{TWILIO_API_BASE}/{self._account_sid}/Messages.json"
        headers = {
            "Authorization": self._basic_auth_header(),
        }

        session = self._http_session or aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
        )
        try:
            for chunk in chunks:
                form_data = aiohttp.FormData()
                form_data.add_field("From", self._from_number)
                form_data.add_field("To", chat_id)
                form_data.add_field("Body", chunk)

                try:
                    async with session.post(url, data=form_data, headers=headers) as resp:
                        body = await resp.json()
                        if resp.status >= 400:
                            error_msg = body.get("message", str(body))
                            logger.error(
                                "[sms] send failed to %s: %s %s",
                                _redact_phone(chat_id),
                                resp.status,
                                error_msg,
                            )
                            return SendResult(
                                success=False,
                                error=f"Twilio {resp.status}: {error_msg}",
                            )
                        msg_sid = body.get("sid", "")
                        last_result = SendResult(success=True, message_id=msg_sid)
                except Exception as e:
                    logger.error("[sms] send error to %s: %s", _redact_phone(chat_id), e)
                    return SendResult(success=False, error=str(e))
        finally:
            # Close session only if we created a fallback (no persistent session)
            if not self._http_session and session:
                await session.close()

        return last_result

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": chat_id, "type": "dm"}

    # ------------------------------------------------------------------
    # SMS-specific formatting
    # ------------------------------------------------------------------

    def format_message(self, content: str) -> str:
        """Strip markdown — SMS renders it as literal characters."""
        content = re.sub(r"\*\*(.+?)\*\*", r"\1", content, flags=re.DOTALL)
        content = re.sub(r"\*(.+?)\*", r"\1", content, flags=re.DOTALL)
        content = re.sub(r"__(.+?)__", r"\1", content, flags=re.DOTALL)
        content = re.sub(r"_(.+?)_", r"\1", content, flags=re.DOTALL)
        content = re.sub(r"```[a-z]*\n?", "", content)
        content = re.sub(r"`(.+?)`", r"\1", content)
        content = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)
        content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()

    # ------------------------------------------------------------------
    # Twilio webhook handler
    # ------------------------------------------------------------------

    async def _handle_webhook(self, request) -> "aiohttp.web.Response":
        from aiohttp import web

        try:
            raw = await request.read()
            body_text = raw.decode("utf-8")
            # Twilio sends form-encoded data, not JSON
            form_pairs = urllib.parse.parse_qsl(body_text, keep_blank_values=True)
            form = urllib.parse.parse_qs(body_text, keep_blank_values=True)
        except Exception as e:
            logger.error("[sms] webhook parse error: %s", e)
            return _empty_twiml_response(web, status=400)

        if not self._validate_twilio_signature(request, form_pairs):
            logger.warning("[sms] rejected inbound webhook with invalid Twilio signature")
            return _empty_twiml_response(web, status=403)

        # Extract fields (parse_qs returns lists)
        from_number = (form.get("From", [""]))[0].strip()
        to_number = (form.get("To", [""]))[0].strip()
        text = (form.get("Body", [""]))[0].strip()
        message_sid = (form.get("MessageSid", [""]))[0].strip()

        if not from_number or not text:
            return _empty_twiml_response(web)

        # Ignore messages from our own number (echo prevention)
        if from_number == self._from_number:
            logger.debug("[sms] ignoring echo from own number %s", _redact_phone(from_number))
            return _empty_twiml_response(web)

        logger.info(
            "[sms] inbound from %s -> %s: %s",
            _redact_phone(from_number),
            _redact_phone(to_number),
            text[:80],
        )

        source = self.build_source(
            chat_id=from_number,
            chat_name=from_number,
            chat_type="dm",
            user_id=from_number,
            user_name=from_number,
        )
        event = MessageEvent(
            text=text,
            message_type=MessageType.TEXT,
            source=source,
            raw_message=form,
            message_id=message_sid,
        )

        # Non-blocking: Twilio expects a fast response
        task = asyncio.create_task(self.handle_message(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Return empty TwiML — we send replies via the REST API, not inline TwiML
        return _empty_twiml_response(web)
