#!/usr/bin/env python3
"""
HermesMemory MCP Server
======================

MCP tools for Hermes agent to interact with HermesMemory.

Tools:
- hermes_status: Overview of the memory system
- hermes_search: Semantic search across all memories
- hermes_remember: Store important information
- hermes_forget: Remove information
- hermes_list: List all wings/rooms
- hermes_facts: Query the knowledge graph
"""

import json
import os
import chromadb
from pathlib import Path
from typing import Optional

# Default palace path
DEFAULT_PALACE = os.path.expanduser("~/.hermes/memory")

# =============================================================================
# CHROMA DB HELPERS
# =============================================================================


def _get_client(palace_path: str = DEFAULT_PALACE):
    os.makedirs(palace_path, exist_ok=True)
    return chromadb.PersistentClient(path=palace_path)


def _get_collection(palace_path: str = DEFAULT_PALACE, name: str = "hermes_drawers"):
    client = _get_client(palace_path)
    try:
        return client.get_collection(name)
    except Exception:
        return client.create_collection(name)


# =============================================================================
# MCP TOOLS
# =============================================================================


def hermes_status(palace_path: str = DEFAULT_PALACE) -> dict:
    """Get overview of the HermesMemory system."""
    try:
        client = _get_client(palace_path)
        collections = client.list_collections()
        stats = {
            "palace_path": palace_path,
            "collections": len(collections),
            "total_memories": 0,
        }
        for col_info in collections:
            col = client.get_collection(col_info.name)
            try:
                count = col.count()
                stats["total_memories"] += count
                stats[col_info.name] = count
            except Exception:
                pass
        return {"status": "ok", "stats": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def hermes_search(
    query: str,
    palace_path: str = DEFAULT_PALACE,
    collection: str = "hermes_drawers",
    n_results: int = 5,
    wing: Optional[str] = None,
    room: Optional[str] = None,
) -> dict:
    """
    Search the memory system.
    
    This uses HermesMemory's dual-retriever (BM25 + semantic) when available,
    falling back to ChromaDB's built-in semantic search.
    """
    try:
        col = _get_collection(palace_path, collection)
        
        # Build metadata filter
        where_filter = {}
        if wing and room:
            where_filter = {"$and": [{"wing": wing}, {"room": room}]}
        elif wing:
            where_filter = {"wing": wing}
        elif room:
            where_filter = {"room": room}
        
        kwargs = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter
        
        results = col.query(**kwargs)
        
        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "wing": meta.get("wing", "unknown"),
                "room": meta.get("room", "unknown"),
                "source": meta.get("source_file", "unknown"),
                "similarity": round(1 - dist, 3),
            })
        
        return {
            "query": query,
            "results": hits,
            "count": len(hits),
        }
    except Exception as e:
        return {"query": query, "results": [], "error": str(e)}


def hermes_remember(
    text: str,
    wing: str,
    room: str,
    source_file: str = "manual",
    palace_path: str = DEFAULT_PALACE,
    collection: str = "hermes_drawers",
) -> dict:
    """Store information in memory."""
    import uuid
    import datetime
    
    try:
        col = _get_collection(palace_path, collection)
        
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        metadata = {
            "wing": wing,
            "room": room,
            "source_file": source_file,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        
        col.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[metadata],
        )
        
        return {
            "status": "stored",
            "id": doc_id,
            "wing": wing,
            "room": room,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def hermes_forget(
    doc_id: str,
    palace_path: str = DEFAULT_PALACE,
    collection: str = "hermes_drawers",
) -> dict:
    """Remove a memory by ID."""
    try:
        col = _get_collection(palace_path, collection)
        col.delete(ids=[doc_id])
        return {"status": "deleted", "id": doc_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def hermes_list(
    palace_path: str = DEFAULT_PALACE,
    collection: str = "hermes_drawers",
    by: str = "wing",  # "wing" or "room"
) -> dict:
    """List all wings or rooms."""
    try:
        col = _get_collection(palace_path, collection)
        
        # Get unique values by using get with empty query
        # We'll use a workaround since ChromaDB doesn't have GROUP BY
        all_data = col.get(include=["metadatas"])
        
        values = set()
        for meta in all_data["metadatas"]:
            val = meta.get(by, "unknown")
            values.add(val)
        
        return {
            by: sorted(list(values)),
            "count": len(values),
        }
    except Exception as e:
        return {by: [], "error": str(e)}


def hermes_facts(
    entity: str,
    palace_path: str = DEFAULT_PALACe,
    collection: str = "hermes_kg",
) -> dict:
    """
    Query facts about an entity from the knowledge graph.
    
    Note: This requires the knowledge_graph collection to be set up.
    """
    try:
        client = _get_client(palace_path)
        col = client.get_collection(collection)
        
        results = col.get(
            where={"subject": entity},
            include=["documents", "metadatas"],
        )
        
        facts = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            facts.append({
                "subject": meta.get("subject", entity),
                "predicate": meta.get("predicate", "unknown"),
                "object": meta.get("object", doc),
                "valid_from": meta.get("valid_from"),
                "valid_to": meta.get("valid_to"),
            })
        
        return {
            "entity": entity,
            "facts": facts,
            "count": len(facts),
        }
    except Exception as e:
        return {"entity": entity, "facts": [], "error": str(e)}


# =============================================================================
# CLI
# =============================================================================


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="HermesMemory MCP Server")
    parser.add_argument("--palace", default=DEFAULT_PALACE, help="Palace path")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    
    args = parser.parse_args()
    
    print(f"HermesMemory MCP Server")
    print(f"  Palace: {args.palace}")
    print(f"  Port: {args.port}")
    print(f"  Use: claude mcp add hermes-memory -- python -m hermes_memory.mcp_server --palace {args.palace}")
