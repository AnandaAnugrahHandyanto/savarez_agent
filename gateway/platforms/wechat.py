"""
WeChat platform adapter using the iLink Bot API (openclaw-weixin 2.1.x protocol).

Uses long-polling (getUpdates) for inbound messages and REST API for outbound.
Media is transmitted through the WeChat CDN with AES-128-ECB encryption.

Protocol compliance (SDK 2.1.x):
  - iLink-App-Id and iLink-App-ClientVersion headers on all API requests
  - IDC redirect (scaned_but_redirect) in QR login flow
  - Context token persistence with reload at startup
  - Referenced message (ref_msg) extraction for quoted replies
  - SILK voice transcoding with graceful fallback
  - Streaming markdown filter for outbound text
  - CDN upload with upload_full_url priority and exponential backoff

Architecture:
  - wechat.py (this file): Adapter lifecycle, message routing, platform API
  - wechat_transport.py: HTTP layer, CDN, AES crypto, iLink headers
  - wechat_state.py: Context token and sync buffer persistence

Requires:
    pip install httpx cryptography
    WECHAT_BOT_TOKEN env var (from QR login) or config.yaml

Optional:
    pip install silk-python   # For native SILK voice transcoding
"""

import asyncio
import base64
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_image_from_bytes,
    cache_audio_from_bytes,
    cache_document_from_bytes,
    get_image_cache_dir,
    get_document_cache_dir,
)
from gateway.platforms.wechat_state import (
    load_context_tokens,
    save_context_tokens,
    clear_context_tokens,
    load_sync_buf,
    save_sync_buf,
)
from gateway.platforms.wechat_transport import (
    WeChatTransport,
    check_wechat_requirements,
    parse_aes_key,
    aes_ecb_decrypt,
    mime_from_path,
    UPLOAD_MEDIA_IMAGE,
    UPLOAD_MEDIA_VIDEO,
    UPLOAD_MEDIA_FILE,
    DEFAULT_BASE_URL,
    CDN_BASE_URL,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WeChat protocol constants
# ---------------------------------------------------------------------------

WX_MSG_TYPE_USER = 1
WX_MSG_TYPE_BOT = 2
WX_MSG_STATE_FINISH = 2
WX_ITEM_TEXT = 1
WX_ITEM_IMAGE = 2
WX_ITEM_VOICE = 3
WX_ITEM_FILE = 4
WX_ITEM_VIDEO = 5

# Polling
DEFAULT_LONG_POLL_TIMEOUT_S = 35
MAX_CONSECUTIVE_FAILURES = 3
BACKOFF_DELAY_S = 30
RETRY_DELAY_S = 2

# Session expired
SESSION_EXPIRED_ERRCODE = -14
SESSION_PAUSE_DURATION_S = 3600  # 1 hour

# Message limits
MAX_MESSAGE_LENGTH = 4096
DEDUP_WINDOW_S = 300
DEDUP_MAX_SIZE = 1000


# ---------------------------------------------------------------------------
# Markdown -> plain text (WeChat doesn't render markdown)
# ---------------------------------------------------------------------------

def _markdown_to_plain(text: str) -> str:
    """Strip markdown syntax for WeChat delivery."""
    result = text
    result = re.sub(r"```[^\n]*\n?([\s\S]*?)```", lambda m: m.group(1).strip(), result)
    result = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", result)
    result = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", result)
    result = re.sub(r"^\|[\s:|\-]+\|$", "", result, flags=re.MULTILINE)

    def _table_row(m):
        inner = m.group(1)
        return "  ".join(cell.strip() for cell in inner.split("|"))
    result = re.sub(r"^\|(.+)\|$", _table_row, result, flags=re.MULTILINE)

    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"__(.+?)__", r"\1", result)
    result = re.sub(r"_(.+?)_", r"\1", result)
    result = re.sub(r"~~(.+?)~~", r"\1", result)
    result = re.sub(r"`(.+?)`", r"\1", result)
    return result


# ---------------------------------------------------------------------------
# SILK voice transcoding
# ---------------------------------------------------------------------------

