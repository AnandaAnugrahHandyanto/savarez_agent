from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

from .aegis import AegisPolicyGate, PolicyConfig
from .mcp import MCPReadAPI
from .projection import DroidProjectionWorker, LadybugSQLiteStore
from .retriever import GraphRetriever, TokenBudgetPolicy


class MemPalaceLadybugProjectionProvider(MemoryProvider):
    """Local read-only memory provider backed by MemPalace and Ladybug projection."""

    @property
    def name(self) -> str:
        return "mempalace-ladybug-projection"

    def __init__(self) -> None:
        self._session_id = ""
        self._hermes_home: Optional[Path] = None
        self._mempalace_home: Optional[Path] = None
        self._output_dir: Optional[Path] = None
        self._active_projection: Optional[Path] = None
        self._api: Optional[MCPReadAPI] = None
        self._retriever = GraphRetriever(TokenBudgetPolicy())
        self._gate = AegisPolicyGate(PolicyConfig())

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = session_id
        self._hermes_home = Path(kwargs.get("hermes_home") or Path.home() / ".hermes")
        hermes_home = Path(kwargs.get("hermes_home") or Path.home() / ".hermes")
        self._output_dir = Path(kwargs.get("mempalace_ladybug_output_dir") or hermes_home / "mempalace-ladybug-projection")
        self._mempalace_home = Path(kwargs.get("mempalace_home") or self._mempalace_home or Path.home() / ".mempalace")
        source_db = self._mempalace_home / "knowledge_graph.sqlite3"
        if source_db.exists():
            manifest = DroidProjectionWorker(self._output_dir).build(source_db)
            self._active_projection = self._output_dir / "active"
            self._api = MCPReadAPI(LadybugSQLiteStore(self._active_projection / "ladybug.sqlite3"), self._gate)
            (self._output_dir / "last_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    def system_prompt_block(self) -> str:
        return (
            "\nMemory read-only projection policy:\n"
            "- MemPalace is the source of truth for user memory.\n"
            "- LadybugDB-compatible projection is a mandatory read-only graph cache.\n"
            "- Do not claim you wrote memory facts unless a user explicitly asked for Hermes memory maintenance.\n"
            "- Use bounded graph context and cite projection manifest freshness when relevant.\n"
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._active_projection:
            return ""
        graph = self._api._load_graph_from_store() if self._api else {"nodes": {}, "edges": []}
        context = self._retriever.retrieve(graph, entity_id="person:warren-l", query=query)
        return self._retriever.format_context(context)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "mempalace_ladybug_entity",
                "description": "Read bounded facts connected to a memory entity from the read-only Ladybug projection.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "predicates": {"type": "array", "items": {"type": "string"}},
                        "max_nodes": {"type": "integer", "default": 25},
                        "max_edges": {"type": "integer", "default": 50},
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "mempalace_ladybug_subgraph",
                "description": "Read a bounded, policy-gated subgraph from the read-only Ladybug projection.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "predicates": {"type": "array", "items": {"type": "string"}},
                        "max_depth": {"type": "integer", "default": 2},
                        "max_nodes": {"type": "integer", "default": 50},
                        "max_edges": {"type": "integer", "default": 100},
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "mempalace_ladybug_manifest",
                "description": "Read the read-only memory projection manifest for freshness, counts, and rollback pointer.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        ]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs: Any) -> str:
        if tool_name == "mempalace_ladybug_manifest":
            manifest_path = self._output_dir / "last_manifest.json" if self._output_dir else None
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path and manifest_path.exists() else {}
            return json.dumps({"status": "ok", "result": manifest}, sort_keys=True)
        if tool_name not in {"mempalace_ladybug_entity", "mempalace_ladybug_subgraph"}:
            raise ValueError(f"write tool not exposed by read-only memory provider: {tool_name}")
        if not self._api:
            return json.dumps({"status": "error", "error": "projection not initialized"}, sort_keys=True)
        graph = self._api._load_graph_from_store()
        decision = self._gate.evaluate(args, graph)
        return json.dumps({"status": "ok", "result": decision.filtered_graph}, sort_keys=True)

    def on_memory_write(self, action: str, target: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mirror built-in memory writes by invalidating projection freshness.

        The built-in memory write still owns MemPalace. Droid rebuilds the
        read-only projection on next initialize/build pass.
        """
        if not self._output_dir:
            return
        self._output_dir.mkdir(parents=True, exist_ok=True)
        stale = self._output_dir / "stale_after_memory_write.json"
        stale.write_text(json.dumps({
            "action": action,
            "target": target,
            "metadata": metadata or {},
            "projection_status": "stale_until_droid_rebuild",
        }, indent=2, sort_keys=True), encoding="utf-8")

    def shutdown(self) -> None:
        return
