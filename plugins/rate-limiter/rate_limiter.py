"""Cross-session rate limit guard for side clients.

Writes rate limit state to a shared file so all sessions (CLI, gateway,
cron, auxiliary) can check whether a provider is currently rate-limited
before making requests. Prevents retry amplification when RPH is tapped.

Each 429 from a provider triggers up to 9 API calls per conversation turn
(3 SDK retries x 3 Hermes retries), and every one of those calls counts
against RPH. By recording the rate limit state on first 429 and checking
it before subsequent attempts, we eliminate the amplification effect.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

_STATE_SUBDIR = "rate_limits"
_STATE_FILENAME = "nous.json"
_CONFIG_FILENAME = "config.json"


def _state_path() -> str:
    """Return the path to the rate limit state file."""
    try:
        from hermes_constants import get_hermes_home
        base = get_hermes_home()
    except ImportError:
        base = os.path.join(os.path.expanduser("~"), ".hermes")
    return os.path.join(base, _STATE_SUBDIR, _STATE_FILENAME)


def _config_path() -> str:
    """Return the path to the rate limiter config file."""
    try:
        from hermes_constants import get_hermes_home
        base = get_hermes_home()
    except ImportError:
        base = os.path.join(os.path.expanduser("~"), ".hermes")
    return os.path.join(base, _STATE_SUBDIR, _CONFIG_FILENAME)


def _load_config() -> dict:
    """Load the rate limiter config."""
    path = _config_path()
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Default config: enabled, 5 minute cooldown
        return {"enabled": True, "default_cooldown": 300.0}


def _save_config(config: dict) -> None:
    """Save the rate limiter config."""
    path = _config_path()
    try:
        state_dir = os.path.dirname(path)
        os.makedirs(state_dir, exist_ok=True)

        # Atomic write: write to temp file + rename
        fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(config, f)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.debug("Failed to save rate limiter config: %s", exc)


def is_enabled() -> bool:
    """Check if the rate limiter is enabled."""
    config = _load_config()
    return config.get("enabled", True)


def set_enabled(enabled: bool) -> None:
    """Enable or disable the rate limiter."""
    config = _load_config()
    config["enabled"] = enabled
    _save_config(config)


def get_default_cooldown() -> float:
    """Get the default cooldown in seconds."""
    config = _load_config()
    return config.get("default_cooldown", 300.0)


def set_default_cooldown(cooldown: float) -> None:
    """Set the default cooldown in seconds."""
    if cooldown < 0:
        raise ValueError("Cooldown must be non-negative")
    config = _load_config()
    config["default_cooldown"] = cooldown
    _save_config(config)


def _parse_reset_seconds(headers: Optional[Mapping[str, str]]) -> Optional[float]:
    """Extract the best available reset-time estimate from response headers.

    Priority:
      1. x-ratelimit-reset-requests-1h  (hourly RPH window — most useful)
      2. x-ratelimit-reset-requests     (per-minute RPM window)
      3. retry-after                     (generic HTTP header)

    Returns seconds-from-now, or None if no usable header found.
    """
    if not headers:
        return None

    lowered = {k.lower(): v for k, v in headers.items()}

    for key in (
        "x-ratelimit-reset-requests-1h",
        "x-ratelimit-reset-requests",
        "retry-after",
    ):
        raw = lowered.get(key)
        if raw is not None:
            try:
                val = float(raw)
                if val > 0:
                    return val
            except (TypeError, ValueError):
                pass

    return None


def record_rate_limit(
    *,
    headers: Optional[Mapping[str, str]] = None,
    error_context: Optional[dict[str, Any]] = None,
    default_cooldown: float = 300.0,
) -> None:
    """Record that a provider is rate-limited.

    Parses the reset time from response headers or error context.
    Falls back to ``default_cooldown`` (5 minutes) if no reset info
    is available. Writes to a shared file that all sessions can read.

    Args:
        headers: HTTP response headers from the 429 error.
        error_context: Structured error context from _extract_api_error_context().
        default_cooldown: Fallback cooldown in seconds when no header data.
    """
    now = time.time()
    reset_at = None

    # Try headers first (most accurate)
    header_seconds = _parse_reset_seconds(headers)
    if header_seconds is not None:
        reset_at = now + header_seconds

    # Try error_context reset_at (from body parsing)
    if reset_at is None and isinstance(error_context, dict):
        ctx_reset = error_context.get("reset_at")
        if isinstance(ctx_reset, (int, float)) and ctx_reset > now:
            reset_at = float(ctx_reset)

    # Default cooldown
    if reset_at is None:
        reset_at = now + default_cooldown

    path = _state_path()
    try:
        state_dir = os.path.dirname(path)
        os.makedirs(state_dir, exist_ok=True)

        state = {
            "reset_at": reset_at,
            "recorded_at": now,
            "reset_seconds": reset_at - now,
        }

        # Atomic write: write to temp file + rename
        fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        logger.info(
            "Rate limit recorded: resets in %.0fs (at %.0f)",
            reset_at - now, reset_at,
        )
    except Exception as exc:
        logger.debug("Failed to write rate limit state: %s", exc)


def get_rate_limit_remaining() -> Optional[float]:
    """Check if a provider is currently rate-limited.

    Returns:
        Seconds remaining until reset, or None if not rate-limited.
    """
    path = _state_path()
    try:
        with open(path) as f:
            state = json.load(f)
        reset_at = state.get("reset_at", 0)
        remaining = reset_at - time.time()
        if remaining > 0:
            return remaining
        # Expired — clean up
        try:
            os.unlink(path)
        except OSError:
            pass
        return None
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError):
        return None


def clear_rate_limit() -> None:
    """Clear the rate limit state (e.g., after a successful request)."""
    try:
        os.unlink(_state_path())
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.debug("Failed to clear rate limit state: %s", exc)


def format_remaining(seconds: float) -> str:
    """Format seconds remaining into human-readable duration."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        m, sec = divmod(s, 60)
        return f"{m}m {sec}s" if sec else f"{m}m"
    h, remainder = divmod(s, 3600)
    m = remainder // 60
    return f"{h}h {m}m" if m else f"{h}h"


