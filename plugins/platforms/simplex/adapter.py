"""SimpleX Chat platform adapter (Hermes plugin).

Connects to a simplex-chat daemon running in WebSocket mode.
Inbound messages arrive via a persistent WebSocket connection.
Outbound messages use the same WebSocket with JSON commands.

This adapter ships as a Hermes platform plugin under
``plugins/platforms/simplex/``. The Hermes plugin loader scans the
directory at startup, calls ``register(ctx)``, and the platform
becomes available to ``gateway/run.py`` and ``tools/send_message_tool``
through the registry — no edits to core files are required.

SimpleX chat daemon setup:
    simplex-chat -p 5225          # start daemon on port 5225
    # or via Docker:
    # docker run -p 5225:5225 simplexchat/simplex-chat-cli -p 5225

Required environment variables:
    SIMPLEX_WS_URL             WebSocket URL of the daemon
                               (default: ws://127.0.0.1:5225)

Optional environment variables:
    SIMPLEX_ALLOWED_USERS      Comma-separated contact IDs (allowlist)
    SIMPLEX_ALLOW_ALL_USERS    Set 'true' to allow all contacts
    SIMPLEX_HOME_CHANNEL       Default contact/group display name for cron delivery
    SIMPLEX_HOME_CHANNEL_NAME  Human label for the home channel

The ``websockets`` Python package is imported lazily — the plugin is
discoverable and `hermes setup` can describe it even when websockets is
not installed. ``check_requirements()`` returns False until the package
is present, so the gateway will not attempt to instantiate the adapter.
"""

import asyncio
import inspect
import json
import logging
import os
import random
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Lazy import: BasePlatformAdapter and friends live in the main repo.
# Imported at module top because they're stdlib-only inside Hermes — no
# external dependency that would block the plugin from loading.
from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    cache_image_from_bytes,
    cache_audio_from_bytes,
    cache_document_from_bytes,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_MESSAGE_LENGTH = 16_000  # SimpleX has no hard limit; keep chunking sane
TYPING_INTERVAL = 10.0
WS_RETRY_DELAY_INITIAL = 2.0
WS_RETRY_DELAY_MAX = 60.0
HEALTH_CHECK_INTERVAL = 30.0
HEALTH_CHECK_STALE_THRESHOLD = 120.0
CATCH_UP_TAIL_LIMIT = 50

# Correlation ID prefix for requests we send so we can ignore our own echoes.
_CORR_PREFIX = "hermes-"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_comma_list(value: str) -> List[str]:
    """Split a comma-separated string into a stripped list."""
    return [v.strip() for v in value.split(",") if v.strip()]


def _guess_extension(data: bytes) -> str:
    """Guess file extension from magic bytes."""
    if data[:4] == b"\x89PNG":
        return ".png"
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:4] == b"GIF8":
        return ".gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:4] == b"%PDF":
        return ".pdf"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return ".mp4"
    if data[:4] == b"OggS":
        return ".ogg"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return ".mp3"
    return ".bin"


def _is_image_ext(ext: str) -> bool:
    return ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp")


def _is_audio_ext(ext: str) -> bool:
    return ext.lower() in (".mp3", ".wav", ".ogg", ".m4a", ".aac")


# ---------------------------------------------------------------------------
# SimpleX Adapter
# ---------------------------------------------------------------------------

