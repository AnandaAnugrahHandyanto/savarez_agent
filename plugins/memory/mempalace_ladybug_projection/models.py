from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Entity:
    """Canonical graph entity."""

    id: str
    name: str
    type: str = "unknown"
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "properties": dict(self.properties),
        }


@dataclass(frozen=True)
class Source:
    """Provenance for a canonical fact."""

    drawer_id: str = ""
    drawer_hash: str = ""
    source_file: str = ""
    source_closet: str = ""
    adapter_name: str = "mempalace-ladybug-projection"
    adapter_version: str = "0.2.0"
    extracted_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drawer_id": self.drawer_id,
            "drawer_hash": self.drawer_hash,
            "source_file": self.source_file,
            "source_closet": self.source_closet,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "extracted_at": self.extracted_at,
        }


@dataclass(frozen=True)
class Triple:
    """Canonical subject-predicate-object fact from MemPalace."""

    triple_id: str
    subject: Entity
    predicate: str
    object: Entity
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    confidence: float = 1.0
    source: Source = field(default_factory=lambda: Source())
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triple_id": self.triple_id,
            "subject": self.subject.to_dict(),
            "predicate": self.predicate,
            "object": self.object.to_dict(),
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "confidence": self.confidence,
            "source": self.source.to_dict(),
            "properties": dict(self.properties),
        }


@dataclass
class GraphEdge:
    """Directed graph edge derived from one or more triples."""

    id: str
    subject: str
    predicate: str
    object: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "properties": dict(self.properties),
        }


@dataclass
class Graph:
    """In-memory graph used by projection, policy, MCP, and retrieval."""

    nodes: Dict[str, Entity] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_entity(self, entity: Entity) -> None:
        self.nodes[entity.id] = entity

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {entity_id: entity.to_dict() for entity_id, entity in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
        }