def check_rate_limit_before_call(
    provider: str = "",
    model: str = "",
) -> Optional[float]:
    """Check if we should rate-limit before making an API call.

    This is called from run_agent.py BEFORE making the API call.
    It tracks request counts per minute and returns the remaining time
    if we're rate-limited, or None if we can proceed.

    Args:
        provider: Provider name (e.g., "nvidia", "openrouter", "nous")
        model: Model name (for per-model limits if configured)

    Returns:
        Seconds remaining until reset, or None if not rate-limited.
    """
    # Check if rate limiter is enabled
    if not is_enabled():
        return None

    config = _load_config()
    if not config:
        return None

    # Get the limit for this provider
    provider_key = provider.lower() if provider else "default"
    limit_config = config.get("limits", {}).get(provider_key, {})
    rpm = limit_config.get("requests_per_minute")

    if not rpm:
        # Try default limit
        rpm = config.get("limits", {}).get("default", {}).get("requests_per_minute")
        if not rpm:
            return None

    # Track request counts in memory
    # Use a simple sliding window approach
    now = time.time()
    window_start = now - 60.0  # 1-minute window

    # Get or create request tracker for this provider
    tracker_key = f"{provider_key}:{model}" if model else provider_key

    # Load existing tracker state
    tracker_path = os.path.join(os.path.dirname(_state_path()), f"tracker_{provider_key}.json")
    try:
        with open(tracker_path) as f:
            tracker = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        tracker = {"requests": [], "last_reset": now}

    # Clean up old requests outside the window
    tracker["requests"] = [t for t in tracker.get("requests", []) if t > window_start]

    # Check if we're at the limit
    request_count = len(tracker["requests"])
    if request_count >= rpm:
        # We're rate-limited - calculate when the oldest request will expire
        if tracker["requests"]:
            oldest_request = min(tracker["requests"])
            remaining = oldest_request + 60.0 - now
            if remaining > 0:
                logger.warning(
                    "Rate limit reached for %s: %d requests in last minute. Wait %.0fs.",
                    provider_key,
                    request_count,
                    remaining,
                )
                return remaining

    # Record this request
    tracker["requests"].append(now)

    # Save tracker state
    try:
        state_dir = os.path.dirname(tracker_path)
        os.makedirs(state_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(tracker, f)
            os.replace(tmp_path, tracker_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception as exc:
        logger.debug("Failed to write rate limit tracker: %s", exc)

    return None


# Hook functions for plugin integration
def check_rate_limit(
    session_id: str = "",
    user_message: str = "",
    conversation_history: list = [],
    is_first_turn: bool = False,
    model: str = "",
    platform: str = "",
    sender_id: str = "",
    **kwargs
) -> Optional[dict]:
    """Pre-LLM call hook: inject context if rate-limited.

    NOTE: pre_llm_call cannot block the LLM call - it can only inject context.
    We inject a message to inform the user about the rate limit.
    """
    # Check if rate limiter is enabled
    if not is_enabled():
        return None

    remaining = get_rate_limit_remaining()
    if remaining is not None:
        logger.warning(
            "Rate limit active: %s remaining. Injecting context.",
            format_remaining(remaining),
        )
        # Inject context to inform the user
        return {
            "context": (
                f"⚠️ RATE LIMIT ACTIVE\n"
                f"Provider is rate-limited. Wait {format_remaining(remaining)} before retrying.\n"
                f"Use /ratelimit status to check current state.\n"
                f"Use /ratelimit clear to reset (use with caution)."
            )
        }
    return None


def record_rate_limit_hook(
    session_id: str = "",
    user_message: str = "",
    assistant_response: str = "",
    model: str = "",
    **kwargs
) -> None:
    """Post-LLM call hook: record rate limit if 429 received."""
    # Check if rate limiter is enabled
    if not is_enabled():
        return

    # This would be called with error context from the LLM call
    error_context = kwargs.get("error_context")
    headers = kwargs.get("headers")
    if error_context or headers:
        # Use configured default cooldown
        default_cooldown = get_default_cooldown()
        record_rate_limit(headers=headers, error_context=error_context, default_cooldown=default_cooldown)
