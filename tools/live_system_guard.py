"""Runtime guard for commands that can kill the live Hermes gateway.

This is intentionally narrower than the dangerous-command approval layer:
it only blocks self-management commands while the current Python process is
running inside a Hermes gateway service. Approvals/yolo are not bypasses here;
the safe path is to schedule a restart outside the gateway cgroup.
"""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Iterable

from utils import is_truthy_value

_FORCE_ENV = "HERMES_LIVE_SYSTEM_GUARD"
_DISABLE_ENV = "HERMES_DISABLE_LIVE_SYSTEM_GUARD"

_GATEWAY_TOKENS = (
    "hermes-gateway",
    "hermes.service",
    "hermes_cli.main gateway",
    "hermes_cli/main.py gateway",
    "gateway/run.py",
)

_SYSTEMCTL_MUTATING_VERBS = {
    "restart",
    "try-restart",
    "reload-or-restart",
    "try-reload-or-restart",
    "stop",
    "kill",
    "reload",
}

_SERVICE_MUTATING_VERBS = {
    "restart",
    "stop",
    "force-stop",
    "kill",
    "reload",
}

_PROCESS_KILLERS = {"pkill", "killall", "taskkill", "skill", "fuser"}


def _cmd_to_string(command) -> str:
    if command is None:
        return ""
    if isinstance(command, (bytes, bytearray)):
        return bytes(command).decode(errors="replace")
    if isinstance(command, str):
        return command
    if isinstance(command, (list, tuple)):
        return " ".join(str(part) for part in command)
    return str(command)


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _basenames(tokens: Iterable[str]) -> list[str]:
    return [token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] for token in tokens]


def _mentions_gateway(command: str) -> bool:
    lower = command.lower()
    return any(token in lower for token in _GATEWAY_TOKENS)


def _read_proc_text(path: str) -> str:
    try:
        return Path(path).read_text(errors="replace")
    except Exception:
        return ""


def running_inside_gateway_service() -> bool:
    """Return True when this process appears to be the live gateway service."""
    if is_truthy_value(os.getenv(_DISABLE_ENV, "")):
        return False
    if is_truthy_value(os.getenv(_FORCE_ENV, "")):
        return True

    cgroup = _read_proc_text("/proc/self/cgroup").lower()
    if "hermes-gateway" in cgroup:
        return True

    cmdline = _read_proc_text("/proc/self/cmdline").replace("\x00", " ").lower()
    if "hermes" in cmdline and "gateway" in cmdline:
        return True

    # systemd sets INVOCATION_ID on services. Treat it as gateway-only when the
    # gateway session marker is also present, to avoid catching unrelated units.
    if os.getenv("INVOCATION_ID") and (
        os.getenv("HERMES_GATEWAY_SESSION")
        or os.getenv("HERMES_SESSION_PLATFORM")
    ):
        return True

    return False


def _shell_script_args(tokens: list[str]) -> Iterable[str]:
    names = _basenames(token.lower() for token in tokens)
    for index, name in enumerate(names):
        if name not in {"bash", "sh", "zsh", "ksh"}:
            continue
        for opt_index in range(index + 1, len(tokens)):
            opt = tokens[opt_index]
            if not opt.startswith("-"):
                continue
            if "c" in opt and opt_index + 1 < len(tokens):
                yield tokens[opt_index + 1]
                break


def _matches_systemctl_gateway_mutation(
    command: str,
    *,
    _depth: int = 0,
) -> str | None:
    if "systemctl" not in command.lower() or not _mentions_gateway(command):
        return None
    tokens = _tokens(command.lower())
    names = _basenames(tokens)
    if "systemctl" not in names:
        if _depth < 2:
            for script in _shell_script_args(tokens):
                nested = _matches_systemctl_gateway_mutation(
                    script,
                    _depth=_depth + 1,
                )
                if nested:
                    return nested
        return None
    for verb in _SYSTEMCTL_MUTATING_VERBS:
        if verb in names:
            return f"systemctl {verb} targeting hermes-gateway"
    return None