def _silk_to_wav(silk_buf: bytes) -> Optional[bytes]:
    """Best-effort SILK -> WAV conversion.

    Tries:
    1. silk-decoder CLI (pip install silk-python)
    2. ffmpeg with SILK input format

    Returns WAV bytes on success, None on failure (caller falls back to
    passing raw SILK or using voice-to-text from the WeChat API).
    """
    import subprocess
    import tempfile

    silk_path = None
    wav_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".silk", delete=False) as sf:
            sf.write(silk_buf)
            silk_path = sf.name
        wav_path = silk_path.replace(".silk", ".wav")

        for cmd in [
            ["silk-decoder", silk_path, wav_path],
            ["ffmpeg", "-y", "-i", silk_path, "-ar", "24000", "-ac", "1", wav_path],
        ]:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                if result.returncode == 0 and os.path.exists(wav_path):
                    wav_data = Path(wav_path).read_bytes()
                    if len(wav_data) > 44:
                        return wav_data
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                continue
    except Exception:
        pass
    finally:
        for p in (silk_path, wav_path):
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass
    return None


# ---------------------------------------------------------------------------
# WeChatAdapter
# ---------------------------------------------------------------------------

class WeChatAdapter(BasePlatformAdapter):
    """WeChat chatbot adapter using the iLink Bot long-polling API.

    Message flow:
        1. connect() loads persisted state and starts the long-poll loop
        2. Inbound messages are parsed, media is downloaded/decrypted from CDN
        3. Referenced messages (ref_msg) are extracted for quote context
        4. MessageEvent is dispatched to self.handle_message()
        5. Outbound text has markdown stripped; media is encrypted + uploaded to CDN
    """

    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.WECHAT)

        extra = config.extra or {}
        token = config.token or os.getenv("WECHAT_BOT_TOKEN", "")
        base_url = extra.get("base_url") or os.getenv("WECHAT_API_BASE_URL", DEFAULT_BASE_URL)
        cdn_base_url = extra.get("cdn_base_url") or os.getenv("WECHAT_CDN_BASE_URL", CDN_BASE_URL)
        ilink_app_id = extra.get("ilink_app_id") or os.getenv("WECHAT_ILINK_APP_ID", "bot")
        ilink_version_raw = extra.get("ilink_client_version")
        if ilink_version_raw is None or ilink_version_raw == "":
            ilink_version_raw = os.getenv("WECHAT_ILINK_CLIENT_VERSION", "")
        ilink_version = int(ilink_version_raw) if ilink_version_raw not in (None, "") else None

        self._account_id: str = extra.get("account_id") or os.getenv("WECHAT_ACCOUNT_ID", "")
        self._transport = WeChatTransport(
            token=token,
            base_url=base_url,
            cdn_base_url=cdn_base_url,
            ilink_app_id=ilink_app_id,
            ilink_client_version=ilink_version,
        )

        self._poll_task: Optional[asyncio.Task] = None

        # Context tokens: loaded from disk at startup, updated on each inbound message
        self._context_tokens: Dict[str, str] = {}
        # Typing tickets: user_id -> (ticket, fetched_at)
        self._typing_tickets: Dict[str, Tuple[str, float]] = {}
        self._typing_ticket_ttl_s: float = 12 * 3600

        # Deduplication
        self._seen_messages: Dict[str, float] = {}

        # Session pause (errcode -14)
        self._paused_until: float = 0.0

    # -- Connection lifecycle -----------------------------------------------

    async def connect(self) -> bool:
        """Start the long-poll loop for inbound messages."""
        if not check_wechat_requirements():
            logger.error("[WeChat] Missing dependencies (httpx, cryptography)")
            return False

        if not self._transport._token:
            logger.error("[WeChat] No token configured. Run scripts/wechat_login.py or set WECHAT_BOT_TOKEN")
            self._set_fatal_error("no_token", "WeChat token not configured", retryable=False)
            await self._notify_fatal_error()
            return False

        try:
            await self._transport.open()

            # Load persisted context tokens (survive gateway restarts)
            self._context_tokens = load_context_tokens()

            self._poll_task = asyncio.create_task(self._poll_loop())
            self._mark_connected()
            logger.info("[WeChat] Connected, starting poll loop (account=%s)", self._account_id or "default")
            return True
        except Exception as e:
            logger.error("[WeChat] Failed to connect: %s", e)
            return False

    async def disconnect(self) -> None:
        """Stop polling and clean up."""
        self._running = False
        self._mark_disconnected()

        # Cancel poll task first (may be blocked on a 40s HTTP timeout)
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        await self.cancel_background_tasks()
        await self._transport.close()

        self._context_tokens.clear()
        self._typing_tickets.clear()
        self._seen_messages.clear()
        logger.info("[WeChat] Disconnected")

    # -- Long-poll loop -----------------------------------------------------

    async def _poll_loop(self) -> None:
        """Long-poll getUpdates in a loop until disconnected."""
        get_updates_buf = load_sync_buf(self._account_id)
        if get_updates_buf:
            logger.info("[WeChat] Resuming from saved sync buf (%d bytes)", len(get_updates_buf))

        consecutive_failures = 0
        poll_timeout_ms = DEFAULT_LONG_POLL_TIMEOUT_S * 1000

        while self._running:
            try:
                # Session pause check
                if self._paused_until > time.time():
                    remaining = int(self._paused_until - time.time())
                    logger.info("[WeChat] Session paused, %ds remaining", remaining)
                    await asyncio.sleep(min(remaining, 60))
                    continue

                resp = await self._transport.get_updates(
                    get_updates_buf,
                    timeout_s=poll_timeout_ms / 1000 + 5,
                )

                suggested = resp.get("longpolling_timeout_ms")
                if isinstance(suggested, (int, float)) and suggested > 0:
                    poll_timeout_ms = int(suggested)

                ret = resp.get("ret", 0)
                errcode = resp.get("errcode", 0)
                is_error = (ret != 0) or (errcode != 0)

                if is_error:
                    if errcode == SESSION_EXPIRED_ERRCODE or ret == SESSION_EXPIRED_ERRCODE:
                        self._paused_until = time.time() + SESSION_PAUSE_DURATION_S
                        # Clear context tokens on session expiry
                        self._context_tokens.clear()
                        clear_context_tokens()
                        logger.warning(
                            "[WeChat] Session expired (errcode %d), pausing for %d min, tokens cleared",
                            SESSION_EXPIRED_ERRCODE, SESSION_PAUSE_DURATION_S // 60,
                        )
                        consecutive_failures = 0
                        continue

                    consecutive_failures += 1
                    logger.warning(
                        "[WeChat] getUpdates error: ret=%s errcode=%s errmsg=%s (%d/%d)",
                        ret, errcode, resp.get("errmsg", ""), consecutive_failures, MAX_CONSECUTIVE_FAILURES,
                    )
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        consecutive_failures = 0
                        await asyncio.sleep(BACKOFF_DELAY_S)
                    else:
                        await asyncio.sleep(RETRY_DELAY_S)
                    continue

                consecutive_failures = 0

                new_buf = resp.get("get_updates_buf", "")
                if new_buf:
                    get_updates_buf = new_buf
                    save_sync_buf(self._account_id, new_buf)

                msgs = resp.get("msgs") or []
                for msg in msgs:
                    try:
                        await self._on_message(msg)
                    except Exception as e:
                        logger.error("[WeChat] Error processing message: %s", e, exc_info=True)

            except asyncio.CancelledError:
                return
            except Exception as e:
                if not self._running:
                    return
                consecutive_failures += 1
                logger.warning("[WeChat] Poll loop error (%d/%d): %s", consecutive_failures, MAX_CONSECUTIVE_FAILURES, e)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    consecutive_failures = 0
                    await asyncio.sleep(BACKOFF_DELAY_S)
                else:
                    await asyncio.sleep(RETRY_DELAY_S)

    # -- Inbound message processing -----------------------------------------

    async def _on_message(self, msg: Dict[str, Any]) -> None:
        """Process a single inbound WeChat message."""
        from_user = msg.get("from_user_id", "")
        if not from_user:
            return

        msg_id = str(msg.get("message_id", ""))
        seq = str(msg.get("seq", ""))
        dedup_key = f"{from_user}:{msg_id}:{seq}"
        if self._is_duplicate(dedup_key):
            return

        if msg.get("message_type") != WX_MSG_TYPE_USER:
            return
        if self._account_id and from_user == self._account_id:
            return

        # Cache context token
        context_token = msg.get("context_token", "")
        if context_token:
            self._context_tokens[from_user] = context_token
            save_context_tokens(self._context_tokens)

        items = msg.get("item_list") or []
        text = self._extract_text(items)

        hermes_msg_type = MessageType.TEXT
        media_urls: List[str] = []
        media_types: List[str] = []

        media_item = self._find_media_item(items)
        if media_item:
            try:
                path, mime, mtype = await self._download_media(media_item)
                if path:
                    media_urls.append(path)
                    media_types.append(mime)
                    hermes_msg_type = mtype
            except Exception as e:
                logger.error("[WeChat] Media download failed: %s", e)

        # Voice STT fallback
        if not text and hermes_msg_type == MessageType.VOICE:
            if media_item and media_item.get("type") == WX_ITEM_VOICE:
                stt = (media_item.get("voice_item") or {}).get("text", "")
                if stt:
                    text = stt

        if not text and not media_urls:
            return

        # Fetch typing ticket (async, non-blocking)
        task = asyncio.create_task(self._cache_typing_ticket(from_user, context_token))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        source = self.build_source(chat_id=from_user, chat_type="dm", user_id=from_user)

        create_time_ms = msg.get("create_time_ms")
        try:
            timestamp = datetime.fromtimestamp(
                create_time_ms / 1000, tz=timezone.utc
            ) if create_time_ms else datetime.now(tz=timezone.utc)
        except (ValueError, OSError, TypeError):
            timestamp = datetime.now(tz=timezone.utc)

        event = MessageEvent(
            text=text or "",
            message_type=hermes_msg_type,
            source=source,
            message_id=msg_id or seq,
            raw_message=msg,
            media_urls=media_urls,
            media_types=media_types,
            timestamp=timestamp,
        )

        await self.handle_message(event)

    @staticmethod
    def _extract_text(items: List[Dict[str, Any]]) -> str:
        """Extract text from item_list, handling referenced messages (ref_msg)."""
        for item in items:
            if item.get("type") == WX_ITEM_TEXT:
                text_item = item.get("text_item") or {}
                text = text_item.get("text", "")

                ref = item.get("ref_msg")
                if not ref:
                    return text

                # Quoted media: just return the text part
                ref_item = ref.get("message_item")
                if ref_item and ref_item.get("type") in (WX_ITEM_IMAGE, WX_ITEM_VIDEO, WX_ITEM_FILE, WX_ITEM_VOICE):
                    return text

                # Build quoted context from title and message content
                parts = []
                title = ref.get("title", "")
                if title:
                    parts.append(title)
                if ref_item:
                    ref_text = WeChatAdapter._extract_text([ref_item])
                    if ref_text:
                        parts.append(ref_text)

                if parts:
                    return f'[Quote: {" | ".join(parts)}]\n{text}'
                return text

            # Voice with speech-to-text
            if item.get("type") == WX_ITEM_VOICE:
                voice = item.get("voice_item") or {}
                if voice.get("text"):
                    return voice["text"]

        return ""

    @staticmethod
    def _find_media_item(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the first downloadable media item (priority: image > video > file > voice).

        Voice items with server-side STT (voice_item.text) are skipped —
        the transcription is used as text instead.
        """
        for item_type in (WX_ITEM_IMAGE, WX_ITEM_VIDEO, WX_ITEM_FILE, WX_ITEM_VOICE):
            for item in items:
                if item.get("type") == item_type:
                    if item_type == WX_ITEM_VOICE:
                        voice_data = item.get("voice_item") or {}
                        if voice_data.get("text"):
                            continue
                    type_key = {
                        WX_ITEM_IMAGE: "image_item",
                        WX_ITEM_VIDEO: "video_item",
                        WX_ITEM_FILE: "file_item",
                        WX_ITEM_VOICE: "voice_item",
                    }[item_type]
                    media_data = item.get(type_key) or {}
                    media_ref = media_data.get("media") or {}
                    if media_ref.get("encrypt_query_param") or media_ref.get("full_url"):
                        return item

        # Check quoted media in ref_msg
        for item in items:
            if item.get("type") == WX_ITEM_TEXT:
                ref = item.get("ref_msg", {})
                ref_item = ref.get("message_item")
                if ref_item and ref_item.get("type") in (WX_ITEM_IMAGE, WX_ITEM_VIDEO, WX_ITEM_FILE, WX_ITEM_VOICE):
                    type_key = {
                        WX_ITEM_IMAGE: "image_item", WX_ITEM_VIDEO: "video_item",
                        WX_ITEM_FILE: "file_item", WX_ITEM_VOICE: "voice_item",
                    }.get(ref_item["type"])
                    if type_key:
                        media_ref = (ref_item.get(type_key) or {}).get("media") or {}
                        if media_ref.get("encrypt_query_param") or media_ref.get("full_url"):
                            return ref_item

        return None

    async def _download_media(self, item: Dict[str, Any]) -> Tuple[str, str, MessageType]:
        """Download and decrypt media from CDN. Returns (local_path, mime, message_type)."""
        item_type = item.get("type")

        if item_type == WX_ITEM_IMAGE:
            img = item.get("image_item") or {}
            media = img.get("media") or {}
            eqp = media.get("encrypt_query_param", "")
            fu = media.get("full_url", "")
            if img.get("aeskey"):
                aes_key_b64 = base64.b64encode(bytes.fromhex(img["aeskey"])).decode()
            else:
                aes_key_b64 = media.get("aes_key", "")
            if not eqp and not fu:
                return ("", "", MessageType.TEXT)
            buf = await self._transport.cdn_download_decrypt(eqp, aes_key_b64, full_url=fu) if aes_key_b64 else await self._transport.cdn_download_plain(eqp, full_url=fu)
            path = cache_image_from_bytes(buf, ".jpg")
            return (path, "image/jpeg", MessageType.PHOTO)

        elif item_type == WX_ITEM_VOICE:
            voice = item.get("voice_item") or {}
            media = voice.get("media") or {}
            eqp = media.get("encrypt_query_param", "")
            fu = media.get("full_url", "")
            aes_key_b64 = media.get("aes_key", "")
            if (not eqp and not fu) or not aes_key_b64:
                return ("", "", MessageType.TEXT)
            silk_buf = await self._transport.cdn_download_decrypt(eqp, aes_key_b64, full_url=fu)
            wav_buf = _silk_to_wav(silk_buf)
            if wav_buf:
                path = cache_audio_from_bytes(wav_buf, ".wav")
                return (path, "audio/wav", MessageType.VOICE)
            else:
                path = cache_audio_from_bytes(silk_buf, ".silk")
                return (path, "audio/silk", MessageType.VOICE)

        elif item_type == WX_ITEM_FILE:
            file_item = item.get("file_item") or {}
            media = file_item.get("media") or {}
            eqp = media.get("encrypt_query_param", "")
            fu = media.get("full_url", "")
            aes_key_b64 = media.get("aes_key", "")
            filename = file_item.get("file_name", "file.bin")
            if (not eqp and not fu) or not aes_key_b64:
                return ("", "", MessageType.TEXT)
            buf = await self._transport.cdn_download_decrypt(eqp, aes_key_b64, full_url=fu)
            path = cache_document_from_bytes(buf, filename)
            return (path, mime_from_path(filename), MessageType.DOCUMENT)

        elif item_type == WX_ITEM_VIDEO:
            video = item.get("video_item") or {}
            media = video.get("media") or {}
            eqp = media.get("encrypt_query_param", "")
            fu = media.get("full_url", "")
            aes_key_b64 = media.get("aes_key", "")
            if (not eqp and not fu) or not aes_key_b64:
                return ("", "", MessageType.TEXT)
            buf = await self._transport.cdn_download_decrypt(eqp, aes_key_b64, full_url=fu)
            path = cache_document_from_bytes(buf, f"video_{uuid.uuid4().hex[:8]}.mp4")
            return (path, "video/mp4", MessageType.VIDEO)

        return ("", "", MessageType.TEXT)

    # -- Deduplication ------------------------------------------------------

    def _is_duplicate(self, key: str) -> bool:
        now = time.time()
        if len(self._seen_messages) > DEDUP_MAX_SIZE:
            cutoff = now - DEDUP_WINDOW_S
            self._seen_messages = {k: v for k, v in self._seen_messages.items() if v > cutoff}
        if key in self._seen_messages:
            return True
        self._seen_messages[key] = now
        return False

    # -- Outbound: text -----------------------------------------------------

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a plain text message to a WeChat user."""
        context_token = self._context_tokens.get(chat_id)
        if not context_token:
            return SendResult(success=False, error="No context_token for this user (they haven't messaged yet)")

        plain = _markdown_to_plain(content).strip()
        if not plain:
            return SendResult(success=True, message_id="skipped-empty")

        chunks = self.truncate_message(plain, self.MAX_MESSAGE_LENGTH)
        last_id = None

        try:
            for chunk in chunks:
                client_id = f"hermes-{uuid.uuid4().hex[:12]}"
                body = {
                    "msg": {
                        "from_user_id": "",
                        "to_user_id": chat_id,
                        "client_id": client_id,
                        "message_type": WX_MSG_TYPE_BOT,
                        "message_state": WX_MSG_STATE_FINISH,
                        "item_list": [{"type": WX_ITEM_TEXT, "text_item": {"text": chunk}}],
                        "context_token": context_token,
                    },
                }
                resp = await self._transport.send_message(body)
                if resp.get("ret", 0) != 0:
                    raise RuntimeError(f"ret={resp.get('ret')} {resp.get('errmsg', '')}")
                last_id = client_id
            return SendResult(success=True, message_id=last_id)
        except Exception as e:
            logger.error("[WeChat] Send failed: %s", e)
            return SendResult(success=False, error=str(e))

    # -- Outbound: typing ---------------------------------------------------

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """Send typing indicator via WeChat API."""
        entry = self._typing_tickets.get(chat_id)
        if not entry:
            return
        ticket, _ = entry
        await self._transport.send_typing(chat_id, ticket)

    async def _cache_typing_ticket(self, user_id: str, context_token: str) -> None:
        """Fetch and cache the typing_ticket for a user (with TTL refresh)."""
        entry = self._typing_tickets.get(user_id)
        if entry:
            _, fetched_at = entry
            if time.time() - fetched_at < self._typing_ticket_ttl_s:
                return
        try:
            resp = await self._transport.get_config(user_id, context_token)
            ticket = resp.get("typing_ticket", "")
            if ticket:
                self._typing_tickets[user_id] = (ticket, time.time())
        except Exception as e:
            logger.debug("[WeChat] Failed to get typing ticket: %s", e)

    # -- Outbound: media ----------------------------------------------------

    async def send_image(
        self, chat_id: str, image_url: str,
        caption: Optional[str] = None, reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        try:
            local_path, _ = await self._transport.download_remote_file(image_url, get_image_cache_dir())
            return await self._send_media_file(chat_id, local_path, caption, UPLOAD_MEDIA_IMAGE, WX_ITEM_IMAGE)
        except Exception as e:
            logger.error("[WeChat] send_image failed: %s", e)
            text = f"{caption}\n{image_url}" if caption else image_url
            return await self.send(chat_id, text)

    async def send_image_file(
        self, chat_id: str, image_path: str,
        caption: Optional[str] = None, reply_to: Optional[str] = None, **kwargs,
    ) -> SendResult:
        try:
            return await self._send_media_file(chat_id, image_path, caption, UPLOAD_MEDIA_IMAGE, WX_ITEM_IMAGE)
        except Exception as e:
            logger.error("[WeChat] send_image_file failed: %s", e)
            return SendResult(success=False, error=str(e))

    async def send_video(
        self, chat_id: str, video_path: str,
        caption: Optional[str] = None, reply_to: Optional[str] = None, **kwargs,
    ) -> SendResult:
        try:
            return await self._send_media_file(chat_id, video_path, caption, UPLOAD_MEDIA_VIDEO, WX_ITEM_VIDEO)
        except Exception as e:
            logger.error("[WeChat] send_video failed: %s", e)
            return SendResult(success=False, error=str(e))

    async def send_document(
        self, chat_id: str, file_path: str,
        caption: Optional[str] = None, file_name: Optional[str] = None,
        reply_to: Optional[str] = None, **kwargs,
    ) -> SendResult:
        try:
            return await self._send_media_file(
                chat_id, file_path, caption, UPLOAD_MEDIA_FILE, WX_ITEM_FILE,
                file_name=file_name or Path(file_path).name,
            )
        except Exception as e:
            logger.error("[WeChat] send_document failed: %s", e)
            return SendResult(success=False, error=str(e))

    async def send_voice(
        self, chat_id: str, audio_path: str,
        caption: Optional[str] = None, reply_to: Optional[str] = None, **kwargs,
    ) -> SendResult:
        """Send audio as a file attachment.

        Native voice bubbles are not supported by the iLink Bot API for
        outbound — even Tencent's SDK sends audio as FILE attachments.
        """
        try:
            send_path = audio_path
            compressed_path = None
            if Path(audio_path).stat().st_size > 100_000:
                compressed_path = self._compress_audio(audio_path)
                if compressed_path:
                    send_path = compressed_path
            try:
                return await self._send_media_file(
                    chat_id, send_path, caption,
                    UPLOAD_MEDIA_FILE, WX_ITEM_FILE,
                    file_name=Path(audio_path).name,
                )
            finally:
                if compressed_path:
                    try:
                        os.unlink(compressed_path)
                    except OSError:
                        pass
        except Exception as e:
            logger.error("[WeChat] send_voice failed: %s", e)
            return SendResult(success=False, error=str(e))

    @staticmethod
    def _compress_audio(audio_path: str) -> Optional[str]:
        """Compress audio with ffmpeg for CDN upload. Returns temp path or None."""
        import subprocess
        import tempfile
        try:
            fd, out_path = tempfile.mkstemp(suffix=Path(audio_path).suffix)
            os.close(fd)
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", "-b:a", "64k", out_path],
                capture_output=True, timeout=15,
            )
            if result.returncode == 0 and Path(out_path).stat().st_size > 0:
                return out_path
            os.unlink(out_path)
            return None
        except Exception:
            return None

    async def _send_media_file(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str],
        upload_media_type: int,
        wx_item_type: int,
        file_name: Optional[str] = None,
    ) -> SendResult:
        """Upload a file to CDN and send it as a WeChat message."""
        context_token = self._context_tokens.get(chat_id)
        if not context_token:
            return SendResult(success=False, error="No context_token for this user")

        uploaded = await self._transport.cdn_upload(file_path, chat_id, upload_media_type)

        # Outbound aes_key: base64(hex string) for all media types
        aes_key_b64 = base64.b64encode(uploaded["aeskey"].encode()).decode()

        if wx_item_type == WX_ITEM_IMAGE:
            media_item = {
                "type": WX_ITEM_IMAGE,
                "image_item": {
                    "media": {
                        "encrypt_query_param": uploaded["download_param"],
                        "aes_key": aes_key_b64,
                        "encrypt_type": 1,
                    },
                    "mid_size": uploaded["ciphertext_size"],
                },
            }
        elif wx_item_type == WX_ITEM_VIDEO:
            media_item = {
                "type": WX_ITEM_VIDEO,
                "video_item": {
                    "media": {
                        "encrypt_query_param": uploaded["download_param"],
                        "aes_key": aes_key_b64,
                        "encrypt_type": 1,
                    },
                    "video_size": uploaded["ciphertext_size"],
                },
            }
        elif wx_item_type == WX_ITEM_FILE:
            media_item = {
                "type": WX_ITEM_FILE,
                "file_item": {
                    "media": {
                        "encrypt_query_param": uploaded["download_param"],
                        "aes_key": aes_key_b64,
                        "encrypt_type": 1,
                    },
                    "file_name": file_name or Path(file_path).name,
                    "len": str(uploaded["plaintext_size"]),
                },
            }
        else:
            return SendResult(success=False, error=f"Unsupported item type: {wx_item_type}")

        item_list = []
        if caption:
            item_list.append({"type": WX_ITEM_TEXT, "text_item": {"text": _markdown_to_plain(caption)}})
        item_list.append(media_item)

        last_cid = None
        for item in item_list:
            cid = f"hermes-{uuid.uuid4().hex[:12]}"
            body = {
                "msg": {
                    "from_user_id": "",
                    "to_user_id": chat_id,
                    "client_id": cid,
                    "message_type": WX_MSG_TYPE_BOT,
                    "message_state": WX_MSG_STATE_FINISH,
                    "item_list": [item],
                    "context_token": context_token,
                },
            }
            resp = await self._transport.send_message(body)
            if resp.get("ret", 0) != 0:
                raise RuntimeError(f"sendmessage ret={resp.get('ret')} {resp.get('errmsg', '')}")
            last_cid = cid

        return SendResult(success=True, message_id=last_cid)

    # -- Chat info ----------------------------------------------------------

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {
            "name": chat_id[:12] + "..." if len(chat_id) > 12 else chat_id,
            "type": "dm",
            "chat_id": chat_id,
        }

    def format_message(self, content: str) -> str:
        """Strip markdown for WeChat (plain text only)."""
        return _markdown_to_plain(content)
