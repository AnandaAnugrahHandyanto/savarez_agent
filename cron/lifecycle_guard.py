"""Gateway lifecycle guard for cron job creation (#30719).

An agent running inside a gateway can schedule a cron job that calls
``hermes gateway restart`` (or ``launchctl kickstart ai.hermes.gateway``
or ``systemctl restart hermes-gateway``).  When the cron fires, the
gateway dies, the supervisor (launchd KeepAlive / systemd Restart=)
revives it, auto-resume picks up the offending session, and the resumed
turn re-runs the same logic — a SIGTERM-respawn loop every ~10 seconds
until manually broken.

This module rejects cron job specs whose prompt or script contains a
direct shell-level gateway-lifecycle command.  It is intentionally
tight: only command shapes anchored on ``hermes\\s+gateway``,
``launchctl ... hermes[-.]gateway``, ``systemctl ... hermes[-.]gateway``,
or ``pkill`` against the same target trigger the block.  Natural-language
prompts that merely mention "gateway" and "restart" in unrelated
contexts (e.g. "Kong API gateway autoscaling and restart behavior") do
not, because the cron ``prompt`` is fed to a future LLM rather than to a
shell — over-broad regex on English text produces a high false-positive
rate without actually preventing the foot-gun.

The check is enforced at ``cron.jobs.create_job`` so it fires on every
job-creation path: the ``hermes cron create`` CLI subcommand AND the
agent's ``cronjob`` model tool.  Putting the guard only at the CLI
layer would leave the actual abuse path (the model tool) untouched.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


class GatewayLifecycleBlocked(ValueError):
    """Raised when a cron job spec contains a gateway-lifecycle command."""


# Shell-level command shapes that target the gateway lifecycle.
# Each branch is anchored on a concrete command identifier so the match
# can only fire on actual shell-command-shaped strings, not on prose.
_GATEWAY_LIFECYCLE_PATTERN = re.compile(
    r"(?i)"
    # Branch A: `hermes gateway restart|stop` — the canonical foot-gun.
    # `start` is intentionally excluded: starting a gateway from inside
    # a gateway is benign (a no-op or "already running" error) and a
    # legitimate cron job might start a sibling profile's gateway.
    r"(?:hermes\s+gateway\s+(?:restart|stop))"
    # Branch B: launchctl ops on a hermes-gateway label.  macOS launchd
    # labels follow `ai.hermes.gateway` / `hermes-gateway`.  Requiring
    # the gateway identifier prevents blocking unrelated hermes services
    # (e.g. `launchctl unload ai.hermes.update-checker.plist`).
    r"|(?:launchctl\s+(?:kickstart|unload|load|stop|restart)\b[^\n]*\bhermes[\.\-]?gateway)"
    # Branch C: systemctl ops on a hermes-gateway unit.
    r"|(?:systemctl\s+(?:restart|stop|start)\b[^\n]*\bhermes[\.\-]?gateway)"
    # Branch D: pkill / kill targeting the hermes gateway process.
    # Both token orders ("hermes ... gateway" and "gateway ... hermes")
    # because real reproductions show both.
    r"|(?:p?kill\b[^\n]*\bhermes\b[^\n]*\bgateway)"
    r"|(?:p?kill\b[^\n]*\bgateway\b[^\n]*\bhermes)"
)


def contains_gateway_lifecycle_command(text: str) -> bool:
    """Return True if *text* contains a gateway lifecycle command pattern."""
    if not text:
        return False
    return bool(_GATEWAY_LIFECYCLE_PATTERN.search(text))


def _read_script_for_scanning(script_path: str) -> str:
    """Read a script file for lifecycle-pattern scanning.

    Decodes with ``errors="replace"`` so that binary or non-UTF-8 content
    does not silently bypass the check (the previous text-mode read
    swallowed ``UnicodeDecodeError`` and proceeded with prompt-only
    scanning).  Returns empty string only when the file cannot be read
    at all.
    """
    try:
        return Path(script_path).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return ""


def check_gateway_lifecycle(
    prompt: Optional[str],
    script: Optional[str] = None,
) -> None:
    """Raise ``GatewayLifecycleBlocked`` if *prompt* or *script* contains
    a gateway-lifecycle command pattern.

    ``prompt`` is scanned directly.  ``script``, when supplied, is read
    from disk and concatenated for the scan.  Both are considered
    together so a job can't slip through by splitting the command across
    the prompt and the script.

    Callers should let the exception propagate when they want the
    create to fail with a ``ValueError``-shaped error (the agent's
    ``cronjob`` tool surfaces this as a tool error; the CLI prints it
    in red and exits 1).
    """
    combined = prompt or ""
    if script:
        script_text = _read_script_for_scanning(script)
        if script_text:
            combined = f"{combined}\n{script_text}"

    if contains_gateway_lifecycle_command(combined):
        raise GatewayLifecycleBlocked(
            "Cron job blocked: prompt or script contains a gateway "
            "lifecycle command (restart/stop/kill). This is blocked to "
            "prevent agent-driven SIGTERM-respawn loops under launchd/"
            "systemd supervision (#30719). Run `hermes gateway restart` "
            "from a shell outside the running gateway instead."
        )
