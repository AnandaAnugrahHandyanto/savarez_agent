"""Composio → MCP bridge.

Exposes Composio OAuth-backed tools as an MCP server (stdio
transport) so any MCP-aware client (including the hermes-agent
``mcp_tool.py`` client) can call them like native tools.

Architecture
------------
::

    hermes agent ──► mcp_tool.py client ──► stdin/stdout
                                                │
                                                ▼
                                       ComposioMCPServer (this file)
                                                │
                                                ▼
                                       ComposioClient (REST)
                                                │
                                                ▼
                                       https://backend.composio.dev

Each invocation of this process owns a single :class:`ComposioMCPServer`
which:

1. On startup, lists the user's connected accounts and the
   corresponding toolkits via the REST client.
2. Registers one MCP tool per (toolkit, tool-slug) pair, ranked
   via :func:`client.rank_tools` so the LLM's tool catalog stays
   under control.
3. On ``tools/call``, looks up the tool by name, picks the
   active connected account for its toolkit, and proxies the
   call to Composio's ``/api/v3/tools/execute`` endpoint.

The server is **stateless** between calls (Composio itself holds
connection state).  All config is read once at startup from
``ComposioConfig.from_global_config()``.

Failure modes
-------------
- No API key:  server starts but ``list_tools`` returns an empty
  list with a clear error in the instructions.  ``call_tool``
  returns a JSON error text content (not an MCP protocol error).
- Unknown tool name:  returns ``isError=True`` with a helpful hint.
- Composio call failure:  same — never raises through MCP.

The MCP server is intentionally tolerant.  An MCP client that
encounters a transport error will tear down the stdio connection
and the hermes ``mcp_tool.py`` will mark the server as failed;
that's the wrong granularity for "Composio is rate-limiting us
right now" — those should be tool-level errors so the agent can
retry or pick a different tool.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

# Plugin-internal imports.  This file is only ever executed as
# ``python -m plugins.integration.composio.mcp_server`` so absolute
# imports work (the project root is on sys.path).
from plugins.integration.composio.client import (
    ComposioClient,
    ComposioConfig,
    ComposioConnectedAccount,
    ComposioError,
    ComposioTool,
    rank_tools,
)

logger = logging.getLogger("composio_mcp")

# Server identity sent to the MCP client during initialize.
SERVER_NAME = "composio"
SERVER_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Catalog builder
# ---------------------------------------------------------------------------


@dataclass
class ComposioCatalog:
    """Pre-built (toolkit, tool, account) lookup table.

    Built once at server startup; the MCP server uses it for both
    ``list_tools`` (build the response) and ``call_tool`` (resolve
    a name back to its backing data).
    """

    tools: List[ComposioTool] = field(default_factory=list)
    # tool.mcp_tool_name() -> (ComposioTool, ComposioConnectedAccount)
    by_name: Dict[str, Tuple[ComposioTool, ComposioConnectedAccount]] = field(
        default_factory=dict
    )
    errors: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.by_name

    def tool_names(self) -> List[str]:
        return list(self.by_name.keys())


# ---------------------------------------------------------------------------
# Catalog construction
# ---------------------------------------------------------------------------


def _filter_toolkits(
    config: ComposioConfig, account_toolkits: List[str]
) -> List[str]:
    """Apply the ``allowed_toolkits`` / ``allowlist_only`` policy.

    - If ``allowlist_only`` is True, only toolkits in the whitelist
      AND the connected set pass.
    - If the whitelist is non-empty but ``allowlist_only`` is False,
      the whitelist *narrows* the connected set.
    - If both empty, every connected toolkit passes.
    """
    if config.allowlist_only:
        if not config.allowed_toolkits:
            return []
        return [t for t in account_toolkits if t in config.allowed_toolkits]
    if config.allowed_toolkits:
        return [t for t in account_toolkits if t in config.allowed_toolkits]
    return account_toolkits


async def build_catalog(
    config: ComposioConfig, client: ComposioClient
) -> ComposioCatalog:
    """Build the tool catalog by enumerating connected accounts.

    For each connected account, we fetch the toolkit's tool list and
    rank it via :func:`client.rank_tools` to keep the per-toolkit
    tool count bounded.
    """
    cat = ComposioCatalog()
    if not config.is_configured():
        cat.errors.append(
            "Composio API key not configured. "
            "Run `hermes composio setup` to set one."
        )
        return cat

    try:
        accounts = await client.list_connected_accounts()
    except ComposioError as exc:
        cat.errors.append(f"Failed to list connected accounts: {exc}")
        return cat

    if not accounts:
        cat.errors.append(
            "No active Composio connections. "
            "Run `hermes composio connect <toolkit>` to authorize one."
        )
        return cat

    eligible = _filter_toolkits(config, [a.toolkit for a in accounts])
    if not eligible:
        cat.errors.append(
            f"No toolkits match allowed_toolkits={config.allowed_toolkits!r} "
            f"and allowlist_only={config.allowlist_only}."
        )
        return cat

    # One account per toolkit (prefer the first active).  holaOS picks
    # via pickOnePerToolkit (workspace_default → first active); we
    # use first active for simplicity.
    by_toolkit: Dict[str, ComposioConnectedAccount] = {}
    for acc in accounts:
        if acc.toolkit in eligible and acc.toolkit not in by_toolkit:
            by_toolkit[acc.toolkit] = acc

    for toolkit, account in by_toolkit.items():
        try:
            tools = await client.list_toolkit_tools(
                toolkit, limit=max(config.max_tools_per_toolkit * 3, 20)
            )
        except ComposioError as exc:
            cat.errors.append(f"Failed to list tools for {toolkit}: {exc}")
            continue

        top = rank_tools(tools, config.max_tools_per_toolkit)
        for t in top:
            cat.tools.append(t)
            cat.by_name[t.mcp_tool_name()] = (t, account)

    return cat


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


def _to_mcp_tool(t: ComposioTool, account: ComposioConnectedAccount) -> Tool:
    """Convert a :class:`ComposioTool` to an MCP ``Tool`` definition.

    We append a hint about the connected account to the description
    so the LLM can see which account a call will go to (matters
    when the user has multiple gmail accounts, etc.).
    """
    desc = t.description or t.name
    if account.email:
        desc = f"{desc}\n\n(connected account: {account.email})"
    return Tool(
        name=t.mcp_tool_name(),
        description=desc,
        inputSchema=t.input_schema or {"type": "object", "properties": {}},
    )


class ComposioMCPServer:
    """The MCP server implementation.

    Lifecycle::

        server = ComposioMCPServer()
        await server.run()         # blocks until stdin closes

    The server is a single instance per process; ``run()`` is
    idempotent and can be called only once.
    """

    def __init__(self, config: Optional[ComposioConfig] = None):
        self._config = config or ComposioConfig.from_global_config()
        self._server = Server(SERVER_NAME, version=SERVER_VERSION)
        self._catalog: Optional[ComposioCatalog] = None
        self._client: Optional[ComposioClient] = None
        self._register_handlers()

    # -- handler wiring ----------------------------------------------------

    def _register_handlers(self) -> None:
        server = self._server

        @server.list_tools()  # type: ignore[arg-type]
        async def _list_tools() -> ListToolsResult:
            cat = await self._ensure_catalog()
            if cat.is_empty:
                # Return an empty list rather than raising.  The
                # LLM can still see the server exists; absence of
                # tools surfaces via the catalog errors (logged
                # once at startup) and via the MCP server
                # ``instructions`` field.
                return ListToolsResult(tools=[])
            return ListToolsResult(
                tools=[_to_mcp_tool(t, acc) for t, acc in cat.by_name.values()]
            )

        @server.call_tool()  # type: ignore[arg-type]
        async def _call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            return await self.handle_call(name, arguments or {})

        # Expose the dispatcher as a public method so tests (and any
        # other in-process callers) can drive the same routing the
        # MCP stdio protocol uses, without the protocol envelope.
        self.handle_call = self._handle_call  # type: ignore[attr-defined]

    # -- catalog lifecycle -------------------------------------------------

    async def _ensure_catalog(self) -> ComposioCatalog:
        if self._catalog is not None:
            return self._catalog
        if self._client is None:
            self._client = ComposioClient(self._config)
        self._catalog = await build_catalog(self._config, self._client)
        if self._catalog.errors:
            for err in self._catalog.errors:
                logger.warning("composio catalog: %s", err)
        logger.info(
            "composio catalog built: %d tools across %d toolkits",
            len(self._catalog.tools),
            len({t.toolkit for t in self._catalog.tools}),
        )
        return self._catalog

    # -- tool execution ----------------------------------------------------

    async def _handle_call(
        self, name: str, arguments: Dict[str, Any]
    ) -> CallToolResult:
        """Public dispatcher: name → (tool, account) → execute.

        Same path the MCP ``tools/call`` handler uses, exposed so
        tests and in-process callers (e.g. ``setup.cmd_tools``) can
        drive it without going through the stdio protocol envelope.
        """
        cat = await self._ensure_catalog()
        entry = cat.by_name.get(name)
        if entry is None:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=(
                        f"Unknown Composio tool {name!r}. "
                        "Re-run `hermes composio status` to see the current "
                        "catalog — the tool may have been removed by "
                        "Composio or is not connected."
                    ),
                )],
                isError=True,
            )
        tool, account = entry
        return await self._dispatch_call(tool, account, arguments)

    async def _dispatch_call(
        self,
        tool: ComposioTool,
        account: ComposioConnectedAccount,
        arguments: Dict[str, Any],
    ) -> CallToolResult:
        """Forward an MCP tool call to Composio's execute endpoint."""
        assert self._client is not None
        try:
            result = await self._client.execute_tool(
                tool.slug,
                connected_account_id=account.id,
                arguments=arguments,
            )
        except ComposioError as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Composio error: {exc}")],
                isError=True,
            )
        except Exception as exc:  # last-resort safety net
            logger.exception("composio tool %s crashed", tool.slug)
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Unexpected Composio MCP error: {exc!r}",
                )],
                isError=True,
            )

        # Composio returns a JSON envelope.  Pass it through as
        # pretty-printed text; the agent's downstream code will
        # json.loads it if it wants structured access.
        successful = bool(result.get("successful", True))
        text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            isError=not successful,
        )

    # -- run loop ----------------------------------------------------------

    async def run(self) -> None:
        """Block on stdio until the client disconnects."""
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self._server.run(
                    read_stream,
                    write_stream,
                    self._server.create_initialization_options(),
                )
        finally:
            if self._client is not None:
                await self._client.aclose()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: ``python -m plugins.integration.composio.mcp_server``.

    Optional flags:

    - ``--print-catalog``  build the catalog, dump it as JSON to
      stdout, and exit.  Useful for debugging without bringing up
      the full stdio protocol.

    - ``--config KEY=VAL``  override a single config field
      (repeated).  Recognized keys mirror :class:`ComposioConfig`
      fields: ``api_key``, ``base_url``, ``user_id``,
      ``max_tools_per_toolkit``, ``allowlist_only``.

    The default (no flags) is to start the stdio MCP server.
    """
    parser = argparse.ArgumentParser(
        prog="composio-mcp",
        description="Local MCP server that proxies to Composio's REST API.",
    )
    parser.add_argument(
        "--print-catalog",
        action="store_true",
        help="Build and print the catalog as JSON, then exit.",
    )
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        metavar="KEY=VAL",
        help="Override a single config field (repeatable).",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("COMPOSIO_MCP_LOG_LEVEL", "WARNING"),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.WARNING),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,  # stdio MCP must use stderr for logs
    )

    config = ComposioConfig.from_global_config()
    for kv in args.config:
        if "=" not in kv:
            parser.error(f"--config expects KEY=VAL, got {kv!r}")
        k, v = kv.split("=", 1)
        if not hasattr(config, k):
            parser.error(f"unknown config field {k!r}")
        # Best-effort type coercion
        target = getattr(config, k)
        if isinstance(target, bool):
            setattr(config, k, v.lower() in ("1", "true", "yes", "on"))
        elif isinstance(target, int):
            try:
                setattr(config, k, int(v))
            except ValueError:
                parser.error(f"{k} expects an integer, got {v!r}")
        elif isinstance(target, list):
            setattr(config, k, [x.strip() for x in v.split(",") if x.strip()])
        else:
            setattr(config, k, v)

    if args.print_catalog:
        return _cli_print_catalog(config)

    server = ComposioMCPServer(config=config)
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        return 130
    return 0


def _cli_print_catalog(config: ComposioConfig) -> int:
    """Build the catalog and dump it to stdout as JSON."""
    async def _go() -> Dict[str, Any]:
        async with ComposioClient(config) as client:
            cat = await build_catalog(config, client)
            return {
                "errors": cat.errors,
                "tool_count": len(cat.tools),
                "tools": [
                    {
                        "name": t.mcp_tool_name(),
                        "toolkit": t.toolkit,
                        "slug": t.slug,
                        "description": t.description,
                        "input_schema": t.input_schema,
                    }
                    for t in cat.tools
                ],
            }

    try:
        out = asyncio.run(_go())
    except ComposioError as exc:
        print(json.dumps({"errors": [str(exc)]}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
