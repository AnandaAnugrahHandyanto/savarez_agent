"""Minimal gateway session types for standalone WeChat bridge."""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now()


def _hash_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _hash_sender_id(value: str) -> str:
    return f"user_{_hash_id(value)}"


def _hash_chat_id(value: str) -> str:
    colon = value.find(":")
    if colon > 0:
        prefix = value[:colon]
        return f"{prefix}:{_hash_id(value[colon + 1:])}"
    return _hash_id(value)


from wechat_hermes.gateway_config import (
    Platform,
    GatewayConfig,
    SessionResetPolicy,
    HomeChannel,
)


@dataclass
class SessionSource:
    """
    Describes where a message originated from.
    
    This information is used to:
    1. Route responses back to the right place
    2. Inject context into the system prompt
    3. Track origin for cron job delivery
    """
    platform: Platform
    chat_id: str
    chat_name: Optional[str] = None
    chat_type: str = "dm"  # "dm", "group", "channel", "thread"
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    thread_id: Optional[str] = None  # For forum topics, Discord threads, etc.
    chat_topic: Optional[str] = None  # Channel topic/description (Discord, Slack)
    user_id_alt: Optional[str] = None  # Signal UUID (alternative to phone number)
    chat_id_alt: Optional[str] = None  # Signal group internal ID
    is_bot: bool = False  # True when the message author is a bot/webhook (Discord)
    
    @property
    def description(self) -> str:
        """Human-readable description of the source."""
        if self.platform == Platform.LOCAL:
            return "CLI terminal"
        
        parts = []
        if self.chat_type == "dm":
            parts.append(f"DM with {self.user_name or self.user_id or 'user'}")
        elif self.chat_type == "group":
            parts.append(f"group: {self.chat_name or self.chat_id}")
        elif self.chat_type == "channel":
            parts.append(f"channel: {self.chat_name or self.chat_id}")
        else:
            parts.append(self.chat_name or self.chat_id)
        
        if self.thread_id:
            parts.append(f"thread: {self.thread_id}")
        
        return ", ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "platform": self.platform.value,
            "chat_id": self.chat_id,
            "chat_name": self.chat_name,
            "chat_type": self.chat_type,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "thread_id": self.thread_id,
            "chat_topic": self.chat_topic,
        }
        if self.user_id_alt:
            d["user_id_alt"] = self.user_id_alt
        if self.chat_id_alt:
            d["chat_id_alt"] = self.chat_id_alt
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSource":
        return cls(
            platform=Platform(data["platform"]),
            chat_id=str(data["chat_id"]),
            chat_name=data.get("chat_name"),
            chat_type=data.get("chat_type", "dm"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            thread_id=data.get("thread_id"),
            chat_topic=data.get("chat_topic"),
            user_id_alt=data.get("user_id_alt"),
            chat_id_alt=data.get("chat_id_alt"),
        )
    


@dataclass
class SessionContext:
    """
    Full context for a session, used for dynamic system prompt injection.
    
    The agent receives this information to understand:
    - Where messages are coming from
    - What platforms are available
    - Where it can deliver scheduled task outputs
    """
    source: SessionSource
    connected_platforms: List[Platform]
    home_channels: Dict[Platform, HomeChannel]
    shared_multi_user_session: bool = False
    
    # Session metadata
    session_key: str = ""
    session_id: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "connected_platforms": [p.value for p in self.connected_platforms],
            "home_channels": {
                p.value: hc.to_dict() for p, hc in self.home_channels.items()
            },
            "shared_multi_user_session": self.shared_multi_user_session,
            "session_key": self.session_key,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


_PII_SAFE_PLATFORMS = frozenset({
    Platform.WHATSAPP,
    Platform.SIGNAL,
    Platform.TELEGRAM,
    Platform.BLUEBUBBLES,
})
"""Platforms where user IDs can be safely redacted (no in-message mention system
that requires raw IDs).  Discord is excluded because mentions use ``<@user_id>``
and the LLM needs the real ID to tag users."""


def build_session_context_prompt(
    context: SessionContext,
    *,
    redact_pii: bool = False,
) -> str:
    """
    Build the dynamic system prompt section that tells the agent about its context.
    
    This is injected into the system prompt so the agent knows:
    - Where messages are coming from
    - What platforms are connected
    - Where it can deliver scheduled task outputs

    When *redact_pii* is True **and** the source platform is in
    ``_PII_SAFE_PLATFORMS``, phone numbers are stripped and user/chat IDs
    are replaced with deterministic hashes before being sent to the LLM.
    Platforms like Discord are excluded because mentions need real IDs.
    Routing still uses the original values (they stay in SessionSource).
    """
    # Only apply redaction on platforms where IDs aren't needed for mentions
    redact_pii = redact_pii and context.source.platform in _PII_SAFE_PLATFORMS
    lines = [
        "## Current Session Context",
        "",
    ]
    
    # Source info
    platform_name = context.source.platform.value.title()
    if context.source.platform == Platform.LOCAL:
        lines.append(f"**Source:** {platform_name} (the machine running this agent)")
    else:
        # Build a description that respects PII redaction
        src = context.source
        if redact_pii:
            # Build a safe description without raw IDs
            _uname = src.user_name or (
                _hash_sender_id(src.user_id) if src.user_id else "user"
            )
            _cname = src.chat_name or _hash_chat_id(src.chat_id)
            if src.chat_type == "dm":
                desc = f"DM with {_uname}"
            elif src.chat_type == "group":
                desc = f"group: {_cname}"
            elif src.chat_type == "channel":
                desc = f"channel: {_cname}"
            else:
                desc = _cname
        else:
            desc = src.description
        lines.append(f"**Source:** {platform_name} ({desc})")
    
    # Channel topic (if available - provides context about the channel's purpose)
    if context.source.chat_topic:
        lines.append(f"**Channel Topic:** {context.source.chat_topic}")

    # User identity.
    # In shared multi-user sessions (shared threads OR shared non-thread groups
    # when group_sessions_per_user=False), multiple users contribute to the same
    # conversation.  Don't pin a single user name in the system prompt — it
    # changes per-turn and would bust the prompt cache.  Instead, note that
    # this is a multi-user session; individual sender names are prefixed on
    # each user message by the gateway.
    if context.shared_multi_user_session:
        session_label = "Multi-user thread" if context.source.thread_id else "Multi-user session"
        lines.append(
            f"**Session type:** {session_label} — messages are prefixed "
            "with [sender name]. Multiple users may participate."
        )
    elif context.source.user_name:
        lines.append(f"**User:** {context.source.user_name}")
    elif context.source.user_id:
        uid = context.source.user_id
        if redact_pii:
            uid = _hash_sender_id(uid)
        lines.append(f"**User ID:** {uid}")
    
    # Platform-specific behavioral notes
    if context.source.platform == Platform.SLACK:
        lines.append("")
        lines.append(
            "**Platform notes:** You are running inside Slack. "
            "You do NOT have access to Slack-specific APIs — you cannot search "
            "channel history, pin/unpin messages, manage channels, or list users. "
            "Do not promise to perform these actions. If the user asks, explain "
            "that you can only read messages sent directly to you and respond."
        )
    elif context.source.platform == Platform.DISCORD:
        lines.append("")
        lines.append(
            "**Platform notes:** You are running inside Discord. "
            "You do NOT have access to Discord-specific APIs — you cannot search "
            "channel history, pin messages, manage roles, or list server members. "
            "Do not promise to perform these actions. If the user asks, explain "
            "that you can only read messages sent directly to you and respond."
        )

    # Connected platforms
    platforms_list = ["local (files on this machine)"]
    for p in context.connected_platforms:
        if p != Platform.LOCAL:
            platforms_list.append(f"{p.value}: Connected ✓")
    
    lines.append(f"**Connected Platforms:** {', '.join(platforms_list)}")
    
    # Home channels
    if context.home_channels:
        lines.append("")
        lines.append("**Home Channels (default destinations):**")
        for platform, home in context.home_channels.items():
            hc_id = _hash_chat_id(home.chat_id) if redact_pii else home.chat_id
            lines.append(f"  - {platform.value}: {home.name} (ID: {hc_id})")
    
    # Delivery options for scheduled tasks
    lines.append("")
    lines.append("**Delivery options for scheduled tasks:**")
    
    from wechat_hermes.hermes_home import display_hermes_home

    # Origin delivery
    if context.source.platform == Platform.LOCAL:
        lines.append("- `\"origin\"` → Local output (saved to files)")
    else:
        _origin_label = context.source.chat_name or (
            _hash_chat_id(context.source.chat_id) if redact_pii else context.source.chat_id
        )
        lines.append(f"- `\"origin\"` → Back to this chat ({_origin_label})")

    # Local always available
    lines.append(
        f"- `\"local\"` → Save to local files only ({display_hermes_home()}/cron/output/)"
    )
    
    # Platform home channels
    for platform, home in context.home_channels.items():
        lines.append(f"- `\"{platform.value}\"` → Home channel ({home.name})")
    
    # Note about explicit targeting
    lines.append("")
    lines.append("*For explicit targeting, use `\"platform:chat_id\"` format if the user provides a specific chat ID.*")
    
    return "\n".join(lines)


@dataclass
class SessionEntry:
    """
    Entry in the session store.
    
    Maps a session key to its current session ID and metadata.
    """
    session_key: str
    session_id: str
    created_at: datetime
    updated_at: datetime
    
    # Origin metadata for delivery routing
    origin: Optional[SessionSource] = None
    
    # Display metadata
    display_name: Optional[str] = None
    platform: Optional[Platform] = None
    chat_type: str = "dm"
    
    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cost_status: str = "unknown"
    
    # Last API-reported prompt tokens (for accurate compression pre-check)
    last_prompt_tokens: int = 0
    
    # Set when a session was created because the previous one expired;
    # consumed once by the message handler to inject a notice into context
    was_auto_reset: bool = False
    auto_reset_reason: Optional[str] = None  # "idle" or "daily"
    reset_had_activity: bool = False  # whether the expired session had any messages
    
    # Set by the background expiry watcher after it successfully flushes
    # memories for this session.  Persisted to sessions.json so the flag
    # survives gateway restarts (the old in-memory _pre_flushed_sessions
    # set was lost on restart, causing redundant re-flushes).
    memory_flushed: bool = False

    # When True the next call to get_or_create_session() will auto-reset
    # this session (create a new session_id) so the user starts fresh.
    # Set by /stop to break stuck-resume loops (#7536).
    suspended: bool = False

    # When True the session was interrupted by a gateway restart/shutdown
    # drain timeout, but recovery is still expected.  Unlike ``suspended``,
    # ``resume_pending`` preserves the existing session_id on next access —
    # the user stays on the same transcript and the agent auto-continues
    # from where it left off.  Cleared after the next successful turn.
    # Escalation to ``suspended`` is handled by the existing
    # ``.restart_failure_counts`` stuck-loop counter (#7536), not by a
    # parallel counter on this entry.
    resume_pending: bool = False
    resume_reason: Optional[str] = None  # e.g. "restart_timeout"
    last_resume_marked_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "session_key": self.session_key,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "display_name": self.display_name,
            "platform": self.platform.value if self.platform else None,
            "chat_type": self.chat_type,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.total_tokens,
            "last_prompt_tokens": self.last_prompt_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "cost_status": self.cost_status,
            "memory_flushed": self.memory_flushed,
            "suspended": self.suspended,
            "resume_pending": self.resume_pending,
            "resume_reason": self.resume_reason,
            "last_resume_marked_at": (
                self.last_resume_marked_at.isoformat()
                if self.last_resume_marked_at
                else None
            ),
        }
        if self.origin:
            result["origin"] = self.origin.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionEntry":
        origin = None
        if "origin" in data and data["origin"]:
            origin = SessionSource.from_dict(data["origin"])
        
        platform = None
        if data.get("platform"):
            try:
                platform = Platform(data["platform"])
            except ValueError as e:
                logger.debug("Unknown platform value %r: %s", data["platform"], e)

        last_resume_marked_at = None
        _lrma = data.get("last_resume_marked_at")
        if _lrma:
            try:
                last_resume_marked_at = datetime.fromisoformat(_lrma)
            except (TypeError, ValueError):
                last_resume_marked_at = None

        return cls(
            session_key=data["session_key"],
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            origin=origin,
            display_name=data.get("display_name"),
            platform=platform,
            chat_type=data.get("chat_type", "dm"),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_read_tokens=data.get("cache_read_tokens", 0),
            cache_write_tokens=data.get("cache_write_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            last_prompt_tokens=data.get("last_prompt_tokens", 0),
            estimated_cost_usd=data.get("estimated_cost_usd", 0.0),
            cost_status=data.get("cost_status", "unknown"),
            memory_flushed=data.get("memory_flushed", False),
            suspended=data.get("suspended", False),
            resume_pending=data.get("resume_pending", False),
            resume_reason=data.get("resume_reason"),
            last_resume_marked_at=last_resume_marked_at,
        )


def is_shared_multi_user_session(
    source: SessionSource,
    *,
    group_sessions_per_user: bool = True,
    thread_sessions_per_user: bool = False,
) -> bool:
    """Return True when a non-DM session is shared across participants.

    Mirrors the isolation rules in :func:`build_session_key`:
      - DMs are never shared.
      - Threads are shared unless ``thread_sessions_per_user`` is True.
      - Non-thread group/channel sessions are shared unless
        ``group_sessions_per_user`` is True (default: True = isolated).
    """
    if source.chat_type == "dm":
        return False
    if source.thread_id:
        return not thread_sessions_per_user
    return not group_sessions_per_user


def build_session_key(
    source: SessionSource,
    group_sessions_per_user: bool = True,
    thread_sessions_per_user: bool = False,
) -> str:
    """Build a deterministic session key from a message source.

    This is the single source of truth for session key construction.

    DM rules:
      - DMs include chat_id when present, so each private conversation is isolated.
      - thread_id further differentiates threaded DMs within the same DM chat.
      - Without chat_id, thread_id is used as a best-effort fallback.
      - Without thread_id or chat_id, DMs share a single session.

    Group/channel rules:
      - chat_id identifies the parent group/channel.
      - user_id/user_id_alt isolates participants within that parent chat when available when
        ``group_sessions_per_user`` is enabled.
      - thread_id differentiates threads within that parent chat.  When
        ``thread_sessions_per_user`` is False (default), threads are *shared* across all
        participants — user_id is NOT appended, so every user in the thread
        shares a single session.  This is the expected UX for threaded
        conversations (Telegram forum topics, Discord threads, Slack threads).
      - Without participant identifiers, or when isolation is disabled, messages fall back to one
        shared session per chat.
      - Without identifiers, messages fall back to one session per platform/chat_type.
    """
    platform = source.platform.value
    if source.chat_type == "dm":
        if source.chat_id:
            if source.thread_id:
                return f"agent:main:{platform}:dm:{source.chat_id}:{source.thread_id}"
            return f"agent:main:{platform}:dm:{source.chat_id}"
        if source.thread_id:
            return f"agent:main:{platform}:dm:{source.thread_id}"
        return f"agent:main:{platform}:dm"

    participant_id = source.user_id_alt or source.user_id
    key_parts = ["agent:main", platform, source.chat_type]

    if source.chat_id:
        key_parts.append(source.chat_id)
    if source.thread_id:
        key_parts.append(source.thread_id)

    # In threads, default to shared sessions (all participants see the same
    # conversation).  Per-user isolation only applies when explicitly enabled
    # via thread_sessions_per_user, or when there is no thread (regular group).
    isolate_user = group_sessions_per_user
    if source.thread_id and not thread_sessions_per_user:
        isolate_user = False

    if isolate_user and participant_id:
        key_parts.append(str(participant_id))

    return ":".join(key_parts)
