from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hermex.config import Config, build_core_store
from hermex.core.embedding import embed_text
from hermex.core.store.base import CoreStore


STATIC_TOOLS: list[dict[str, Any]] = [
    {
        "name": "hermex_memory_search",
        "description": (
            "Search Hermex cross-session execution memory for relevant prior attempts, "
            "failures, and solutions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "hermex_what_failed",
        "description": "Return known failure modes for a tool or task class from Hermex memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string"},
                "task": {"type": "string"},
            },
        },
    },
]


class HermexMCPServer:
    def __init__(self, store: CoreStore) -> None:
        self._store = store

    async def handle(self, body: dict[str, Any]) -> dict[str, Any]:
        method = body.get("method")
        params = body.get("params") or {}
        request_id = body.get("id")

        if method == "initialize":
            return self._ok(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "hermex", "version": "0.1.0"},
                },
            )
        if method == "tools/list":
            return self._ok(request_id, {"tools": STATIC_TOOLS})
        if method == "tools/call":
            result = await self._dispatch(params.get("name"), params.get("arguments") or {})
            return self._ok(request_id, {"content": [{"type": "text", "text": json.dumps(result)}]})
        return self._err(request_id, -32601, f"unknown method: {method}")

    async def _dispatch(self, tool_name: str | None, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "hermex_memory_search":
            return await self._memory_search(args)
        if tool_name == "hermex_what_failed":
            return await self._what_failed(args)
        return {"error": f"unknown tool: {tool_name}"}

    async def _memory_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "")
        hits = await self._store.telemetry.search_similar(
            embed_text(query),
            top_k=int(args.get("top_k") or 5),
            exclude_session=str(args.get("exclude_session") or ""),
        )
        return {
            "results": [
                {"session": hit.session_id, "summary": hit.summary, "sim": round(hit.score, 4)}
                for hit in hits
            ]
        }

    async def _what_failed(self, args: dict[str, Any]) -> dict[str, Any]:
        query = f"{args.get('tool', '')} {args.get('task', '')} failure"
        hits = await self._store.telemetry.search_failures(embed_text(query), top_k=int(args.get("top_k") or 5))
        return {
            "known_failures": [
                {
                    "tool": hit.tool_name,
                    "reason": hit.failure_reason,
                    "session": hit.session_id,
                    "summary": hit.summary,
                }
                for hit in hits
            ]
        }

    @staticmethod
    def _ok(request_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _err(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def create_mcp_app(config: Config) -> FastAPI:
    app = FastAPI(title="Hermex MCP")
    app.state.server = HermexMCPServer(build_core_store(config))

    @app.post("/mcp")
    async def mcp_endpoint(request: Request) -> JSONResponse:
        body = await request.json()
        server: HermexMCPServer = app.state.server
        return JSONResponse(await server.handle(body))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
