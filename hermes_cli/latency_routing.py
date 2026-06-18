from __future__ import annotations

import re
from typing import Final


_SHORT_TURN_CHAR_LIMIT: Final = 100
_SHORT_TURN_WORD_LIMIT: Final = 18
_LOW_LATENCY_CLAUDE_MODEL: Final = "anthropic/claude-sonnet-4.6"
_NATIVE_CLAUDE_PROVIDERS: Final[tuple[str, ...]] = ("anthropic", "opencode-zen")
_VENDOR_PREFIX_CLAUDE_PROVIDERS: Final[tuple[str, ...]] = (
    "openrouter",
    "kilocode",
    "nous",
)

_ACK_PATTERNS: Final[tuple[str, ...]] = (
    "ok",
    "okay",
    "k",
    "yes",
    "yep",
    "yup",
    "sure",
    "thanks",
    "thank you",
    "thx",
    "got it",
    "understood",
    "sounds good",
    "sgtm",
    "confirmed",
    "confirm",
    "done",
    "great",
    "perfect",
    "cool",
    "네",
    "확인했습니다",
    "감사합니다",
)
_GREETING_PATTERNS: Final[tuple[str, ...]] = (
    "hi",
    "hello",
    "hey",
    "yo",
    "gm",
    "good morning",
    "good afternoon",
    "good evening",
    "안녕하세요",
)
_COMPLEX_MARKERS: Final[tuple[str, ...]] = (
    "analyze",
    "analysis",
    "research",
    "investigate",
    "debug",
    "fix",
    "bug",
    "error",
    "failing",
    "failure",
    "implement",
    "change",
    "continue",
    "create",
    "edit",
    "open",
    "proceed",
    "refactor",
    "resume",
    "run",
    "start",
    "update",
    "write",
    "code",
    "test",
    "pytest",
    "lint",
    "lsp",
    "build",
    "terminal",
    "shell",
    "command",
    "tool",
    "browser",
    "repo",
    "file",
    "kanban",
    "dispatch",
    "delegate",
    "delegation",
    "worker",
    "subagent",
    "ticket",
    "blocked",
    "pr",
    "pull request",
    "ci",
    "github",
    "checks",
    "코드",
    "수정해줘",
    "칸반",
    "워커",
    "디스패치해줘",
    "실패",
    "분석해줘",
)


def route_latency_model(model: str, provider: str | None, user_message: str) -> str:
    if not _is_claude_opus(model):
        return model
    if not _is_short_low_complexity_turn(user_message):
        return model
    return _target_for_provider(model, provider)


def _is_claude_opus(model: str) -> bool:
    normalized = model.strip().lower().replace(".", "-")
    return "claude-opus-4" in normalized


def _is_short_low_complexity_turn(user_message: str) -> bool:
    preview = _message_preview(user_message)
    if not preview:
        return False
    if len(preview) > _SHORT_TURN_CHAR_LIMIT:
        return False
    if len(preview.split()) > _SHORT_TURN_WORD_LIMIT:
        return False
    if preview.startswith("/"):
        return False
    if "```" in user_message or "\n" in user_message.strip():
        return False
    if _contains_marker(preview, _COMPLEX_MARKERS):
        return False
    return _contains_marker(preview, _ACK_PATTERNS) or _contains_marker(preview, _GREETING_PATTERNS)


def _message_preview(user_message: str) -> str:
    preview = " ".join(user_message[:_SHORT_TURN_CHAR_LIMIT].lower().split())
    return preview.strip(" \t\r\n.!?,:;")


def _contains_marker(preview: str, markers: tuple[str, ...]) -> bool:
    for marker in markers:
        if re.search(rf"(^|\W){re.escape(marker)}(\W|$)", preview):
            return True
    return False


def _target_for_provider(model: str, provider: str | None) -> str:
    normalized_provider = (provider or "").strip().lower()
    if normalized_provider in _NATIVE_CLAUDE_PROVIDERS:
        return "claude-sonnet-4-6"
    if normalized_provider in _VENDOR_PREFIX_CLAUDE_PROVIDERS or "/" in model:
        return _LOW_LATENCY_CLAUDE_MODEL
    return "claude-sonnet-4-6"
