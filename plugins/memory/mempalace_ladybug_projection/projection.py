from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .aegis import PolicyConfig
from .mempalace_adapter import MemPalaceKGAdapter
from .models import Entity, Graph, GraphEdge, Triple
from .ontology import ADAPTER_NAME, DEFAULT_ENTITY_TYPES, POLICY_VERSION, SCHEMA_VERSION, VERSION, hash_json, validate_triple


class LadybugSQLiteStore:
    """SQLite-backed LadybugDB-compatible projection store.

    The optional DuckDB/LadybugDB engine path is intentionally abstracted. In
    environments without the optional binary package, this store provides a
    dependency-free graph projection using the same node/edge schema.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if str(db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        con = self._connect()
        try:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    properties TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    properties TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(subject) REFERENCES nodes(id),
                    FOREIGN KEY(object) REFERENCES nodes(id)
                );
                CREATE TABLE IF NOT EXISTS facts (
                    triple_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    source TEXT NOT NULL DEFAULT '{}',
                    properties TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS predicates (
                    name TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS drawers (
                    id TEXT PRIMARY KEY,
                    drawer_hash TEXT,
                    source_file TEXT,
                    source_closet TEXT
                );
                CREATE TABLE IF NOT EXISTS projection_manifests (
                    projection_id TEXT PRIMARY KEY,
                    manifest TEXT NOT NULL
                );
                """
            )
            con.commit()
        finally:
            con.close()

    def write_graph(self, graph: Graph, facts: Iterable[Triple]) -> None:
        con = self._connect()
        try:
            con.execute("DELETE FROM edges")
            con.execute("DELETE FROM facts")
            con.execute("DELETE FROM predicates")
            con.execute("DELETE FROM nodes")
            for entity in graph.nodes.values():
                con.execute(
                    "INSERT INTO nodes(id, name, type, properties) VALUES (?, ?, ?, ?)",
                    (entity.id, entity.name, entity.type, json.dumps(entity.properties, sort_keys=True)),
                )
            for edge in graph.edges:
                con.execute(
                    "INSERT INTO edges(id, subject, predicate, object, properties) VALUES (?, ?, ?, ?, ?)",
                    (edge.id, edge.subject, edge.predicate, edge.object, json.dumps(edge.properties, sort_keys=True)),
                )
                con.execute("INSERT OR IGNORE INTO predicates(name) VALUES (?)", (edge.predicate,))
            for fact in facts:
                con.execute(
                    "INSERT INTO facts(triple_id, subject, predicate, object, valid_from, valid_to, confidence, source, properties) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        fact.triple_id,
                        fact.subject.id,
                        fact.predicate,
                        fact.object.id,
                        fact.valid_from,
                        fact.valid_to,
                        fact.confidence,
                        json.dumps(fact.source.to_dict(), sort_keys=True),
                        json.dumps(fact.properties, sort_keys=True),
                    ),
                )
            con.commit()
        finally:
            con.close()

    def count_nodes(self) -> int:
        if str(self.db_path) == ":memory:":
            return 0
        con = self._connect()
        try:
            return int(con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])
        finally:
            con.close()

    def count_edges(self) -> int:
        if str(self.db_path) == ":memory:":
            return 0
        con = self._connect()
        try:
            return int(con.execute("SELECT COUNT(*) FROM edges").fetchone()[0])
        finally:
            con.close()


