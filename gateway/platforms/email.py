"""
Email platform adapter for the Hermes gateway.

Allows users to interact with Hermes by sending emails.

Supported auth modes:
    - basic IMAP + SMTP username/password
    - Outlook OAuth (Graph-backed inbox polling + MIME sendMail)

Environment variables:
    EMAIL_AUTH_MODE     — "basic" or "outlook_oauth" (auto-detected when omitted)
    EMAIL_IMAP_HOST     — IMAP server host (e.g., imap.gmail.com)
    EMAIL_IMAP_PORT     — IMAP server port (default: 993)
    EMAIL_SMTP_HOST     — SMTP server host (e.g., smtp.gmail.com)
    EMAIL_SMTP_PORT     — SMTP server port (default: 587)
    EMAIL_ADDRESS       — Email address for the agent
    EMAIL_PASSWORD      — Email password or app-specific password
    EMAIL_OAUTH_TOKEN_FILE — Outlook delegated token cache (default: ~/.outlook-mcp-tokens.json)
    EMAIL_POLL_INTERVAL — Seconds between mailbox checks (default: 15)
    EMAIL_ALLOWED_USERS — Comma-separated list of allowed sender addresses
"""

import asyncio
import base64
import email as email_lib
import imaplib
import json
import logging
import os
import re
import smtplib
import ssl
import time
import uuid
from email.header import decode_header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import quote

import httpx

from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_document_from_bytes,
    cache_image_from_bytes,
)
from gateway.config import Platform, PlatformConfig

logger = logging.getLogger(__name__)
# Automated sender patterns — emails from these are silently ignored
_NOREPLY_PATTERNS = (
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "bounce", "notifications@",
    "automated@", "auto-confirm", "auto-reply", "automailer",
)

# RFC headers that indicate bulk/automated mail
_AUTOMATED_HEADERS = {
    "Auto-Submitted": lambda v: v.lower() != "no",
    "Precedence": lambda v: v.lower() in {"bulk", "list", "junk"},
    "X-Auto-Response-Suppress": lambda v: bool(v),
    "List-Unsubscribe": lambda v: bool(v),
}

# Gmail-safe max length per email body
MAX_MESSAGE_LENGTH = 50_000

# Supported image extensions for inline detection
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_OUTLOOK_DEFAULT_TOKEN_FILE = "~/.outlook-mcp-tokens.json"
_OUTLOOK_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
_OUTLOOK_TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_OUTLOOK_TOKEN_REFRESH_SKEW_SECONDS = 120


