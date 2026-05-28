"""
Reusable Hermes profile context manager.

Provides :func:`profile_context` — a context manager that temporarily
switches the process to a named Hermes profile, loading its .env,
config, and home directory. Used by the cron scheduler (per-job profile
overrides) and the messaging gateway (per-user profile routing).

Thread-safety: snapshots and restores os.environ via delta-based restore.
Not safe for concurrent use within the same process; callers must
serialise (cron scheduler does this, gateway runs one agent per session).
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@contextmanager
def profile_context(profile_name: str, label: str = ""):
    """Temporarily switch the process to a named Hermes profile.

    While active:
    - ``get_hermes_home()`` returns the profile directory
    - ``os.environ`` reflects the profile's .env (loaded on top of the
      current environment)
    - .env loading uses ``load_hermes_dotenv`` so it honours the same
      override / project-env rules as the rest of the Hermes codebase

    On exit the previous ``HERMES_HOME`` override and environment are
    restored exactly.  New keys added by the profile .env are removed;
    changed keys are reverted to their prior values.

    Parameters
    ----------
    profile_name:
        Canonical profile name (e.g. ``"automations"``).  Passed through
        ``normalize_profile_name`` so casing / whitespace is forgiving.
    label:
        Human-readable context tag for log messages (e.g. a job ID, user
        ID, or session key).  If empty, profile_name is used.

    Yields
    ------
    str | None
        The normalized profile name on success, or ``None`` if the
        profile could not be resolved (caller should fall back to the
        default profile).
    """
    from hermes_cli.profiles import normalize_profile_name, resolve_profile_env
    from hermes_constants import (
        reset_hermes_home_override,
        set_hermes_home_override,
    )

    raw = str(profile_name or "").strip()
    if not raw:
        yield None
        return

    tag = label or raw
    normalized = normalize_profile_name(raw)

    try:
        profile_home = Path(resolve_profile_env(normalized)).resolve()
    except (FileNotFoundError, ValueError) as exc:
        logger.warning(
            "Profile context '%s': profile %r not valid (%s) — "
            "falling back to default",
            tag, raw, exc,
        )
        yield None
        return

    env_snapshot = os.environ.copy()
    override_token = None

    try:
        override_token = set_hermes_home_override(profile_home)
        # Load the profile's .env into the current process environment.
        # This surfaces API keys, tokens, home-channel vars, etc. so
        # downstream code that reads os.environ sees the right values.
        from hermes_cli.env_loader import load_hermes_dotenv
        load_hermes_dotenv(
            hermes_home=profile_home,
            project_env=None,  # don't re-load project .env
        )

        logger.info(
            "Profile context '%s': using profile '%s' (%s)",
            tag, normalized, profile_home,
        )
        yield normalized
    finally:
        if override_token is not None:
            reset_hermes_home_override(override_token)
        # Delta-based restore so concurrent threads are not disrupted.
        added = set(os.environ.keys()) - set(env_snapshot.keys())
        for k in added:
            os.environ.pop(k, None)
        for k, v in env_snapshot.items():
            if os.environ.get(k) != v:
                os.environ[k] = v


def resolve_user_profile(platform: str, user_id: Optional[str]) -> Optional[str]:
    """Resolve a platform user ID to a Hermes profile name.

    Reads ``{PLATFORM}_USER_PROFILE_MAP`` from the environment.
    Format: ``user_id1:profile1,user_id2:profile2,...``

    Returns the profile name if the user is mapped, or ``None``.
    """
    if not user_id or not platform:
        return None

    env_var = f"{platform.upper()}_USER_PROFILE_MAP"
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return None

    mappings = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        uid, profile = pair.split(":", 1)
        mappings[uid.strip()] = profile.strip()

    return mappings.get(user_id)
