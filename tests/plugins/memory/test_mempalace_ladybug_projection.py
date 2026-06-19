import json
import sqlite3
from pathlib import Path

import pytest

from plugins.memory.mempalace_ladybug_projection.models import Entity, Source, Triple
from plugins.memory.mempalace_ladybug_projection.ontology import (
    DEFAULT_PREDICATES,
    DEFAULT_ENTITY_TYPES,
    normalize_entity_id,
    validate_entity,
    validate_predicate,
)
from plugins.memory.mempalace_ladybug_projection.aegis import AegisPolicyGate, PolicyConfig, PolicyViolation
from plugins.memory.mempalace_ladybug_projection.mempalace_adapter import MemPalaceKGAdapter
from plugins.memory.mempalace_ladybug_projection.projection import DroidProjectionWorker, LadybugSQLiteStore
from plugins.memory.mempalace_ladybug_projection.mcp import MCPReadAPI
from plugins.memory.mempalace_ladybug_projection.retriever import GraphRetriever, TokenBudgetPolicy
from plugins.memory.mempalace_ladybug_projection.provider import MemPalaceLadybugProjectionProvider


def test_ontology_normalizes_entities_and_rejects_unknown_predicates():
    entity = Entity(id="person:warren-l", name="Warren L", type="person")
    assert validate_entity(entity, DEFAULT_ENTITY_TYPES) is None

    assert normalize_entity_id("person", "Warren L") == "person:warren-l"
    assert validate_predicate("leads", DEFAULT_PREDICATES) is None
    with pytest.raises(PolicyViolation, match="unknown predicate"):
        validate_predicate("secret_write", DEFAULT_PREDICATES)


def test_aegis_denies_unauthorized_predicate_and_redacts_secrets(tmp_path):
    graph = {
        "nodes": {
            "person:warren-l": Entity(id="person:warren-l", name="Warren L", type="person"),
            "project:edgegde": Entity(id="project:edgegde", name="EdgeGDE", type="project"),
        },
        "edges": [
            {
                "id": "edge-1",
                "subject": "person:warren-l",
                "predicate": "leads",
                "object": "project:edgegde",
                "properties": {"confidence": 1.0, "valid_from": "2026-06-18", "api_key": "sk-secret"},
            }
        ],
    }
    gate = AegisPolicyGate(PolicyConfig(
        actor_id="agent",
        actor_role="assistant",
        allowed_predicates={"leads"},
        max_depth=2,
        max_nodes=10,
        max_edges=10,
        min_confidence=0.8,
        require_source=True,
        redact_secrets=True,
    ))

    with pytest.raises(PolicyViolation, match="predicate"):
        gate.evaluate({"predicates": ["secret_write"], "max_depth": 1, "max_nodes": 10, "max_edges": 10}, graph)

    decision = gate.evaluate({"predicates": ["leads"], "max_depth": 1, "max_nodes": 10, "max_edges": 10}, graph)
    assert decision.allowed
    assert decision.filtered_graph["edges"][0]["properties"]["api_key"] == "[REDACTED]"


