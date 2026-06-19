from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Set

from .ontology import redact_secrets, validate_predicate


from .exceptions import PolicyViolation


@dataclass(frozen=True)
class PolicyConfig:
    actor_id: str = "agent"
    actor_role: str = "assistant"
    allowed_scopes: Set[str] = field(default_factory=lambda: {"default"})
    allowed_predicates: Set[str] = field(default_factory=lambda: {
        "leads",
        "owns",
        "works_on",
        "depends_on",
        "uses_tool",
        "uses_model",
        "contains",
        "references",
        "located_in",
        "governed_by",
        "derived_from",
        "supersedes",
        "expires",
        "has_policy",
        "has_source",
        "has",
        "prefers",
        "values",
        "version",
        "provider",
        "runs",
        "model",
        "expects",
        "cost_conscious",
        "max_retries",
        "backoff_sequence",
        "context_length",
        "drawer_count",
        "self_audits",
        "integration",
        "works_from",
        "works_in",
    })
    max_depth: int = 3
    max_nodes: int = 100
    max_edges: int = 250
    min_confidence: float = 0.8
    require_source: bool = True
    redact_secrets: bool = True


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = "allowed"
    filtered_graph: Dict[str, Any] | None = None
    denied_predicates: Set[str] = frozenset()
    result_limit_hit: bool = False


class AegisPolicyGate:
    """Policy gate between MCP/readers and the Ladybug projection."""

    def __init__(self, config: PolicyConfig | None = None):
        self.config = config or PolicyConfig()

    def evaluate(self, query: Dict[str, Any], graph: Dict[str, Any]) -> PolicyDecision:
        self._validate_query(query)
        predicates = set(query.get("predicates") or [])
        denied = {predicate for predicate in predicates if predicate not in self.config.allowed_predicates}
        if denied:
            raise PolicyViolation(f"predicate not allowed by Aegis: {', '.join(sorted(denied))}")

        max_depth = min(int(query.get("max_depth") or self.config.max_depth), self.config.max_depth)
        max_nodes = min(int(query.get("max_nodes") or self.config.max_nodes), self.config.max_nodes)
        max_edges = min(int(query.get("max_edges") or self.config.max_edges), self.config.max_edges)

        nodes: Dict[str, Any] = {}
        edges: list[Dict[str, Any]] = []
        entity_id = query.get("entity_id")
        for edge in graph.get("edges", []):
            if not self._edge_allowed(edge):
                continue
            if entity_id and entity_id not in {edge.get("subject"), edge.get("object")}:
                continue
            if float(edge.get("properties", {}).get("confidence", edge.get("confidence", 1.0))) < self.config.min_confidence:
                continue
            edges.append(self._clean_edge(edge))
            nodes[edge["subject"]] = graph.get("nodes", {}).get(edge["subject"], {"id": edge["subject"], "type": "unknown"})
            nodes[edge["object"]] = graph.get("nodes", {}).get(edge["object"], {"id": edge["object"], "type": "unknown"})
            if len(edges) >= max_edges:
                break

        if len(nodes) > max_nodes:
            limited_nodes: Dict[str, Any] = {}
            for edge in edges:
                if len(limited_nodes) >= max_nodes:
                    break
                for entity_id_key in ("subject", "object"):
                    entity = edge.get(entity_id_key)
                    if entity and entity not in limited_nodes:
                        limited_nodes[entity] = nodes.get(entity, {"id": entity, "type": "unknown"})
            nodes = limited_nodes

        result_limit_hit = len(edges) >= max_edges or len(nodes) >= max_nodes
        filtered = {"nodes": nodes, "edges": edges}
        if self.config.redact_secrets:
            filtered = redact_secrets(filtered)  # type: ignore[assignment]
        return PolicyDecision(True, "allowed", filtered, denied, result_limit_hit)

    def _validate_query(self, query: Dict[str, Any]) -> None:
        if query.get("mode") in {"write", "mutate", "delete"}:
            raise PolicyViolation("write mode denied by Aegis")
        for predicate in query.get("predicates") or []:
            validate_predicate(str(predicate), self.config.allowed_predicates)
        if int(query.get("max_depth", self.config.max_depth)) > self.config.max_depth:
            raise PolicyViolation("max_depth exceeds policy limit")
        if int(query.get("max_nodes", self.config.max_nodes)) > self.config.max_nodes:
            raise PolicyViolation("max_nodes exceeds policy limit")
        if int(query.get("max_edges", self.config.max_edges)) > self.config.max_edges:
            raise PolicyViolation("max_edges exceeds policy limit")

    def _edge_allowed(self, edge: Dict[str, Any]) -> bool:
        predicate = str(edge.get("predicate", ""))
        return predicate in self.config.allowed_predicates

    def _clean_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        properties = dict(edge.get("properties") or {})
        properties.setdefault("confidence", edge.get("confidence", 1.0))
        return {
            "id": edge.get("id", ""),
            "subject": edge.get("subject", ""),
            "predicate": edge.get("predicate", ""),
            "object": edge.get("object", ""),
            "properties": properties,
        }