def _get_ms_oauth_settings(environ: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    env = environ if environ is not None else os.environ
    return {
        "tenant_id": (env.get("MS_TENANT_ID") or env.get("MSGRAPH_TENANT_ID") or "").strip(),
        "client_id": (env.get("MS_CLIENT_ID") or env.get("MSGRAPH_CLIENT_ID") or "").strip(),
        "client_secret": (env.get("MS_CLIENT_SECRET") or env.get("MSGRAPH_CLIENT_SECRET") or "").strip(),
    }


def _get_oauth_token_path(environ: Optional[Mapping[str, str]] = None) -> Path:
    env = environ if environ is not None else os.environ
    raw = (env.get("EMAIL_OAUTH_TOKEN_FILE") or _OUTLOOK_DEFAULT_TOKEN_FILE).strip()
    return Path(os.path.expanduser(raw))


def _looks_like_outlook_host(host: str) -> bool:
    normalized = (host or "").strip().lower()
    if not normalized:
        return False
    return any(
        token in normalized
        for token in (
            "outlook",
            "office365",
            "office.com",
            "exchange",
            "hotmail",
            "live.com",
        )
    )


def _outlook_oauth_env_ready(environ: Optional[Mapping[str, str]] = None) -> bool:
    env = environ if environ is not None else os.environ
    address = (env.get("EMAIL_ADDRESS") or "").strip()
    settings = _get_ms_oauth_settings(env)
    return bool(address and settings["tenant_id"] and settings["client_id"] and settings["client_secret"])


def _basic_email_env_ready(environ: Optional[Mapping[str, str]] = None) -> bool:
    env = environ if environ is not None else os.environ
    return bool(
        (env.get("EMAIL_ADDRESS") or "").strip()
        and (env.get("EMAIL_PASSWORD") or "").strip()
        and (env.get("EMAIL_IMAP_HOST") or "").strip()
        and (env.get("EMAIL_SMTP_HOST") or "").strip()
    )


def _determine_email_auth_mode(environ: Optional[Mapping[str, str]] = None) -> str:
    env = environ if environ is not None else os.environ
    explicit = (env.get("EMAIL_AUTH_MODE") or "").strip().lower()
    if explicit:
        return explicit

    if _basic_email_env_ready(env):
        return "basic"

    if _outlook_oauth_env_ready(env):
        token_path = _get_oauth_token_path(env)
        imap_host = env.get("EMAIL_IMAP_HOST") or ""
        smtp_host = env.get("EMAIL_SMTP_HOST") or ""
        if token_path.exists() and (
            not (imap_host or smtp_host)
            or _looks_like_outlook_host(imap_host)
            or _looks_like_outlook_host(smtp_host)
        ):
            return "outlook_oauth"

    return "basic"


def _normalize_epoch_seconds(raw: Any) -> Optional[float]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value > 1_000_000_000_000:
        value /= 1000.0
    return value

def _send_imap_id(imap: "imaplib.IMAP4") -> None:
    """Send RFC 2971 IMAP ID command identifying this client.

    Required by 163/NetEase mailbox after LOGIN: without it, every UID
    SEARCH/FETCH returns ``BYE Unsafe Login`` and disconnects.  Other
    IMAP servers either honor it silently or reject the unknown command;
    we swallow failures so non-supporting servers keep working.
    """
    try:
        try:
            from hermes_cli import __version__ as _hermes_version
        except Exception:  # noqa: BLE001 — keep ID best-effort if import fails
            _hermes_version = "0"
        imap.xatom(
            "ID",
            f'("name" "hermes-agent" "version" "{_hermes_version}" '
            '"vendor" "NousResearch" '
            '"support-email" "noreply@nousresearch.com")',
        )
    except Exception as e:  # noqa: BLE001 — best-effort, never fatal
        logger.debug("[Email] IMAP ID command not accepted: %s", e)


def _is_automated_sender(address: str, headers: dict) -> bool:
    """Return True if this email is from an automated/noreply source."""
    addr = address.lower()
    if any(pattern in addr for pattern in _NOREPLY_PATTERNS):
        return True
    for header, check in _AUTOMATED_HEADERS.items():
        value = headers.get(header, "")
        if value and check(value):
            return True
    return False
    
def check_email_requirements() -> bool:
    """Check if email platform dependencies are available."""
    if _determine_email_auth_mode() == "outlook_oauth":
        return _outlook_oauth_env_ready() and _get_oauth_token_path().exists()

    return _basic_email_env_ready()


def _decode_header_value(raw: str) -> str:
    """Decode an RFC 2047 encoded email header into a plain string."""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _extract_text_body(msg: email_lib.message.Message) -> str:
    """Extract the plain-text body from a potentially multipart email."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            # Skip attachments
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: try text/html and strip tags
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    return _strip_html(html)
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                return _strip_html(text)
            return text
        return ""


def _strip_html(html: str) -> str:
    """Naive HTML tag stripper for fallback text extraction."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_email_address(raw: str) -> str:
    """Extract bare email address from 'Name <addr>' format."""
    match = re.search(r"<([^>]+)>", raw)
    if match:
        return match.group(1).strip().lower()
    return raw.strip().lower()


def _extract_attachments(
    msg: email_lib.message.Message,
    skip_attachments: bool = False,
) -> List[Dict[str, Any]]:
    """Extract attachment metadata and cache files locally.

    When *skip_attachments* is True, all attachment/inline parts are ignored
    (useful for malware protection or bandwidth savings).
    """
    attachments = []
    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if skip_attachments and ("attachment" in disposition or "inline" in disposition):
            continue
        if "attachment" not in disposition and "inline" not in disposition:
            continue
        # Skip text/plain and text/html body parts
        content_type = part.get_content_type()
        if content_type in {"text/plain", "text/html"} and "attachment" not in disposition:
            continue

        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)
        else:
            ext = part.get_content_subtype() or "bin"
            filename = f"attachment.{ext}"

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        ext = Path(filename).suffix.lower()
        if ext in _IMAGE_EXTS:
            try:
                cached_path = cache_image_from_bytes(payload, ext)
            except ValueError:
                logger.debug("Skipping non-image attachment %s (invalid magic bytes)", filename)
                continue
            attachments.append({
                "path": cached_path,
                "filename": filename,
                "type": "image",
                "media_type": content_type,
            })
        else:
            cached_path = cache_document_from_bytes(payload, filename)
            attachments.append({
                "path": cached_path,
                "filename": filename,
                "type": "document",
                "media_type": content_type,
            })

    return attachments


