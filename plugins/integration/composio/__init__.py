"""Composio integration plugin — entry point.

Exposes 1000+ OAuth-backed apps (Gmail, GitHub, Slack, Notion,
Linear, Jira, ...) to Hermes as a local MCP server.  Architecture
and design notes: see ``mcp_server.py`` module docstring.

This module is what the plugin loader sees at import time.
Following the convention in ``plugins/memory/honcho/__init__.py``,
we:

1. Export the plugin's identity (``PLUGIN_NAME`` etc.) for any
   code that introspects loaded plugins.
2. Provide ``register(manager)`` — called by the plugin loader
   when the plugin is loaded.  We use it to attach a
   ``hermes composio`` subcommand and an MCP server installer
   hook to the CLI.

Lifecycle
---------
1. User edits ``~/.hermes/config.yaml`` to enable the plugin
   (or it ships enabled by default).
2. The plugin loader imports this module on first Hermes start.
3. ``register(manager)`` wires up CLI commands; the actual MCP
   server is **not** started here — it is spawned lazily by
   ``tools/mcp_tool.py`` once the agent enables the ``mcp``
   toolset and tries to discover ``mcp_servers.composio``.

The plugin therefore has no long-running background threads; all
heavy lifting happens in the MCP server subprocess.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


PLUGIN_NAME = "composio"
PLUGIN_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Hook implementations
# ---------------------------------------------------------------------------


def on_load(manager: Any) -> None:
    """Called by the plugin loader right after this module is imported.

    We use it to add the ``hermes composio`` subcommand to the
    CLI parser.  Other plugin systems (memory, model providers)
    attach to other hooks; this plugin is purely CLI + config.
    """
    try:
        # The plugin loader gives us a ``PluginContext`` whose
        # ``register_cli_command(name, help, setup_fn)`` wires a
        # top-level ``hermes <name> ...`` subcommand.
        from plugins.integration.composio.setup import build_parser

        manager.register_cli_command(
            name="composio",
            help="Composio integration — 1000+ OAuth apps via local MCP server.",
            setup_fn=build_parser,
            description=(
                "Configure Composio API key, list connected accounts, "
                "start OAuth flows, and install the MCP server entry."
            ),
        )
        logger.debug("composio plugin: registered 'hermes composio' subcommand")
    except Exception as exc:  # pragma: no cover — registration is best-effort
        logger.debug("composio plugin: could not register CLI subcommand: %s", exc)


# Optional hooks (no-ops) — listed here so the plugin loader
# notices we considered the full hook surface.
def on_session_start(*args: Any, **kwargs: Any) -> None:  # pragma: no cover
    pass


def on_session_end(*args: Any, **kwargs: Any) -> None:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Plugin entry: register()
# ---------------------------------------------------------------------------


def register(manager: Any) -> Optional[Dict[str, Any]]:
    """Single hook called by the plugin loader.

    Returns a small descriptor so the loader can include this
    plugin in ``hermes plugins list`` output.  We deliberately
    keep it minimal — no state, no background work.
    """
    on_load(manager)
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "category": "integration",
        "summary": (
            "Composio integration — exposes 1000+ OAuth apps to the "
            "agent as a local MCP server. Configure via `hermes composio setup`."
        ),
    }


__all__ = ["PLUGIN_NAME", "PLUGIN_VERSION", "register", "on_load"]
