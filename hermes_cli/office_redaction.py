"""Redaction helpers for Hermes AI Office DTO serialization.

The Office API is browser-facing and aggregates sensitive operational data.  Keep
this module deliberately conservative: display strings may be shortened or
masked, but raw prompts, transcripts, tool calls, credentials, and local paths
must not leak through DTOs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re


REDACTION_POLICY_VERSION = 1
_REDACTED = "[REDACTED]"

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # OpenAI-style and similar API keys.  Keep broad enough for sentinel tests
    # but avoid matching ordinary short words.
    re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b"),
    # Authorization header values.
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{6,}=*\b", re.IGNORECASE),
    # Telegram bot token shape: numeric bot id, colon, long secret.
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{10,}\b"),
    # Profile-local credential/config file references.
    re.compile(r"(?:(?:/[^\s]+)+/)?(?:\.env|auth\.json)\b"),
    # Common Hermes/OS paths that should not become browser display strings.
    re.compile(r"/(?:home|mnt|tmp|var)/(?:[^\s'\"<>]+)")
)


@dataclass
class RedactionReport:
    """Summary of redaction actions applied while serializing OfficeState."""

    policy_version: int = REDACTION_POLICY_VERSION
    redacted_field_count: int = 0
    omitted_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: "RedactionReport") -> None:
        self.redacted_field_count += other.redacted_field_count
        for section in other.omitted_sections:
            if section not in self.omitted_sections:
                self.omitted_sections.append(section)
        for warning in other.warnings:
            if warning not in self.warnings:
                self.warnings.append(warning)

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "redacted_field_count": self.redacted_field_count,
            "omitted_sections": list(self.omitted_sections),
            "warnings": list(self.warnings),
        }


def redact_display_text(value: object) -> tuple[str, RedactionReport]:
    """Return a browser-safe display string plus a redaction report.

    This helper is intentionally for short display fields only.  Source sections
    such as transcripts, prompts, tool-call JSON, cron scripts, and Kanban task
    bodies should be omitted before calling this function, not passed through for
    partial masking.
    """

    text = "" if value is None else str(value)
    report = RedactionReport()
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted, count = pattern.subn(_REDACTED, redacted)
        report.redacted_field_count += count
    if report.redacted_field_count:
        report.warnings.append("display_text_redacted")
    return redacted, report
