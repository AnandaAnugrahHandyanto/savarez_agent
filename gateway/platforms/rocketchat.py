"""Rocket.Chat gateway adapter.

Connects to a self-hosted Rocket.Chat instance via its REST API (v1) for
outbound traffic and the Realtime (DDP) WebSocket for inbound messages.
No external Rocket.Chat library required — uses aiohttp, which is already
a Hermes dependency.

Design notes:
    Rocket.Chat's docs recommend REST for writes (chat.postMessage,
    chat.update, rooms.media) and DDP for reads (stream-room-messages).
    The bot subscribes to the ``__my_messages__`` virtual room id, which
    covers every channel/DM/group the bot is a member of — no per-room
    enumeration required.

    Personal Access Tokens double as DDP resume tokens, so a single
    ``ROCKETCHAT_TOKEN`` + ``ROCKETCHAT_USER_ID`` pair authenticates both
    surfaces. Generate the PAT with "Ignore Two Factor" checked to keep
    unattended REST calls working on 2FA-enabled workspaces.

Environment variables:
    ROCKETCHAT_URL              Server URL (e.g. https://rc.example.com)
    ROCKETCHAT_TOKEN            Personal Access Token (used as auth token)
    ROCKETCHAT_USER_ID          Bot user's _id (shown alongside the PAT)
    ROCKETCHAT_ALLOWED_USERS    Comma-separated user IDs
    ROCKETCHAT_HOME_CHANNEL     Room ID for cron/notification delivery
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from gateway.config import Platform, PlatformConfig
from gateway.platforms.helpers import MessageDeduplicator
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
)

logger = logging.getLogger(__name__)

# Rocket.Chat's default Message_MaxAllowedSize is 5000; admins can raise it
# but the safe default for multi-line messages is 5000.
MAX_MESSAGE_LENGTH = 5000

# Room type codes returned by the Rocket.Chat API.
#   d = direct message (1:1)
#   c = public channel
#   p = private group (private channel)
#   l = livechat / omnichannel
_ROOM_TYPE_MAP = {
    "d": "dm",
    "c": "channel",
    "p": "group",
    "l": "group",
}

# Reconnect parameters (exponential backoff).
_RECONNECT_BASE_DELAY = 2.0
_RECONNECT_MAX_DELAY = 60.0
_RECONNECT_JITTER = 0.2

# DDP protocol version. Rocket.Chat supports "1" across 7.x/8.x.
_DDP_PROTOCOL_VERSION = "1"


def check_rocketchat_requirements() -> bool:
    """Return True if the Rocket.Chat adapter can be used."""
    token = os.getenv("ROCKETCHAT_TOKEN", "")
    url = os.getenv("ROCKETCHAT_URL", "")
    user_id = os.getenv("ROCKETCHAT_USER_ID", "")
    if not token:
        logger.debug("Rocket.Chat: ROCKETCHAT_TOKEN not set")
        return False
    if not url:
        logger.warning("Rocket.Chat: ROCKETCHAT_URL not set")
        return False
    if not user_id:
        logger.warning("Rocket.Chat: ROCKETCHAT_USER_ID not set")
        return False
    try:
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        logger.warning("Rocket.Chat: aiohttp not installed")
        return False


class RocketchatAdapter(BasePlatformAdapter):
    """Gateway adapter for Rocket.Chat (self-hosted)."""

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.ROCKETCHAT)

        self._base_url: str = (
            config.extra.get("url", "")
            or os.getenv("ROCKETCHAT_URL", "")
        ).rstrip("/")
        self._token: str = config.token or os.getenv("ROCKETCHAT_TOKEN", "")
        self._bot_user_id: str = (
            config.extra.get("user_id", "")
            or os.getenv("ROCKETCHAT_USER_ID", "")
        )

        # Filled in by connect() once we look up the bot's username.
        self._bot_username: str = ""

        # aiohttp session + websocket handle
        self._session: Any = None  # aiohttp.ClientSession
        self._ws: Any = None       # aiohttp.ClientWebSocketResponse
        self._ws_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._closing = False

        # DDP bookkeeping
        self._ddp_next_id = 1
        self._ddp_subs: Dict[str, bool] = {}  # sub-id -> ready

        # Room type cache (roomId -> "dm"/"group"/"channel").
        # Rocket.Chat DDP events don't include room type, so we look it up
        # lazily via REST and cache the answer.
        self._room_type_cache: Dict[str, str] = {}

        # Reply mode: "thread" to nest replies, "off" for flat messages.
        self._reply_mode: str = (
            config.extra.get("reply_mode", "")
            or os.getenv("ROCKETCHAT_REPLY_MODE", "off")
        ).lower()

        # Dedup cache (prevent reprocessing the same message _id).
        self._dedup = MessageDeduplicator()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Auth-Token": self._token,
            "X-User-Id": self._bot_user_id,
            "Content-Type": "application/json",
        }

    async def _api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET /api/v1/{path}."""
        import aiohttp
        url = f"{self._base_url}/api/v1/{path.lstrip('/')}"
        try:
            async with self._session.get(
                url, headers=self._headers(), params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("RC API GET %s → %s: %s", path, resp.status, body[:200])
                    return {}
                return await resp.json()
        except aiohttp.ClientError as exc:
            logger.error("RC API GET %s network error: %s", path, exc)
            return {}

    async def _api_post(
        self, path: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """POST /api/v1/{path} with JSON body."""
        import aiohttp
        url = f"{self._base_url}/api/v1/{path.lstrip('/')}"
        try:
            async with self._session.post(
                url, headers=self._headers(), json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("RC API POST %s → %s: %s", path, resp.status, body[:200])
                    return {}
                return await resp.json()
        except aiohttp.ClientError as exc:
            logger.error("RC API POST %s network error: %s", path, exc)
            return {}

    async def _upload_file(
        self,
        room_id: str,
        file_data: bytes,
        filename: str,
        content_type: str,
        caption: Optional[str] = None,
        tmid: Optional[str] = None,
    ) -> Optional[str]:
        """Upload a file via the two-step rooms.media flow.

        Step 1 uploads the bytes; step 2 confirms and creates the message.
        Returns the message _id on success, None on failure.
        """
        import aiohttp

        # Step 1: upload the file bytes.
        step1_url = f"{self._base_url}/api/v1/rooms.media/{room_id}"
        form = aiohttp.FormData()
        form.add_field(
            "file",
            file_data,
            filename=filename,
            content_type=content_type,
        )
        headers = {
            "X-Auth-Token": self._token,
            "X-User-Id": self._bot_user_id,
        }
        try:
            async with self._session.post(
                step1_url, headers=headers, data=form,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("RC rooms.media → %s: %s", resp.status, body[:200])
                    return None
                step1 = await resp.json()
        except aiohttp.ClientError as exc:
            logger.error("RC rooms.media network error: %s", exc)
            return None

        file_id = (step1.get("file") or {}).get("_id")
        if not file_id:
            logger.error("RC rooms.media returned no file id: %s", step1)
            return None

        # Step 2: confirm — this creates the message.
        step2_path = f"rooms.mediaConfirm/{room_id}/{file_id}"
        payload: Dict[str, Any] = {}
        if caption:
            payload["msg"] = caption
        if tmid and self._reply_mode == "thread":
            payload["tmid"] = tmid
        step2 = await self._api_post(step2_path, payload)
        msg = step2.get("message") or {}
        return msg.get("_id")

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to Rocket.Chat and start the DDP listener."""
        import aiohttp

        if not self._base_url or not self._token or not self._bot_user_id:
            logger.error("Rocket.Chat: URL, token, or user id not configured")
            return False

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        self._closing = False

        # Verify credentials and fetch bot identity.
        me = await self._api_get("me")
        if not me or not me.get("success"):
            logger.error(
                "Rocket.Chat: failed to authenticate — check "
                "ROCKETCHAT_TOKEN, ROCKETCHAT_USER_ID, ROCKETCHAT_URL"
            )
            await self._session.close()
            return False

        # /api/v1/me returns the bot's user record at the top level.
        if me.get("_id") and me["_id"] != self._bot_user_id:
            logger.warning(
                "Rocket.Chat: ROCKETCHAT_USER_ID (%s) doesn't match /me (%s) — using /me",
                self._bot_user_id, me["_id"],
            )
            self._bot_user_id = me["_id"]
        self._bot_username = me.get("username", "")
        logger.info(
            "Rocket.Chat: authenticated as @%s (%s) on %s",
            self._bot_username,
            self._bot_user_id,
            self._base_url,
        )

        # Start DDP WebSocket in background.
        self._ws_task = asyncio.create_task(self._ws_loop())
        self._mark_connected()
        return True

    async def disconnect(self) -> None:
        """Disconnect from Rocket.Chat."""
        self._closing = True

        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):
                pass

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session and not self._session.closed:
            await self._session.close()

        logger.info("Rocket.Chat: disconnected")

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a message (or multiple chunks) to a room."""
        if not content:
            return SendResult(success=True)

        formatted = self.format_message(content)
        chunks = self.truncate_message(formatted, MAX_MESSAGE_LENGTH)

        last_id = None
        for chunk in chunks:
            payload: Dict[str, Any] = {
                "roomId": chat_id,
                "text": chunk,
            }
            # Thread support: reply_to is the root message id.
            if reply_to and self._reply_mode == "thread":
                payload["tmid"] = reply_to

            data = await self._api_post("chat.postMessage", payload)
            if not data or not data.get("success"):
                return SendResult(success=False, error="Failed to post message")
            msg = data.get("message") or {}
            last_id = msg.get("_id") or last_id

        return SendResult(success=True, message_id=last_id)

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return room name and type.

        Rocket.Chat exposes one unified ``rooms.info`` endpoint that works
        for channels, private groups, and DMs.
        """
        data = await self._api_get("rooms.info", params={"roomId": chat_id})
        room = (data or {}).get("room") or {}
        if not room:
            return {"name": chat_id, "type": "channel"}

        raw_type = room.get("t", "c")
        chat_type = _ROOM_TYPE_MAP.get(raw_type, "channel")
        self._room_type_cache[chat_id] = chat_type

        # For DMs, Rocket.Chat stores participant usernames in ``usernames``
        # rather than a display name.
        if chat_type == "dm":
            others = [
                u for u in room.get("usernames", [])
                if u and u != self._bot_username
            ]
            name = others[0] if others else chat_id
        else:
            name = room.get("fname") or room.get("name") or chat_id

        return {"name": name, "type": chat_type, "chat_id": chat_id}

    # ------------------------------------------------------------------
    # Optional overrides
    # ------------------------------------------------------------------

    async def send_typing(
        self, chat_id: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Notify that the bot is typing.

        Rocket.Chat 6.x+ replaced the legacy ``/typing`` stream with
        ``/user-activity``, and 8.x expects the activity string ``"user-typing"``
        (not ``"typing"``) plus a trailing empty object that the web client
        reserves for extension payloads. The server accepts the older shapes
        without error but no client-side UI is wired to render them, so the
        indicator silently fails to appear. Verified by subscribing to the
        user-activity stream on a Rocket.Chat 8.2 instance and capturing what
        the official web client sends when a real user types.
        """
        if not self._ws or self._ws.closed:
            return
        if not self._bot_username:
            return
        await self._ddp_method(
            "stream-notify-room",
            [f"{chat_id}/user-activity", self._bot_username, ["user-typing"], {}],
        )

    async def stop_typing(self, chat_id: str) -> None:
        """Clear the typing indicator (empty user-activity list)."""
        if not self._ws or self._ws.closed:
            return
        if not self._bot_username:
            return
        await self._ddp_method(
            "stream-notify-room",
            [f"{chat_id}/user-activity", self._bot_username, [], {}],
        )

    async def edit_message(
        self, chat_id: str, message_id: str, content: str, *, finalize: bool = False
    ) -> SendResult:
        """Edit an existing message via chat.update."""
        formatted = self.format_message(content)
        data = await self._api_post(
            "chat.update",
            {"roomId": chat_id, "msgId": message_id, "text": formatted},
        )
        if not data or not data.get("success"):
            return SendResult(success=False, error="Failed to edit message")
        msg = data.get("message") or {}
        return SendResult(success=True, message_id=msg.get("_id", message_id))

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Download an image and upload it as a file attachment."""
        return await self._send_url_as_file(
            chat_id, image_url, caption, reply_to, "image"
        )

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload a local image file."""
        return await self._send_local_file(
            chat_id, image_path, caption, reply_to
        )

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload a local file as a document."""
        return await self._send_local_file(
            chat_id, file_path, caption, reply_to, file_name
        )

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload an audio file."""
        return await self._send_local_file(
            chat_id, audio_path, caption, reply_to
        )

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Upload a video file."""
        return await self._send_local_file(
            chat_id, video_path, caption, reply_to
        )

    def format_message(self, content: str) -> str:
        """Rocket.Chat renders Markdown natively and previews plain image
        URLs — strip image markdown to match Mattermost's behavior.
        """
        content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\2", content)
        return content

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    async def _send_url_as_file(
        self,
        chat_id: str,
        url: str,
        caption: Optional[str],
        reply_to: Optional[str],
        kind: str = "file",
    ) -> SendResult:
        """Download a URL and upload it as a file attachment."""
        from tools.url_safety import is_safe_url
        if not is_safe_url(url):
            logger.warning("Rocket.Chat: blocked unsafe URL (SSRF protection)")
            return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to)

        import aiohttp

        file_data = None
        ct = "application/octet-stream"
        fname = url.rsplit("/", 1)[-1].split("?")[0] or f"{kind}.png"

        for attempt in range(3):
            try:
                async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status >= 500 or resp.status == 429:
                        if attempt < 2:
                            logger.debug("RC download retry %d/2 for %s (status %d)",
                                         attempt + 1, url[:80], resp.status)
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                    if resp.status >= 400:
                        return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to)
                    file_data = await resp.read()
                    ct = resp.content_type or "application/octet-stream"
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                logger.warning("Rocket.Chat: failed to download %s after %d attempts: %s", url, attempt + 1, exc)
                return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to)

        if file_data is None:
            return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to)

        msg_id = await self._upload_file(
            chat_id, file_data, fname, ct, caption, reply_to,
        )
        if not msg_id:
            return await self.send(chat_id, f"{caption or ''}\n{url}".strip(), reply_to)
        return SendResult(success=True, message_id=msg_id)

    async def _send_local_file(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str],
        reply_to: Optional[str],
        file_name: Optional[str] = None,
    ) -> SendResult:
        """Upload a local file via the two-step rooms.media flow."""
        import mimetypes

        p = Path(file_path)
        if not p.exists():
            return await self.send(
                chat_id, f"{caption or ''}\n(file not found: {file_path})", reply_to
            )

        fname = file_name or p.name
        ct = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        file_data = p.read_bytes()

        msg_id = await self._upload_file(
            chat_id, file_data, fname, ct, caption, reply_to,
        )
        if not msg_id:
            return SendResult(success=False, error="File upload failed")
        return SendResult(success=True, message_id=msg_id)

    # ------------------------------------------------------------------
    # DDP / WebSocket
    # ------------------------------------------------------------------

    async def _ddp_send(self, payload: Dict[str, Any]) -> None:
        """Send a DDP frame if the socket is open."""
        if not self._ws or self._ws.closed:
            return
        await self._ws.send_json(payload)

    async def _ddp_method(self, method: str, params: List[Any]) -> str:
        """Invoke a DDP method (fire-and-forget). Returns the method id."""
        call_id = str(self._ddp_next_id)
        self._ddp_next_id += 1
        await self._ddp_send({
            "msg": "method",
            "method": method,
            "id": call_id,
            "params": params,
        })
        return call_id

    async def _ddp_sub(self, name: str, params: List[Any]) -> str:
        """Subscribe to a DDP publication. Returns the sub id."""
        sub_id = str(uuid.uuid4())
        self._ddp_subs[sub_id] = False
        await self._ddp_send({
            "msg": "sub",
            "id": sub_id,
            "name": name,
            "params": params,
        })
        return sub_id

    async def _ws_loop(self) -> None:
        """Connect to the DDP socket and listen for events, reconnecting on failure."""
        delay = _RECONNECT_BASE_DELAY
        while not self._closing:
            try:
                await self._ws_connect_and_listen()
                # Clean disconnect — reset delay.
                delay = _RECONNECT_BASE_DELAY
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._closing:
                    return
                import aiohttp
                err_str = str(exc).lower()
                if isinstance(exc, aiohttp.WSServerHandshakeError) and exc.status in (401, 403):
                    logger.error("Rocket.Chat WS auth failed (HTTP %d) — stopping reconnect", exc.status)
                    return
                if "401" in err_str or "403" in err_str or "unauthorized" in err_str:
                    logger.error("Rocket.Chat WS permanent error: %s — stopping reconnect", exc)
                    return
                logger.warning("Rocket.Chat WS error: %s — reconnecting in %.0fs", exc, delay)

            if self._closing:
                return

            import random
            jitter = delay * _RECONNECT_JITTER * random.random()
            await asyncio.sleep(delay + jitter)
            delay = min(delay * 2, _RECONNECT_MAX_DELAY)

    async def _ws_connect_and_listen(self) -> None:
        """Single DDP WebSocket session: connect, login, subscribe, listen."""
        # Build WS URL: https:// → wss://, http:// → ws://
        ws_url = re.sub(r"^http", "ws", self._base_url) + "/websocket"
        logger.info("Rocket.Chat: connecting to %s", ws_url)

        self._ws = await self._session.ws_connect(ws_url, heartbeat=None)
        self._ddp_subs.clear()

        # DDP handshake.
        await self._ddp_send({
            "msg": "connect",
            "version": _DDP_PROTOCOL_VERSION,
            "support": [_DDP_PROTOCOL_VERSION],
        })

        # DDP login with the PAT as the resume token.
        await self._ddp_method("login", [{"resume": self._token}])

        # Subscribe to the unified "all my messages" stream.
        # Rocket.Chat's __my_messages__ virtual id covers every channel/DM/
        # group the bot is a member of, so we don't need per-room subs.
        await self._ddp_sub("stream-room-messages", ["__my_messages__", False])
        logger.info("Rocket.Chat: DDP logged in and subscribed")

        async for raw_msg in self._ws:
            if self._closing:
                return

            if raw_msg.type in (raw_msg.type.TEXT, raw_msg.type.BINARY):
                try:
                    event = json.loads(raw_msg.data)
                except (json.JSONDecodeError, TypeError):
                    continue
                await self._handle_ddp_frame(event)
            elif raw_msg.type in (
                raw_msg.type.ERROR, raw_msg.type.CLOSE,
                raw_msg.type.CLOSING, raw_msg.type.CLOSED,
            ):
                logger.info("Rocket.Chat: DDP WebSocket closed (%s)", raw_msg.type)
                break

    async def _handle_ddp_frame(self, event: Dict[str, Any]) -> None:
        """Dispatch a single DDP frame."""
        kind = event.get("msg")
        if kind == "ping":
            # Heartbeat: echo the optional id back.
            pong: Dict[str, Any] = {"msg": "pong"}
            if "id" in event:
                pong["id"] = event["id"]
            await self._ddp_send(pong)
            return

        if kind == "ready":
            for sub_id in event.get("subs", []):
                self._ddp_subs[sub_id] = True
            return

        if kind == "nosub":
            sub_id = event.get("id", "")
            err = event.get("error") or {}
            self._ddp_subs.pop(sub_id, None)
            if err:
                logger.warning("Rocket.Chat: sub %s rejected: %s", sub_id, err)
            return

        if kind == "changed":
            collection = event.get("collection")
            if collection != "stream-room-messages":
                return
            fields = event.get("fields") or {}
            args = fields.get("args") or []
            if not args:
                return
            await self._handle_message(args[0])
            return

        # Ignore: connected, result, added, removed, updated, error.

    async def _handle_message(self, post: Dict[str, Any]) -> None:
        """Process an incoming Rocket.Chat message."""
        sender = post.get("u") or {}
        sender_id = sender.get("_id", "")
        sender_name = sender.get("username", "") or sender_id

        # Ignore own messages — otherwise the bot replies to itself.
        if sender_id == self._bot_user_id:
            return

        # Rocket.Chat emits "system" messages (join, leave, role grants, etc.)
        # via the same stream with a populated ``t`` field. Skip them.
        if post.get("t"):
            return

        post_id = post.get("_id", "")
        if self._dedup.is_duplicate(post_id):
            return

        room_id = post.get("rid", "")
        if not room_id:
            return

        # Look up the room type lazily; cache forever.
        chat_type = self._room_type_cache.get(room_id)
        if chat_type is None:
            chat_type = await self._resolve_room_type(room_id)
            self._room_type_cache[room_id] = chat_type

        message_text = post.get("msg", "") or ""

        # Mention gating for non-DM rooms.
        #   ROCKETCHAT_REQUIRE_MENTION: require @mention in channels (default: true)
        #   ROCKETCHAT_FREE_RESPONSE_CHANNELS: rooms exempt from the requirement
        if chat_type != "dm":
            require_mention = os.getenv(
                "ROCKETCHAT_REQUIRE_MENTION", "true"
            ).lower() not in ("false", "0", "no")

            free_channels_raw = os.getenv("ROCKETCHAT_FREE_RESPONSE_CHANNELS", "")
            free_channels = {ch.strip() for ch in free_channels_raw.split(",") if ch.strip()}
            is_free_channel = room_id in free_channels

            mentions = post.get("mentions") or []
            mention_ids = {m.get("_id") for m in mentions if isinstance(m, dict)}
            mention_names = {m.get("username") for m in mentions if isinstance(m, dict)}
            has_mention = (
                self._bot_user_id in mention_ids
                or self._bot_username in mention_names
                or "all" in mention_ids or "here" in mention_ids
            )
            # Fall back to text scan (covers @username typed manually but
            # not yet resolved by the server, which happens on edits).
            if not has_mention and self._bot_username:
                pattern = re.compile(
                    rf"(?:^|\W)@{re.escape(self._bot_username)}(?:\W|$)",
                    re.IGNORECASE,
                )
                has_mention = bool(pattern.search(message_text))

            if require_mention and not is_free_channel and not has_mention:
                return

            # Strip @mention from the text so the agent sees clean input.
            if has_mention and self._bot_username:
                message_text = re.sub(
                    rf"(^|\W)@{re.escape(self._bot_username)}(\W|$)",
                    r"\1\2",
                    message_text,
                    flags=re.IGNORECASE,
                ).strip()

        # Thread support: tmid is the parent message id for threaded replies.
        thread_id = post.get("tmid") or None

        msg_type = MessageType.TEXT
        if message_text.startswith("/"):
            msg_type = MessageType.COMMAND

        # Download file attachments.
        media_urls, media_types = await self._download_attachments(post)

        if media_types and msg_type == MessageType.TEXT:
            if any(m.startswith("image/") for m in media_types):
                msg_type = MessageType.PHOTO
            elif any(m.startswith("audio/") for m in media_types):
                msg_type = MessageType.VOICE
            else:
                msg_type = MessageType.DOCUMENT

        source = self.build_source(
            chat_id=room_id,
            chat_type=chat_type,
            user_id=sender_id,
            user_name=sender_name,
            thread_id=thread_id,
        )

        from gateway.platforms.base import resolve_channel_prompt
        channel_prompt = resolve_channel_prompt(
            self.config.extra, room_id, None,
        )

        msg_event = MessageEvent(
            text=message_text,
            message_type=msg_type,
            source=source,
            raw_message=post,
            message_id=post_id,
            media_urls=media_urls if media_urls else None,
            media_types=media_types if media_types else None,
            channel_prompt=channel_prompt,
        )

        await self.handle_message(msg_event)

    async def _resolve_room_type(self, room_id: str) -> str:
        """Look up a room's type via REST. Defaults to 'channel' on failure."""
        data = await self._api_get("rooms.info", params={"roomId": room_id})
        room = (data or {}).get("room") or {}
        return _ROOM_TYPE_MAP.get(room.get("t", "c"), "channel")

    async def _download_attachments(
        self, post: Dict[str, Any]
    ) -> tuple[List[str], List[str]]:
        """Download every file attached to *post* into the local cache.

        Rocket.Chat's stream payload surfaces attachments in two places:
          * post["file"] for single-file uploads (name, type, _id)
          * post["attachments"] with entries that carry image_url /
            audio_url / video_url / title_link pointing at /file-upload/...

        Authenticated fetches use the same X-Auth-Token/X-User-Id header pair
        as the REST API.
        """
        import aiohttp

        media_urls: List[str] = []
        media_types: List[str] = []

        candidates: List[Dict[str, str]] = []

        # Primary single-file attachment.
        primary = post.get("file") or {}
        if isinstance(primary, dict) and primary.get("_id"):
            candidates.append({
                "id": primary["_id"],
                "name": primary.get("name", f"file_{primary['_id']}"),
                "type": primary.get("type", "application/octet-stream"),
            })

        # Multi-attachment payload (e.g., an image plus an audio clip).
        for att in post.get("attachments") or []:
            if not isinstance(att, dict):
                continue
            # Prefer an explicit path from image_url/audio_url/title_link.
            path = (
                att.get("image_url")
                or att.get("audio_url")
                or att.get("video_url")
                or att.get("title_link")
                or ""
            )
            m = re.match(r"^/file-upload/([^/?#]+)/([^/?#]+)", path)
            if not m:
                continue
            fid = m.group(1)
            if any(c["id"] == fid for c in candidates):
                continue  # already queued via post["file"]
            fname = att.get("title") or m.group(2)
            # Guess a content type from attachment hints.
            if att.get("image_url"):
                mime = att.get("image_type") or "image/png"
            elif att.get("audio_url"):
                mime = att.get("audio_type") or "audio/ogg"
            elif att.get("video_url"):
                mime = att.get("video_type") or "video/mp4"
            else:
                mime = "application/octet-stream"
            candidates.append({"id": fid, "name": fname, "type": mime})

        for cand in candidates:
            try:
                url = f"{self._base_url}/file-upload/{cand['id']}/{cand['name']}"
                async with self._session.get(
                    url,
                    headers={
                        "X-Auth-Token": self._token,
                        "X-User-Id": self._bot_user_id,
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status >= 400:
                        logger.warning("Rocket.Chat: failed to download file %s: HTTP %s",
                                       cand["id"], resp.status)
                        continue
                    file_data = await resp.read()
                    mime = resp.content_type or cand["type"]
                    ext = Path(cand["name"]).suffix

                    from gateway.platforms.base import (
                        cache_image_from_bytes,
                        cache_audio_from_bytes,
                        cache_document_from_bytes,
                    )
                    if mime.startswith("image/"):
                        local_path = cache_image_from_bytes(file_data, ext or ".png")
                    elif mime.startswith("audio/"):
                        local_path = cache_audio_from_bytes(file_data, ext or ".ogg")
                    else:
                        local_path = cache_document_from_bytes(file_data, cand["name"])
                    media_urls.append(local_path)
                    media_types.append(mime)
            except Exception as exc:
                logger.warning("Rocket.Chat: error downloading file %s: %s", cand["id"], exc)

        return media_urls, media_types
