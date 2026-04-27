"""Auto-restart hook invoked when sensitive configuration changes.

The gateway only loads ``~/.hermes/.env`` and ``~/.hermes/config.yaml`` at
startup — it has no SIGHUP, file-watcher, or reload path. Without this
hook, ``hermes setup model`` and friends silently leave the running
gateway with stale credentials, which surfaces as 401/404 from upstream
inference providers until the user manually restarts.

The hook lives at the persistence layer (``save_env_value`` /
``set_config_value``) and is gated by a regex of credential-shaped keys,
so every command that mutates config benefits without per-callsite
plumbing.
"""

from __future__ import annotations

import os
import re
import threading
from typing import Optional


# Sensitive keys that, when changed, require the gateway to reload its
# inference / platform credentials. Centralised here so future providers
# can extend the list in one place.
_SENSITIVE_KEY_RE = re.compile(
    r"^("
    r"LLM_MODEL|HERMES_MODEL|HERMES_INFERENCE_PROVIDER"
    r"|.+_API_KEY"
    r"|.+_TOKEN"
    r"|OPENROUTER_.*"
    r"|OPENAI_BASE_URL|OPENAI_API_KEY"
    r"|ANTHROPIC_TOKEN|ANTHROPIC_API_KEY"
    r"|WHATSAPP_(MODE|ENABLED|ALLOWED_USERS)"
    r"|TELEGRAM_(BOT_TOKEN|ALLOWED_USERS|HOME_CHANNEL)"
    r"|DISCORD_.*"
    r"|SLACK_.*"
    r"|MATRIX_.*"
    r"|SIGNAL_.*"
    r"|MATTERMOST_.*"
    r"|EMAIL_.*"
    r"|TWILIO_.*"
    r"|DINGTALK_.*"
    r")$"
)

# Re-entrancy guard: when the hook itself ends up writing config (e.g. a
# downstream helper calls save_env_value), we don't want to recurse.
_in_hook = threading.local()


def is_sensitive_key(key: str) -> bool:
    """Return True when changes to ``key`` should trigger a gateway restart."""
    return bool(_SENSITIVE_KEY_RE.match(key.upper()))


def _opt_out_active(no_restart: bool) -> bool:
    if no_restart:
        return True
    raw = os.environ.get("HERMES_NO_AUTO_RESTART", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def maybe_restart_gateway(
    reason: str,
    no_restart: bool = False,
    quiet: bool = False,
) -> Optional[str]:
    """Restart the gateway if it is running and the user has not opted out.

    Returns one of the ``RestartResult.*`` constants from
    ``hermes_cli.gateway`` when a restart was attempted, or ``None`` when
    no action was taken (gateway not running, opt-out active, or
    re-entrant call).
    """
    if getattr(_in_hook, "active", False):
        return None
    if _opt_out_active(no_restart):
        if not quiet:
            print(f"ℹ Auto-restart skipped ({reason}). Run 'hermes gateway restart' to apply.")
        return None

    # Lazy imports keep this module import-cheap and avoid circulars with
    # hermes_cli.config / hermes_cli.gateway.
    try:
        from gateway.status import get_running_pid
        from hermes_cli.gateway import restart_gateway, RestartResult
    except Exception as exc:
        if not quiet:
            print(f"⚠ Could not check gateway status ({exc}); restart manually if needed.")
        return None

    if get_running_pid() is None:
        return RestartResult.NOT_RUNNING

    _in_hook.active = True
    try:
        return restart_gateway(reason=reason, quiet=quiet)
    finally:
        _in_hook.active = False
