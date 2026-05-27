"""Enhanced Memory — two-tier fact store with condensation and semantic search.

A Hermes Agent MemoryProvider plugin that provides:
- Two-tier fact storage: raw_facts → condenser → condensed
- FTS5 full-text search on both tiers
- Optional Gemini-powered semantic vector search (sqlite-vec)
- Automatic fact extraction from conversations
- Priority-based memory condensation

Config in $HERMES_HOME/config.yaml:
  memory:
    provider: enhanced-memory

  plugins:
    enhanced-memory:
      db_path: $HERMES_HOME/memory_store.db
      auto_extract: true
      auto_condense: true
      semantic_search: true
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error
from hermes_cli.config import cfg_get

from .store import EnhancedMemoryStore
from .condenser import FactCondenser

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

ENHANCED_MEMORY_SCHEMA = {
    "name": "enhanced_memory",
    "description": (
        "Two-tier persistent memory with condensation and semantic search. "
        "Stores facts across sessions, automatically groups and deduplicates them.\n\n"
        "ACTIONS:\n"
        "• add — Store a fact (preference, decision, env detail, project info).\n"
        "• search — FTS5 keyword search across all facts.\n"
        "• semantic_search — Find facts by MEANING (cross-language, synonym-aware). "
        "Configurable: Gemini, OpenAI, or local sentence-transformers.\n"
        "• condense — Run the condensation pipeline: group, deduplicate, prioritize.\n"
        "• list_condensed — View condensed memory entries sorted by priority.\n"
        "• stats — Memory statistics (counts, categories, index status).\n\n"
        "CATEGORIES: user_pref, project, tool, env, decision, security, general.\n\n"
        "WHEN TO USE:\n"
        "- User shares preferences or corrections → add with category 'user_pref'\n"
        "- You discover env/tool details → add with 'tool' or 'env'\n"
        "- Need context about the user → semantic_search first, then search\n"
        "- After long sessions → condense to compress facts"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "search", "semantic_search", "condense", "list_condensed", "stats"],
                "description": "Action to perform.",
            },
            "content": {
                "type": "string",
                "description": "Fact content (required for 'add').",
            },
            "query": {
                "type": "string",
                "description": "Search query (required for 'search' and 'semantic_search').",
            },
            "category": {
                "type": "string",
                "enum": ["user_pref", "project", "tool", "env", "decision", "security", "general"],
                "description": "Fact category. Default: 'general'.",
            },
            "source": {
                "type": "string",
                "description": "Fact source: 'dialog', 'manual', 'auto_extract'. Default: 'dialog'.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results for search (default: 10).",
            },
            "dry_run": {
                "type": "boolean",
                "description": "For 'condense': preview without writing. Default: false.",
            },
        },
        "required": ["action"],
    },
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_plugin_config() -> dict:
    """Load plugin config from config.yaml."""
    try:
        from hermes_constants import get_hermes_home
        config_path = get_hermes_home() / "config.yaml"
    except Exception:
        from pathlib import Path
        config_path = Path.home() / ".hermes" / "config.yaml"

    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path, encoding="utf-8-sig") as f:
            all_config = yaml.safe_load(f) or {}
        return cfg_get(all_config, "plugins", "enhanced-memory", default={}) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class EnhancedMemoryProvider(MemoryProvider):
    """Two-tier memory with condensation and optional semantic vector search."""

    def __init__(self, config: dict | None = None):
        self._config = config or _load_plugin_config()
        self._store: Optional[EnhancedMemoryStore] = None
        self._condenser: Optional[FactCondenser] = None
        self._semantic: Optional[Any] = None  # SemanticSearch, lazy-loaded
        self._session_id: str = ""
        self._session_turns: int = 0
        self._auto_extract: bool = bool(self._config.get("auto_extract", True))
        self._auto_condense: bool = bool(self._config.get("auto_condense", True))
        self._semantic_enabled: bool = bool(self._config.get("semantic_search", True))

    @property
    def name(self) -> str:
        return "enhanced-memory"

    def is_available(self) -> bool:
        """Always available — SQLite is stdlib. Semantic search degrades gracefully."""
        return True

    def get_config_schema(self) -> list:
        try:
            from hermes_constants import display_hermes_home
            _default_db = f"{display_hermes_home()}/memory_store.db"
        except Exception:
            _default_db = "~/.hermes/memory_store.db"
        return [
            {"key": "db_path", "description": "SQLite database path", "default": _default_db},
            {"key": "auto_extract", "description": "Auto-extract facts from conversations at session end",
             "default": "true", "choices": ["true", "false"]},
            {"key": "auto_condense", "description": "Auto-condense facts periodically",
             "default": "true", "choices": ["true", "false"]},
            {"key": "semantic_search", "description": "Enable semantic vector search",
             "default": "true", "choices": ["true", "false"]},
            {"key": "embedding_provider", "description": "Embedding provider: gemini, openai, local, none",
             "default": "gemini", "choices": ["gemini", "openai", "openai-large", "local", "local-multilingual", "none"]},
            {"key": "embedding_model", "description": "Embedding model name (provider-specific)",
             "default": "(auto from provider)"},
            {"key": "embedding_dims", "description": "Embedding dimensions (auto from provider, override if needed)",
             "default": "(auto)"},
            {"key": "embedding_device", "description": "Device for local models: cpu, cuda, mps",
             "default": "cpu", "choices": ["cpu", "cuda", "mps"]},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write config to config.yaml under plugins.enhanced-memory."""
        from pathlib import Path
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing = {}
            if config_path.exists():
                with open(config_path, encoding="utf-8-sig") as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["enhanced-memory"] = values
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception as e:
            logger.warning("Failed to save enhanced-memory config: %s", e)

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize store, condenser, and optional semantic search."""
        try:
            from hermes_constants import get_hermes_home
            _hermes_home = str(get_hermes_home())
        except Exception:
            from pathlib import Path
            _hermes_home = str(Path.home() / ".hermes")

        _default_db = _hermes_home + "/memory_store.db"
        db_path = self._config.get("db_path", _default_db)
        if isinstance(db_path, str):
            db_path = db_path.replace("$HERMES_HOME", _hermes_home)
            db_path = db_path.replace("${HERMES_HOME}", _hermes_home)

        self._store = EnhancedMemoryStore(db_path=db_path)
        self._condenser = FactCondenser(self._store)
        self._session_id = session_id
        self._session_turns = 0

        # Lazy-init semantic search
        if self._semantic_enabled:
            self._init_semantic(db_path)

        logger.info("Enhanced memory initialized: %s", db_path)

    def _init_semantic(self, db_path: str) -> None:
        """Try to initialize semantic search. Fail gracefully."""
        try:
            from .embeddings import SemanticSearch
            self._semantic = SemanticSearch(db_path=db_path, config=self._config)
            if not self._semantic.is_available():
                pname = self._semantic.provider_name
                logger.info("Semantic search unavailable (provider=%s)", pname)
                self._semantic = None
        except ImportError:
            logger.debug("sqlite-vec not installed, semantic search disabled")
            self._semantic = None
        except Exception as e:
            logger.debug("Semantic search init failed: %s", e)
            self._semantic = None

    def system_prompt_block(self) -> str:
        """Return status text for the system prompt."""
        if not self._store:
            return ""
        try:
            s = self._store.stats()
            raw = s.get("raw_total", 0)
            condensed = s.get("condensed_total", 0)
            semantic = "enabled" if self._semantic else "disabled"

            return (
                "# Enhanced Memory\n"
                f"Active. {raw} raw facts, {condensed} condensed entries. "
                f"Semantic search: {semantic}.\n"
                "Use enhanced_memory tool to add/search facts, run condensation, "
                "or perform semantic search."
            )
        except Exception:
            return "# Enhanced Memory\nActive."

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall relevant facts for the upcoming turn."""
        if not self._store or not query:
            return ""

        results = []

        # 1. Try semantic search first (best quality)
        if self._semantic:
            try:
                sem_results = self._semantic.search(query, k=3)
                for r in sem_results:
                    fact_id = r["fact_id"]
                    # Resolve content
                    if fact_id < -10000:
                        real_id = -(fact_id + 10000)
                        c = self._store.get_condensed_by_id(real_id)
                        if c:
                            results.append(f"- [condensed] {c['summary'][:200]}")
                    else:
                        rf = self._store.get_raw_by_id(fact_id)
                        if rf:
                            results.append(f"- {rf['content'][:200]}")
            except Exception as e:
                logger.debug("Semantic prefetch failed: %s", e)

        # 2. Fallback/supplement with FTS5
        try:
            # Search condensed first (higher signal)
            condensed = self._store.search_condensed(query=query, limit=3)
            for c in condensed:
                line = f"- [{c.get('category', '')}] {c['summary'][:200]}"
                if line not in results:
                    results.append(line)

            # Then raw facts
            if len(results) < 5:
                raw = self._store.search_raw(query, limit=3)
                for r in raw:
                    line = f"- {r['content'][:200]}"
                    if line not in results:
                        results.append(line)
        except Exception as e:
            logger.debug("FTS prefetch failed: %s", e)

        if not results:
            return ""

        return "## Enhanced Memory Recall\n" + "\n".join(results[:5])

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Track turns for periodic condensation."""
        self._session_turns += 1

        # Auto-condense every 20 turns
        if self._auto_condense and self._session_turns % 20 == 0:
            try:
                uncondensed = self._store.stats().get("raw_uncondensed", 0)
                if uncondensed > 10:
                    self._condenser.condense()
                    logger.info("Auto-condensed %d facts", uncondensed)
            except Exception as e:
                logger.debug("Auto-condense failed: %s", e)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [ENHANCED_MEMORY_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != "enhanced_memory":
            return tool_error(f"Unknown tool: {tool_name}")
        return self._handle_enhanced_memory(args)

    # -- Optional hooks -------------------------------------------------------

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Extract facts from conversation at session end."""
        if not self._auto_extract or not self._store or not messages:
            return
        self._auto_extract_facts(messages)

        # Also condense if there are enough uncondensed facts
        if self._auto_condense:
            try:
                uncondensed = self._store.stats().get("raw_uncondensed", 0)
                if uncondensed > 5:
                    self._condenser.condense()
                    # Re-index for semantic search
                    if self._semantic:
                        self._index_new_facts()
            except Exception as e:
                logger.debug("Session-end condense failed: %s", e)

    def on_memory_write(self, action: str, target: str, content: str,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mirror built-in memory writes as raw facts."""
        if action == "add" and self._store and content:
            try:
                category = "user_pref" if target == "user" else "general"
                self._store.add_raw_fact(
                    content, category=category, source="memory_write",
                    session_id=self._session_id
                )
            except Exception as e:
                logger.debug("Memory write mirror failed: %s", e)

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        """Extract facts before context compression discards messages."""
        if not self._store or not messages:
            return ""
        count = self._auto_extract_facts(messages)
        if count > 0:
            return f"[Enhanced Memory extracted {count} facts before compression]"
        return ""

    def on_session_switch(self, new_session_id: str, *,
                          parent_session_id: str = "", reset: bool = False,
                          **kwargs) -> None:
        """Update session tracking on switch."""
        self._session_id = new_session_id
        if reset:
            self._session_turns = 0

    def shutdown(self) -> None:
        """Clean shutdown."""
        self._store = None
        self._condenser = None
        self._semantic = None

    # -- Tool handler ---------------------------------------------------------

    def _handle_enhanced_memory(self, args: dict) -> str:
        try:
            action = args["action"]

            if action == "add":
                content = args.get("content", "")
                if not content:
                    return tool_error("'content' is required for 'add' action")
                fact_id = self._store.add_raw_fact(
                    content,
                    category=args.get("category", "general"),
                    source=args.get("source", "dialog"),
                    session_id=self._session_id,
                )
                # Index for semantic search
                if self._semantic:
                    try:
                        self._semantic.index_facts(
                            [{"id": fact_id, "content": content}],
                            source_table="raw_facts"
                        )
                    except Exception:
                        pass
                return json.dumps({"fact_id": fact_id, "status": "added"})

            elif action == "search":
                query = args.get("query", "")
                if not query:
                    return tool_error("'query' is required for 'search' action")
                limit = int(args.get("limit", 10))

                # Search both tiers
                raw_results = self._store.search_raw(query, limit=limit)
                condensed_results = self._store.search_condensed(
                    query=query, limit=limit
                )

                return json.dumps({
                    "raw_facts": raw_results,
                    "condensed": condensed_results,
                    "total": len(raw_results) + len(condensed_results),
                })

            elif action == "semantic_search":
                query = args.get("query", "")
                if not query:
                    return tool_error("'query' is required for 'semantic_search'")
                if not self._semantic:
                    return json.dumps({
                        "error": "Semantic search unavailable. Check: sqlite-vec installed, "
                                 "embedding provider configured, and required API key set.",
                        "fallback": "Use 'search' action for FTS5 keyword search instead."
                    })

                k = int(args.get("limit", 5))
                results = self._semantic.search(query, k=k)

                # Resolve fact content
                enriched = []
                for r in results:
                    fact_id = r["fact_id"]
                    entry = {"distance": r["distance"], "similarity": r["similarity"]}

                    if fact_id < -10000:
                        real_id = -(fact_id + 10000)
                        c = self._store.get_condensed_by_id(real_id)
                        if c:
                            entry.update({
                                "source": "condensed", "id": real_id,
                                "topic": c["topic"], "content": c["summary"],
                                "category": c["category"], "priority": c["priority"],
                            })
                    else:
                        rf = self._store.get_raw_by_id(fact_id)
                        if rf:
                            entry.update({
                                "source": "raw_facts", "id": fact_id,
                                "content": rf["content"],
                                "category": rf["category"],
                            })

                    if "content" in entry:
                        enriched.append(entry)

                return json.dumps({"results": enriched, "count": len(enriched)})

            elif action == "condense":
                dry_run = bool(args.get("dry_run", False))
                entries = self._condenser.condense(dry_run=dry_run)

                # Re-index after condensation
                if not dry_run and self._semantic:
                    try:
                        self._index_new_facts()
                    except Exception:
                        pass

                return json.dumps({
                    "entries": [
                        {"topic": e["topic"], "category": e["category"],
                         "priority": e["priority"],
                         "fact_count": len(e.get("source_ids", [])),
                         "action": e.get("action", "unknown")}
                        for e in entries
                    ],
                    "count": len(entries),
                    "dry_run": dry_run,
                })

            elif action == "list_condensed":
                category = args.get("category")
                limit = int(args.get("limit", 20))
                results = self._store.search_condensed(
                    category=category, limit=limit
                )
                return json.dumps({"condensed": results, "count": len(results)})

            elif action == "stats":
                store_stats = self._store.stats()
                result = {
                    "raw_facts": store_stats.get("raw_facts", {}),
                    "condensed": store_stats.get("condensed", {}),
                    "semantic_search": {
                        "enabled": self._semantic is not None,
                        "stats": self._semantic.stats() if self._semantic else None,
                    },
                }
                return json.dumps(result)

            else:
                return tool_error(f"Unknown action: {action}")

        except KeyError as exc:
            return tool_error(f"Missing required argument: {exc}")
        except Exception as exc:
            logger.exception("Enhanced memory tool error")
            return tool_error(str(exc))

    # -- Auto-extraction from conversations -----------------------------------

    def _auto_extract_facts(self, messages: list) -> int:
        """Extract facts from conversation messages using pattern matching."""
        _PREF_PATTERNS = [
            re.compile(r'\bI\s+(?:prefer|like|love|use|want|need)\s+(.+)', re.IGNORECASE),
            re.compile(r'\bmy\s+(?:favorite|preferred|default)\s+\w+\s+is\s+(.+)', re.IGNORECASE),
            re.compile(r'\bI\s+(?:always|never|usually)\s+(.+)', re.IGNORECASE),
            # Russian patterns
            re.compile(r'\bя\s+(?:предпочитаю|люблю|использую|хочу)\s+(.+)', re.IGNORECASE),
            re.compile(r'\bмой\s+(?:любимый|предпочтительный)\s+\w+\s+(?:—|это)\s+(.+)', re.IGNORECASE),
        ]
        _DECISION_PATTERNS = [
            re.compile(r'\bwe\s+(?:decided|agreed|chose)\s+(?:to\s+)?(.+)', re.IGNORECASE),
            re.compile(r'\bthe\s+project\s+(?:uses|needs|requires)\s+(.+)', re.IGNORECASE),
            # Russian
            re.compile(r'\bмы\s+(?:решили|выбрали|договорились)\s+(.+)', re.IGNORECASE),
            re.compile(r'\bпроект\s+(?:использует|требует)\s+(.+)', re.IGNORECASE),
        ]
        _ENV_PATTERNS = [
            re.compile(r'\b(?:running|installed|configured|using)\s+(.+?\s+(?:version|v\d))', re.IGNORECASE),
            re.compile(r'\b(?:OS|server|machine)\s+(?:is|runs)\s+(.+)', re.IGNORECASE),
        ]

        extracted = 0
        seen = set()

        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            if not isinstance(content, str) or len(content) < 10:
                continue

            # Skip if we've seen very similar content
            norm = content[:100].lower().strip()
            if norm in seen:
                continue
            seen.add(norm)

            for pattern in _PREF_PATTERNS:
                if pattern.search(content):
                    try:
                        self._store.add_raw_fact(
                            content[:400], category="user_pref",
                            source="auto_extract", session_id=self._session_id
                        )
                        extracted += 1
                    except Exception:
                        pass
                    break

            for pattern in _DECISION_PATTERNS:
                if pattern.search(content):
                    try:
                        self._store.add_raw_fact(
                            content[:400], category="decision",
                            source="auto_extract", session_id=self._session_id
                        )
                        extracted += 1
                    except Exception:
                        pass
                    break

            for pattern in _ENV_PATTERNS:
                if pattern.search(content):
                    try:
                        self._store.add_raw_fact(
                            content[:400], category="env",
                            source="auto_extract", session_id=self._session_id
                        )
                        extracted += 1
                    except Exception:
                        pass
                    break

        if extracted:
            logger.info("Auto-extracted %d facts from conversation", extracted)
        return extracted

    # -- Semantic indexing helper ----------------------------------------------

    def _index_new_facts(self) -> None:
        """Index any unindexed facts for semantic search."""
        if not self._semantic or not self._store:
            return
        try:
            unindexed = self._semantic.get_unindexed(self._store)
            raw = unindexed.get("raw_facts", [])
            condensed = unindexed.get("condensed", [])

            if raw:
                self._semantic.index_facts(raw, source_table="raw_facts")
            if condensed:
                self._semantic.index_facts(condensed, source_table="condensed")
        except Exception as e:
            logger.debug("Semantic indexing failed: %s", e)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register the enhanced memory provider with the plugin system."""
    config = _load_plugin_config()
    provider = EnhancedMemoryProvider(config=config)
    ctx.register_memory_provider(provider)
