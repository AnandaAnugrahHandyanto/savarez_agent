"""hermes-memory-store — holographic memory plugin using MemoryProvider interface.

Registers as a MemoryProvider plugin, giving the agent structured fact storage
with entity resolution, semantic retrieval, explainable ranking, and
related-memory linking.

Original plugin by dusterbloom (PR #2351), adapted to the MemoryProvider ABC.

Config in $HERMES_HOME/config.yaml (profile-scoped):
  plugins:
    hermes-memory-store:
      db_path: $HERMES_HOME/memory_store.db   # omit to use the default
      auto_extract: false
      default_trust: 0.5
      min_trust_threshold: 0.3
      temporal_decay_half_life: 45
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error
from .embeddings import build_embedding_provider
from .ingestion import (
    drain_understanding_ingest,
    ingest_settings,
    queue_session_ingest,
    queue_turn_ingest,
)
from .store import MemoryStore
from .retrieval import FactRetriever

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

FACT_STORE_SCHEMA = {
    "name": "fact_store",
    "description": (
        "Deep structured memory with algebraic reasoning. "
        "Use alongside the memory tool — memory for always-on context, "
        "fact_store for deep recall and compositional queries.\n\n"
        "ACTIONS (simple → powerful):\n"
        "• add — Store a fact the user would expect you to remember.\n"
        "• search — Hybrid recall across keyword, semantic, recency, salience, and confidence.\n"
        "• probe — Entity recall: ALL facts about a person/thing.\n"
        "• related — What connects to an entity? Structural adjacency.\n"
        "• reason — Compositional: facts connected to MULTIPLE entities simultaneously.\n"
        "• contradict — Memory hygiene: find facts making conflicting claims.\n"
        "• update/remove/list — CRUD operations.\n\n"
        "IMPORTANT: Before answering questions about the user, ALWAYS probe or reason first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "search", "probe", "related", "reason", "contradict", "update", "remove", "list"],
            },
            "content": {"type": "string", "description": "Fact content (required for 'add')."},
            "query": {"type": "string", "description": "Search query (required for 'search')."},
            "entity": {"type": "string", "description": "Entity name for 'probe'/'related'."},
            "entities": {"type": "array", "items": {"type": "string"}, "description": "Entity names for 'reason'."},
            "fact_id": {"type": "integer", "description": "Fact ID for 'update'/'remove'."},
            "category": {"type": "string", "enum": ["user_pref", "project", "tool", "general"]},
            "tags": {"type": "string", "description": "Comma-separated tags."},
            "trust_delta": {"type": "number", "description": "Trust adjustment for 'update'."},
            "min_trust": {"type": "number", "description": "Minimum trust filter (default: 0.3)."},
            "limit": {"type": "integer", "description": "Max results (default: 10)."},
            "debug": {"type": "boolean", "description": "Return explain/debug scoring details for search."},
            "source_channel": {"type": "string", "description": "Optional source channel label for add/update."},
            "source_confidence": {"type": "number", "description": "Optional source confidence override for add/update."},
            "intent_type": {"type": "string", "description": "Optional intent/type override for add/update."},
            "salience_score": {"type": "number", "description": "Optional salience override for add/update."},
        },
        "required": ["action"],
    },
}

FACT_FEEDBACK_SCHEMA = {
    "name": "fact_feedback",
    "description": (
        "Rate a fact after using it. Mark 'helpful' if accurate, 'unhelpful' if outdated. "
        "This trains the memory — good facts rise, bad facts sink."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["helpful", "unhelpful"]},
            "fact_id": {"type": "integer", "description": "The fact ID to rate."},
        },
        "required": ["action", "fact_id"],
    },
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_plugin_config() -> dict:
    from hermes_constants import get_hermes_home
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path) as f:
            all_config = yaml.safe_load(f) or {}
        return all_config.get("plugins", {}).get("hermes-memory-store", {}) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class HolographicMemoryProvider(MemoryProvider):
    """Holographic memory with structured enrichment and explainable retrieval."""

    def __init__(self, config: dict | None = None):
        self._config = config or _load_plugin_config()
        self._store = None
        self._retriever = None
        self._min_trust = float(self._config.get("min_trust_threshold", 0.3))
        self._ingest_settings = ingest_settings(self._config)
        self._session_id = ""
        self._write_enabled = True

    @property
    def name(self) -> str:
        return "holographic"

    def is_available(self) -> bool:
        return True  # SQLite is always available, numpy is optional

    def save_config(self, values, hermes_home):
        """Write config to config.yaml under plugins.hermes-memory-store."""
        from pathlib import Path
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing = {}
            if config_path.exists():
                with open(config_path) as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["hermes-memory-store"] = values
            with open(config_path, "w") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception:
            pass

    def get_config_schema(self):
        from hermes_constants import display_hermes_home
        _default_db = f"{display_hermes_home()}/memory_store.db"
        return [
            {"key": "db_path", "description": "SQLite database path", "default": _default_db},
            {"key": "auto_extract", "description": "Auto-extract facts at session end", "default": "false", "choices": ["true", "false"]},
            {"key": "deferred_ingest", "description": "Enable bounded deferred understanding ingestion", "default": "true", "choices": ["true", "false"]},
            {"key": "turn_understanding", "description": "Extract understanding from user turns", "default": "true", "choices": ["true", "false"]},
            {"key": "ingest_batch_size", "description": "Deferred ingest batch size", "default": "2"},
            {"key": "ingest_max_pending", "description": "Max queued deferred ingest items", "default": "200"},
            {"key": "ingest_retry_delay_seconds", "description": "Base retry delay for failed ingest", "default": "60"},
            {"key": "session_ingest_message_limit", "description": "Max session messages captured for deferred session ingest", "default": "80"},
            {"key": "default_trust", "description": "Default trust score for new facts", "default": "0.5"},
            {"key": "hrr_dim", "description": "HRR vector dimensions", "default": "1024"},
            {"key": "link_threshold", "description": "Related-memory link threshold", "default": "0.36"},
            {"key": "temporal_decay_half_life", "description": "Recency half-life in days", "default": "45"},
            {"key": "semantic_provider", "description": "Semantic embedding provider", "default": "none", "choices": ["none", "openai"]},
            {"key": "semantic_model", "description": "Embedding model", "default": "text-embedding-3-small", "when": {"semantic_provider": "openai"}},
            {"key": "semantic_dimensions", "description": "Embedding dimensions (optional)", "default": "1536", "when": {"semantic_provider": "openai"}},
            {"key": "semantic_base_url", "description": "OpenAI-compatible base URL (optional)", "default": "", "when": {"semantic_provider": "openai"}},
            {"key": "semantic_api_key", "description": "Embedding API key", "secret": True, "env_var": "HOLOGRAPHIC_OPENAI_API_KEY", "when": {"semantic_provider": "openai"}},
            {"key": "rank_semantic_weight", "description": "Ranking weight: semantic", "default": "0.35"},
            {"key": "rank_keyword_weight", "description": "Ranking weight: keyword", "default": "0.25"},
            {"key": "rank_recency_weight", "description": "Ranking weight: recency", "default": "0.15"},
            {"key": "rank_salience_weight", "description": "Ranking weight: salience", "default": "0.15"},
            {"key": "rank_confidence_weight", "description": "Ranking weight: confidence", "default": "0.10"},
        ]

    def initialize(self, session_id: str, **kwargs) -> None:
        from hermes_constants import get_hermes_home
        _hermes_home = str(get_hermes_home())
        _default_db = _hermes_home + "/memory_store.db"
        db_path = self._config.get("db_path", _default_db)
        # Expand $HERMES_HOME in user-supplied paths so config values like
        # "$HERMES_HOME/memory_store.db" or "~/.hermes/memory_store.db" both
        # resolve to the active profile's directory.
        if isinstance(db_path, str):
            db_path = db_path.replace("$HERMES_HOME", _hermes_home)
            db_path = db_path.replace("${HERMES_HOME}", _hermes_home)
        default_trust = float(self._config.get("default_trust", 0.5))
        hrr_dim = int(self._config.get("hrr_dim", 1024))
        temporal_decay = int(self._config.get("temporal_decay_half_life", 45))
        embedder = build_embedding_provider(self._config)

        self._store = MemoryStore(
            db_path=db_path,
            default_trust=default_trust,
            hrr_dim=hrr_dim,
            embedding_provider=embedder,
            link_threshold=float(self._config.get("link_threshold", 0.36)),
        )
        self._retriever = FactRetriever(
            store=self._store,
            temporal_decay_half_life=temporal_decay,
            hrr_dim=hrr_dim,
            semantic_weight=float(self._config.get("rank_semantic_weight", 0.35)),
            keyword_weight=float(self._config.get("rank_keyword_weight", 0.25)),
            recency_weight=float(self._config.get("rank_recency_weight", 0.15)),
            salience_weight=float(self._config.get("rank_salience_weight", 0.15)),
            confidence_weight=float(self._config.get("rank_confidence_weight", 0.10)),
        )
        self._ingest_settings = ingest_settings(self._config)
        self._session_id = session_id
        agent_context = kwargs.get("agent_context", "")
        platform = kwargs.get("platform", "")
        self._write_enabled = agent_context not in ("cron", "flush", "subagent") and platform != "cron"

    def system_prompt_block(self) -> str:
        if not self._store:
            return ""
        try:
            total = self._store._conn.execute(
                "SELECT COUNT(*) FROM facts"
            ).fetchone()[0]
        except Exception:
            total = 0
        if total == 0:
            return (
                "# Holographic Memory\n"
                "Active. Empty understanding index.\n"
                "Use fact_store(action='add') to store durable facts about people, projects, preferences, decisions, and incidents.\n"
                "Use fact_store(action='search', debug=true) for explainable recall diagnostics.\n"
                "Use fact_feedback to rate facts after using them (trains trust scores)."
            )
        return (
            f"# Holographic Memory\n"
            f"Active. {total} facts stored with structured enrichment, semantic retrieval, and trust scoring.\n"
            f"Use fact_store to search, probe entities, reason across entities, or add facts.\n"
            f"Use fact_feedback to rate facts after using them (trains trust scores)."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._retriever or not query:
            return ""
        try:
            if self._store and self._ingest_settings.get("deferred_ingest"):
                drain_understanding_ingest(
                    self._store,
                    self._config,
                    limit=1,
                    reason="prefetch",
                )
            results = self._retriever.search(query, min_trust=self._min_trust, limit=5)
            if not results:
                return ""
            lines = []
            for r in results:
                score = r.get("score", 0.0)
                topics = ", ".join(r.get("metadata", {}).get("topics", [])[:3])
                suffix = f" ({topics})" if topics else ""
                lines.append(f"- [{score:.2f}] {r.get('content', '')}{suffix}")
            return "## Holographic Memory\n" + "\n".join(lines)
        except Exception as e:
            logger.debug("Holographic prefetch failed: %s", e)
            return ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if not self._store or not self._write_enabled:
            return
        try:
            result = queue_turn_ingest(
                self._store,
                self._config,
                session_id=session_id or self._session_id,
                user_content=user_content,
                assistant_content=assistant_content,
            )
            if result.get("reason") == "queue_full":
                logger.warning(
                    "Holographic deferred ingest queue full for session %s",
                    session_id or self._session_id,
                )
        except Exception as exc:
            logger.debug("Holographic sync_turn enqueue failed: %s", exc)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if not self._store or not self._ingest_settings.get("deferred_ingest"):
            return
        try:
            drain_understanding_ingest(
                self._store,
                self._config,
                reason="queue_prefetch",
            )
        except Exception as exc:
            logger.debug("Holographic deferred ingest drain failed: %s", exc)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [FACT_STORE_SCHEMA, FACT_FEEDBACK_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name == "fact_store":
            return self._handle_fact_store(args)
        elif tool_name == "fact_feedback":
            return self._handle_fact_feedback(args)
        return tool_error(f"Unknown tool: {tool_name}")

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not self._store or not self._write_enabled:
            return
        if self._config.get("auto_extract", False) and messages:
            try:
                queue_session_ingest(
                    self._store,
                    self._config,
                    session_id=self._session_id,
                    messages=messages,
                )
            except Exception as exc:
                logger.debug("Holographic session ingest enqueue failed: %s", exc)

        if not self._ingest_settings.get("deferred_ingest"):
            return
        try:
            drain_understanding_ingest(
                self._store,
                self._config,
                limit=max(self._ingest_settings.get("ingest_batch_size", 2), 4),
                reason="session_end",
            )
        except Exception as exc:
            logger.debug("Holographic session-end drain failed: %s", exc)

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        """Mirror built-in memory writes as facts."""
        if action == "add" and self._store and self._write_enabled and content:
            try:
                category = "user_pref" if target == "user" else "general"
                self._store.add_fact(
                    content,
                    category=category,
                    source_channel=f"builtin:{target}",
                )
            except Exception as e:
                logger.debug("Holographic memory_write mirror failed: %s", e)

    def shutdown(self) -> None:
        if self._store:
            try:
                if self._ingest_settings.get("deferred_ingest"):
                    drain_understanding_ingest(
                        self._store,
                        self._config,
                        limit=max(self._ingest_settings.get("ingest_batch_size", 2), 4),
                        reason="shutdown",
                    )
                self._store.close()
            except Exception:
                pass
        self._store = None
        self._retriever = None

    # -- Tool handlers -------------------------------------------------------

    def _handle_fact_store(self, args: dict) -> str:
        try:
            action = args["action"]
            store = self._store
            retriever = self._retriever

            if action == "add":
                fact_id = store.add_fact(
                    args["content"],
                    category=args.get("category", "general"),
                    tags=args.get("tags", ""),
                    source_channel=args.get("source_channel", "tool:fact_store"),
                    source_confidence=float(args["source_confidence"]) if "source_confidence" in args else None,
                    intent_type=args.get("intent_type"),
                    salience_score=float(args["salience_score"]) if "salience_score" in args else None,
                )
                return json.dumps({"fact_id": fact_id, "status": "added"})

            elif action == "search":
                results = retriever.search(
                    args["query"],
                    category=args.get("category"),
                    min_trust=float(args.get("min_trust", self._min_trust)),
                    limit=int(args.get("limit", 10)),
                    debug=bool(args.get("debug", False)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "probe":
                results = retriever.probe(
                    args["entity"],
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "related":
                results = retriever.related(
                    args["entity"],
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "reason":
                entities = args.get("entities", [])
                if not entities:
                    return tool_error("reason requires 'entities' list")
                results = retriever.reason(
                    entities,
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "contradict":
                results = retriever.contradict(
                    category=args.get("category"),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"results": results, "count": len(results)})

            elif action == "update":
                updated = store.update_fact(
                    int(args["fact_id"]),
                    content=args.get("content"),
                    trust_delta=float(args["trust_delta"]) if "trust_delta" in args else None,
                    tags=args.get("tags"),
                    category=args.get("category"),
                    source_channel=args.get("source_channel"),
                    source_confidence=float(args["source_confidence"]) if "source_confidence" in args else None,
                    intent_type=args.get("intent_type"),
                    salience_score=float(args["salience_score"]) if "salience_score" in args else None,
                )
                return json.dumps({"updated": updated})

            elif action == "remove":
                removed = store.remove_fact(int(args["fact_id"]))
                return json.dumps({"removed": removed})

            elif action == "list":
                facts = store.list_facts(
                    category=args.get("category"),
                    min_trust=float(args.get("min_trust", 0.0)),
                    limit=int(args.get("limit", 10)),
                )
                return json.dumps({"facts": facts, "count": len(facts)})

            else:
                return tool_error(f"Unknown action: {action}")

        except KeyError as exc:
            return tool_error(f"Missing required argument: {exc}")
        except Exception as exc:
            return tool_error(str(exc))

    def _handle_fact_feedback(self, args: dict) -> str:
        try:
            fact_id = int(args["fact_id"])
            helpful = args["action"] == "helpful"
            result = self._store.record_feedback(fact_id, helpful=helpful)
            return json.dumps(result)
        except KeyError as exc:
            return tool_error(f"Missing required argument: {exc}")
        except Exception as exc:
            return tool_error(str(exc))

# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register the holographic memory provider with the plugin system."""
    config = _load_plugin_config()
    provider = HolographicMemoryProvider(config=config)
    ctx.register_memory_provider(provider)
