"""CLI flag verification for CMH subprocess wrapper foundations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

CLAUDE_REQUIRED_FLAGS: tuple[str, ...] = (
    "--print",
    "--max-budget-usd",
    "--output-format",
    "--no-session-persistence",
)

CLAUDE_OPTIONAL_FLAGS: tuple[str, ...] = (
    "--plugin-dir",
    "--model",
    "--permission-mode",
    "--tools",
    "--bare",
)

CODEX_REQUIRED_FLAGS_UNRESOLVED: tuple[str, ...] = ()

_LONG_FLAG_RE = re.compile(r"(?<![\w-])--[a-zA-Z0-9][a-zA-Z0-9-]*")


@dataclass(frozen=True)
class FlagValidationResult:
    cli_name: str
    ok: bool
    required_flags: tuple[str, ...]
    optional_flags: tuple[str, ...]
    available_flags: dict[str, bool]
    missing_required_flags: list[str]


def extract_long_flags(help_text: str) -> set[str]:
    """Return long CLI flags found in help output or verified docs."""
    return set(_LONG_FLAG_RE.findall(help_text or ""))


def validate_flags(
    cli_name: str,
    help_text: str,
    required_flags: Iterable[str],
    optional_flags: Iterable[str] = (),
) -> FlagValidationResult:
    """Validate required and optional flags against a text evidence source."""
    required = tuple(required_flags)
    optional = tuple(optional_flags)
    found = extract_long_flags(help_text)
    requested = required + optional
    available = {flag: flag in found for flag in requested}
    missing = [flag for flag in required if flag not in found]
    return FlagValidationResult(
        cli_name=cli_name,
        ok=not missing,
        required_flags=required,
        optional_flags=optional,
        available_flags=available,
        missing_required_flags=missing,
    )