class DroidProjectionWorker:
    """Deterministic projection worker from MemPalace KG to LadybugDB-compatible output."""

    def __init__(self, output_dir: str | Path, policy_config: PolicyConfig | None = None):
        self.output_dir = Path(output_dir)
        self.policy_config = policy_config or PolicyConfig()

    def build(self, source_db: str | Path, policy_version: str = POLICY_VERSION) -> Dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        active_dir = self.output_dir / "active"
        if active_dir.exists():
            previous_manifest = active_dir / "manifest.json"
        else:
            previous_manifest = None

        staging_dir = self.output_dir / ".staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True)

        adapter = MemPalaceKGAdapter(source_db)
        triples = adapter.read_triples()
        for triple in triples:
            validate_triple(triple, DEFAULT_ENTITY_TYPES, self.policy_config.allowed_predicates)

        graph = self._graph_from_triples(triples)
        manifest = self._manifest(triples, graph, policy_version, previous_manifest)
        (staging_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        (staging_dir / "graph.json").write_text(json.dumps(graph.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        LadybugSQLiteStore(staging_dir / "ladybug.sqlite3").write_graph(graph, triples)
        (staging_dir / "projection.jsonl").write_text(
            "".join(json.dumps(triple.to_dict(), sort_keys=True) + "\n" for triple in triples),
            encoding="utf-8",
        )

        active_dir.mkdir(parents=True, exist_ok=True)
        for child in staging_dir.iterdir():
            destination = active_dir / child.name
            if child.is_dir():
                shutil.copytree(child, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(child, destination)
        shutil.rmtree(staging_dir)
        (self.output_dir / "active.json").write_text(json.dumps({"projection_id": manifest["projection_id"], "active_dir": "active"}, indent=2, sort_keys=True), encoding="utf-8")

        if previous_manifest is not None and previous_manifest.exists():
            previous_id = json.loads(previous_manifest.read_text(encoding="utf-8")).get("projection_id", "")
            (self.output_dir / "active_previous.json").write_text(json.dumps({"projection_id": previous_id}, indent=2), encoding="utf-8")
        return manifest

    def _graph_from_triples(self, triples: Iterable[Triple]) -> Graph:
        graph = Graph()
        for triple in triples:
            graph.add_entity(triple.subject)
            graph.add_entity(triple.object)
            edge_id = hash_json({"triple_id": triple.triple_id, "direction": "subject_object"})
            graph.add_edge(GraphEdge(
                id=edge_id,
                subject=triple.subject.id,
                predicate=triple.predicate,
                object=triple.object.id,
                properties={
                    "fact_id": triple.triple_id,
                    "valid_from": triple.valid_from,
                    "valid_to": triple.valid_to,
                    "confidence": triple.confidence,
                    "source_drawer_id": triple.source.drawer_id,
                    "adapter_version": triple.source.adapter_version,
                    "policy_version": POLICY_VERSION,
                },
            ))
            reverse_id = hash_json({"triple_id": triple.triple_id, "direction": "object_subject"})
            graph.add_edge(GraphEdge(
                id=reverse_id,
                subject=triple.object.id,
                predicate=f"inverse:{triple.predicate}",
                object=triple.subject.id,
                properties={
                    "fact_id": triple.triple_id,
                    "valid_from": triple.valid_from,
                    "valid_to": triple.valid_to,
                    "confidence": triple.confidence,
                    "source_drawer_id": triple.source.drawer_id,
                    "adapter_version": triple.source.adapter_version,
                    "policy_version": POLICY_VERSION,
                    "inverse_of": triple.predicate,
                },
            ))
        return graph

    def _manifest(self, triples: list[Triple], graph: Graph, policy_version: str, previous_manifest: Optional[Path]) -> Dict[str, Any]:
        previous_id = ""
        if previous_manifest is not None and previous_manifest.exists():
            previous_id = json.loads(previous_manifest.read_text(encoding="utf-8")).get("projection_id", "")
        payload = {
            "projection_id": f"mempalace-ladybug-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "schema_version": SCHEMA_VERSION,
            "adapter_version": VERSION,
            "mempalace_version": "3.3.3",
            "ladybug_version": "sqlite-compatible-1.0.0",
            "source_drawer_count": len({triple.source.drawer_id for triple in triples if triple.source.drawer_id}),
            "changed_drawer_count": len({triple.source.drawer_id for triple in triples if triple.source.drawer_id}),
            "entity_count": len(graph.nodes),
            "fact_count": len(triples),
            "edge_count": len(graph.edges),
            "policy_version": policy_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "droid",
            "approved_by": "hermes",
            "source_hash": hash_json([triple.to_dict() for triple in triples]),
            "projection_hash": hash_json(graph.to_dict()),
            "rollback_to": previous_id,
        }
        return payload
