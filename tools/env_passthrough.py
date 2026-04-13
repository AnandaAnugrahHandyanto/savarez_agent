"""Environment variable passthrough registry.

Skills that declare ``required_environment_variables`` in their frontmatter
need those vars available in sandboxed execution environments (execute_code,
terminal).  By default both sandboxes strip secrets from the child process
environment for security.  This module provides a session-scoped allowlist
so skill-declared vars (and user-configured overrides) pass through.

Two sources feed the allowlist:

1. **Skill declarations** — when a skill is loaded via ``skill_view``, its
   ``required_environment_variables`` are registered here automatically.
2. **User config** — ``terminal.env_passthrough`` in config.yaml lets users
   explicitly allowlist vars for non-skill use cases.

Both ``code_execution_tool.py`` and ``tools/environments/local.py`` consult
:func:`is_env_passthrough` before stripping a variable.
"""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# Session-scoped set of env var names that should pass through to sandboxes.
# Backed by ContextVar to prevent cross-session data bleed in the gateway pipeline.
_allowed_env_vars_var: ContextVar[set[str]] = ContextVar("_allowed_env_vars")


def _get_allowed() -> set[str]:
    """Get or create the allowed env vars set for the current context/session."""
    try:
        return _allowed_env_vars_var.get()
    except LookupError:
        val: set[str] = set()
        _allowed_env_vars_var.set(val)
        return val


# Cache for the config-based allowlist (loaded once per process).
_config_passthrough: frozenset[str] | None = None


# Environment variable names (or substrings) that must NEVER be allowed through
# to sandboxes, even if a skill declares them in required_environment_variables.
# A malicious skill could declare `required_environment_variables: [OPENROUTER_API_KEY]`
# to exfiltrate API keys into a sandbox where they can be read via os.environ.
# This blocklist mirrors the critical entries from local.py's provider env blocklist.
_NEVER_PASSTHROUGH_SUBSTRINGS = frozenset({
    "API_KEY", "API_SECRET", "ACCESS_TOKEN", "BOT_TOKEN",
    "OPENROUTER", "ANTHROPIC", "OPENAI",
    "TELEGRAM_BOT", "SLACK_BOT", "SLACK_APP",
    "DISCORD_BOT", "DISCORD_TOKEN",
    "SUDO_PASSWORD",
    "HASS_TOKEN",
    "GITHUB_TOKEN", "GH_TOKEN",
    "MODAL_TOKEN",
    "DAYTONA_API",
    "EMAIL_PASSWORD",
    "MATRIX_ACCESS_TOKEN", "MATRIX_PASSWORD",
    "SIGNAL_HTTP",
    "WHATSAPP_",
})


def _is_blocked_passthrough(name: str) -> bool:
    """Return True if *name* matches a never-passthrough pattern.

    Uses substring matching (case-insensitive) against known sensitive
    variable name fragments.  This is intentionally broad — false positives
    are preferable to credential leaks.
    """
    upper = name.upper()
    for substring in _NEVER_PASSTHROUGH_SUBSTRINGS:
        if substring in upper:
            return True
    return False


def register_env_passthrough(var_names: Iterable[str]) -> None:
    """Register environment variable names as allowed in sandboxed environments.

    Typically called when a skill declares ``required_environment_variables``.
    Variables matching known sensitive patterns (API keys, tokens, passwords)
    are silently rejected to prevent credential exfiltration via malicious skills.
    """
    for name in var_names:
        name = name.strip()
        if not name:
            continue
        if _is_blocked_passthrough(name):
            logger.warning(
                "env passthrough: BLOCKED '%s' — matches sensitive variable pattern. "
                "Skills cannot passthrough API keys, tokens, or credentials.",
                name,
            )
            continue
        _get_allowed().add(name)
        logger.debug("env passthrough: registered %s", name)


def _load_config_passthrough() -> frozenset[str]:
    """Load ``tools.env_passthrough`` from config.yaml (cached)."""
    global _config_passthrough
    if _config_passthrough is not None:
        return _config_passthrough

    result: set[str] = set()
    try:
        from hermes_cli.config import read_raw_config
        cfg = read_raw_config()
        passthrough = cfg.get("terminal", {}).get("env_passthrough")
        if isinstance(passthrough, list):
            for item in passthrough:
                if isinstance(item, str) and item.strip():
                    result.add(item.strip())
    except Exception as e:
        logger.debug("Could not read tools.env_passthrough from config: %s", e)

    _config_passthrough = frozenset(result)
    return _config_passthrough


def is_env_passthrough(var_name: str) -> bool:
    """Check whether *var_name* is allowed to pass through to sandboxes.

    Returns ``True`` if the variable was registered by a skill or listed in
    the user's ``tools.env_passthrough`` config.
    """
    if var_name in _get_allowed():
        return True
    return var_name in _load_config_passthrough()


def get_all_passthrough() -> frozenset[str]:
    """Return the union of skill-registered and config-based passthrough vars."""
    return frozenset(_get_allowed()) | _load_config_passthrough()


def clear_env_passthrough() -> None:
    """Reset the skill-scoped allowlist (e.g. on session reset)."""
    _get_allowed().clear()


