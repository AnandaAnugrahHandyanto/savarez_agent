"""Source-aware busy-input policy for gateway sessions.

The gateway's global ``display.busy_input_mode`` remains the safe default.
This module lets operators add ordered, generic source rules without baking
platform-specific workflows (Dispatch, worker lanes, etc.) into gateway/run.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Sequence

BusyInputMode = Literal["interrupt", "queue", "steer"]
_VALID_MODES: set[str] = {"interrupt", "queue", "steer"}


def normalize_busy_input_mode(value: Any, *, default: BusyInputMode | None = None) -> BusyInputMode | None:
    """Normalize a busy-input mode string, returning *default* for invalid values."""
    mode = str(value or "").strip().lower()
    if mode in _VALID_MODES:
        return mode  # type: ignore[return-value]
    return default


def _string_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, Iterable):
        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return tuple(items)
    text = str(value).strip()
    return (text,) if text else ()


@dataclass(frozen=True)
class BusyInputRule:
    """One ordered source-aware override for a busy gateway session."""

    mode: BusyInputMode
    platform: str | None = None
    is_bot: bool | None = None
    user_ids: tuple[str, ...] = field(default_factory=tuple)
    chat_ids: tuple[str, ...] = field(default_factory=tuple)
    message_types: tuple[str, ...] = field(default_factory=tuple)
    text_prefixes: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_config(cls, raw: Any) -> "BusyInputRule | None":
        if not isinstance(raw, dict):
            return None
        mode = normalize_busy_input_mode(raw.get("mode"))
        if mode is None:
            return None

        platform = raw.get("platform")
        platform_text = str(platform).strip().lower() if platform not in {None, ""} else None

        raw_is_bot = raw.get("is_bot")
        is_bot = raw_is_bot if isinstance(raw_is_bot, bool) else None

        return cls(
            mode=mode,
            platform=platform_text,
            is_bot=is_bot,
            user_ids=_string_list(raw.get("user_ids")),
            chat_ids=_string_list(raw.get("chat_ids")),
            message_types=tuple(item.lower() for item in _string_list(raw.get("message_types"))),
            text_prefixes=_string_list(raw.get("text_prefixes")),
        )

    def matches(self, event: Any) -> bool:
        source = getattr(event, "source", None)
        if source is None:
            return False

        if self.platform is not None and _platform_value(getattr(source, "platform", None)) != self.platform:
            return False

        if self.is_bot is not None and bool(getattr(source, "is_bot", False)) is not self.is_bot:
            return False

        if self.user_ids:
            user_candidates = {
                str(value)
                for value in (
                    getattr(source, "user_id", None),
                    getattr(source, "user_id_alt", None),
                )
                if value not in {None, ""}
            }
            if not user_candidates.intersection(self.user_ids):
                return False

        if self.chat_ids:
            chat_candidates = {
                str(value)
                for value in (
                    getattr(source, "chat_id", None),
                    getattr(source, "thread_id", None),
                    getattr(source, "parent_chat_id", None),
                    getattr(source, "chat_id_alt", None),
                )
                if value not in {None, ""}
            }
            if not chat_candidates.intersection(self.chat_ids):
                return False

        if self.message_types:
            message_type = _message_type_value(getattr(event, "message_type", None))
            if message_type not in self.message_types:
                return False

        if self.text_prefixes:
            text = str(getattr(event, "text", "") or "")
            if not any(text.startswith(prefix) for prefix in self.text_prefixes):
                return False

        return True


def _platform_value(platform: Any) -> str | None:
    value = getattr(platform, "value", platform)
    if value in {None, ""}:
        return None
    return str(value).strip().lower()


def _message_type_value(message_type: Any) -> str | None:
    value = getattr(message_type, "value", message_type)
    if value in {None, ""}:
        return None
    return str(value).strip().lower()


def load_busy_input_rules(config: Any) -> list[BusyInputRule]:
    """Load ordered ``display.busy_input_rules`` entries from config data."""
    if not isinstance(config, dict):
        return []
    display = config.get("display")
    if not isinstance(display, dict):
        return []
    raw_rules = display.get("busy_input_rules") or []
    if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
        return []

    rules: list[BusyInputRule] = []
    for raw_rule in raw_rules:
        rule = BusyInputRule.from_config(raw_rule)
        if rule is not None:
            rules.append(rule)
    return rules


def resolve_busy_input_mode(
    event: Any,
    default_mode: Any,
    rules: Sequence[BusyInputRule] | None = None,
) -> BusyInputMode:
    """Resolve the effective busy-input mode for *event*.

    Rules are evaluated in order.  The first matching rule wins.  With no
    matching rule, the normalized global default is returned; invalid defaults
    fail safe to ``interrupt``.
    """
    fallback = normalize_busy_input_mode(default_mode, default="interrupt") or "interrupt"
    for rule in rules or []:
        if rule.matches(event):
            return rule.mode
    return fallback
