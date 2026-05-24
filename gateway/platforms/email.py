"""
Email platform adapter for the Hermes gateway.

Allows users to interact with Hermes by sending emails.
Uses IMAP to receive and SMTP to send messages.

Environment variables:
    EMAIL_IMAP_HOST     — IMAP server host (e.g., imap.gmail.com)
    EMAIL_IMAP_PORT     — IMAP server port (default: 993)
    EMAIL_SMTP_HOST     — SMTP server host (e.g., smtp.gmail.com)
    EMAIL_SMTP_PORT     — SMTP server port (default: 587)
    EMAIL_ADDRESS       — Email address for the agent
    EMAIL_PASSWORD      — Email password or app-specific password
    EMAIL_POLL_INTERVAL — Seconds between mailbox checks (default: 15)
    EMAIL_ALLOWED_USERS — Comma-separated list of allowed sender addresses
"""

import asyncio
import email as email_lib
import imaplib
import json
import logging
import os
import re
import smtplib
import ssl
import uuid
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import formatdate
from email import encoders
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    
def _coerce_port(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_email_accounts_from_env() -> List[Dict[str, Any]]:
    """Load additional email account definitions from EMAIL_ACCOUNTS JSON."""
    raw = os.getenv("EMAIL_ACCOUNTS", "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [acct for acct in parsed if isinstance(acct, dict)]


def _normalize_email_account(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize one email account config dict, resolving optional password_env."""
    address = str(data.get("address") or data.get("email") or "").strip()
    password = str(data.get("password") or "")
    password_env = str(data.get("password_env") or "").strip()
    if not password and password_env:
        password = os.getenv(password_env, "")
    imap_host = str(data.get("imap_host") or data.get("imap") or "").strip()
    smtp_host = str(data.get("smtp_host") or data.get("smtp") or "").strip()
    if not all([address, password, imap_host, smtp_host]):
        return None
    return {
        "address": address,
        "password": password,
        "imap_host": imap_host,
        "imap_port": _coerce_port(data.get("imap_port"), 993),
        "smtp_host": smtp_host,
        "smtp_port": _coerce_port(data.get("smtp_port"), 587),
    }


def _default_email_account_from_env() -> Optional[Dict[str, Any]]:
    return _normalize_email_account({
        "address": os.getenv("EMAIL_ADDRESS", ""),
        "password": os.getenv("EMAIL_PASSWORD", ""),
        "imap_host": os.getenv("EMAIL_IMAP_HOST", ""),
        "imap_port": os.getenv("EMAIL_IMAP_PORT", "993"),
        "smtp_host": os.getenv("EMAIL_SMTP_HOST", ""),
        "smtp_port": os.getenv("EMAIL_SMTP_PORT", "587"),
    })


def has_configured_email_accounts(config: Optional[PlatformConfig] = None) -> bool:
    """Return True if env vars or PlatformConfig define at least one account."""
    account_defs = []
    if config and isinstance(config.extra, dict):
        account_defs = config.extra.get("accounts") or []
    if not account_defs:
        account_defs = _load_email_accounts_from_env()
    if any(_normalize_email_account(acct) for acct in account_defs if isinstance(acct, dict)):
        return True
    return bool(_default_email_account_from_env())


def check_email_requirements() -> bool:
    """Check if email platform dependencies are available."""
    return has_configured_email_accounts()


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
    """Email gateway adapter using IMAP (receive) and SMTP (send)."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.EMAIL)

        extra = config.extra or {}
        account_defs = extra.get("accounts") or _load_email_accounts_from_env()
        self._accounts: List[Dict[str, Any]] = [
            acct for acct in (_normalize_email_account(a) for a in account_defs) if acct
        ]
        default_account = _default_email_account_from_env()
        if not self._accounts and default_account:
            self._accounts.append(default_account)

        primary = self._accounts[0] if self._accounts else {
            "address": os.getenv("EMAIL_ADDRESS", ""),
            "password": os.getenv("EMAIL_PASSWORD", ""),
            "imap_host": os.getenv("EMAIL_IMAP_HOST", ""),
            "imap_port": _coerce_port(os.getenv("EMAIL_IMAP_PORT", "993"), 993),
            "smtp_host": os.getenv("EMAIL_SMTP_HOST", ""),
            "smtp_port": _coerce_port(os.getenv("EMAIL_SMTP_PORT", "587"), 587),
        }
        # Backward-compatible attributes used by existing tests and callers.
        self._address = primary.get("address", "")
        self._password = primary.get("password", "")
        self._imap_host = primary.get("imap_host", "")
        self._imap_port = primary.get("imap_port", 993)
        self._smtp_host = primary.get("smtp_host", "")
        self._smtp_port = primary.get("smtp_port", 587)
        self._poll_interval = int(os.getenv("EMAIL_POLL_INTERVAL", "15"))

        # Skip attachments — configured via config.yaml:
        #   platforms:
        #     email:
        #       skip_attachments: true
        self._skip_attachments = extra.get("skip_attachments", False)

        # Track message IDs we've already processed to avoid duplicates
        self._seen_uids: set = set()
        self._seen_uids_max: int = 2000   # cap to prevent unbounded memory growth
        self._poll_task: Optional[asyncio.Task] = None

        # Map chat_id (sender email) -> last subject + message-id for threading
        self._thread_context: Dict[str, Dict[str, str]] = {}

        account_addresses = ", ".join(a["address"] for a in self._accounts) or self._address
        logger.info("[Email] Adapter initialized for %s", account_addresses)

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

    def _uid_key(self, account: Dict[str, Any], uid: bytes) -> Any:
        """Namespace UIDs by account when multiple mailboxes are configured."""
        if len(self._accounts) <= 1:
            return uid
        return (account["address"].lower(), uid)

    def _account_for_recipient(self, to_addr: str) -> Dict[str, Any]:
        ctx = self._thread_context.get(to_addr, {})
        account_address = ctx.get("account_address")
        if account_address:
            for account in self._accounts:
                if account["address"].lower() == account_address.lower():
                    return account
        return self._accounts[0] if self._accounts else {
            "address": self._address,
            "password": self._password,
            "smtp_host": self._smtp_host,
            "smtp_port": self._smtp_port,
        }

    async def connect(self) -> bool:
        """Connect to the IMAP server and start polling for new messages."""
        if not self._accounts:
            logger.error("[Email] No email accounts configured")
            return False

        for account in self._accounts:
            try:
                # Test IMAP connection
                imap = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"], timeout=30)
                try:
                    imap.login(account["address"], account["password"])
                    _send_imap_id(imap)
                    # Mark all existing messages as seen so we only process new ones
                    imap.select("INBOX")
                    status, data = imap.uid("search", None, "ALL")
                    if status == "OK" and data and data[0]:
                        for uid in data[0].split():
                            self._seen_uids.add(self._uid_key(account, uid))
                    # Keep only the most recent UIDs to prevent unbounded growth
                    self._trim_seen_uids()
                finally:
                    try:
                        imap.logout()
                    except Exception:
                        pass
                logger.info("[Email] IMAP connection test passed for %s. %d existing messages skipped.", account["address"], len(self._seen_uids))
            except Exception as e:
                logger.error("[Email] IMAP connection failed for %s: %s", account["address"], e)
                return False

            try:
                # Test SMTP connection
                smtp = smtplib.SMTP(account["smtp_host"], account["smtp_port"], timeout=30)
                try:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.login(account["address"], account["password"])
                finally:
                    try:
                        smtp.quit()
                    except Exception:
                        smtp.close()
                logger.info("[Email] SMTP connection test passed for %s.", account["address"])
            except Exception as e:
                logger.error("[Email] SMTP connection failed for %s: %s", account["address"], e)
                return False

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        print(f"[Email] Connected as {', '.join(a['address'] for a in self._accounts)}")
        return True

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
            await self._dispatch_message(msg_data)

    def _fetch_new_messages(self) -> List[Dict[str, Any]]:
        """Fetch new (unseen) messages from IMAP. Runs in executor thread."""
        results = []
        for account in (self._accounts or [{
            "address": self._address,
            "password": self._password,
            "imap_host": self._imap_host,
            "imap_port": self._imap_port,
        }]):
            try:
                imap = imaplib.IMAP4_SSL(account["imap_host"], account["imap_port"], timeout=30)
                try:
                    imap.login(account["address"], account["password"])
                    _send_imap_id(imap)
                    imap.select("INBOX")

                    status, data = imap.uid("search", None, "UNSEEN")
                    if status != "OK" or not data or not data[0]:
                        continue

                    for uid in data[0].split():
                        uid_key = self._uid_key(account, uid)
                        if uid_key in self._seen_uids:
                            continue
                        self._seen_uids.add(uid_key)
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
                            "account_address": account["address"],
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
                logger.error("[Email] IMAP fetch error for %s: %s", account.get("address", "<unknown>"), e)
        return results

    async def _dispatch_message(self, msg_data: Dict[str, Any]) -> None:
        """Convert a fetched email into a MessageEvent and dispatch it."""
        sender_addr = msg_data["sender_addr"]

        # Skip self-messages from any configured account
        own_addresses = {account["address"].lower() for account in self._accounts}
        if sender_addr.lower() in own_addresses or sender_addr == self._address.lower():
            return

        # Never reply to automated senders
        if _is_automated_sender(sender_addr, {}):
            logger.debug("[Email] Dropping automated sender at dispatch: %s", sender_addr)
            return

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
                return

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
            "account_address": msg_data.get("account_address", self._address),
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
        """Send an email via SMTP. Runs in executor thread."""
        account = self._account_for_recipient(to_addr)
        msg = MIMEMultipart()
        msg["From"] = account["address"]
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
        msg_id = f"<hermes-{uuid.uuid4().hex[:12]}@{account['address'].split('@')[1]}>"
        msg["Message-ID"] = msg_id

        msg.attach(MIMEText(body, "plain", "utf-8"))

        smtp = smtplib.SMTP(account["smtp_host"], account["smtp_port"], timeout=30)
        try:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(account["address"], account["password"])
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()

        logger.info("[Email] Sent reply to %s (subject: %s)", to_addr, subject)
        return msg_id

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
        """Send an email with multiple file attachments via SMTP."""
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
        """Send an email with a file attachment via SMTP."""
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
