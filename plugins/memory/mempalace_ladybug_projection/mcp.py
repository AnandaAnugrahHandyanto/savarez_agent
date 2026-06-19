from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .aegis import AegisPolicyGate, PolicyConfig
from .projection import LadybugSQLiteStore


class MCPReadAPI:
    """Read-only MCP-style API surface for Ladybug projection queries."""

    READ_TOOLS = {
        "kg_entity": "Read facts connected to a single entity.",
        "kg_relationship": "Read facts with a specific predicate.",
        "kg_path": "Read bounded paths between two entities.",
        "kg_timeline": "Read temporal facts for an entity.",
        "kg_subgraph": "Read a bounded, policy-gated subgraph.",
        "kg_projection_manifest": "Read projection health and freshness.",
    }

    def __init__(self, store: LadybugSQLiteStore, gate: AegisPolicyGate | None = None):
        self.store = store
        self.gate = gate or AegisPolicyGate(PolicyConfig())

    def get_tool_schemas(self) -> list[Dict[str, Any]]:
        schemas = []
        for name, description in self.READ_TOOLS.items():
            schemas.append({
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": self._properties_for(name),
                    "required": self._required_for(name),
                },
            })
        return schemas

    def handle_tool_call(self, name: str, arguments: Dict[str, Any], active_projection: Optional[str] = None) -> str:
        if name not in self.READ_TOOLS:
            raise ValueError(f"write tool not exposed by read-only MCP API: {name}")
        if name == "kg_projection_manifest":
            if active_projection:
                manifest_path = Path(active_projection) / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            else:
                manifest = {"status": "no_active_projection"}
            return json.dumps({"status": "ok", "result": manifest}, sort_keys=True)
        graph = self._load_graph_from_store()
        decision = self.gate.evaluate(arguments, graph)
        return json.dumps({"status": "ok", "result": decision.filtered_graph}, sort_keys=True)

    def _properties_for(self, name: str) -> Dict[str, Any]:
        base = {
            "entity_id": {"type": "string"},
            "predicates": {"type": "array", "items": {"type": "string"}},
            "max_depth": {"type": "integer", "default": 3},
            "max_nodes": {"type": "integer", "default": 100},
            "max_edges": {"type": "integer", "default": 250},
            "actor_id": {"type": "string"},
            "actor_role": {"type": "string"},
        }
        if name == "kg_path":
            base["target_entity_id"] = {"type": "string"}
        if name == "kg_projection_manifest":
            return {"active_projection": {"type": "string"}}
        return base

    def _required_for(self, name: str) -> list[str]:
        if name == "kg_projection_manifest":
            return []
        if name == "kg_path":
            return ["entity_id", "target_entity_id"]
        return ["entity_id"]

    def _load_graph_from_store(self) -> Dict[str, Any]:
        if str(self.store.db_path) == ":memory:":
            return {"nodes": {}, "edges": []}
        con = self.store._connect()
        try:
            nodes = {
                row[0]: {"id": row[0], "name": row[1], "type": row[2], "properties": json.loads(row[3])}
                for row in con.execute("SELECT id, name, type, properties FROM nodes").fetchall()
            }
            edges = [
                {"id": row[0], "subject": row[1], "predicate": row[2], "object": row[3], "properties": json.loads(row[4])}
                for row in con.execute("SELECT id, subject, predicate, object, properties FROM edges").fetchall()
            ]
        finally:
            con.close()
        return {"nodes": nodes, "edges": edges}
