"""
Timezone-aware clock for Hermes.

Provides a single ``now()`` helper that returns a timezone-aware datetime
based on the user's configured IANA timezone (e.g. ``Asia/Kolkata``).

Resolution order:
  1. ``HERMES_TIMEZONE`` environment variable
  2. ``timezone`` key in ``~/.hermes/config.yaml``
  3. Falls back to the server's local time (``datetime.now().astimezone()``)

Invalid timezone values log a warning and fall back safely — Hermes never
crashes due to a bad timezone string.
"""

import logging
import os
import re
from datetime import datetime, timezone
from hermes_constants import get_config_path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.8 fallback (shouldn't be needed — Hermes requires 3.9+)
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

# Cached state — resolved once, reused on every call.
# Call reset_cache() to force re-resolution (e.g. after config changes).
_cached_tz: Optional[ZoneInfo] = None
_cached_tz_name: Optional[str] = None
_cache_resolved: bool = False
_UTC_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
PARIS_TZ = ZoneInfo("Europe/Paris")


def _resolve_timezone_name() -> str:
    """Read the configured IANA timezone string (or empty string).

    This does file I/O when falling through to config.yaml, so callers
    should cache the result rather than calling on every ``now()``.
    """
    # 1. Environment variable (highest priority — set by Supervisor, etc.)
    tz_env = os.getenv("HERMES_TIMEZONE", "").strip()
    if tz_env:
        return tz_env

    # 2. config.yaml ``timezone`` key
    try:
        import yaml
        config_path = get_config_path()
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            tz_cfg = cfg.get("timezone", "")
            if isinstance(tz_cfg, str) and tz_cfg.strip():
                return tz_cfg.strip()
    except Exception:
        pass

    return ""


def _get_zoneinfo(name: str) -> Optional[ZoneInfo]:
    """Validate and return a ZoneInfo, or None if invalid."""
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (KeyError, Exception) as exc:
        logger.warning(
            "Invalid timezone '%s': %s. Falling back to server local time.",
            name, exc,
        )
        return None


def get_timezone() -> Optional[ZoneInfo]:
    """Return the user's configured ZoneInfo, or None (meaning server-local).

    Resolved once and cached. Call ``reset_cache()`` after config changes.
    """
    global _cached_tz, _cached_tz_name, _cache_resolved
    if not _cache_resolved:
        _cached_tz_name = _resolve_timezone_name()
        _cached_tz = _get_zoneinfo(_cached_tz_name)
        _cache_resolved = True
    return _cached_tz


def now() -> datetime:
    """
    Return the current time as a timezone-aware datetime.

    If a valid timezone is configured, returns wall-clock time in that zone.
    Otherwise returns the server's local time (via ``astimezone()``).
    """
    tz = get_timezone()
    if tz is not None:
        return datetime.now(tz)
    # No timezone configured — use server-local (still tz-aware)
    return datetime.now().astimezone()


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def format_utc_z(dt: datetime) -> str:
    """Format a datetime as canonical UTC ``YYYY-MM-DDTHH:MM:SSZ``."""
    if dt.tzinfo is None:
        raise ValueError("format_utc_z() requires a timezone-aware datetime")
    utc_dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc_z(value: str) -> datetime:
    """Strictly parse canonical UTC ``YYYY-MM-DDTHH:MM:SSZ`` strings."""
    if not isinstance(value, str) or not _UTC_Z_RE.fullmatch(value):
        raise ValueError(f"Expected UTC-Z timestamp YYYY-MM-DDTHH:MM:SSZ, got {value!r}")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def utc_to_paris(value: datetime | str, *, format: str = "short") -> str:
    """Render a UTC datetime/string in Paris civil time for display only."""
    dt = parse_utc_z(value) if isinstance(value, str) else value
    if dt.tzinfo is None:
        raise ValueError("utc_to_paris() requires a timezone-aware datetime")
    paris_dt = dt.astimezone(PARIS_TZ)
    if format == "iso":
        return paris_dt.isoformat(timespec="seconds")
    if format == "long":
        return paris_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    return paris_dt.strftime("%Y-%m-%d %H:%M")


def paris_now() -> datetime:
    """Return current Paris civil time."""
    return utc_now().astimezone(PARIS_TZ)


def paris_hour_for_sinusoid(dt_utc: datetime | str) -> float:
    """Return fractional Paris civil hour for deterministic day/night curves."""
    dt = parse_utc_z(dt_utc) if isinstance(dt_utc, str) else dt_utc
    if dt.tzinfo is None:
        raise ValueError("paris_hour_for_sinusoid() requires a timezone-aware datetime")
    paris_dt = dt.astimezone(PARIS_TZ)
    return (
        paris_dt.hour
        + paris_dt.minute / 60
        + paris_dt.second / 3600
        + paris_dt.microsecond / 3_600_000_000
    )

