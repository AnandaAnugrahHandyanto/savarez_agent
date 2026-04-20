"""Gateway configuration models and serialization helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.config import get_hermes_home
from utils import is_truthy_value


def _coerce_bool(value: Any, default: bool = True) -> bool:
    """Coerce bool-ish config values, preserving a caller-provided default."""
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
        return default
    return is_truthy_value(value, default=default)


def _normalize_unauthorized_dm_behavior(value: Any, default: str = "pair") -> str:
    """Normalize unauthorized DM behavior to a supported value."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"pair", "ignore"}:
            return normalized
    return default


class Platform(Enum):
    """Supported messaging platforms."""

    LOCAL = "local"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    SIGNAL = "signal"
    MATTERMOST = "mattermost"
    MATRIX = "matrix"
    HOMEASSISTANT = "homeassistant"
    EMAIL = "email"
    SMS = "sms"
    DINGTALK = "dingtalk"
    API_SERVER = "api_server"
    WEBHOOK = "webhook"
    FEISHU = "feishu"
    WECOM = "wecom"
    WECOM_CALLBACK = "wecom_callback"
    WEIXIN = "weixin"
    BLUEBUBBLES = "bluebubbles"
    QQBOT = "qqbot"


@dataclass
class HomeChannel:
    """
    Default destination for a platform.

    When a cron job specifies deliver="telegram" without a specific chat ID,
    messages are sent to this home channel.
    """

    platform: Platform
    chat_id: str
    name: str  # Human-readable name for display

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "chat_id": self.chat_id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HomeChannel":
        return cls(
            platform=Platform(data["platform"]),
            chat_id=str(data["chat_id"]),
            name=data.get("name", "Home"),
        )


@dataclass
class SessionResetPolicy:
    """
    Controls when sessions reset (lose context).

    Modes:
    - "daily": Reset at a specific hour each day
    - "idle": Reset after N minutes of inactivity
    - "both": Whichever triggers first (daily boundary OR idle timeout)
    - "none": Never auto-reset (context managed only by compression)
    """

    mode: str = "both"  # "daily", "idle", "both", or "none"
    at_hour: int = 4  # Hour for daily reset (0-23, local time)
    idle_minutes: int = 1440  # Minutes of inactivity before reset (24 hours)
    notify: bool = True  # Send a notification to the user when auto-reset occurs
    notify_exclude_platforms: tuple = (
        "api_server",
        "webhook",
    )  # Platforms that don't get reset notifications

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "at_hour": self.at_hour,
            "idle_minutes": self.idle_minutes,
            "notify": self.notify,
            "notify_exclude_platforms": list(self.notify_exclude_platforms),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionResetPolicy":
        # Handle both missing keys and explicit null values (YAML null → None)
        mode = data.get("mode")
        at_hour = data.get("at_hour")
        idle_minutes = data.get("idle_minutes")
        notify = data.get("notify")
        exclude = data.get("notify_exclude_platforms")
        return cls(
            mode=mode if mode is not None else "both",
            at_hour=at_hour if at_hour is not None else 4,
            idle_minutes=idle_minutes if idle_minutes is not None else 1440,
            notify=notify if notify is not None else True,
            notify_exclude_platforms=tuple(exclude)
            if exclude is not None
            else ("api_server", "webhook"),
        )


@dataclass
class PlatformConfig:
    """Configuration for a single messaging platform."""

    enabled: bool = False
    token: Optional[str] = None  # Bot token (Telegram, Discord)
    api_key: Optional[str] = None  # API key if different from token
    home_channel: Optional[HomeChannel] = None

    # Reply threading mode (Telegram/Slack)
    # - "off": Never thread replies to original message
    # - "first": Only first chunk threads to user's message (default)
    # - "all": All chunks in multi-part replies thread to user's message
    reply_to_mode: str = "first"

    # Platform-specific settings
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "enabled": self.enabled,
            "extra": self.extra,
            "reply_to_mode": self.reply_to_mode,
        }
        if self.token:
            result["token"] = self.token
        if self.api_key:
            result["api_key"] = self.api_key
        if self.home_channel:
            result["home_channel"] = self.home_channel.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlatformConfig":
        home_channel = None
        if "home_channel" in data:
            home_channel = HomeChannel.from_dict(data["home_channel"])

        return cls(
            enabled=data.get("enabled", False),
            token=data.get("token"),
            api_key=data.get("api_key"),
            home_channel=home_channel,
            reply_to_mode=data.get("reply_to_mode", "first"),
            extra=data.get("extra", {}),
        )


