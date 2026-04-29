"""
Hermes Agent — Memory Module

Persistent knowledge graph and incremental indexing system.
Inspired by MemPalace (ChromaDB + MCP) and nashsu/llm_wiki patterns.

Components:
  - KnowledgeGraph   : SQLite-backed knowledge graph (entities + relations)
  - IncrementalIndexer: Background indexer with async processing
  - Retriever        : BM25 + optional vector search + multi-hop retrieval
  - MemoryStore      : Session / working / long-term memory tiers
  - EntityExtractor  : Pattern-based entity and relation extraction
  - WikiBuilder      : LLM Wiki-style compound knowledge pages

Usage:
    from hermes_agent.memory import KnowledgeGraph, MemoryStore

    kg = KnowledgeGraph()
    entity = kg.upsert_entity("Python", entity_type="language", confidence=0.9)
    print(f"Created entity: {entity.name}")
"""

from __future__ import annotations

__version__ = "1.0.0"

# Core classes
from memory.knowledge_graph import KnowledgeGraph, Entity, Relation
from memory.memory_store import MemoryStore, Fact
from memory.entity_extractor import EntityExtractor, ExtractionResult
from memory.retriever import Retriever, RetrievalResult, RetrievalResults, BM25
from memory.indexer import IncrementalIndexer, IndexItem
from memory.wiki_builder import WikiBuilder, WikiPage

__all__ = [
    # Version
    "__version__",
    # Knowledge graph
    "KnowledgeGraph",
    "Entity",
    "Relation",
    # Memory store
    "MemoryStore",
    "Fact",
    # Entity extraction
    "EntityExtractor",
    "ExtractionResult",
    # Retrieval
    "Retriever",
    "RetrievalResult",
    "RetrievalResults",
    "BM25",
    # Indexer
    "IncrementalIndexer",
    "IndexItem",
    # Wiki builder
    "WikiBuilder",
    "WikiPage",
]
