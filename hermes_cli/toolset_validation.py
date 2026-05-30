"""Shared explicit-toolset validation — single source of truth.

A caller explicitly named toolsets; are they real? Enforces ONE fail-closed
contract everywhere (CLI, TUI gateway, cron, OpenAI-compatible API server):

    explicit, ALL unknown   -> hard fail   (raise / return error string)
    explicit, PARTIAL valid -> warn, continue with the valid subset
    omitted / all / *       -> None        (caller loads the full default set)

CRITICAL: nothing here calls sys.exit(). It returns or raises. SystemExit is a
BaseException and would escape `except Exception` daemon boundaries (e.g.
gateway/platforms/base.py:4056), killing a worker task. Only the interactive
CLI entry frame converts a failure into sys.exit(2).

Lifted from hermes_cli/oneshot.py (which self-discovers plugins + reads MCP
config), so it is safe to call from any lifecycle position.
"""

from __future__ import annotations

import sys
from typing import Callable

_ALL = {"all", "*"}


class InvalidToolsetError(ValueError):
    """Explicit, non-empty toolset request resolved to nothing valid."""

    def __init__(self, message: str, unknown: list[str] | None = None):
        super().__init__(message)
        self.unknown = unknown or []


def normalize_toolsets(toolsets: object = None) -> list[str] | None:
    if not toolsets:
        return None
    items = [toolsets] if isinstance(toolsets, str) else toolsets
    if not isinstance(items, (list, tuple)):
        items = [items]
    parts: list[str] = []
    for item in items:
        parts.extend(item.split(",") if isinstance(item, str) else [str(item)])
    return [p for p in (s.strip() for s in parts) if p] or None


def _default_warn(message: str) -> None:
    sys.stderr.write(message if message.endswith("\n") else message + "\n")


def validate_explicit_toolsets(
    toolsets: object = None,
    *,
    source: str = "hermes",
    warn: Callable[[str], None] | None = None,
) -> tuple[list[str] | None, str | None]:
    """Return (valid_toolsets, error_message).

    (valid, None) -> use this subset.
    (None,  None) -> nothing explicit, or `all`/`*` -> caller uses full default set.
    (None,  error)-> all-unknown; `error` is a ready-to-emit line (caller picks delivery).

    Partial-invalid notices go through `warn` (default: stderr). `source`
    prefixes every message (e.g. "hermes -z", "[tui]", "cron").
    """
    emit = warn or _default_warn
    normalized = normalize_toolsets(toolsets)
    if normalized is None:
        return None, None

    try:
        from toolsets import validate_toolset
    except Exception as exc:
        return None, f"{source}: failed to validate toolsets: {exc}"

    built_in = [name for name in normalized if validate_toolset(name)]
    unresolved = [name for name in normalized if name not in built_in]

    if unresolved:
        try:
            from hermes_cli.plugins import discover_plugins

            discover_plugins()
        except Exception:
            pass
        now_valid = [name for name in unresolved if validate_toolset(name)]
        built_in.extend(now_valid)
        unresolved = [name for name in unresolved if name not in now_valid]

    if any(name in _ALL for name in built_in):
        if ignored := [name for name in normalized if name not in _ALL]:
            emit(f"{source}: 'all' enables every toolset; ignoring: {', '.join(ignored)}")
        return None, None

    mcp_names: set[str] = set()
    mcp_disabled: set[str] = set()
    if unresolved:
        try:
            from hermes_cli.config import read_raw_config
            from hermes_cli.tools_config import _parse_enabled_flag

            servers = read_raw_config().get("mcp_servers")
            for name, cfg in (servers if isinstance(servers, dict) else {}).items():
                if isinstance(cfg, dict):
                    target = mcp_names if _parse_enabled_flag(cfg.get("enabled", True), default=True) else mcp_disabled
                    target.add(str(name))
        except Exception:
            mcp_names, mcp_disabled = set(), set()

    valid = built_in + [name for name in unresolved if name in mcp_names]
    disabled = [name for name in unresolved if name in mcp_disabled]
    unknown = [name for name in unresolved if name not in mcp_names and name not in mcp_disabled]

    if unknown:
        emit(f"{source}: ignoring unknown toolsets: {', '.join(unknown)}")
    if disabled:
        emit(f"{source}: ignoring disabled MCP servers (set enabled: true in config.yaml to use): {', '.join(disabled)}")

    if not valid:
        return None, f"{source}: no valid toolsets in request (unknown: {', '.join(unknown) or '-'})."
    return valid, None


def validate_explicit_toolsets_or_raise(
    toolsets: object = None,
    *,
    source: str = "hermes",
    warn: Callable[[str], None] | None = None,
) -> list[str] | None:
    """Daemon-side adapter: raise InvalidToolsetError on all-unknown, else return the subset (or None)."""
    valid, error = validate_explicit_toolsets(toolsets, source=source, warn=warn)
    if error:
        raise InvalidToolsetError(error, unknown=normalize_toolsets(toolsets))
    return valid