@dataclass
class StreamingConfig:
    """Configuration for real-time token streaming to messaging platforms."""

    enabled: bool = False
    transport: str = "edit"  # "edit" (progressive editMessageText) or "off"
    edit_interval: float = 1.0  # Seconds between message edits
    buffer_threshold: int = 40  # Chars before forcing an edit
    cursor: str = " ▉"  # Cursor shown during streaming

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "transport": self.transport,
            "edit_interval": self.edit_interval,
            "buffer_threshold": self.buffer_threshold,
            "cursor": self.cursor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StreamingConfig":
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", False),
            transport=data.get("transport", "edit"),
            edit_interval=float(data.get("edit_interval", 1.0)),
            buffer_threshold=int(data.get("buffer_threshold", 40)),
            cursor=data.get("cursor", " ▉"),
        )


@dataclass
class GatewayConfig:
    """
    Main gateway configuration.

    Manages all platform connections, session policies, and delivery settings.
    """

    # Platform configurations
    platforms: Dict[Platform, PlatformConfig] = field(default_factory=dict)

    # Session reset policies by type
    default_reset_policy: SessionResetPolicy = field(default_factory=SessionResetPolicy)
    reset_by_type: Dict[str, SessionResetPolicy] = field(default_factory=dict)
    reset_by_platform: Dict[Platform, SessionResetPolicy] = field(default_factory=dict)

    # Reset trigger commands
    reset_triggers: List[str] = field(default_factory=lambda: ["/new", "/reset"])

    # User-defined quick commands (slash commands that bypass the agent loop)
    quick_commands: Dict[str, Any] = field(default_factory=dict)

    # Storage paths
    sessions_dir: Path = field(default_factory=lambda: get_hermes_home() / "sessions")

    # Delivery settings
    always_log_local: bool = True  # Always save cron outputs to local files

    # STT settings
    stt_enabled: bool = True  # Whether to auto-transcribe inbound voice messages

    # Session isolation in shared chats
    group_sessions_per_user: bool = True
    thread_sessions_per_user: bool = False

    # Unauthorized DM policy
    unauthorized_dm_behavior: str = "pair"  # "pair" or "ignore"

    # Streaming configuration
    streaming: StreamingConfig = field(default_factory=StreamingConfig)

    # Session store pruning: drop SessionEntry records older than this many days.
    session_store_max_age_days: int = 90

    def get_connected_platforms(self) -> List[Platform]:
        """Return list of platforms that are enabled and configured."""
        connected = []
        for platform, config in self.platforms.items():
            if not config.enabled:
                continue
            # Weixin requires both a token and an account_id
            if platform == Platform.WEIXIN:
                if config.extra.get("account_id") and (
                    config.token or config.extra.get("token")
                ):
                    connected.append(platform)
                continue
            # Platforms that use token/api_key auth
            if config.token or config.api_key:
                connected.append(platform)
            # WhatsApp uses enabled flag only (bridge handles auth)
            elif platform == Platform.WHATSAPP:
                connected.append(platform)
            # Signal uses extra dict for config (http_url + account)
            elif platform == Platform.SIGNAL and config.extra.get("http_url"):
                connected.append(platform)
            # Email uses extra dict for config (address + imap_host + smtp_host)
            elif platform == Platform.EMAIL and config.extra.get("address"):
                connected.append(platform)
            # SMS uses api_key (Twilio auth token) — SID checked via env
            elif platform == Platform.SMS and os.getenv("TWILIO_ACCOUNT_SID"):
                connected.append(platform)
            # API Server uses enabled flag only (no token needed)
            elif platform == Platform.API_SERVER:
                connected.append(platform)
            # Webhook uses enabled flag only (secrets are per-route)
            elif platform == Platform.WEBHOOK:
                connected.append(platform)
            # Feishu uses extra dict for app credentials
            elif platform == Platform.FEISHU and config.extra.get("app_id"):
                connected.append(platform)
            # WeCom bot mode uses extra dict for bot credentials
            elif platform == Platform.WECOM and config.extra.get("bot_id"):
                connected.append(platform)
            # WeCom callback mode uses corp_id or apps list
            elif platform == Platform.WECOM_CALLBACK and (
                config.extra.get("corp_id") or config.extra.get("apps")
            ):
                connected.append(platform)
            # BlueBubbles uses extra dict for local server config
            elif platform == Platform.BLUEBUBBLES and config.extra.get("server_url") and config.extra.get("password"):
                connected.append(platform)
            # QQBot uses extra dict for app credentials
            elif platform == Platform.QQBOT and config.extra.get("app_id") and config.extra.get("client_secret"):
                connected.append(platform)
            # DingTalk uses client_id/client_secret from config.extra or env vars
            elif platform == Platform.DINGTALK and (
                config.extra.get("client_id") or os.getenv("DINGTALK_CLIENT_ID")
            ) and (
                config.extra.get("client_secret") or os.getenv("DINGTALK_CLIENT_SECRET")
            ):
                connected.append(platform)

        return connected

    def get_home_channel(self, platform: Platform) -> Optional[HomeChannel]:
        """Get the home channel for a platform."""
        config = self.platforms.get(platform)
        if config:
            return config.home_channel
        return None

    def get_reset_policy(
        self,
        platform: Optional[Platform] = None,
        session_type: Optional[str] = None,
    ) -> SessionResetPolicy:
        """
        Get the appropriate reset policy for a session.

        Priority: platform override > type override > default
        """
        if platform and platform in self.reset_by_platform:
            return self.reset_by_platform[platform]

        if session_type and session_type in self.reset_by_type:
            return self.reset_by_type[session_type]

        return self.default_reset_policy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platforms": {p.value: c.to_dict() for p, c in self.platforms.items()},
            "default_reset_policy": self.default_reset_policy.to_dict(),
            "reset_by_type": {k: v.to_dict() for k, v in self.reset_by_type.items()},
            "reset_by_platform": {
                p.value: v.to_dict() for p, v in self.reset_by_platform.items()
            },
            "reset_triggers": self.reset_triggers,
            "quick_commands": self.quick_commands,
            "sessions_dir": str(self.sessions_dir),
            "always_log_local": self.always_log_local,
            "stt_enabled": self.stt_enabled,
            "group_sessions_per_user": self.group_sessions_per_user,
            "thread_sessions_per_user": self.thread_sessions_per_user,
            "unauthorized_dm_behavior": self.unauthorized_dm_behavior,
            "streaming": self.streaming.to_dict(),
            "session_store_max_age_days": self.session_store_max_age_days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayConfig":
        platforms = {}
        for platform_name, platform_data in data.get("platforms", {}).items():
            try:
                platform = Platform(platform_name)
                platforms[platform] = PlatformConfig.from_dict(platform_data)
            except ValueError:
                pass  # Skip unknown platforms

        reset_by_type = {}
        for type_name, policy_data in data.get("reset_by_type", {}).items():
            reset_by_type[type_name] = SessionResetPolicy.from_dict(policy_data)

        reset_by_platform = {}
        for platform_name, policy_data in data.get("reset_by_platform", {}).items():
            try:
                platform = Platform(platform_name)
                reset_by_platform[platform] = SessionResetPolicy.from_dict(policy_data)
            except ValueError:
                pass

        default_policy = SessionResetPolicy()
        if "default_reset_policy" in data:
            default_policy = SessionResetPolicy.from_dict(data["default_reset_policy"])

        sessions_dir = get_hermes_home() / "sessions"
        if "sessions_dir" in data:
            sessions_dir = Path(data["sessions_dir"])

        quick_commands = data.get("quick_commands", {})
        if not isinstance(quick_commands, dict):
            quick_commands = {}

        stt_enabled = data.get("stt_enabled")
        if stt_enabled is None:
            stt_enabled = (
                data.get("stt", {}).get("enabled")
                if isinstance(data.get("stt"), dict)
                else None
            )

        group_sessions_per_user = data.get("group_sessions_per_user")
        thread_sessions_per_user = data.get("thread_sessions_per_user")
        unauthorized_dm_behavior = _normalize_unauthorized_dm_behavior(
            data.get("unauthorized_dm_behavior"),
            "pair",
        )

        try:
            session_store_max_age_days = int(data.get("session_store_max_age_days", 90))
            if session_store_max_age_days < 0:
                session_store_max_age_days = 0
        except (TypeError, ValueError):
            session_store_max_age_days = 90

        return cls(
            platforms=platforms,
            default_reset_policy=default_policy,
            reset_by_type=reset_by_type,
            reset_by_platform=reset_by_platform,
            reset_triggers=data.get("reset_triggers", ["/new", "/reset"]),
            quick_commands=quick_commands,
            sessions_dir=sessions_dir,
            always_log_local=data.get("always_log_local", True),
            stt_enabled=_coerce_bool(stt_enabled, True),
            group_sessions_per_user=_coerce_bool(group_sessions_per_user, True),
            thread_sessions_per_user=_coerce_bool(thread_sessions_per_user, False),
            unauthorized_dm_behavior=unauthorized_dm_behavior,
            streaming=StreamingConfig.from_dict(data.get("streaming", {})),
            session_store_max_age_days=session_store_max_age_days,
        )

    def get_unauthorized_dm_behavior(self, platform: Optional[Platform] = None) -> str:
        """Return the effective unauthorized-DM behavior for a platform."""
        if platform:
            platform_cfg = self.platforms.get(platform)
            if platform_cfg and "unauthorized_dm_behavior" in platform_cfg.extra:
                return _normalize_unauthorized_dm_behavior(
                    platform_cfg.extra.get("unauthorized_dm_behavior"),
                    self.unauthorized_dm_behavior,
                )
        return self.unauthorized_dm_behavior


__all__ = [
    "GatewayConfig",
    "HomeChannel",
    "Platform",
    "PlatformConfig",
    "SessionResetPolicy",
    "StreamingConfig",
    "_coerce_bool",
    "_normalize_unauthorized_dm_behavior",
]
