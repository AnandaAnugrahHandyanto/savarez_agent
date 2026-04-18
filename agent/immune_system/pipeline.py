"""Pipeline glue: scan + wrap, gated on an opt-in environment variable.

Kept deliberately thin so call sites in the agent loop add only one line:

    tool_result = scan_and_wrap(tool_result, tool_name=name)

With HERMES_IMMUNE_SYSTEM unset the helper short-circuits and returns the
input unchanged — no regex runs, zero allocation, zero latency impact.
"""

from __future__ import annotations

import logging
import os

from .defense import wrap
from .scanner import scan

logger = logging.getLogger(__name__)

ENV_FLAG = "HERMES_IMMUNE_SYSTEM"
_TRUTHY = {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    """Return True when the immune system is enabled via env var."""
    return os.environ.get(ENV_FLAG, "").strip().lower() in _TRUTHY


def scan_and_wrap(
    content: str,
    tool_name: str = "",
    min_severity: str = "low",
) -> str:
    """Scan `content` and wrap it if a match at/above `min_severity` is found.

    No-op when the env flag is off, content is empty, or nothing at/above
    `min_severity` was flagged. Logs at INFO when content is wrapped.
    """
    if not is_enabled() or not content:
        return content

    result = scan(content)
    if not result.at_least(min_severity):
        return content

    logger.info(
        "[immune-system] wrapped tool=%r severity=%s matches=%d flags=%s",
        tool_name or "?",
        result.max_severity,
        len(result.matches),
        sorted({m.pattern_id for m in result.matches}),
    )
    return wrap(content, result, tool_name=tool_name)
