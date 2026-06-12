"""`hermes composio` subcommands: setup, status, connect, disconnect, mcp.

These are the human-facing entry points.  Behind the scenes they
write to ``~/.hermes/composio.json`` (config) and ``~/.hermes/config.yaml``
(``mcp_servers`` entry pointing at our stdio server).

Surface area
------------
- ``hermes composio setup``        — interactive wizard (API key, user_id)
- ``hermes composio status``       — list config + connected accounts
- ``hermes composio connect <kit>`` — start an OAuth flow (returns URL)
- ``hermes composio disconnect <toolkit>``
                                     — remove an MCP tool from the catalog
                                       (does NOT revoke the OAuth grant;
                                       use the provider's UI for that)
- ``hermes composio mcp install``   — write the MCP server entry into
                                       config.yaml so the agent picks it up
- ``hermes composio mcp uninstall`` — remove the entry
- ``hermes composio tools``         — print the live catalog (calls
                                       ``mcp_server --print-catalog``)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.config import read_raw_config, save_config
from hermes_constants import get_hermes_home

from plugins.integration.composio.client import (
    ComposioClient,
    ComposioConfig,
    ComposioError,
    list_accounts_sync,
    list_tools_sync,
    rank_tools,
)

logger = logging.getLogger(__name__)


MCP_SERVER_NAME = "composio"  # the key written into mcp_servers
MCP_PYTHON_MODULE = "plugins.integration.composio.mcp_server"


# ---------------------------------------------------------------------------
# `setup` — interactive wizard
# ---------------------------------------------------------------------------


def cmd_setup(args: argparse.Namespace) -> int:
    """Interactive or scripted setup.

    In non-interactive mode (``--api-key``, ``--user-id`` flags),
    values are taken from flags.  Otherwise we prompt via stdin.

    Side effects:
      * Writes ``~/.hermes/composio.json`` (api key + toolkit policy).
      * If ``--enable`` (default) is passed, also adds the plugin
        to ``plugins.enabled`` in ``~/.hermes/config.yaml`` so the
        loader activates it on next session start.  Use
        ``--no-enable`` to skip.
    """
    config = ComposioConfig.from_global_config()

    if args.api_key:
        config.api_key = args.api_key
    elif not config.api_key and not args.non_interactive:
        config.api_key = _prompt_secret("Composio API key")

    if args.user_id:
        config.user_id = args.user_id

    if args.base_url:
        config.base_url = args.base_url

    if args.max_tools_per_toolkit is not None:
        config.max_tools_per_toolkit = args.max_tools_per_toolkit

    if args.allowed_toolkits is not None:
        config.allowed_toolkits = list(args.allowed_toolkits)

    if args.allowlist_only is not None:
        config.allowlist_only = bool(args.allowlist_only)

    if not config.api_key:
        print(
            "ERROR: API key is required. Pass --api-key or run interactively.",
            file=sys.stderr,
        )
        return 2

    config.save()
    print(f"Saved config to {config.config_path}")
    print(json.dumps(config.as_dict_safe(), indent=2))

    if getattr(args, "enable", False):
        if _enable_plugin_in_config():
            print("Enabled 'integration/composio' in plugins.enabled.")
            print("Restart the agent to load the plugin.")
    return 0


def _enable_plugin_in_config() -> bool:
    """Add 'integration/composio' to plugins.enabled.  Returns True if changed."""
    cfg = read_raw_config() or {}
    enabled = cfg.get("plugins", {}).get("enabled")
    if not isinstance(enabled, list):
        enabled = []
    if "integration/composio" in enabled:
        return False
    enabled.append("integration/composio")
    cfg.setdefault("plugins", {})["enabled"] = enabled
    save_config(cfg)
    return True


def _prompt_secret(prompt: str) -> str:
    """Read a secret from stdin, with a fallback for non-tty environments."""
    import getpass
    try:
        return getpass.getpass(f"{prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


# ---------------------------------------------------------------------------
# `status`
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    config = ComposioConfig.from_global_config()
    print("Composio configuration:")
    print(json.dumps(config.as_dict_safe(), indent=2))

    if not config.is_configured():
        print("\nAPI key not set — run `hermes composio setup` first.")
        return 1

    print("\nConnected accounts:")
    try:
        accounts = list_accounts_sync(config)
    except ComposioError as exc:
        print(f"  ERROR: {exc}")
        return 2
    except Exception as exc:  # network etc
        print(f"  ERROR: {exc!r}")
        return 2

    if not accounts:
        print("  (none — run `hermes composio connect <toolkit>` to add one)")
    else:
        for a in accounts:
            label = a.email or a.id
            print(f"  - {a.toolkit:<20} {a.id}  {label}  [{a.status}]")

    print()
    print("MCP server entry:")
    mcp_cfg = _read_mcp_config()
    if MCP_SERVER_NAME in mcp_cfg:
        print(f"  installed as mcp_servers.{MCP_SERVER_NAME}")
    else:
        print(f"  not installed — run `hermes composio mcp install`")
    return 0


# ---------------------------------------------------------------------------
# `connect` — start an OAuth flow
# ---------------------------------------------------------------------------


def cmd_connect(args: argparse.Namespace) -> int:
    config = ComposioConfig.from_global_config()
    if not config.is_configured():
        print("ERROR: run `hermes composio setup` first.", file=sys.stderr)
        return 2

    import asyncio

    async def _go() -> Dict[str, Any]:
        async with ComposioClient(config) as client:
            return await client.initiate_oauth(args.toolkit)

    try:
        result = asyncio.run(_go())
    except ComposioError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    redirect = (
        result.get("redirect_url")
        or result.get("url")
        or result.get("authorization_url")
    )
    if not redirect:
        print("Composio response did not contain a redirect URL:")
        print(json.dumps(result, indent=2))
        return 2

    print(f"Open this URL to authorize {args.toolkit}:")
    print(f"  {redirect}")
    print(
        "\nAfter approval, Composio will store the connection. "
        "Run `hermes composio status` to confirm."
    )
    return 0


# ---------------------------------------------------------------------------
# `disconnect` — remove from MCP catalog (NOT OAuth revoke)
# ---------------------------------------------------------------------------


def cmd_disconnect(args: argparse.Namespace) -> int:
    config = ComposioConfig.from_global_config()
    new_list = [t for t in config.allowed_toolkits if t != args.toolkit]
    if len(new_list) == len(config.allowed_toolkits):
        print(
            f"Note: {args.toolkit!r} was not in allowed_toolkits. "
            "If you meant to revoke the OAuth grant, do it from the "
            "Composio dashboard or the provider's app settings.",
            file=sys.stderr,
        )
    config.allowed_toolkits = new_list
    if args.toolkit not in new_list and not new_list:
        # If user removed the last toolkit from the whitelist, drop
        # allowlist_only too so the catalog re-expands.
        config.allowlist_only = False
    config.save()
    print(f"Updated allowed_toolkits: {new_list}")
    return 0


# ---------------------------------------------------------------------------
# `mcp install` / `mcp uninstall`
# ---------------------------------------------------------------------------


def _python_executable() -> str:
    """Find the Python interpreter that should run the MCP server.

    Prefers ``sys.executable`` (the interpreter running the CLI).
    Falls back to ``python3`` on PATH.
    """
    exe = sys.executable or "python3"
    return exe


def _read_mcp_config() -> Dict[str, Any]:
    """Return the ``mcp_servers`` section of ~/.hermes/config.yaml."""
    cfg = read_raw_config() or {}
    servers = cfg.get("mcp_servers")
    return servers if isinstance(servers, dict) else {}


def cmd_mcp_install(args: argparse.Namespace) -> int:
    """Write the MCP server entry into config.yaml so the agent
    auto-discovers it on next session start.

    The entry uses stdio transport (the simplest, most reliable
    option) and a generated module invocation.  No subprocess
    is started here — discovery happens lazily in
    ``hermes_cli/mcp_startup.py`` once the agent enables the
    ``mcp`` toolset.
    """
    cfg = read_raw_config() or {}
    servers = cfg.get("mcp_servers")
    if not isinstance(servers, dict):
        servers = {}

    python = _python_executable()
    # ``-m plugins.integration.composio.mcp_server`` lets us reuse
    # the same import path the plugin's own __init__.py uses, so
    # PYTHONPATH stays consistent across both code paths.
    servers[MCP_SERVER_NAME] = {
        "command": python,
        "args": ["-m", MCP_PYTHON_MODULE],
        "env": {},  # inherits; api_key is read from ~/.hermes/composio.json
        "timeout": 120,
        "connect_timeout": 30,
    }
    cfg["mcp_servers"] = servers
    save_config(cfg)
    print(
        f"Installed MCP server 'mcp_servers.{MCP_SERVER_NAME}' "
        f"in {get_hermes_home() / 'config.yaml'}"
    )
    print(
        "Restart the agent (or /reload-mcp in CLI) for the new server "
        "to be picked up."
    )
    return 0


def cmd_mcp_uninstall(args: argparse.Namespace) -> int:
    cfg = read_raw_config() or {}
    servers = cfg.get("mcp_servers")
    if not isinstance(servers, dict) or MCP_SERVER_NAME not in servers:
        print(f"MCP server {MCP_SERVER_NAME!r} was not installed.")
        return 0
    servers.pop(MCP_SERVER_NAME, None)
    cfg["mcp_servers"] = servers
    save_config(cfg)
    print(f"Removed MCP server 'mcp_servers.{MCP_SERVER_NAME}'.")
    return 0


# ---------------------------------------------------------------------------
# `tools` — print the live catalog by invoking mcp_server --print-catalog
# ---------------------------------------------------------------------------


def cmd_tools(args: argparse.Namespace) -> int:
    """Spawn the MCP server once with ``--print-catalog`` and print JSON.

    This is a convenience command so users don't need to know the
    internal module path.  We use subprocess + the same Python so
    the import path resolves identically.
    """
    python = _python_executable()
    cmd = [python, "-m", MCP_PYTHON_MODULE, "--print-catalog"]
    if args.log_level:
        cmd.extend(["--log-level", args.log_level])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        print("ERROR: catalog build timed out after 60s", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hermes composio",
        description="Composio integration plugin — 1000+ OAuth apps via MCP.",
    )
    sub = p.add_subparsers(dest="subcommand", required=True)

    # setup
    s = sub.add_parser("setup", help="Configure API key and user_id.")
    s.add_argument("--api-key", help="Composio API key (skip prompt).")
    s.add_argument("--user-id", help="Composio user/connection owner ID.")
    s.add_argument("--base-url", help="Override backend base URL.")
    s.add_argument("--max-tools-per-toolkit", type=int)
    s.add_argument(
        "--allowed-toolkits", nargs="*", help="Whitelist of toolkit slugs."
    )
    s.add_argument(
        "--allowlist-only", dest="allowlist_only", action="store_true", default=None,
        help="Only expose whitelisted toolkits.",
    )
    s.add_argument(
        "--no-allowlist-only", dest="allowlist_only", action="store_false", default=None,
    )
    s.add_argument(
        "--non-interactive", action="store_true",
        help="Fail instead of prompting for missing values.",
    )
    s.add_argument(
        "--enable", dest="enable", action="store_true", default=True,
        help="Add 'integration/composio' to plugins.enabled in config.yaml (default).",
    )
    s.add_argument(
        "--no-enable", dest="enable", action="store_false",
        help="Skip enabling the plugin in config.yaml.",
    )
    s.set_defaults(func=cmd_setup)

    # status
    s = sub.add_parser("status", help="Show config + connected accounts.")
    s.set_defaults(func=cmd_status)

    # connect
    s = sub.add_parser(
        "connect", help="Start an OAuth flow for a toolkit (prints the URL)."
    )
    s.add_argument("toolkit", help="Toolkit slug, e.g. gmail, github, slack.")
    s.set_defaults(func=cmd_connect)

    # disconnect
    s = sub.add_parser(
        "disconnect",
        help="Remove a toolkit from the local allowlist (does NOT revoke OAuth).",
    )
    s.add_argument("toolkit", help="Toolkit slug to remove from allowed_toolkits.")
    s.set_defaults(func=cmd_disconnect)

    # mcp subcommand
    m = sub.add_parser("mcp", help="Install/uninstall the MCP server entry.")
    m_sub = m.add_subparsers(dest="mcp_action", required=True)
    mi = m_sub.add_parser("install", help="Add the MCP server to config.yaml.")
    mi.set_defaults(func=cmd_mcp_install)
    mu = m_sub.add_parser("uninstall", help="Remove the MCP server from config.yaml.")
    mu.set_defaults(func=cmd_mcp_uninstall)

    # tools
    t = sub.add_parser("tools", help="Print the live tool catalog as JSON.")
    t.add_argument("--log-level", default="WARNING")
    t.set_defaults(func=cmd_tools)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