def _matches_service_gateway_mutation(command: str) -> str | None:
    names = _basenames(_tokens(command.lower()))
    if "service" in names and "hermes-gateway" in names:
        for verb in _SERVICE_MUTATING_VERBS:
            if verb in names:
                return f"service hermes-gateway {verb}"

    lower = command.lower()
    if re.search(r"(?:^|\s)/etc/init\.d/hermes-gateway\b", lower):
        for verb in _SERVICE_MUTATING_VERBS:
            if re.search(rf"\b{re.escape(verb)}\b", lower):
                return f"/etc/init.d/hermes-gateway {verb}"
    return None


def _matches_hermes_gateway_cli_mutation(command: str) -> str | None:
    names = _basenames(_tokens(command.lower()))
    if "hermes" in names and "gateway" in names:
        for verb in ("restart", "stop"):
            if verb in names:
                return f"hermes gateway {verb}"
    return None


def _matches_process_killer(command: str) -> str | None:
    names = _basenames(_tokens(command.lower()))
    if not any(name in _PROCESS_KILLERS for name in names):
        return None
    lower = command.lower()
    if "hermes" in lower or "gateway" in lower or ("python" in lower and "-f" in names):
        return "process-killer command targeting hermes/python"
    return None


def _match_live_gateway_mutation(command: str) -> str | None:
    return (
        _matches_systemctl_gateway_mutation(command)
        or _matches_service_gateway_mutation(command)
        or _matches_hermes_gateway_cli_mutation(command)
        or _matches_process_killer(command)
    )


def _match_live_gateway_mutation_in_code(code: str) -> str | None:
    lower = _cmd_to_string(code).lower()
    if "systemctl" in lower and _mentions_gateway(lower):
        for verb in _SYSTEMCTL_MUTATING_VERBS:
            if re.search(rf"\b{re.escape(verb)}\b", lower):
                return f"systemctl {verb} targeting hermes-gateway"
    if re.search(r"\bservice\b", lower) and "hermes-gateway" in lower:
        for verb in _SERVICE_MUTATING_VERBS:
            if re.search(rf"\b{re.escape(verb)}\b", lower):
                return f"service hermes-gateway {verb}"
    if re.search(r"\b(pkill|killall|taskkill|skill|fuser)\b", lower):
        if "hermes" in lower or "gateway" in lower or "python" in lower:
            return "process-killer command targeting hermes/python"
    return None


def _blocked_result(reason: str, message: str) -> dict:
    return {
        "approved": False,
        "status": "blocked",
        "pattern_key": "live_gateway_system_guard",
        "description": reason,
        "message": message,
    }


def check_live_gateway_system_command(command: str) -> dict | None:
    """Return a blocked-result dict if *command* would self-kill the gateway."""
    command_text = _cmd_to_string(command)
    reason = _match_live_gateway_mutation(command_text)
    if not reason or not running_inside_gateway_service():
        return None
    return _blocked_result(
        reason,
        (
            "BLOCKED: this command would mutate the live Hermes gateway from "
            "inside hermes-gateway.service. systemd can kill the child command "
            "with the gateway cgroup and leave the service stopped. Use "
            "/usr/local/sbin/hermes-gateway-safe-restart for restarts, or run "
            "stop/kill from an external shell."
        ),
    )


def check_live_gateway_system_code(code: str) -> dict | None:
    """Static preflight for execute_code scripts before local Python starts."""
    code_text = _cmd_to_string(code)
    reason = _match_live_gateway_mutation_in_code(code_text)
    if not reason or not running_inside_gateway_service():
        return None
    return _blocked_result(
        reason,
        (
            "BLOCKED: this execute_code script appears to mutate the live "
            "Hermes gateway from inside hermes-gateway.service. systemd can "
            "kill the child command with the gateway cgroup and leave the "
            "service stopped. Use /usr/local/sbin/hermes-gateway-safe-restart "
            "for restarts, or run stop/kill from an external shell."
        ),
    )