def test_mempalace_adapter_reads_sqlite_kg(tmp_path):
    db = tmp_path / "knowledge_graph.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT DEFAULT 'unknown', properties TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE TABLE triples (id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT NOT NULL, valid_from TEXT, valid_to TEXT, confidence REAL DEFAULT 1.0, source_closet TEXT, source_file TEXT, source_drawer_id TEXT, adapter_name TEXT, extracted_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?)", ("person:warren-l", "Warren L", "person", "{}", "2026-06-18T00:00:00Z"))
    con.execute("INSERT INTO triples VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("triple-1", "person:warren-l", "leads", "project:edgegde", "2026-06-18", None, 1.0, "memory-reference", "drawer.md", "drawer-1", "mempalace", "2026-06-18T00:00:00Z"))
    con.commit()
    con.close()

    adapter = MemPalaceKGAdapter(db)
    triples = adapter.read_triples()
    assert len(triples) == 1
    assert triples[0].subject.id == "person:warren-l"
    assert triples[0].predicate == "leads"
    assert triples[0].source.drawer_id == "drawer-1"


def test_projection_worker_builds_manifest_and_ladybug_sqlite_projection(tmp_path):
    source_db = tmp_path / "source.sqlite3"
    con = sqlite3.connect(source_db)
    con.execute("CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT DEFAULT 'unknown', properties TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE TABLE triples (id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT NOT NULL, valid_from TEXT, valid_to TEXT, confidence REAL DEFAULT 1.0, source_closet TEXT, source_file TEXT, source_drawer_id TEXT, adapter_name TEXT, extracted_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?)", ("person:warren-l", "Warren L", "person", "{}", "2026-06-18T00:00:00Z"))
    con.execute("INSERT INTO entities VALUES (?, ?, ?, ?, ?)", ("project:edgegde", "EdgeGDE", "project", "{}", "2026-06-18T00:00:00Z"))
    con.execute("INSERT INTO triples VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("triple-1", "person:warren-l", "leads", "project:edgegde", "2026-06-18", None, 1.0, "memory-reference", "drawer.md", "drawer-1", "mempalace", "2026-06-18T00:00:00Z"))
    con.commit()
    con.close()

    output = tmp_path / "ladybug"
    worker = DroidProjectionWorker(output_dir=output)
    manifest = worker.build(source_db=source_db)

    assert manifest["entity_count"] == 2
    assert manifest["fact_count"] == 1
    assert manifest["edge_count"] == 2
    assert (output / "active.json").exists()
    assert (output / "active" / "manifest.json").exists()

    store = LadybugSQLiteStore(output / "active" / "ladybug.sqlite3")
    assert store.count_nodes() == 2
    assert store.count_edges() == 2


def test_mcp_read_api_exposes_only_read_tools_and_rejects_writes():
    api = MCPReadAPI(LadybugSQLiteStore(":memory:"))
    names = {schema["name"] for schema in api.get_tool_schemas()}
    assert "kg_entity" in names
    assert "kg_relationship" in names
    assert "kg_subgraph" in names
    assert "kg_add_fact" not in names

    with pytest.raises(ValueError, match="write tool"):
        api.handle_tool_call("kg_add_fact", {}, active_projection=None)


def test_retriever_bounds_graph_context_and_formats_compact_context():
    graph = {
        "nodes": {
            "person:warren-l": Entity(id="person:warren-l", name="Warren L", type="person"),
            "project:edgegde": Entity(id="project:edgegde", name="EdgeGDE", type="project"),
            "tool:hermes": Entity(id="tool:hermes", name="Hermes", type="tool"),
        },
        "edges": [
            {"id": "edge-1", "subject": "person:warren-l", "predicate": "leads", "object": "project:edgegde", "properties": {"confidence": 1.0}},
            {"id": "edge-2", "subject": "project:edgegde", "predicate": "uses_tool", "object": "tool:hermes", "properties": {"confidence": 1.0}},
        ],
    }
    retriever = GraphRetriever(TokenBudgetPolicy(max_nodes=2, max_edges=1, max_source_snippets=1))
    context = retriever.retrieve(graph, entity_id="person:warren-l", query="what does Warren lead?")

    assert len(context["nodes"]) <= 2
    assert len(context["edges"]) <= 1
    assert "Warren L" in retriever.format_context(context)


def test_provider_registers_read_only_tools_and_system_prompt(tmp_path):
    provider = MemPalaceLadybugProjectionProvider()
    provider._output_dir = tmp_path / "projection"
    provider._mempalace_home = tmp_path / "mempalace"
    provider._mempalace_home.mkdir()
    db = provider._mempalace_home / "knowledge_graph.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE entities (id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT DEFAULT 'unknown', properties TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.execute("CREATE TABLE triples (id TEXT PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT NOT NULL, valid_from TEXT, valid_to TEXT, confidence REAL DEFAULT 1.0, source_closet TEXT, source_file TEXT, source_drawer_id TEXT, adapter_name TEXT, extracted_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    con.commit()
    con.close()

    provider.initialize(session_id="test", hermes_home=tmp_path)
    schemas = provider.get_tool_schemas()
    names = {schema["name"] for schema in schemas}
    assert "mempalace_ladybug_entity" in names
    assert "mempalace_ladybug_manifest" in names
    assert "mempalace_ladybug_add_fact" not in names
    assert "read-only" in provider.system_prompt_block()
