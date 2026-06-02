"""Discord EntryAdapter MVP.

Normalizes Discord message payloads into EntryEvent.
Maps category -> workspace, channel -> session, thread -> sub-session.
Adapters must NOT call agents directly.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .entry_adapter import EntryAdapter, EntryAdapterRegistry
from .entry_event import EntryEvent
from .workspace import Workspace, DEFAULT_WORKSPACE_ID
from .session import Session, DEFAULT_SESSION_ID

# Required top-level keys in a valid Discord raw payload.
_REQUIRED_FIELDS = frozenset({"guild_id", "channel_id", "author", "content"})

# Self-message marker — author.bot or author.id == bot_user_id.
_BOT_FLAG_KEY = "bot"


class DiscordAdapter:
    """Concrete EntryAdapter for Discord messages.

    Stateless — workspace/session resolution is pure mapping, no I/O.
    """

    entrypoint = "discord"

    def __init__(self, bot_user_id: str | None = None) -> None:
        self.bot_user_id = bot_user_id

    # -- EntryAdapter protocol ----------------------------------------------

    def normalize_event(self, raw: dict[str, Any]) -> EntryEvent:
        """Convert a Discord message_create payload to EntryEvent.

        Raises ValueError if required Discord fields are missing.
        Raises ValueError if the message is from a bot or self.
        """
        _validate_discord_payload(raw)

        author = raw["author"]
        if _is_bot_message(author, self.bot_user_id):
            raise ValueError(
                "Discord bot/self messages must not produce EntryEvents. "
                f"author={author.get('id', '?')}"
            )

        guild_id = str(raw["guild_id"])
        category_id = str(raw.get("category_id") or "")
        channel_id = str(raw["channel_id"])
        thread_id = raw.get("thread_id")

        workspace_id = _workspace_for(guild_id, category_id)
        session_id = _session_for(channel_id, thread_id)

        return EntryEvent(
            event_id=str(raw.get("id") or uuid4().hex),
            entrypoint="discord",
            external_source_id=guild_id,
            external_channel_id=channel_id,
            external_thread_id=str(thread_id) if thread_id else None,
            external_user_id=str(author.get("id")),
            workspace_id=workspace_id,
            session_id=session_id,
            message=str(raw.get("content", "")),
            intent=_detect_intent(raw),
            origin_entrypoint="discord",
            dedupe_key=f"discord:{raw.get('id')}",
        )

    def resolve_workspace(self, event: EntryEvent) -> Workspace | None:
        """Map Discord category to Workspace.

        Returns a Workspace with id `ws-discord-{category_id}` if a category
        is available; otherwise returns None (caller should use default).
        """
        # Category is embedded in workspace_id during normalize_event.
        wid = event.workspace_id
        if wid == DEFAULT_WORKSPACE_ID:
            return None
        return Workspace(
            workspace_id=wid,
            name=f"Discord:{wid}",
            entrypoint="discord",
            external_source_id=event.external_source_id,
        )

    def resolve_session(
        self, event: EntryEvent, workspace: Workspace
    ) -> Session | None:
        """Map Discord channel/thread to Session.

        Returns a Session with id `ses-discord-{channel_id}` (or thread variant).
        """
        sid = event.session_id
        if sid == DEFAULT_SESSION_ID:
            return None
        return Session(
            session_id=sid,
            workspace_id=workspace.workspace_id,
            name=f"Discord:{sid}",
            entrypoint="discord",
            external_channel_id=event.external_channel_id,
            external_thread_id=event.external_thread_id,
        )

    def health(self) -> dict[str, Any]:
        """Report adapter health.

        Configured = bot_user_id is set.  Otherwise "unconfigured".
        """
        if self.bot_user_id:
            return {"entrypoint": "discord", "status": "configured", "bot_user_id": self.bot_user_id}
        return {"entrypoint": "discord", "status": "unconfigured", "reason": "bot_user_id not set"}


# ---------------------------------------------------------------------------
# Pure mapping helpers
# ---------------------------------------------------------------------------

def _validate_discord_payload(raw: dict[str, Any]) -> None:
    missing = _REQUIRED_FIELDS - raw.keys()
    if missing:
        raise ValueError(f"Discord payload missing required fields: {sorted(missing)}")


def _is_bot_message(author: dict[str, Any], bot_user_id: str | None) -> bool:
    if author.get(_BOT_FLAG_KEY):
        return True
    if bot_user_id and str(author.get("id")) == bot_user_id:
        return True
    return False


def _workspace_for(guild_id: str, category_id: str) -> str:
    """Discord category -> workspace; guild + no category -> guild workspace."""
    if category_id:
        return f"ws-discord-{category_id}"
    return f"ws-discord-guild-{guild_id}"


def _session_for(channel_id: str, thread_id: str | None) -> str:
    """Discord thread -> sub-session; channel -> session."""
    if thread_id:
        return f"ses-discord-thread-{thread_id}"
    return f"ses-discord-{channel_id}"


def _detect_intent(raw: dict[str, Any]) -> str | None:
    content = str(raw.get("content", ""))
    mentions = raw.get("mentions_me")
    if mentions:
        return "mention"
    if content.startswith("!"):
        return "command"
    return None


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_discord_adapter(
    registry: EntryAdapterRegistry,
    bot_user_id: str | None = None,
) -> DiscordAdapter:
    """Create and register a DiscordAdapter in the given registry."""
    adapter = DiscordAdapter(bot_user_id=bot_user_id)
    registry.register(adapter)
    return adapter
