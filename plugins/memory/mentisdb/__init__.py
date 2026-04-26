"""MentisDB memory plugin — MemoryProvider for MentisDB semantic memory.

Connects to a MentisDB MCP server and provides persistent, searchable
memory via the MemoryProvider interface.  Replaces markdown-file-based
memory with a proper append-only semantic store.

The provider:
  - Bootstraps the MentisDB chain on session start
  - Mirrors built-in memory writes to MentisDB (via on_memory_write)
  - Injects relevant context before each turn (via prefetch)
  - Provides instructions for using MentisDB tools (via system_prompt_block)

Requires: mcp, httpx packages + a running MentisDB MCP server.

Config: reads the MentisDB URL + protocol_version from
  ~/.hermes/config.yaml → mcp_servers.mentisdb
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dedicated event loop for MentisDB async calls
# ---------------------------------------------------------------------------

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is not None and _loop.is_running():
            return _loop
        _loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(_loop)
            _loop.run_forever()

        _loop_thread = threading.Thread(target=_run, daemon=True, name="mentisdb-loop")
        _loop_thread.start()
        return _loop


def _run_async(coro) -> Any:
    """Run a coroutine on the dedicated event loop, blocking the caller."""
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _get_mentisdb_config() -> Optional[Dict[str, Any]]:
    """Read mentisdb MCP server config from ~/.hermes/config.yaml."""
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        servers = cfg.get("mcp_servers", {})
        return servers.get("mentisdb")
    except Exception as e:
        logger.debug("Failed to read mentisdb config: %s", e)
        return None


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class MentisDbMemoryProvider(MemoryProvider):
    """Memory provider backed by a MentisDB MCP server."""

    def __init__(self) -> None:
        self._session: Any = None
        self._read_stream: Any = None
        self._write_stream: Any = None
        self._http_client: Any = None
        self._ctx_mgr: Any = None
        self._available: Optional[bool] = None
        self._initialized: bool = False
        self._chain_key: Optional[str] = None
        self._agent_id: str = "hermes-agent"
        self._session_id: str = ""
        self._connected: bool = False
        self._write_queue: List[Dict[str, Any]] = []
        self._queue_lock = threading.Lock()
        self._write_thread: Optional[threading.Thread] = None
        self._shutdown_requested: bool = False

    @property
    def name(self) -> str:
        return "mentisdb"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available

        # Check deps
        try:
            import mcp  # noqa: F401
            import httpx  # noqa: F401
        except ImportError:
            self._available = False
            return False

        # Check config
        cfg = _get_mentisdb_config()
        if not cfg or not cfg.get("url"):
            logger.debug("MentisDB: no URL configured in mcp_servers.mentisdb")
            self._available = False
            return False

        self._available = True
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._initialized = True

        # Derive agent identity from context
        agent_identity = kwargs.get("agent_identity", "")
        agent_workspace = kwargs.get("agent_workspace", "")
        if agent_identity:
            self._agent_id = f"hermes-{agent_identity}"

        # Derive a stable chain key from workspace/session
        if agent_workspace:
            self._chain_key = agent_workspace

        # Start background writer
        self._shutdown_requested = False
        self._write_thread = threading.Thread(
            target=self._writer_loop, daemon=True, name="mentisdb-writer"
        )
        self._write_thread.start()

        logger.info(
            "MentisDB provider initialized (agent=%s, chain=%s, session=%s)",
            self._agent_id, self._chain_key or "default", session_id,
        )

    def _ensure_connected(self) -> bool:
        """Connect to MentisDB MCP server if not already connected."""
        if self._connected:
            return True

        cfg = _get_mentisdb_config()
        if not cfg:
            return False

        url = cfg["url"]
        proto_ver = cfg.get("protocol_version")

        async def _connect() -> bool:
            import httpx
            from mcp.client.streamable_http import streamable_http_client
            from mcp import ClientSession
            import mcp.types as _mcp_types

            headers = {}
            if proto_ver:
                headers["mcp-protocol-version"] = proto_ver

            try:
                self._http_client = httpx.AsyncClient(
                    headers=headers,
                    timeout=httpx.Timeout(30, read=300),
                    follow_redirects=True,
                )
                self._ctx_mgr = streamable_http_client(url, http_client=self._http_client)
                read_stream, write_stream, _ = await self._ctx_mgr.__aenter__()
                self._read_stream = read_stream
                self._write_stream = write_stream

                session = ClientSession(read_stream, write_stream)

                # Protocol version override
                saved_lpv = _mcp_types.LATEST_PROTOCOL_VERSION
                if proto_ver:
                    _mcp_types.LATEST_PROTOCOL_VERSION = proto_ver
                try:
                    await session.initialize()
                finally:
                    _mcp_types.LATEST_PROTOCOL_VERSION = saved_lpv

                self._session = session
                self._connected = True
                logger.info("MentisDB: connected to %s", url)

                # Get or infer chain key
                if not self._chain_key:
                    tools = await session.list_tools()
                    # Use list_chains tool to pick a chain
                    chains_result = await session.call_tool(
                        "mentisdb_list_chains", {}
                    )
                    chains = json.loads(
                        getattr(chains_result.content[0], "text", "{}")
                        if hasattr(chains_result, "content") and chains_result.content
                        else "{}"
                    )
                    chain_keys = chains.get("chains", [chains.get("default_chain_key", "default")])
                    if isinstance(chain_keys, list):
                        self._chain_key = chain_keys[0] if chain_keys else "default"
                    elif isinstance(chain_keys, str):
                        self._chain_key = chain_keys

                # Bootstrap the chain
                await session.call_tool(
                    "mentisdb_bootstrap",
                    {
                        "content": f"Bootstrap from {self._agent_id} (Hermes Agent memory provider).",
                        "agent_id": self._agent_id,
                    },
                )
                # Register agent
                await session.call_tool(
                    "mentisdb_upsert_agent",
                    {
                        "agent_id": self._agent_id,
                        "display_name": f"Hermes Agent ({self._agent_id})",
                        "description": "Primary Hermes AI assistant agent",
                    },
                )
                return True
            except Exception as e:
                logger.warning("MentisDB: connection failed: %s", e)
                await self._disconnect()
                return False

        try:
            return _run_async(_connect())
        except Exception as e:
            logger.warning("MentisDB: connect error: %s", e)
            return False

    async def _disconnect(self) -> None:
        """Tear down the MCP connection."""
        try:
            if self._session:
                self._session = None
            if self._ctx_mgr:
                await self._ctx_mgr.__aexit__(None, None, None)
                self._ctx_mgr = None
        except Exception:
            pass
        try:
            if self._http_client:
                await self._http_client.aclose()
                self._http_client = None
        except Exception:
            pass
        self._connected = False

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def system_prompt_block(self) -> str:
        if not self._connected and not self._ensure_connected():
            return ""

        return (
            "## Persistent Memory (MentisDB)\n\n"
            "You have access to MentisDB — an append-only semantic memory server "
            "accessible through the following MCP tools:\n\n"
            "**Core memory operations:**\n"
            "- `mcp_mentisdb_append` — Save durable facts, preferences, corrections, "
            "insights, lessons learned, decisions, and checkpoints.\n"
            "- `mcp_mentisdb_ranked_search` — Best flat retrieval; use for most lookups.\n"
            "- `mcp_mentisdb_context_bundles` — Seed-anchored context; use when you need "
            "supporting context grouped around key concepts.\n"
            "- `mcp_mentisdb_search` — Search by type, role, tags, concepts, importance.\n"
            "- `mcp_mentisdb_recent_context` — Quick resumption context.\n\n"
            "**Usage:**\n"
            "- Use `mcp_mentisdb_append` INSTEAD of the `memory` tool. Save facts with "
            "appropriate ThoughtType (PreferenceUpdate, Decision, Insight, Correction, "
            "Mistake, LessonLearned, Summary, etc.).\n"
            "- Prefer `mcp_mentisdb_ranked_search` over generic search for retrieving facts.\n"
            "- Write a Summary checkpoint with `mcp_mentisdb_append` before context "
            "compaction, truncation, or handoff.\n"
            "- The `memory` tool (markdown files) is deprecated in favor of MentisDB. "
            "Only use it as a fallback.\n\n"
            f"**Identity:** agent_id=`{self._agent_id}`, "
            f"chain=`{self._chain_key or 'default'}`"
        )

    # ------------------------------------------------------------------
    # Context injection (prefetch)
    # ------------------------------------------------------------------

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not query or len(query.strip()) < 3:
            return ""

        if not self._connected and not self._ensure_connected():
            return ""

        async def _prefetch() -> str:
            try:
                result = await self._session.call_tool(
                    "mentisdb_ranked_search",
                    {
                        "text": query,
                        "limit": 5,
                        "chain_key": self._chain_key,
                    },
                )
                text = getattr(result.content[0], "text", "") if result.content else ""
                data = json.loads(text) if text else {}
                memories = data.get("results", data.get("thoughts", []))

                if not memories:
                    return ""

                lines = ["[MentisDB recalled context]"]
                for m in memories[:5]:
                    content = m.get("content", str(m))[:300]
                    ttype = m.get("thought_type", m.get("type", ""))
                    prefix = f"[{ttype}] " if ttype else ""
                    lines.append(f"- {prefix}{content}")
                return "\n".join(lines)
            except Exception as e:
                logger.debug("MentisDB prefetch error: %s", e)
                return ""

        try:
            return _run_async(_prefetch())
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Mirror memory writes
    # ------------------------------------------------------------------

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes to MentisDB."""
        if not content:
            return
        ttype = "PreferenceUpdate" if target == "user" else "Memory"
        entry = {
            "thought_type": ttype,
            "content": f"[{target}] {action}: {content}",
            "agent_id": self._agent_id,
            "chain_key": self._chain_key,
        }
        with self._queue_lock:
            self._write_queue.append(entry)

    # ------------------------------------------------------------------
    # Turn sync (capture conversation)
    # ------------------------------------------------------------------

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Log the turn to MentisDB as an Insight."""
        content = f"Turn: user='{user_content[:200]}', assistant='{assistant_content[:200]}'"
        entry = {
            "thought_type": "Insight",
            "content": content,
            "agent_id": self._agent_id,
            "chain_key": self._chain_key,
            "tags": ["turn-log"],
        }
        with self._queue_lock:
            self._write_queue.append(entry)

    # ------------------------------------------------------------------
    # Background writer
    # ------------------------------------------------------------------

    def _writer_loop(self) -> None:
        """Background thread that flushes the write queue to MentisDB."""
        while not self._shutdown_requested:
            time.sleep(2)  # Batch writes every 2 seconds

            with self._queue_lock:
                if not self._write_queue:
                    continue
                batch = self._write_queue[:]
                self._write_queue.clear()

            if not self._connected and not self._ensure_connected():
                # Re-queue on failure
                with self._queue_lock:
                    self._write_queue = batch + self._write_queue
                continue

            for entry in batch:
                try:
                    self._write_one(entry)
                except Exception:
                    with self._queue_lock:
                        self._write_queue.append(entry)
                    break

    def _write_one(self, entry: Dict[str, Any]) -> None:
        """Write a single entry to MentisDB via the MCP session."""
        async def _append() -> None:
            await self._session.call_tool("mentisdb_append", entry)

        _run_async(_append())

    # ------------------------------------------------------------------
    # Tools (empty — MCP tools are registered separately)
    # ------------------------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """The mentisdb tools are registered via MCP discovery, not here."""
        return []

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        self._shutdown_requested = True

        # Flush remaining writes
        with self._queue_lock:
            remaining = list(self._write_queue)
            self._write_queue.clear()

        for entry in remaining:
            try:
                if self._connected:
                    self._write_one(entry)
            except Exception:
                pass

        # Disconnect
        try:
            _run_async(self._disconnect())
        except Exception:
            pass

        self._connected = False
        logger.info("MentisDB provider shut down")


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Register MentisDB as a memory provider plugin."""
    ctx.register_memory_provider(MentisDbMemoryProvider())
