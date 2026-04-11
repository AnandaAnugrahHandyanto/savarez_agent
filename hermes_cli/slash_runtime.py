"""Shared slash-command inventory and resolution helpers.

This module centralizes command-family resolution for built-ins, skills,
quick commands, and plugin slash commands while preserving the current
surface-specific behavior in CLI and gateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from hermes_cli.commands import (
    COMMANDS,
    COMMAND_REGISTRY,
    _is_gateway_available,
    _resolve_config_gates,
    resolve_command,
)

SlashCommandKind = Literal["builtin", "quick", "plugin", "skill"]
SlashResolutionStatus = Literal["matched", "ambiguous", "unknown"]

_EXACT_KIND_PRIORITY: dict[SlashCommandKind, int] = {
    "builtin": 0,
    "quick": 1,
    "skill": 2,
    "plugin": 3,
}


@dataclass(frozen=True)
class SlashCommandEntry:
    kind: SlashCommandKind
    slash_name: str
    canonical_name: str
    description: str = ""
    payload: Any = None
    allow_prefix: bool = False

    @property
    def bare_name(self) -> str:
        return self.slash_name.lstrip("/")


@dataclass(frozen=True)
class SlashResolution:
    status: SlashResolutionStatus
    entry: SlashCommandEntry | None
    typed_name: str
    args: str
    matches: tuple[str, ...] = ()


def _normalize_args(command_text: str) -> tuple[str, str]:
    stripped = (command_text or "").strip()
    if not stripped:
        return "", ""
    parts = stripped.split(None, 1)
    raw_base = parts[0]
    args = parts[1].strip() if len(parts) > 1 else ""
    return raw_base, args


def _quick_commands_from_config(config: Any) -> dict[str, dict[str, Any]]:
    if config is None:
        return {}
    if isinstance(config, dict):
        quick = config.get("quick_commands", {}) or {}
    else:
        quick = getattr(config, "quick_commands", {}) or {}
    return quick if isinstance(quick, dict) else {}


def _iter_cli_builtin_entries() -> list[SlashCommandEntry]:
    entries: list[SlashCommandEntry] = []
    for cmd in COMMAND_REGISTRY:
        if cmd.gateway_only:
            continue
        desc = COMMANDS.get(f"/{cmd.name}", cmd.description)
        entries.append(
            SlashCommandEntry(
                kind="builtin",
                slash_name=f"/{cmd.name}",
                canonical_name=cmd.name,
                description=desc,
                allow_prefix=True,
            )
        )
        for alias in cmd.aliases:
            entries.append(
                SlashCommandEntry(
                    kind="builtin",
                    slash_name=f"/{alias}",
                    canonical_name=cmd.name,
                    description=COMMANDS.get(f"/{alias}", desc),
                    allow_prefix=True,
                )
            )
    return entries


def _iter_gateway_builtin_entries(config: Any = None) -> list[SlashCommandEntry]:
    entries: list[SlashCommandEntry] = []
    overrides = _resolve_config_gates(config)
    for cmd in COMMAND_REGISTRY:
        if not _is_gateway_available(cmd, overrides):
            continue
        entries.append(
            SlashCommandEntry(
                kind="builtin",
                slash_name=f"/{cmd.name}",
                canonical_name=cmd.name,
                description=cmd.description,
            )
        )
        for alias in cmd.aliases:
            entries.append(
                SlashCommandEntry(
                    kind="builtin",
                    slash_name=f"/{alias}",
                    canonical_name=cmd.name,
                    description=cmd.description,
                )
            )
    return entries


def _iter_skill_entries(
    skill_commands: Mapping[str, dict[str, Any]] | None,
    *,
    allow_prefix: bool,
    include_gateway_underscore_aliases: bool,
) -> list[SlashCommandEntry]:
    entries: list[SlashCommandEntry] = []
    if not skill_commands:
        return entries
    for cmd_key, info in skill_commands.items():
        desc = str(info.get("description", "") or "Skill command")
        entries.append(
            SlashCommandEntry(
                kind="skill",
                slash_name=cmd_key,
                canonical_name=cmd_key.lstrip("/"),
                description=desc,
                payload=info,
                allow_prefix=allow_prefix,
            )
        )
        if include_gateway_underscore_aliases and "-" in cmd_key:
            entries.append(
                SlashCommandEntry(
                    kind="skill",
                    slash_name=cmd_key.replace("-", "_"),
                    canonical_name=cmd_key.lstrip("/"),
                    description=desc,
                    payload=info,
                )
            )
    return entries


def _iter_quick_entries(quick_commands: Mapping[str, dict[str, Any]]) -> list[SlashCommandEntry]:
    return [
        SlashCommandEntry(
            kind="quick",
            slash_name=f"/{name}",
            canonical_name=name,
            description=str(spec.get("description", "") or "Quick command"),
            payload=spec,
        )
        for name, spec in quick_commands.items()
        if isinstance(spec, dict)
    ]


def _iter_plugin_entries(
    plugin_commands: Mapping[str, dict[str, Any]] | None,
    *,
    include_gateway_underscore_aliases: bool,
) -> list[SlashCommandEntry]:
    entries: list[SlashCommandEntry] = []
    if not plugin_commands:
        return entries
    for name, spec in plugin_commands.items():
        desc = str(spec.get("description", "") or "Plugin command")
        entries.append(
            SlashCommandEntry(
                kind="plugin",
                slash_name=f"/{name}",
                canonical_name=name,
                description=desc,
                payload=spec,
            )
        )
        if include_gateway_underscore_aliases and "-" in name:
            entries.append(
                SlashCommandEntry(
                    kind="plugin",
                    slash_name=f"/{name.replace('-', '_')}",
                    canonical_name=name,
                    description=desc,
                    payload=spec,
                )
            )
    return entries


def _pick_exact(entries: list[SlashCommandEntry], slash_name: str) -> SlashCommandEntry | None:
    exact = [entry for entry in entries if entry.slash_name == slash_name]
    if not exact:
        return None
    exact.sort(key=lambda entry: (_EXACT_KIND_PRIORITY[entry.kind], entry.slash_name))
    return exact[0]


def _prefix_resolution(slash_name: str, entries: list[SlashCommandEntry]) -> SlashResolution:
    prefix_entries = [entry for entry in entries if entry.allow_prefix]
    matches = [entry for entry in prefix_entries if entry.slash_name.startswith(slash_name)]
    if not matches:
        return SlashResolution(status="unknown", entry=None, typed_name=slash_name, args="")

    exact = _pick_exact(matches, slash_name)
    if exact is not None:
        return SlashResolution(status="matched", entry=exact, typed_name=slash_name, args="")

    min_len = min(len(entry.slash_name) for entry in matches)
    shortest = [entry for entry in matches if len(entry.slash_name) == min_len]
    if len(shortest) == 1:
        return SlashResolution(status="matched", entry=shortest[0], typed_name=slash_name, args="")

    return SlashResolution(
        status="ambiguous",
        entry=None,
        typed_name=slash_name,
        args="",
        matches=tuple(sorted({entry.slash_name for entry in matches})),
    )


def get_plugin_command_specs() -> dict[str, dict[str, Any]]:
    try:
        from hermes_cli.plugins import get_plugin_commands

        specs = get_plugin_commands()
        return specs if isinstance(specs, dict) else {}
    except Exception:
        return {}


def resolve_cli_slash_command(
    command_text: str,
    *,
    config: Any,
    skill_commands: Mapping[str, dict[str, Any]] | None,
    plugin_commands: Mapping[str, dict[str, Any]] | None = None,
) -> SlashResolution:
    raw_base, args = _normalize_args(command_text)
    slash_name = raw_base.lower()
    if not slash_name.startswith("/"):
        return SlashResolution(status="unknown", entry=None, typed_name=slash_name, args=args)

    builtin = resolve_command(slash_name)
    if builtin is not None and not builtin.gateway_only:
        desc = COMMANDS.get(f"/{builtin.name}", builtin.description)
        return SlashResolution(
            status="matched",
            entry=SlashCommandEntry(
                kind="builtin",
                slash_name=f"/{builtin.name}",
                canonical_name=builtin.name,
                description=desc,
                allow_prefix=True,
            ),
            typed_name=slash_name,
            args=args,
        )

    quick_commands = _quick_commands_from_config(config)
    entries = (
        _iter_cli_builtin_entries()
        + _iter_quick_entries(quick_commands)
        + _iter_plugin_entries(plugin_commands, include_gateway_underscore_aliases=False)
        + _iter_skill_entries(
            skill_commands,
            allow_prefix=True,
            include_gateway_underscore_aliases=False,
        )
    )

    exact = _pick_exact(entries, slash_name)
    if exact is not None:
        return SlashResolution(status="matched", entry=exact, typed_name=slash_name, args=args)

    prefix = _prefix_resolution(slash_name, entries)
    return SlashResolution(
        status=prefix.status,
        entry=prefix.entry,
        typed_name=slash_name,
        args=args,
        matches=prefix.matches,
    )


def resolve_gateway_slash_command(
    command_name: str,
    *,
    config: Any,
    skill_commands: Mapping[str, dict[str, Any]] | None,
    plugin_commands: Mapping[str, dict[str, Any]] | None = None,
) -> SlashResolution:
    bare_name = (command_name or "").strip().lower()
    slash_name = f"/{bare_name}" if bare_name else ""
    if not bare_name:
        return SlashResolution(status="unknown", entry=None, typed_name=slash_name, args="")

    builtin = resolve_command(slash_name)
    if builtin is not None and (not builtin.cli_only or builtin.gateway_config_gate):
        return SlashResolution(
            status="matched",
            entry=SlashCommandEntry(
                kind="builtin",
                slash_name=f"/{builtin.name}",
                canonical_name=builtin.name,
                description=builtin.description,
            ),
            typed_name=slash_name,
            args="",
        )

    quick_commands = _quick_commands_from_config(config)
    entries = (
        _iter_gateway_builtin_entries(config)
        + _iter_quick_entries(quick_commands)
        + _iter_plugin_entries(plugin_commands, include_gateway_underscore_aliases=True)
        + _iter_skill_entries(
            skill_commands,
            allow_prefix=False,
            include_gateway_underscore_aliases=True,
        )
    )

    exact = _pick_exact(entries, slash_name)
    if exact is None:
        return SlashResolution(status="unknown", entry=None, typed_name=slash_name, args="")
    return SlashResolution(status="matched", entry=exact, typed_name=slash_name, args="")
