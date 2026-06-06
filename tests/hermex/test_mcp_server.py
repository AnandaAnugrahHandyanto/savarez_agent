import json

import pytest

from hermex.core.embedding import embed_text
from hermex.core.store import SQLiteStoreConfig, build_sqlite_core_store
from hermex.core.store.base import TelemetryEvent
from hermex.mcp.server import HermexMCPServer


@pytest.mark.asyncio
async def test_mcp_initialize_and_lists_static_tools(tmp_path):
    server = HermexMCPServer(build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3")))

    init = await server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    tools = await server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    assert init["result"]["serverInfo"]["name"] == "hermex"
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert names == {"hermex_memory_search", "hermex_what_failed"}


@pytest.mark.asyncio
async def test_mcp_memory_search_and_what_failed_use_sqlite_store(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))
    await store.telemetry.emit(
        TelemetryEvent(
            session_id="session-a",
            summary="OpenRouter proxy worked when UPSTREAM_BASE was left verbatim.",
            embedding=embed_text("openrouter upstream base proxy"),
            success=True,
        )
    )
    await store.telemetry.emit(
        TelemetryEvent(
            session_id="session-b",
            summary="MCP call failed because the JSON-RPC method was unsupported.",
            embedding=embed_text("mcp json rpc unsupported method failure"),
            tool_name="hermex_mcp",
            success=False,
            failure_reason="unsupported JSON-RPC method",
        )
    )
    server = HermexMCPServer(store)

    memory = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "hermex_memory_search", "arguments": {"query": "openrouter proxy", "top_k": 3}},
        }
    )
    failure = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "hermex_what_failed", "arguments": {"tool": "hermex_mcp", "task": "json rpc"}},
        }
    )

    memory_payload = json.loads(memory["result"]["content"][0]["text"])
    failure_payload = json.loads(failure["result"]["content"][0]["text"])
    assert memory_payload["results"][0]["session"] == "session-a"
    assert "UPSTREAM_BASE" in memory_payload["results"][0]["summary"]
    assert failure_payload["known_failures"][0]["reason"] == "unsupported JSON-RPC method"
