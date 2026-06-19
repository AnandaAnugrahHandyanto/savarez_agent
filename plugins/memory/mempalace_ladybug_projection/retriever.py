from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class TokenBudgetPolicy:
    max_nodes: int = 100
    max_edges: int = 250
    max_source_snippets: int = 10
    max_snippet_chars: int = 500


class GraphRetriever:
    """Bounded graph retriever that avoids raw drawer dumps."""

    def __init__(self, policy: TokenBudgetPolicy | None = None):
        self.policy = policy or TokenBudgetPolicy()

    def retrieve(self, graph: Dict[str, Any], entity_id: str, query: str) -> Dict[str, Any]:
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])
        selected_nodes: Dict[str, Any] = {}
        selected_edges: list[Dict[str, Any]] = []
        if entity_id in nodes:
            selected_nodes[entity_id] = nodes[entity_id]
        for edge in edges:
            if edge.get("subject") == entity_id or edge.get("object") == entity_id:
                if len(selected_edges) >= self.policy.max_edges:
                    break
                selected_edges.append(edge)
                selected_nodes[edge["subject"]] = nodes.get(edge["subject"], {"id": edge["subject"], "type": "unknown"})
                selected_nodes[edge["object"]] = nodes.get(edge["object"], {"id": edge["object"], "type": "unknown"})
                if len(selected_nodes) >= self.policy.max_nodes:
                    break
        return {
            "query": query,
            "entity_id": entity_id,
            "nodes": dict(list(selected_nodes.items())[: self.policy.max_nodes]),
            "edges": selected_edges[: self.policy.max_edges],
            "source_snippets": [],
            "token_policy": {
                "max_nodes": self.policy.max_nodes,
                "max_edges": self.policy.max_edges,
                "max_source_snippets": self.policy.max_source_snippets,
                "max_snippet_chars": self.policy.max_snippet_chars,
            },
        }

    def format_context(self, context: Dict[str, Any]) -> str:
        lines = [f"Memory graph context for {context.get('entity_id')}"]
        for entity in context.get("nodes", {}).values():
            if hasattr(entity, "to_dict"):
                entity = entity.to_dict()
            lines.append(f"- {entity.get('id')}: {entity.get('name') or entity.get('id')} ({entity.get('type')})")
        for edge in context.get("edges", []):
            lines.append(
                f"- {edge.get('subject')} --{edge.get('predicate')}--> {edge.get('object')} "
                f"[confidence={edge.get('properties', {}).get('confidence', 1.0)}]"
            )
        return "\n".join(lines)
