"""Prompt-injection immune system.

Scans tool outputs for injection attempts and wraps suspicious content in
defensive tags that tell the model to treat the payload as data, not
instructions.

Public API:
    scan(content, max_length=...) -> ScanResult
    wrap(content, scan_result, tool_name="") -> str
    scan_and_wrap(content, tool_name="", min_severity="low") -> str
    is_enabled() -> bool

The `scan_and_wrap` pipeline is a no-op unless the HERMES_IMMUNE_SYSTEM
environment variable is set to a truthy value ("1", "true", "yes", "on").
This keeps the feature fully opt-in and guarantees zero behavior change
for existing users.
"""

from .defense import wrap
from .pipeline import ENV_FLAG, is_enabled, scan_and_wrap
from .scanner import Match, ScanResult, scan

__all__ = [
    "ENV_FLAG",
    "Match",
    "ScanResult",
    "is_enabled",
    "scan",
    "scan_and_wrap",
    "wrap",
]
