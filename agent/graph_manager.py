#!/usr/bin/env python3
"""
Context Graph Manager — Wraps Graphiti + Kuzu for persistent personal knowledge graph.

Provides temporal entity/relationship/episode storage with semantic search.
Uses Hermes's auxiliary LLM client for graph ingestion (entity extraction,
deduplication, edge detection). Search requires zero LLM calls.

Storage: ~/.hermes/context-graph/kuzu_db/
LLM: Configured via auxiliary.context_graph in cli-config.yaml or
     AUXILIARY_CONTEXT_GRAPH_MODEL / AUXILIARY_CONTEXT_GRAPH_PROVIDER env vars.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphManager:
    """Wrapper around Graphiti + Kuzu for personal context graph operations.

    Lazy-initializes on first use (~1s startup). All public methods are async.
    """

    def __init__(self, db_path: Path, llm_config: Optional[Dict[str, Any]] = None):
        self._db_path = Path(db_path)
        self._llm_config = llm_config or {}
        self._graphiti = None
        self._initialized = False

    async def _ensure_initialized(self):
        """Lazy init — creates Graphiti + Kuzu on first use."""
        if self._initialized:
            return

        try:
            from graphiti_core import Graphiti
            from graphiti_core.driver.kuzu_driver import KuzuDriver
            from graphiti_core.llm_client import OpenAIClient
            from graphiti_core.llm_client.config import LLMConfig
            from graphiti_core.embedder import OpenAIEmbedder
            from graphiti_core.embedder.openai import OpenAIEmbedderConfig
            from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
        except ImportError as e:
            raise RuntimeError(
                f"graphiti-core[kuzu] not installed: {e}. "
                "Install with: pip install 'graphiti-core[kuzu]'"
            ) from e

        # Create DB directory
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Resolve LLM provider via Hermes auxiliary client
        llm_client = self._build_llm_client(LLMConfig, OpenAIClient)
        embedder = self._build_embedder(OpenAIEmbedderConfig, OpenAIEmbedder)
        cross_encoder = self._build_cross_encoder(LLMConfig, OpenAIRerankerClient)

        # Create Kuzu driver (embedded, file-based)
        driver = KuzuDriver(db=str(self._db_path))

        self._graphiti = Graphiti(
            graph_driver=driver,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
            store_raw_episode_content=True,
        )

        # Build indices (idempotent)
        await self._graphiti.build_indices_and_constraints()
        self._initialized = True
        logger.info("Context graph initialized at %s", self._db_path)

    def _build_llm_client(self, LLMConfig, OpenAIClient):
        """Build a Graphiti-compatible LLM client using Hermes's provider chain."""
        provider, model, base_url, api_key = self._resolve_provider()

        config = LLMConfig(
            api_key=api_key or "no-key-required",
            model=model,
            base_url=base_url,
        )

        return OpenAIClient(config=config)

    def _build_cross_encoder(self, LLMConfig, OpenAIRerankerClient):
        """Build a Graphiti-compatible cross-encoder/reranker client."""
        _provider, _model, base_url, api_key = self._resolve_provider()

        config = LLMConfig(
            api_key=api_key or "no-key-required",
            base_url=base_url,
        )

        return OpenAIRerankerClient(config=config)

    def _resolve_embedder_provider(self):
        """Resolve an embedding-capable provider.

        Not all LLM providers support embeddings (e.g. Anthropic doesn't).
        Priority: OpenRouter > OpenAI > Ollama > same as LLM provider.
        """
        # Check env var overrides
        embed_base = os.environ.get("AUXILIARY_CONTEXT_GRAPH_EMBED_BASE_URL", "").strip()
        embed_key = os.environ.get("AUXILIARY_CONTEXT_GRAPH_EMBED_API_KEY", "").strip()
        if embed_base and embed_key:
            return embed_base, embed_key

        # Try OpenRouter (supports embeddings)
        or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if or_key:
            return "https://openrouter.ai/api/v1", or_key

        # Try OpenAI directly (native embedding support)
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            return None, openai_key  # None = default OpenAI URL

        # Ollama (supports embeddings locally)
        provider, _model, base_url, api_key = self._resolve_provider()
        if provider in ("ollama", "lmstudio", "vllm", "llamacpp", "custom"):
            return base_url, api_key or "no-key-required"

        # Anthropic doesn't support embeddings — give a clear error
        if provider == "anthropic":
            raise RuntimeError(
                "Context graph requires an embedding-capable provider (OpenRouter, OpenAI, or Ollama). "
                "Anthropic does not support embeddings. Set OPENROUTER_API_KEY or OPENAI_API_KEY, "
                "or configure auxiliary.context_graph.provider in cli-config.yaml to use Ollama."
            )

        # Fallback: use whatever the LLM provider is
        return base_url, api_key

    def _build_embedder(self, OpenAIEmbedderConfig, OpenAIEmbedder):
        """Build embedder for vector search.

        Routes to an embedding-capable provider (OpenRouter, OpenAI, Ollama).
        Anthropic doesn't support embeddings, so we never route there.
        """
        embed_base_url, embed_api_key = self._resolve_embedder_provider()

        config = OpenAIEmbedderConfig(
            api_key=embed_api_key or "no-key-required",
            base_url=embed_base_url,
            embedding_model="text-embedding-3-small",
        )

        return OpenAIEmbedder(config=config)

    def _resolve_provider(self):
        """Resolve LLM provider/model/base_url/api_key for the context_graph task.

        Priority:
        1. AUXILIARY_CONTEXT_GRAPH_* env vars
        2. cli-config.yaml auxiliary.context_graph.* section
        3. Auto-detection via Hermes provider chain
        """
        # Check env var overrides first
        provider = os.environ.get("AUXILIARY_CONTEXT_GRAPH_PROVIDER", "").strip().lower()
        model = os.environ.get("AUXILIARY_CONTEXT_GRAPH_MODEL", "").strip()
        base_url = os.environ.get("AUXILIARY_CONTEXT_GRAPH_BASE_URL", "").strip()
        api_key = os.environ.get("AUXILIARY_CONTEXT_GRAPH_API_KEY", "").strip()

        # Check config
        aux_config = self._llm_config.get("auxiliary", {})
        if isinstance(aux_config, dict):
            graph_aux = aux_config.get("context_graph", {})
            if isinstance(graph_aux, dict):
                provider = provider or graph_aux.get("provider", "")
                model = model or graph_aux.get("model", "")
                base_url = base_url or graph_aux.get("base_url", "")
                api_key = api_key or graph_aux.get("api_key", "")

        # Handle Ollama / local server aliases
        if provider in ("ollama", "lmstudio", "vllm", "llamacpp"):
            base_url = base_url or "http://localhost:11434/v1"
            api_key = api_key or "no-key-required"
            model = model or "llama3.2"
            return provider, model, base_url, api_key

        # OpenRouter (default cloud path)
        if not provider or provider in ("auto", "openrouter"):
            or_key = api_key or os.environ.get("OPENROUTER_API_KEY", "").strip()
            if or_key:
                return (
                    "openrouter",
                    model or "google/gemini-2.5-flash",
                    base_url or "https://openrouter.ai/api/v1",
                    or_key,
                )

        # Custom endpoint
        if provider == "custom" or base_url:
            api_key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
            return provider or "custom", model, base_url, api_key

        # Anthropic fallback
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if anthropic_key:
            return (
                "anthropic",
                model or "claude-haiku-4-5-20251001",
                base_url or "https://api.anthropic.com/v1",
                anthropic_key,
            )

        # Last resort — try OpenAI key
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if openai_key:
            return "openai", model or "gpt-4o-mini", base_url, openai_key

        raise RuntimeError(
            "No LLM provider configured for context graph. "
            "Set OPENROUTER_API_KEY, AUXILIARY_CONTEXT_GRAPH_PROVIDER, "
            "or configure auxiliary.context_graph in cli-config.yaml"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_episode(
        self,
        content: str,
        source_type: str = "text",
        name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        group_id: str = "personal",
    ) -> Dict[str, Any]:
        """Ingest a text episode into the graph.

        Runs Graphiti's 5-stage pipeline: context retrieval → node resolution
        → attribute extraction → edge extraction → contradiction detection.
        Requires LLM calls (~2-10s).

        Args:
            content: The text to ingest (decision trace, learning, conversation summary)
            source_type: "text", "message", or "json"
            name: Short label for the episode (auto-generated if empty)
            metadata: Optional metadata dict
            group_id: Namespace for the episode (default: "personal")

        Returns:
            Dict with episode info, extracted entities, and edges
        """
        await self._ensure_initialized()

        from graphiti_core.nodes import EpisodeType

        type_map = {
            "text": EpisodeType.text,
            "message": EpisodeType.message,
            "json": EpisodeType.json,
        }
        episode_type = type_map.get(source_type, EpisodeType.text)

        now = datetime.now(timezone.utc)
        episode_name = name or f"episode-{now.strftime('%Y%m%d-%H%M%S')}"
        source_desc = (metadata or {}).get("source_description", "hermes-agent session")

        result = await self._graphiti.add_episode(
            name=episode_name,
            episode_body=content,
            source_description=source_desc,
            reference_time=now,
            source=episode_type,
            group_id=group_id,
        )

        # Serialize result for JSON response
        entities = []
        for node in (result.nodes or []):
            entities.append({
                "uuid": node.uuid,
                "name": node.name,
                "summary": getattr(node, "summary", ""),
            })

        edges = []
        for edge in (result.edges or []):
            edges.append({
                "uuid": edge.uuid,
                "name": edge.name,
                "fact": edge.fact,
                "valid_at": edge.valid_at.isoformat() if edge.valid_at else None,
                "invalid_at": edge.invalid_at.isoformat() if edge.invalid_at else None,
            })

        return {
            "episode_uuid": result.episode.uuid if result.episode else None,
            "entities_extracted": len(entities),
            "edges_extracted": len(edges),
            "entities": entities,
            "edges": edges,
        }

    async def search(
        self,
        query: str,
        limit: int = 10,
        group_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Search the graph. Returns matching edges (facts with temporal validity).

        Pure graph traversal + vector similarity — no LLM calls, ~300ms.

        Args:
            query: Natural language search query
            limit: Maximum results
            group_ids: Filter by namespace(s)

        Returns:
            Dict with matching edges and their connected entities
        """
        await self._ensure_initialized()

        edges = await self._graphiti.search(
            query=query,
            num_results=limit,
            group_ids=group_ids or ["personal"],
        )

        results = []
        for edge in edges:
            results.append({
                "uuid": edge.uuid,
                "name": edge.name,
                "fact": edge.fact,
                "source_node": edge.source_node_uuid,
                "target_node": edge.target_node_uuid,
                "valid_at": edge.valid_at.isoformat() if edge.valid_at else None,
                "invalid_at": edge.invalid_at.isoformat() if edge.invalid_at else None,
                "expired_at": edge.expired_at.isoformat() if getattr(edge, "expired_at", None) else None,
                "episodes": edge.episodes if edge.episodes else [],
            })

        return {
            "query": query,
            "count": len(results),
            "results": results,
        }

    async def get_episodes(
        self,
        last_n: int = 10,
        group_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent episodes from the graph.

        Args:
            last_n: Number of recent episodes to return
            group_ids: Filter by namespace(s)

        Returns:
            List of episode dicts
        """
        await self._ensure_initialized()

        episodes = await self._graphiti.retrieve_episodes(
            reference_time=datetime.now(timezone.utc),
            last_n=last_n,
            group_ids=group_ids or ["personal"],
        )

        results = []
        for ep in episodes:
            results.append({
                "uuid": ep.uuid,
                "name": ep.name,
                "content": ep.content,
                "source": ep.source.value if hasattr(ep.source, "value") else str(ep.source),
                "source_description": ep.source_description,
                "valid_at": ep.valid_at.isoformat() if ep.valid_at else None,
                "created_at": ep.created_at.isoformat() if ep.created_at else None,
            })

        return results

    async def get_nodes_by_episode(
        self,
        episode_uuid: str,
    ) -> Dict[str, Any]:
        """Get all entities and edges extracted from a specific episode.

        Args:
            episode_uuid: UUID of the episode

        Returns:
            Dict with nodes and edges
        """
        await self._ensure_initialized()

        result = await self._graphiti.get_nodes_and_edges_by_episode(episode_uuid)
        nodes = result.get("nodes", []) if isinstance(result, dict) else []
        edges = result.get("edges", []) if isinstance(result, dict) else []

        return {
            "episode_uuid": episode_uuid,
            "nodes": [
                {"uuid": n.uuid, "name": n.name, "summary": getattr(n, "summary", "")}
                for n in nodes
            ],
            "edges": [
                {"uuid": e.uuid, "name": e.name, "fact": e.fact}
                for e in edges
            ],
        }

    async def export_json(self) -> str:
        """Export the full graph as JSON for backup purposes.

        Returns:
            JSON string with all episodes (last 1000)
        """
        await self._ensure_initialized()

        episodes = await self._graphiti.retrieve_episodes(
            reference_time=datetime.now(timezone.utc),
            last_n=1000,
            group_ids=None,
        )

        export = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "db_path": str(self._db_path),
            "episode_count": len(episodes),
            "episodes": [
                {
                    "uuid": ep.uuid,
                    "name": ep.name,
                    "content": ep.content,
                    "source": ep.source.value if hasattr(ep.source, "value") else str(ep.source),
                    "source_description": ep.source_description,
                    "valid_at": ep.valid_at.isoformat() if ep.valid_at else None,
                    "created_at": ep.created_at.isoformat() if ep.created_at else None,
                }
                for ep in episodes
            ],
        }

        return json.dumps(export, indent=2, ensure_ascii=False)

    async def close(self):
        """Close the graph driver and clean up resources."""
        if self._graphiti:
            try:
                await self._graphiti.close()
            except Exception as e:
                logger.debug("Error closing graph: %s", e)
            self._graphiti = None
            self._initialized = False
