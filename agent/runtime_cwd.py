"""Single source of truth for the agent working directory.

`TERMINAL_CWD` is the runtime carrier for the configured working directory
(design #19214/#19242: `terminal.cwd` is bridged once to `TERMINAL_CWD` at
gateway/cron startup). The local-CLI backend deliberately leaves it unset and
relies on the launch dir. Reading it in one place keeps the system prompt, the
tool surfaces, and context-file discovery agreeing on where the agent lives.

Gateway sessions may set `HERMES_SESSION_CWD` through `set_session_vars`;
that session-scoped override wins over the process-wide `TERMINAL_CWD`.
"""

import os
from pathlib import Path


def _session_cwd() -> str:
    try:
        from gateway.session_context import get_session_context_value
    except ImportError:
        return ""
    return get_session_context_value("HERMES_SESSION_CWD", "").strip()


def resolve_agent_cwd() -> Path:
    session_raw = _session_cwd()
    if session_raw:
        session_path = Path(session_raw).expanduser()
        if session_path.is_dir():
            return session_path

    raw = os.environ.get("TERMINAL_CWD", "").strip()
    if raw:
        p = Path(raw).expanduser()
        if p.is_dir():
            return p
    return Path(os.getcwd())


def resolve_context_cwd() -> Path | None:
    # None means "no configured cwd": build_context_files_prompt then falls back
    # to the launch dir (os.getcwd()) — correct for the local CLI. The gateway
    # avoids slurping its install dir by setting TERMINAL_CWD (see system_prompt.py).
    # No getcwd arm here: that fallback is owned by the caller, not this resolver.
    raw = _session_cwd() or os.environ.get("TERMINAL_CWD", "").strip()
    return Path(raw).expanduser() if raw else None