class EmailAdapter(BasePlatformAdapter):
    """Email gateway adapter using IMAP/SMTP or Outlook OAuth."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.EMAIL)

        self._address = os.getenv("EMAIL_ADDRESS", "")
        self._password = os.getenv("EMAIL_PASSWORD", "")
        self._imap_host = os.getenv("EMAIL_IMAP_HOST", "")
        self._imap_port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        self._smtp_host = os.getenv("EMAIL_SMTP_HOST", "")
        self._smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self._poll_interval = int(os.getenv("EMAIL_POLL_INTERVAL", "15"))
        self._auth_mode = _determine_email_auth_mode()
        self._oauth_token_path = _get_oauth_token_path()
        oauth_settings = _get_ms_oauth_settings()
        self._ms_tenant_id = oauth_settings["tenant_id"]
        self._ms_client_id = oauth_settings["client_id"]
        self._ms_client_secret = oauth_settings["client_secret"]

        # Skip attachments — configured via config.yaml:
        #   platforms:
        #     email:
        #       skip_attachments: true
        extra = config.extra or {}
        self._skip_attachments = extra.get("skip_attachments", False)

        # Track message IDs we've already processed to avoid duplicates
        self._seen_uids: set = set()
        self._seen_uids_max: int = 2000   # cap to prevent unbounded memory growth
        self._poll_task: Optional[asyncio.Task] = None

        # Map chat_id (sender email) -> last subject + message-id for threading
        self._thread_context: Dict[str, Dict[str, str]] = {}

        logger.info("[Email] Adapter initialized for %s using auth mode=%s", self._address, self._auth_mode)

    def _uses_outlook_oauth(self) -> bool:
        return self._auth_mode == "outlook_oauth"

    def _outlook_token_url(self) -> str:
        return _OUTLOOK_TOKEN_URL_TEMPLATE.format(tenant=self._ms_tenant_id)

    def _read_oauth_token_cache(self) -> Dict[str, Any]:
        if not self._oauth_token_path.exists():
            raise RuntimeError(
                f"Outlook OAuth token file not found: {self._oauth_token_path}. "
                "Authenticate the Outlook MCP first or set EMAIL_OAUTH_TOKEN_FILE."
            )
        try:
            payload = json.loads(self._oauth_token_path.read_text())
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to read Outlook OAuth token file {self._oauth_token_path}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"Outlook OAuth token file {self._oauth_token_path} did not contain a JSON object.")
        return payload

    def _write_oauth_token_cache(self, payload: Dict[str, Any]) -> None:
        self._oauth_token_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._oauth_token_path.with_suffix(f"{self._oauth_token_path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp_path.replace(self._oauth_token_path)

    async def _refresh_outlook_access_token(self, token_payload: Dict[str, Any]) -> Dict[str, Any]:
        refresh_token = str(token_payload.get("refresh_token") or "").strip()
        if not refresh_token:
            raise RuntimeError(
                f"Outlook OAuth token file {self._oauth_token_path} does not contain a refresh_token."
            )

        scope = str(
            token_payload.get("scope")
            or os.getenv("EMAIL_OAUTH_SCOPE")
            or "offline_access Mail.Read Mail.Send User.Read"
        ).strip()
        form = {
            "grant_type": "refresh_token",
            "client_id": self._ms_client_id,
            "client_secret": self._ms_client_secret,
            "refresh_token": refresh_token,
            "scope": scope,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(self._outlook_token_url(), data=form)

        if response.status_code >= 400:
            detail = response.text.strip()
            try:
                detail = response.json().get("error_description") or response.json().get("error") or detail
            except ValueError:
                pass
            raise RuntimeError(
                f"Outlook OAuth token refresh failed with HTTP {response.status_code}: {detail}"
            )

        refreshed = response.json()
        if not isinstance(refreshed, dict) or not refreshed.get("access_token"):
            raise RuntimeError("Outlook OAuth token refresh response did not include an access_token.")

        merged = dict(token_payload)
        merged.update(refreshed)
        expires_in = refreshed.get("expires_in") or token_payload.get("expires_in") or 3600
        try:
            expires_in_seconds = int(expires_in)
        except (TypeError, ValueError):
            expires_in_seconds = 3600
        merged["expires_in"] = expires_in_seconds
        merged["expires_at"] = int((time.time() + max(0, expires_in_seconds)) * 1000)
        if not merged.get("refresh_token"):
            merged["refresh_token"] = refresh_token
        self._write_oauth_token_cache(merged)
        return merged

    async def _get_outlook_access_token(self, *, force_refresh: bool = False) -> str:
        token_payload = self._read_oauth_token_cache()
        expires_at = _normalize_epoch_seconds(token_payload.get("expires_at") or token_payload.get("expires_on"))
        access_token = str(token_payload.get("access_token") or "").strip()
        if (
            not force_refresh
            and access_token
            and expires_at is not None
            and expires_at > (time.time() + _OUTLOOK_TOKEN_REFRESH_SKEW_SECONDS)
        ):
            return access_token

        refreshed = await self._refresh_outlook_access_token(token_payload)
        access_token = str(refreshed.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("Outlook OAuth refresh completed without an access token.")
        return access_token

    async def _outlook_graph_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Any] = None,
        content: Optional[str] = None,
        expected_statuses: Tuple[int, ...] = (200,),
    ) -> httpx.Response:
        url = path if path.startswith("http") else f"{_OUTLOOK_GRAPH_BASE_URL}/{path.lstrip('/')}"
        last_error: Optional[str] = None

        for force_refresh in (False, True):
            token = await self._get_outlook_access_token(force_refresh=force_refresh)
            request_headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "Hermes-Agent/email-outlook-oauth",
            }
            if headers:
                request_headers.update(headers)

            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    headers=request_headers,
                    json=json_body,
                    content=content,
                )

            if response.status_code in expected_statuses:
                return response
            if response.status_code == 401 and not force_refresh:
                last_error = response.text.strip()
                continue

            detail = response.text.strip()
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    error = payload.get("error")
                    if isinstance(error, dict):
                        detail = str(error.get("message") or error.get("code") or detail)
            except ValueError:
                pass
            raise RuntimeError(
                f"Outlook Graph request failed: {method} {url} -> HTTP {response.status_code}: {detail}"
            )

        raise RuntimeError(f"Outlook Graph request failed after token refresh: {last_error or 'unknown error'}")

    async def _outlook_graph_json(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        response = await self._outlook_graph_request(method, path, **kwargs)
        if not response.content:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Expected JSON object from Outlook Graph {method} {path}, got {type(payload).__name__}."
            )
        return payload

    def _trim_seen_uids(self) -> None:
        """Keep only the most recent UIDs to prevent unbounded memory growth.

        IMAP UIDs are monotonically increasing integers. When the set grows
        beyond the cap, we keep only the highest half — old UIDs are safe to
        drop because new messages always have higher UIDs and IMAP's UNSEEN
        flag prevents re-delivery regardless.
        """
        if len(self._seen_uids) <= self._seen_uids_max:
            return
        try:
            # UIDs are bytes like b'1234' — sort numerically and keep top half
            sorted_uids = sorted(self._seen_uids, key=lambda u: int(u))
            keep = self._seen_uids_max // 2
            self._seen_uids = set(sorted_uids[-keep:])
            logger.debug("[Email] Trimmed seen UIDs to %d entries", len(self._seen_uids))
        except (ValueError, TypeError):
            # Fallback: just clear old entries if sort fails
            self._seen_uids = set(list(self._seen_uids)[-self._seen_uids_max // 2:])

    async def connect(self) -> bool:
        """Connect to the configured email backend and start polling."""
        if self._uses_outlook_oauth():
            try:
                await self._connect_outlook_oauth()
            except Exception as e:
                logger.error("[Email] Outlook OAuth connection failed: %s", e)
                return False

            self._running = True
            self._poll_task = asyncio.create_task(self._poll_loop())
            print(f"[Email] Connected as {self._address} via Outlook OAuth")
            return True

        try:
            # Test IMAP connection
            imap = imaplib.IMAP4_SSL(self._imap_host, self._imap_port, timeout=30)
            imap.login(self._address, self._password)
            _send_imap_id(imap)
            # Mark all existing messages as seen so we only process new ones
            imap.select("INBOX")
            status, data = imap.uid("search", None, "ALL")
            if status == "OK" and data and data[0]:
                for uid in data[0].split():
                    self._seen_uids.add(uid)
            # Keep only the most recent UIDs to prevent unbounded growth
            self._trim_seen_uids()
            imap.logout()
            logger.info("[Email] IMAP connection test passed. %d existing messages skipped.", len(self._seen_uids))
        except Exception as e:
            logger.error("[Email] IMAP connection failed: %s", e)
            return False

        try:
            # Test SMTP connection
            smtp = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._address, self._password)
            smtp.quit()
            logger.info("[Email] SMTP connection test passed.")
        except Exception as e:
            logger.error("[Email] SMTP connection failed: %s", e)
            return False

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        print(f"[Email] Connected as {self._address}")
        return True

    async def _connect_outlook_oauth(self) -> None:
        profile = await self._outlook_graph_json(
            "GET",
            "/me",
            expected_statuses=(200,),
        )
        mailbox = str(profile.get("mail") or profile.get("userPrincipalName") or "").strip().lower()
        if mailbox and mailbox != self._address.lower():
            logger.warning(
                "[Email] Outlook OAuth token is for %s, but EMAIL_ADDRESS=%s",
                mailbox,
                self._address,
            )

        payload = await self._outlook_graph_json(
            "GET",
            "/me/mailFolders/inbox/messages",
            params={
                "$filter": "isRead eq false",
                "$select": "id",
                "$top": 200,
            },
            expected_statuses=(200,),
        )
        for item in payload.get("value", []) or []:
            message_id = str(item.get("id") or "").strip()
            if message_id:
                self._seen_uids.add(message_id)
        self._trim_seen_uids()
        logger.info("[Email] Outlook OAuth connection test passed. %d existing unread messages skipped.", len(self._seen_uids))

    async def disconnect(self) -> None:
        """Stop polling and disconnect."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        logger.info("[Email] Disconnected.")

    async def _poll_loop(self) -> None:
        """Poll IMAP for new messages at regular intervals."""
        while self._running:
            try:
                await self._check_inbox()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("[Email] Poll error: %s", e)
            await asyncio.sleep(self._poll_interval)

    async def _check_inbox(self) -> None:
        """Check INBOX for unseen messages and dispatch them."""
        # Run IMAP operations in a thread to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        messages = await loop.run_in_executor(None, self._fetch_new_messages)
        for msg_data in messages:
            try:
                acknowledged = await self._dispatch_message(msg_data)
            except Exception as e:
                uid = msg_data.get("uid")
                if uid in self._seen_uids:
                    self._seen_uids.discard(uid)
                logger.error("[Email] Dispatch failed for %s: %s", uid, e)
                continue

            if self._uses_outlook_oauth() and acknowledged:
                uid = str(msg_data.get("uid") or "").strip()
                if uid:
                    try:
                        await self._mark_outlook_message_read(uid)
                    except Exception as e:
                        logger.error("[Email] Failed to mark Outlook message read %s: %s", uid, e)

    def _fetch_new_messages(self) -> List[Dict[str, Any]]:
        """Fetch new (unseen) messages. Runs in executor thread."""
        if self._uses_outlook_oauth():
            try:
                return asyncio.run(self._fetch_new_messages_outlook_oauth())
            except Exception as e:
                logger.error("[Email] Outlook OAuth fetch error: %s", e)
                return []

        results = []
        try:
            imap = imaplib.IMAP4_SSL(self._imap_host, self._imap_port, timeout=30)
            try:
                imap.login(self._address, self._password)
                _send_imap_id(imap)
                imap.select("INBOX")

                status, data = imap.uid("search", None, "UNSEEN")
                if status != "OK" or not data or not data[0]:
                    return results

                for uid in data[0].split():
                    if uid in self._seen_uids:
                        continue
                    self._seen_uids.add(uid)
                    # Trim periodically to prevent unbounded memory growth
                    if len(self._seen_uids) > self._seen_uids_max:
                        self._trim_seen_uids()

                    status, msg_data = imap.uid("fetch", uid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw_email)

                    sender_raw = msg.get("From", "")
                    sender_addr = _extract_email_address(sender_raw)
                    sender_name = _decode_header_value(sender_raw)
                    # Remove email from name if present
                    if "<" in sender_name:
                        sender_name = sender_name.split("<")[0].strip().strip('"')

                    subject = _decode_header_value(msg.get("Subject", "(no subject)"))
                    message_id = msg.get("Message-ID", "")
                    in_reply_to = msg.get("In-Reply-To", "")
                    # Skip automated/noreply senders before any processing
                    msg_headers = dict(msg.items())
                    if _is_automated_sender(sender_addr, msg_headers):
                        logger.debug("[Email] Skipping automated sender: %s", sender_addr)
                        continue
                    body = _extract_text_body(msg)
                    attachments = _extract_attachments(msg, skip_attachments=self._skip_attachments)

                    results.append({
                        "uid": uid,
                        "sender_addr": sender_addr,
                        "sender_name": sender_name,
                        "subject": subject,
                        "message_id": message_id,
                        "in_reply_to": in_reply_to,
                        "body": body,
                        "attachments": attachments,
                        "date": msg.get("Date", ""),
                    })
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass
        except Exception as e:
            logger.error("[Email] IMAP fetch error: %s", e)
        return results

    async def _fetch_new_messages_outlook_oauth(self) -> List[Dict[str, Any]]:
        payload = await self._outlook_graph_json(
            "GET",
            "/me/mailFolders/inbox/messages",
            params={
                "$filter": "isRead eq false",
                "$select": "id,subject,from,body,bodyPreview,internetMessageId,receivedDateTime,hasAttachments",
                "$orderby": "receivedDateTime asc",
                "$top": 25,
            },
            headers={"Prefer": 'outlook.body-content-type="text"'},
            expected_statuses=(200,),
        )
        results: List[Dict[str, Any]] = []
        for item in payload.get("value", []) or []:
            uid = str(item.get("id") or "").strip()
            if not uid or uid in self._seen_uids:
                continue
            self._seen_uids.add(uid)
            if len(self._seen_uids) > self._seen_uids_max:
                self._trim_seen_uids()

            sender = item.get("from") or {}
            email_address = ((sender.get("emailAddress") or {}) if isinstance(sender, dict) else {})
            sender_addr = str(email_address.get("address") or "").strip().lower()
            sender_name = str(email_address.get("name") or sender_addr).strip()
            subject = str(item.get("subject") or "(no subject)")
            message_id = str(item.get("internetMessageId") or uid)
            msg_headers = {}
            if _is_automated_sender(sender_addr, msg_headers):
                logger.debug("[Email] Skipping automated sender: %s", sender_addr)
                await self._mark_outlook_message_read(uid)
                continue

            body_obj = item.get("body") or {}
            body = str(body_obj.get("content") or item.get("bodyPreview") or "")
            attachments = []
            if item.get("hasAttachments") and not self._skip_attachments:
                attachments = await self._fetch_outlook_attachments(uid)

            results.append({
                "uid": uid,
                "sender_addr": sender_addr,
                "sender_name": sender_name,
                "subject": subject,
                "message_id": message_id,
                "in_reply_to": "",
                "body": body,
                "attachments": attachments,
                "date": str(item.get("receivedDateTime") or ""),
            })
        return results

    async def _mark_outlook_message_read(self, message_id: str) -> None:
        quoted_id = quote(message_id, safe="")
        await self._outlook_graph_request(
            "PATCH",
            f"/me/messages/{quoted_id}",
            json_body={"isRead": True},
            expected_statuses=(200,),
        )

    async def _fetch_outlook_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        quoted_id = quote(message_id, safe="")
        payload = await self._outlook_graph_json(
            "GET",
            f"/me/messages/{quoted_id}/attachments",
            expected_statuses=(200,),
        )
        attachments: List[Dict[str, Any]] = []
        for item in payload.get("value", []) or []:
            if str(item.get("@odata.type") or "") != "#microsoft.graph.fileAttachment":
                continue
            filename = str(item.get("name") or "attachment.bin")
            content_type = str(item.get("contentType") or "application/octet-stream")
            content_b64 = str(item.get("contentBytes") or "")
            if not content_b64:
                continue
            try:
                raw = base64.b64decode(content_b64)
            except Exception:
                logger.debug("[Email] Skipping attachment with invalid base64: %s", filename)
                continue
            ext = Path(filename).suffix.lower()
            if ext in _IMAGE_EXTS:
                try:
                    cached_path = cache_image_from_bytes(raw, ext)
                except ValueError:
                    logger.debug("[Email] Skipping invalid image attachment %s", filename)
                    continue
                attachments.append({
                    "path": cached_path,
                    "filename": filename,
                    "type": "image",
                    "media_type": content_type,
                })
            else:
                cached_path = cache_document_from_bytes(raw, filename)
                attachments.append({
                    "path": cached_path,
                    "filename": filename,
                    "type": "document",
                    "media_type": content_type,
                })
        return attachments

    async def _dispatch_message(self, msg_data: Dict[str, Any]) -> bool:
        """Convert a fetched email into a MessageEvent and dispatch it.

        Returns True when the message was handled or intentionally dropped and can
        be acknowledged upstream.
        """
        sender_addr = msg_data["sender_addr"]

        # Skip self-messages
        if sender_addr == self._address.lower():
            return True

        # Never reply to automated senders
        if _is_automated_sender(sender_addr, {}):
            logger.debug("[Email] Dropping automated sender at dispatch: %s", sender_addr)
            return True

        # Skip senders not in EMAIL_ALLOWED_USERS — prevents the adapter
        # from creating a MessageEvent (and thus thread context) for senders
        # that the gateway will never authorize.  Without this early guard,
        # a race between dispatch and authorization can result in the adapter
        # sending a reply even though the handler returned None.
        allowed_raw = os.getenv("EMAIL_ALLOWED_USERS", "").strip()
        if allowed_raw:
            allowed = {addr.strip().lower() for addr in allowed_raw.split(",") if addr.strip()}
            if sender_addr.lower() not in allowed:
                logger.debug("[Email] Dropping non-allowlisted sender at dispatch: %s", sender_addr)
                return True

        subject = msg_data["subject"]
        body = msg_data["body"].strip()
        attachments = msg_data["attachments"]

        # Build message text: include subject as context
        text = body
        if subject and not subject.startswith("Re:"):
            text = f"[Subject: {subject}]\n\n{body}"

        # Determine message type and media
        media_urls = []
        media_types = []
        msg_type = MessageType.TEXT

        for att in attachments:
            media_urls.append(att["path"])
            media_types.append(att["media_type"])
            if att["type"] == "image":
                msg_type = MessageType.PHOTO

        # Store thread context for reply threading
        self._thread_context[sender_addr] = {
            "subject": subject,
            "message_id": msg_data["message_id"],
        }

        source = self.build_source(
            chat_id=sender_addr,
            chat_name=msg_data["sender_name"] or sender_addr,
            chat_type="dm",
            user_id=sender_addr,
            user_name=msg_data["sender_name"] or sender_addr,
        )

        event = MessageEvent(
            text=text or "(empty email)",
            message_type=msg_type,
            source=source,
            message_id=msg_data["message_id"],
            media_urls=media_urls,
            media_types=media_types,
            reply_to_message_id=msg_data["in_reply_to"] or None,
        )

        logger.info("[Email] New message from %s: %s", sender_addr, subject)
        await self.handle_message(event)
        return True

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send an email reply to the given address."""
        try:
            loop = asyncio.get_running_loop()
            message_id = await loop.run_in_executor(
                None, self._send_email, chat_id, content, reply_to
            )
            return SendResult(success=True, message_id=message_id)
        except Exception as e:
            logger.error("[Email] Send failed to %s: %s", chat_id, e)
            return SendResult(success=False, error=str(e))

    def _send_email(
        self,
        to_addr: str,
        body: str,
        reply_to_msg_id: Optional[str] = None,
    ) -> str:
        """Send an email via the configured transport. Runs in executor thread."""
        msg = MIMEMultipart()
        msg["From"] = self._address
        msg["To"] = to_addr

        # Thread context for reply
        ctx = self._thread_context.get(to_addr, {})
        subject = ctx.get("subject", "Hermes Agent")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        msg["Subject"] = subject

        # Threading headers
        original_msg_id = reply_to_msg_id or ctx.get("message_id")
        if original_msg_id:
            msg["In-Reply-To"] = original_msg_id
            msg["References"] = original_msg_id

        msg["Date"] = formatdate(localtime=True)
        msg_id = f"<hermes-{uuid.uuid4().hex[:12]}@{self._address.split('@')[1]}>"
        msg["Message-ID"] = msg_id

        msg.attach(MIMEText(body, "plain", "utf-8"))

        if self._uses_outlook_oauth():
            asyncio.run(self._send_outlook_mime_message(msg))
            logger.info("[Email] Sent Outlook OAuth reply to %s (subject: %s)", to_addr, subject)
            return msg_id

        smtp = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
        try:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._address, self._password)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()

        logger.info("[Email] Sent reply to %s (subject: %s)", to_addr, subject)
        return msg_id

    async def _send_outlook_mime_message(self, msg: Any) -> None:
        raw_mime = base64.b64encode(msg.as_bytes()).decode("ascii")
        await self._outlook_graph_request(
            "POST",
            "/me/sendMail",
            headers={"Content-Type": "text/plain"},
            content=raw_mime,
            expected_statuses=(202,),
        )

    async def send_typing(self, chat_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Email has no typing indicator — no-op."""

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> SendResult:
        """Send an image URL as part of an email body."""
        text = caption or ""
        text += f"\n\nImage: {image_url}"
        return await self.send(chat_id, text.strip(), reply_to)

    async def send_multiple_images(
        self,
        chat_id: str,
        images: List[Tuple[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
        human_delay: float = 0.0,
    ) -> None:
        """Send a batch of images as a single email with multiple MIME attachments.

        Local files are attached directly. URL images have their URL
        appended to the body (email adapter does not download remote
        images). No hard cap — email clients handle dozens of
        attachments fine, subject to SMTP message size limits.
        """
        if not images:
            return

        from urllib.parse import unquote as _unquote

        body_parts: List[str] = []
        local_paths: List[str] = []
        for image_url, alt_text in images:
            if alt_text:
                body_parts.append(alt_text)
            if image_url.startswith("file://"):
                local_path = _unquote(image_url[7:])
                if Path(local_path).exists():
                    local_paths.append(local_path)
                else:
                    logger.warning("[Email] Skipping missing image: %s", local_path)
            else:
                # Remote URLs just get linked in the body (parity with send_image)
                body_parts.append(f"Image: {image_url}")

        if not local_paths and not body_parts:
            return

        body = "\n\n".join(body_parts)

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._send_email_with_attachments,
                chat_id,
                body,
                local_paths,
            )
        except Exception as e:
            logger.error("[Email] Multi-image send failed, falling back: %s", e, exc_info=True)
            await super().send_multiple_images(chat_id, images, metadata, human_delay)

    def _send_email_with_attachments(
        self,
        to_addr: str,
        body: str,
        file_paths: List[str],
    ) -> str:
        """Send an email with multiple file attachments."""
        msg = MIMEMultipart()
        msg["From"] = self._address
        msg["To"] = to_addr

        ctx = self._thread_context.get(to_addr, {})
        subject = ctx.get("subject", "Hermes Agent")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        msg["Subject"] = subject

        original_msg_id = ctx.get("message_id")
        if original_msg_id:
            msg["In-Reply-To"] = original_msg_id
            msg["References"] = original_msg_id

        msg["Date"] = formatdate(localtime=True)
        msg_id = f"<hermes-{uuid.uuid4().hex[:12]}@{self._address.split('@')[1]}>"
        msg["Message-ID"] = msg_id

        if body:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        for file_path in file_paths:
            p = Path(file_path)
            try:
                with open(p, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={p.name}")
                    msg.attach(part)
            except Exception as e:
                logger.warning("[Email] Failed to attach %s: %s", file_path, e)

        if self._uses_outlook_oauth():
            asyncio.run(self._send_outlook_mime_message(msg))
            logger.info("[Email] Sent Outlook OAuth multi-attachment email to %s (%d files)", to_addr, len(file_paths))
            return msg_id

        smtp = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
        try:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._address, self._password)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()

        logger.info("[Email] Sent multi-attachment email to %s (%d files)", to_addr, len(file_paths))
        return msg_id

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a file as an email attachment."""
        try:
            loop = asyncio.get_running_loop()
            message_id = await loop.run_in_executor(
                None,
                self._send_email_with_attachment,
                chat_id,
                caption or "",
                file_path,
                file_name,
            )
            return SendResult(success=True, message_id=message_id)
        except Exception as e:
            logger.error("[Email] Send document failed: %s", e)
            return SendResult(success=False, error=str(e))

    def _send_email_with_attachment(
        self,
        to_addr: str,
        body: str,
        file_path: str,
        file_name: Optional[str] = None,
    ) -> str:
        """Send an email with a file attachment."""
        msg = MIMEMultipart()
        msg["From"] = self._address
        msg["To"] = to_addr

        ctx = self._thread_context.get(to_addr, {})
        subject = ctx.get("subject", "Hermes Agent")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        msg["Subject"] = subject

        original_msg_id = ctx.get("message_id")
        if original_msg_id:
            msg["In-Reply-To"] = original_msg_id
            msg["References"] = original_msg_id

        msg["Date"] = formatdate(localtime=True)
        msg_id = f"<hermes-{uuid.uuid4().hex[:12]}@{self._address.split('@')[1]}>"
        msg["Message-ID"] = msg_id

        if body:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attach file
        p = Path(file_path)
        fname = file_name or p.name
        with open(p, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={fname}")
            msg.attach(part)

        if self._uses_outlook_oauth():
            asyncio.run(self._send_outlook_mime_message(msg))
            return msg_id

        smtp = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
        try:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._address, self._password)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()

        return msg_id

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return basic info about the email chat."""
        ctx = self._thread_context.get(chat_id, {})
        return {
            "name": chat_id,
            "type": "dm",
            "chat_id": chat_id,
            "subject": ctx.get("subject", ""),
        }