class SimplexAdapter(BasePlatformAdapter):
    """SimpleX Chat adapter using the simplex-chat daemon WebSocket API.

    Instantiated by the ``adapter_factory`` passed to
    ``ctx.register_platform()`` in :func:`register`.
    """

    def __init__(self, config: PlatformConfig, **kwargs):
        platform = Platform("simplex")
        super().__init__(config=config, platform=platform)

        extra = getattr(config, "extra", {}) or {}
        self.ws_url = extra.get("ws_url", "ws://127.0.0.1:5225").rstrip("/")

        # Running state
        self._ws = None  # websockets connection
        self._ws_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None
        self._typing_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._last_ws_activity = 0.0
        self._catch_up_primed = False
        self._catch_up_pending = 0
        self._catch_up_corr_ids: set[str] = set()
        self._seen_item_ids: OrderedDict[str, None] = OrderedDict()

        # Track sent correlation IDs to filter echoes
        self._pending_corr_ids: set = set()
        self._max_pending_corr = 200

        logger.info("SimpleX adapter initialized: url=%s", self.ws_url)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to the simplex-chat daemon and start the WebSocket listener."""
        try:
            import websockets  # noqa: F401
        except ImportError:
            logger.error(
                "SimpleX: 'websockets' package not installed. "
                "Run: pip install websockets"
            )
            return False

        if not self.ws_url:
            logger.error("SimpleX: SIMPLEX_WS_URL is required")
            return False

        # Quick connectivity check — try to open and immediately close
        try:
            import websockets as _wsclient
            async with _wsclient.connect(self.ws_url, open_timeout=10):
                pass
        except Exception as e:
            logger.error("SimpleX: cannot reach daemon at %s: %s", self.ws_url, e)
            return False

        self._running = True
        self._last_ws_activity = time.time()
        self._ws_task = asyncio.create_task(self._ws_listener())
        self._health_task = asyncio.create_task(self._health_monitor())

        logger.info("SimpleX: connected to %s", self.ws_url)
        return True

    async def disconnect(self) -> None:
        """Stop WebSocket listener and clean up."""
        self._running = False

        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        for task in self._typing_tasks.values():
            task.cancel()
        self._typing_tasks.clear()

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        logger.info("SimpleX: disconnected")

    # ------------------------------------------------------------------
    # WebSocket listener
    # ------------------------------------------------------------------

    async def _ws_listener(self) -> None:
        """Maintain a persistent WebSocket connection to the daemon."""
        import websockets as _wsclient
        import websockets as _wsexc

        backoff = WS_RETRY_DELAY_INITIAL

        while self._running:
            try:
                logger.debug("SimpleX WS: connecting to %s", self.ws_url)
                async with _wsclient.connect(
                    self.ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    self._ws = ws
                    backoff = WS_RETRY_DELAY_INITIAL
                    self._last_ws_activity = time.time()
                    logger.info("SimpleX WS: connected")
                    await self._request_catch_up()

                    async for raw in ws:
                        if not self._running:
                            break
                        self._last_ws_activity = time.time()
                        try:
                            msg = json.loads(raw)
                            await self._handle_event(msg)
                        except json.JSONDecodeError:
                            logger.debug("SimpleX WS: invalid JSON: %.100s", raw)
                        except Exception:
                            logger.exception("SimpleX WS: error handling event")

            except asyncio.CancelledError:
                break
            except _wsexc.WebSocketException as e:
                if self._running:
                    logger.warning(
                        "SimpleX WS: error: %s (reconnecting in %.0fs)", e, backoff
                    )
            except Exception as e:
                if self._running:
                    logger.warning(
                        "SimpleX WS: unexpected error: %s (reconnecting in %.0fs)",
                        e, backoff,
                    )
            finally:
                self._ws = None

            if self._running:
                jitter = backoff * 0.2 * random.random()
                await asyncio.sleep(backoff + jitter)
                backoff = min(backoff * 2, WS_RETRY_DELAY_MAX)

    # ------------------------------------------------------------------
    # Health monitor
    # ------------------------------------------------------------------

    async def _health_monitor(self) -> None:
        """Validate the WebSocket when no SimpleX events have arrived recently.

        A quiet chat can legitimately produce no `newChatItem` frames for long
        periods, so receive-side idleness alone is not a failure. Use a protocol
        ping to verify the socket instead of force-closing a healthy stream.
        The websockets client will close/reconnect on ping failure.
        """
        while self._running:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            if not self._running:
                break

            elapsed = time.time() - self._last_ws_activity
            if elapsed <= HEALTH_CHECK_STALE_THRESHOLD:
                continue

            ws = self._ws
            if not ws:
                continue

            try:
                maybe_pong_waiter = ws.ping()
                pong_waiter = (
                    await maybe_pong_waiter
                    if inspect.isawaitable(maybe_pong_waiter)
                    else maybe_pong_waiter
                )
                await asyncio.wait_for(pong_waiter, timeout=10)
                self._last_ws_activity = time.time()
                logger.debug("SimpleX: WS idle for %.0fs but ping succeeded", elapsed)
            except Exception:
                logger.warning(
                    "SimpleX: WS idle for %.0fs and ping failed; forcing reconnect",
                    elapsed,
                )
                try:
                    await ws.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Inbound event handling
    # ------------------------------------------------------------------

    async def _handle_event(self, event: dict) -> None:
        """Dispatch a daemon event to the appropriate handler."""
        resp = event.get("resp") if isinstance(event.get("resp"), dict) else {}
        resp_type = event.get("type") or resp.get("type", "")

        # Filter responses to our own commands (echoes)
        corr_id = event.get("corrId", "")
        if corr_id and corr_id.startswith(_CORR_PREFIX):
            self._pending_corr_ids.discard(corr_id)
            return

        # SimpleX WebSocket events are usually wrapped as
        # {"corrId": "", "resp": {"type": "newChatItem", ...}}.
        # Normalize that wrapper and the nested AChatItem/ChatData variants
        # before extracting chatInfo/chatItem.
        payload = resp or event
        if resp_type == "newChatItem":
            await self._handle_new_chat_item(self._normalize_chat_item_wrapper(payload))
        elif resp_type == "newChatItems":
            # Batch variant — process each item.
            for item_wrapper in self._normalize_chat_items_payload(payload):
                await self._handle_new_chat_item(item_wrapper)
        elif resp_type == "chatItems":
            # Catch-up responses come from explicit `/tail @chat N` requests we
            # send after the WebSocket connects/reconnects. They are not a
            # continuous poll loop; the live stream remains the primary path.
            await self._handle_catch_up_chat_items(
                self._normalize_chat_items_payload(payload), corr_id=corr_id
            )
        elif resp_type == "chats":
            # On connect/reconnect, request recent items for each chat once so
            # messages that arrived while the socket was down are not lost.
            await self._handle_catch_up_chats(payload.get("chats") or [])
        elif corr_id in self._catch_up_corr_ids:
            # Count error/unexpected responses to catch-up tail commands so the
            # initial priming window cannot get stuck forever.
            self._complete_catch_up_request(corr_id)
        # Ignore all other event types (delivery receipts, contact updates, etc.)

    async def _request_catch_up(self) -> None:
        """Ask the persistent WebSocket for chats once after connect/reconnect."""
        ok = await self._send_ws({
            "corrId": f"simplex-catchup-chats-{int(time.time() * 1000)}",
            "cmd": "/chats",
        }, persistent_only=True)
        if not ok:
            logger.debug("SimpleX: skipped catch-up request; persistent WS unavailable")

    @staticmethod
    def _quote_simplex_name(name: str) -> str:
        """Quote a SimpleX text-command target component when needed."""
        if not name:
            return ""
        if any(ch.isspace() for ch in name) or "'" in name:
            return "'" + name.replace("'", "\\'") + "'"
        return name

    def _simplex_dm_ref(self, name: str) -> str:
        return f"@{self._quote_simplex_name(name)}"

    def _simplex_group_ref(self, name: str) -> str:
        return f"#{self._quote_simplex_name(name)}"

    def _normalize_chat_item_wrapper(self, payload: dict) -> dict:
        """Normalize SimpleX AChatItem variants to {chatInfo, chatItem}."""
        if not isinstance(payload, dict):
            return {}

        nested = payload.get("chatItem")
        if isinstance(nested, dict):
            # Some daemon responses wrap the actual item as:
            # {type: newChatItem, chatItem: {chatInfo: ..., chatItem: ...}}
            if isinstance(nested.get("chatInfo"), dict) and isinstance(nested.get("chatItem"), dict):
                return nested
            # Already normalized: {chatInfo: ..., chatItem: {content/meta...}}
            if isinstance(payload.get("chatInfo"), dict):
                return payload

        if isinstance(payload.get("chatInfo"), dict) and isinstance(payload.get("item"), dict):
            return {"chatInfo": payload["chatInfo"], "chatItem": payload["item"]}

        return payload

    def _normalize_chat_items_payload(self, payload: dict) -> list[dict]:
        """Normalize `newChatItems`/`chatItems` response shapes to wrappers."""
        raw = payload.get("chatItems") if isinstance(payload, dict) else []
        if isinstance(raw, list):
            return [self._normalize_chat_item_wrapper(item) for item in raw]

        if isinstance(raw, dict):
            shared_chat_info = raw.get("chatInfo") or raw.get("chat") or payload.get("chatInfo")
            items = raw.get("chatItems") or raw.get("items") or []
            normalized = []
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and (item.get("chatInfo") or item.get("chat")):
                    normalized.append(self._normalize_chat_item_wrapper(item))
                elif isinstance(item, dict) and shared_chat_info:
                    normalized.append({"chatInfo": shared_chat_info, "chatItem": item})
            return normalized

        return []

    def _simplex_chat_ref(self, chat: dict) -> Optional[str]:
        """Return a SimpleX chat reference suitable for `/tail <ref> 50`."""
        chat_info = chat.get("chatInfo") or chat.get("chat") or {}
        chat_type = chat_info.get("type", "")

        if chat_type in ("group", "groupInfo"):
            group_info = chat_info.get("groupInfo") or chat_info.get("group") or {}
            name = (
                group_info.get("localDisplayName")
                or group_info.get("displayName")
                or (group_info.get("groupProfile") or {}).get("displayName")
                or ""
            )
            return self._simplex_group_ref(str(name)) if name else None

        contact_info = chat_info.get("contact") or {}
        name = (
            contact_info.get("localDisplayName")
            or contact_info.get("displayName")
            or (contact_info.get("profile") or {}).get("displayName")
            or ""
        )
        return self._simplex_dm_ref(str(name)) if name else None

    async def _handle_catch_up_chats(self, chats: list[dict]) -> None:
        """Request recent items once for each chat returned by `/chats`."""
        refs = [ref for chat in chats if (ref := self._simplex_chat_ref(chat))]
        if not refs:
            if not self._catch_up_primed:
                self._catch_up_primed = True
            return

        if not self._catch_up_primed:
            self._catch_up_pending = len(refs)

        for ref in refs:
            corr_id = f"simplex-catchup-tail-{int(time.time() * 1000)}-{random.randint(0, 9999)}"
            if not self._catch_up_primed:
                self._catch_up_corr_ids.add(corr_id)
            ok = await self._send_ws({
                "corrId": corr_id,
                "cmd": f"/tail {ref} {CATCH_UP_TAIL_LIMIT}",
            }, persistent_only=True)
            if not ok and not self._catch_up_primed:
                self._complete_catch_up_request(corr_id)

        if not self._catch_up_primed and self._catch_up_pending == 0:
            self._catch_up_primed = True

    def _remember_seen_key(self, key: str) -> bool:
        """Remember a de-dupe key, returning True when it was already seen."""
        if key in self._seen_item_ids:
            self._seen_item_ids.move_to_end(key)
            return True
        self._seen_item_ids[key] = None
        while len(self._seen_item_ids) > 1000:
            self._seen_item_ids.popitem(last=False)
        return False

    def _complete_catch_up_request(self, corr_id: str) -> None:
        """Mark one catch-up tail request complete during initial priming."""
        if self._catch_up_primed:
            return
        if corr_id and corr_id in self._catch_up_corr_ids:
            self._catch_up_corr_ids.discard(corr_id)
            self._catch_up_pending = max(0, self._catch_up_pending - 1)
        elif not corr_id and self._catch_up_pending:
            self._catch_up_pending = max(0, self._catch_up_pending - 1)
        if self._catch_up_pending == 0:
            self._catch_up_primed = True
            self._catch_up_corr_ids.clear()

    def _chat_item_seen_key(self, wrapper: dict) -> str:
        """Return a stable per-chat key for de-duplicating chat items."""
        chat_info = wrapper.get("chatInfo") or wrapper.get("chat") or {}
        chat_item = wrapper.get("chatItem") or wrapper.get("item") or {}
        meta = chat_item.get("meta") or {}
        item_id = meta.get("itemId") or chat_item.get("id") or meta.get("itemSharedMsgId")

        if chat_info.get("type", "") in ("group", "groupInfo"):
            group_info = chat_info.get("groupInfo") or chat_info.get("group") or {}
            chat_key = f"group:{group_info.get('groupId') or group_info.get('id') or ''}"
        else:
            contact_info = chat_info.get("contact") or {}
            chat_key = f"direct:{contact_info.get('contactId') or contact_info.get('id') or contact_info.get('localDisplayName') or ''}"

        return f"{chat_key}:{item_id or meta.get('itemTs') or meta.get('createdAt') or json.dumps(meta, sort_keys=True)}"

    def _is_sent_by_us(self, wrapper: dict) -> bool:
        """Return True for items generated by the local SimpleX profile."""
        chat_item = wrapper.get("chatItem") or wrapper.get("item") or {}
        meta = chat_item.get("meta") or {}
        status_type = ((meta.get("itemStatus") or {}).get("type") or "").lower()
        content_type = ((chat_item.get("content") or {}).get("type") or "").lower()
        return status_type.startswith("snd") or content_type.startswith("snd")

    async def _handle_catch_up_chat_items(self, items: list[dict], *, corr_id: str = "") -> None:
        """Handle one-shot `/tail` catch-up responses without replaying history."""
        keyed_items = [(self._chat_item_seen_key(item), item) for item in items]

        if not self._catch_up_primed:
            for key, _ in keyed_items:
                self._remember_seen_key(key)
            self._complete_catch_up_request(corr_id)
            logger.debug(
                "SimpleX: priming catch-up with %d recent item(s), %d response(s) pending",
                len(keyed_items),
                self._catch_up_pending,
            )
            return

        for key, item in keyed_items:
            if self._remember_seen_key(key):
                continue
            if self._is_sent_by_us(item):
                continue
            await self._handle_new_chat_item(item, dedupe=False)

    async def _handle_new_chat_item(self, wrapper: dict, *, dedupe: bool = True) -> None:
        """Process a single newChatItem event into a MessageEvent."""
        wrapper = self._normalize_chat_item_wrapper(wrapper)
        # The same SimpleX item can arrive twice: once as a live newChatItem
        # and again from a connect/reconnect catch-up `/tail @contact N` response.
        # Mark live items as seen so catch-up does not replay them into the
        # gateway and generate a second assistant response.
        if dedupe:
            key = self._chat_item_seen_key(wrapper)
            if self._remember_seen_key(key):
                logger.debug("SimpleX: ignoring duplicate chat item %s", key)
                return

        # The daemon wraps the chat item differently depending on version;
        # normalise both layouts.
        chat_info = wrapper.get("chatInfo") or wrapper.get("chat") or {}
        chat_item = wrapper.get("chatItem") or wrapper.get("item") or {}

        # Only process messages (not calls, deleted items, etc.)
        item_content = chat_item.get("content") or {}
        msg_content = item_content.get("msgContent") or {}
        if not msg_content:
            return

        # Filter out messages sent by us (direction == "snd")
        meta = chat_item.get("meta") or {}
        direction = (meta.get("itemStatus") or {}).get("type", "")
        content_direction = (item_content.get("type") or "")
        if direction.lower().startswith("snd") or content_direction.lower().startswith("snd"):
            return

        # Determine chat type and IDs
        chat_type_raw = chat_info.get("type", "")
        is_group = chat_type_raw in ("group", "groupInfo")

        if is_group:
            group_info = chat_info.get("groupInfo") or chat_info.get("group") or {}
            group_id = str(group_info.get("groupId") or group_info.get("id") or "")
            group_name = (
                group_info.get("localDisplayName")
                or group_info.get("displayName")
                or group_info.get("groupProfile", {}).get("displayName", "")
            )
            # SimpleX text commands address groups by local display name. Keep
            # the numeric/opaque group ID only as a fallback if no name exists.
            group_target = group_name or group_id
            chat_id = f"group:{group_target}" if group_target else ""
            chat_name = group_name or group_target
        else:
            contact_info = chat_info.get("contact") or {}
            contact_id = str(contact_info.get("contactId") or contact_info.get("id") or "")
            contact_name = (
                contact_info.get("localDisplayName")
                or contact_info.get("displayName")
                or contact_id
            )
            # The simplex-chat text command interface sends to display names
            # (e.g. `@alice hi`), not numeric contact IDs. Keep the opaque
            # contact ID as the sender/user ID for authorization, but use the
            # display name as the DM chat ID so replies route correctly.
            chat_id = contact_name
            chat_name = contact_name

        if not chat_id:
            logger.debug("SimpleX: ignoring event with no chat_id")
            return

        # Sender — for groups the message includes a chatItemMember sub-object
        member = chat_item.get("chatItemMember") or {}
        if is_group and member:
            sender_id = str(member.get("memberId") or member.get("id") or chat_id)
            sender_name = (
                member.get("displayName")
                or member.get("localDisplayName")
                or sender_id
            )
        else:
            sender_id = contact_id if not is_group else chat_id
            sender_name = chat_name

        # Extract text
        text = msg_content.get("text") or ""

        # Media attachments
        media_urls: List[str] = []
        media_types: List[str] = []
        file_info = chat_item.get("file") or {}
        if file_info and file_info.get("fileStatus") not in ("cancelled", "error"):
            file_id = file_info.get("fileId")
            file_name = file_info.get("fileName", "file")
            if file_id:
                try:
                    cached = await self._fetch_file(file_id, file_name)
                    if cached:
                        ext = cached.rsplit(".", 1)[-1]
                        if _is_image_ext("." + ext):
                            media_types.append("image/" + ext.replace("jpg", "jpeg"))
                        elif _is_audio_ext("." + ext):
                            media_types.append("audio/" + ext)
                        else:
                            media_types.append("application/octet-stream")
                        media_urls.append(cached)
                except Exception:
                    logger.exception("SimpleX: failed to fetch file %s", file_id)

        # Timestamp
        ts_str = meta.get("itemTs") or meta.get("createdAt") or ""
        try:
            timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now(tz=timezone.utc)

        # Build source
        source = self.build_source(
            chat_id=chat_id,
            chat_name=chat_name,
            chat_type="group" if is_group else "dm",
            user_id=sender_id,
            user_name=sender_name,
        )

        # Message type
        msg_type = MessageType.TEXT
        if media_types:
            if any(mt.startswith("audio/") for mt in media_types):
                msg_type = MessageType.VOICE
            elif any(mt.startswith("image/") for mt in media_types):
                msg_type = MessageType.PHOTO

        event_obj = MessageEvent(
            source=source,
            text=text,
            message_type=msg_type,
            media_urls=media_urls,
            media_types=media_types,
            timestamp=timestamp,
            raw_message=wrapper,
        )

        await self.handle_message(event_obj)

    async def _fetch_file(self, file_id: Any, file_name: str) -> Optional[str]:
        """Ask the daemon to receive and return a file attachment."""
        # simplex-chat exposes `/api/v1/files/{fileId}` on an HTTP port
        # when started with --http-port. However, the canonical WebSocket API
        # does not have a direct binary download command; files are stored on
        # the local filesystem after the daemon accepts them.
        #
        # We request acceptance first, then read from the daemon's local path.
        corr_id = self._make_corr_id()
        cmd = {
            "corrId": corr_id,
            "cmd": f"/freceive {file_id}",
        }
        await self._send_ws(cmd)
        # The daemon will emit a chatItemUpdated event when the file lands;
        # for simplicity we just wait briefly and rely on the daemon's default path.
        await asyncio.sleep(2)

        # simplex-chat stores received files in ~/Downloads or a configured path.
        # We try common locations.
        for search_dir in (
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/.simplex/files"),
            "/tmp/simplex_files",
        ):
            candidate = os.path.join(search_dir, file_name)
            if os.path.exists(candidate):
                with open(candidate, "rb") as f:
                    data = f.read()
                ext = _guess_extension(data)
                if _is_image_ext(ext):
                    return cache_image_from_bytes(data, ext)
                elif _is_audio_ext(ext):
                    return cache_audio_from_bytes(data, ext)
                else:
                    return cache_document_from_bytes(data, file_name)
        return None

    # ------------------------------------------------------------------
    # Outbound messages
    # ------------------------------------------------------------------

    def _make_corr_id(self) -> str:
        """Generate a unique correlation ID for a request."""
        corr_id = f"{_CORR_PREFIX}{int(time.time() * 1000)}-{random.randint(0, 9999)}"
        self._pending_corr_ids.add(corr_id)
        if len(self._pending_corr_ids) > self._max_pending_corr:
            # Trim oldest — sets are unordered so just clear the oldest half
            to_remove = list(self._pending_corr_ids)[:self._max_pending_corr // 2]
            self._pending_corr_ids -= set(to_remove)
        return corr_id

    async def _send_ws(self, payload: dict, *, persistent_only: bool = False) -> bool:
        """Send a JSON payload over WebSocket.

        Prefer the persistent listener socket. For outbound chat messages, fall
        back to a short-lived one-shot WebSocket rather than reporting fake
        success. For commands whose response must be consumed by the listener
        (for example `/chats` and `/tail` catch-up requests), pass
        ``persistent_only=True`` so the response is not lost on an ephemeral
        connection.
        """
        import websockets as _wsclient
        import websockets as _wsexc

        async def _send_ephemeral() -> bool:
            try:
                async with _wsclient.connect(self.ws_url, open_timeout=10, close_timeout=5) as ws2:
                    await ws2.send(json.dumps(payload))
                    # Give simplex-chat a brief chance to ingest the command before
                    # closing the one-shot connection.
                    await asyncio.sleep(0.2)
                self._last_ws_activity = time.time()
                return True
            except Exception as e:
                logger.warning("SimpleX: ephemeral WS send failed: %s", e)
                return False

        ws = self._ws
        if not ws:
            if persistent_only:
                logger.debug("SimpleX: persistent WS not connected; skipping request")
                return False
            logger.info("SimpleX: persistent WS not connected; using one-shot send")
            return await _send_ephemeral()

        try:
            await ws.send(json.dumps(payload))
            self._last_ws_activity = time.time()
            return True
        except _wsexc.ConnectionClosed:
            if persistent_only:
                logger.warning("SimpleX: persistent WS closed while sending request")
                return False
            logger.warning("SimpleX: WS closed while sending; retrying one-shot send")
            return await _send_ephemeral()
        except Exception as e:
            if persistent_only:
                logger.warning("SimpleX: persistent WS request failed: %s", e)
                return False
            logger.warning("SimpleX: WS send error: %s; retrying one-shot send", e)
            return await _send_ephemeral()

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a text message to a contact or group."""
        corr_id = self._make_corr_id()

        if chat_id.startswith("group:"):
            group_name = chat_id[6:]
            cmd_str = f"{self._simplex_group_ref(group_name)} {content}"
        else:
            cmd_str = f"{self._simplex_dm_ref(chat_id)} {content}"

        payload = {
            "corrId": corr_id,
            "cmd": cmd_str,
        }

        ok = await self._send_ws(payload)
        if not ok:
            return SendResult(success=False, error="SimpleX send failed: daemon WebSocket unavailable")
        return SendResult(success=True)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """SimpleX does not expose a typing indicator API — no-op."""
        pass

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send an image (URL) as a message with optional caption.

        SimpleX has no native ``send_image`` over the WebSocket API — file
        attachments require the daemon's filesystem-backed flow which is
        not driven from this adapter. Fall back to a plain text message
        containing the URL and caption.
        """
        text = f"{caption}\n{image_url}".strip() if caption else image_url
        return await self.send(chat_id, text, reply_to=reply_to, metadata=metadata)

    async def get_chat_info(self, chat_id: str) -> dict:
        """Return basic chat info."""
        if chat_id.startswith("group:"):
            return {"chat_id": chat_id, "type": "group", "name": chat_id[6:]}
        return {"chat_id": chat_id, "type": "dm", "name": chat_id}


# ---------------------------------------------------------------------------
# Plugin entry-point hooks
# ---------------------------------------------------------------------------

def check_requirements() -> bool:
    """Plugin gate: require SIMPLEX_WS_URL AND the websockets package.

    Returning False keeps the platform out of ``get_connected_platforms()``
    so the gateway never instantiates the adapter when the dependency is
    missing or no daemon URL is configured.
    """
    if not os.getenv("SIMPLEX_WS_URL"):
        return False
    try:
        import websockets  # noqa: F401
    except ImportError:
        return False
    return True


def validate_config(config) -> bool:
    """Validate that the platform config has enough info to connect."""
    extra = getattr(config, "extra", {}) or {}
    ws_url = os.getenv("SIMPLEX_WS_URL") or extra.get("ws_url", "")
    return bool(ws_url)


def is_connected(config) -> bool:
    """Check whether SimpleX is configured (env or config.yaml)."""
    extra = getattr(config, "extra", {}) or {}
    ws_url = os.getenv("SIMPLEX_WS_URL") or extra.get("ws_url", "")
    return bool(ws_url)


def _env_enablement() -> dict | None:
    """Seed ``PlatformConfig.extra`` from env vars during gateway config load.

    Called by the platform registry's env-enablement hook BEFORE adapter
    construction, so ``gateway status`` and ``get_connected_platforms()``
    reflect env-only configuration without instantiating the WebSocket
    client. Returns ``None`` when SimpleX isn't minimally configured.

    The special ``home_channel`` key in the returned dict is handled by
    the core hook — it becomes a proper ``HomeChannel`` dataclass on the
    ``PlatformConfig`` rather than being merged into ``extra``.
    """
    ws_url = os.getenv("SIMPLEX_WS_URL", "").strip()
    if not ws_url:
        return None
    seed: dict = {"ws_url": ws_url}
    home = os.getenv("SIMPLEX_HOME_CHANNEL", "").strip()
    if home:
        seed["home_channel"] = {
            "chat_id": home,
            "name": os.getenv("SIMPLEX_HOME_CHANNEL_NAME", "").strip() or home,
        }
    return seed


async def _standalone_send(
    pconfig,
    chat_id: str,
    message: str,
    *,
    thread_id: Optional[str] = None,
    media_files: Optional[List[str]] = None,
    force_document: bool = False,
) -> Dict[str, Any]:
    """Open an ephemeral WebSocket to the daemon, send, and close.

    Used by ``tools/send_message_tool._send_via_adapter`` when the gateway
    runner is not in this process (e.g. ``hermes cron`` running as a
    separate process from ``hermes gateway``). Without this hook,
    ``deliver=simplex`` cron jobs fail with "No live adapter for platform".

    ``thread_id`` and ``force_document`` are accepted for signature parity
    with other plugins but are not meaningful here. ``media_files`` is
    accepted but only the text body is delivered — SimpleX requires the
    daemon's filesystem-backed file flow which an ephemeral connection
    cannot drive safely.
    """
    try:
        import websockets as _wsclient
    except ImportError:
        return {"error": "websockets not installed. Run: pip install websockets"}

    extra = getattr(pconfig, "extra", {}) or {}
    ws_url = os.getenv("SIMPLEX_WS_URL") or extra.get("ws_url", "")
    if not ws_url:
        return {"error": "SimpleX standalone send: SIMPLEX_WS_URL is required"}

    try:
        if chat_id.startswith("group:"):
            group_name = chat_id[6:]
            cmd_str = f"#{SimplexAdapter._quote_simplex_name(group_name)} {message}"
        else:
            cmd_str = f"@{SimplexAdapter._quote_simplex_name(chat_id)} {message}"

        payload = {
            "corrId": f"hermes-snd-{int(time.time() * 1000)}",
            "cmd": cmd_str,
        }

        async with _wsclient.connect(ws_url, open_timeout=10, close_timeout=5) as ws:
            await ws.send(json.dumps(payload))
            # Give the daemon a moment to process the command before closing.
            await asyncio.sleep(0.5)

        return {"success": True, "platform": "simplex", "chat_id": chat_id}
    except Exception as e:
        return {"error": f"SimpleX send failed: {e}"}


def interactive_setup() -> None:
    """Minimal stdin wizard for ``hermes setup gateway`` → SimpleX.

    Prompts for the WebSocket URL and the optional allowlist / home channel.
    Writes to ``~/.hermes/.env`` via ``hermes_cli.config``.
    """
    print()
    print("SimpleX Chat setup")
    print("------------------")
    print("Requirements:")
    print("  1. simplex-chat daemon running (e.g. `simplex-chat -p 5225`).")
    print("  2. Python package `websockets` installed (`pip install websockets`).")
    print()

    try:
        from hermes_cli.config import get_env_value, save_env_value
    except ImportError:
        print("hermes_cli.config not available; set SIMPLEX_* vars manually in ~/.hermes/.env")
        return

    def _prompt(var: str, prompt: str, *, secret: bool = False) -> None:
        existing = get_env_value(var) if callable(get_env_value) else None
        suffix = " [keep current]" if existing else ""
        try:
            if secret:
                import getpass
                value = getpass.getpass(f"{prompt}{suffix}: ")
            else:
                value = input(f"{prompt}{suffix}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if value:
            save_env_value(var, value)

    _prompt("SIMPLEX_WS_URL", "Daemon WebSocket URL (default ws://127.0.0.1:5225)")
    _prompt("SIMPLEX_ALLOWED_USERS", "Allowed contact IDs (comma-separated; blank=skip)")
    _prompt("SIMPLEX_HOME_CHANNEL", "Home channel contact/group ID (or empty)")
    print("Done. Make sure the simplex-chat daemon is running before starting the gateway.")


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system at startup."""
    ctx.register_platform(
        name="simplex",
        label="SimpleX Chat",
        adapter_factory=lambda cfg: SimplexAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        is_connected=is_connected,
        required_env=["SIMPLEX_WS_URL"],
        install_hint="pip install websockets   # SimpleX adapter requires the websockets package",
        setup_fn=interactive_setup,
        # Env-driven auto-configuration: seeds PlatformConfig.extra so
        # env-only setups show up in `hermes gateway status` without
        # instantiating the adapter.
        env_enablement_fn=_env_enablement,
        # Cron home-channel delivery support — `deliver=simplex` cron jobs
        # route to SIMPLEX_HOME_CHANNEL when set.
        cron_deliver_env_var="SIMPLEX_HOME_CHANNEL",
        # Out-of-process cron delivery. Without this hook, deliver=simplex
        # cron jobs fail with "No live adapter" when cron runs separately
        # from the gateway.
        standalone_sender_fn=_standalone_send,
        # Auth env vars for _is_user_authorized() integration
        allowed_users_env="SIMPLEX_ALLOWED_USERS",
        allow_all_env="SIMPLEX_ALLOW_ALL_USERS",
        # SimpleX has no hard line length; we still chunk for sanity.
        max_message_length=MAX_MESSAGE_LENGTH,
        # Display
        emoji="🔒",
        # SimpleX uses opaque contact IDs only — no phone numbers or
        # email addresses to redact.
        pii_safe=True,
        allow_update_command=True,
        # LLM guidance
        platform_hint=(
            "You are chatting via SimpleX Chat, a private decentralised "
            "messenger. Contacts are identified by opaque internal IDs, "
            "not phone numbers or usernames. SimpleX supports standard "
            "markdown formatting. There is no typing indicator and no "
            "hard message length limit, but keep responses conversational."
        ),
    )
