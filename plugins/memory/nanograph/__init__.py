"""nanograph — local embedded property-graph memory provider for Hermes.

Backs the agent's long-term memory with nanograph (Arrow/Lance, on-device):
full-text + graph-traversal recall today, optional local-LM-Studio semantic
recall when an embedding provider is configured. Every write lands in
nanograph's ACID store with a CDC mutation ledger (an audit trail of what the
agent committed to memory).

The graph is reached through the in-process `nanograph_py` PyO3 module, which
releases the GIL during database work — so the daemon-thread sync_turn() write
below is genuinely non-blocking with respect to the agent's main loop.

Config in $HERMES_HOME/config.yaml (profile-scoped):
  plugins:
    nanograph:
      db_path: $HERMES_HOME/nanograph/memory.nano   # omit for default
      recall_mode: fulltext        # fulltext | semantic | hybrid
      recall_limit: 6
      persist_turns: true          # store each turn as a Fact(kind="turn")
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

try:  # real helper when running inside Hermes; portable fallback otherwise
    from tools.registry import tool_error
except Exception:  # pragma: no cover
    def tool_error(message: str, **extra: Any) -> str:
        return json.dumps({"error": str(message), **extra})

logger = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).parent
_SCHEMA = (_PLUGIN_DIR / "schema.pg").read_text(encoding="utf-8")
_QUERIES = (_PLUGIN_DIR / "queries.gq").read_text(encoding="utf-8")

_SEMANTIC_MARKER = "// @SEMANTIC_EMBEDDING@"
_RECALL_QUERY = {"semantic": "semantic_recall", "hybrid": "hybrid_recall"}


# ---------------------------------------------------------------------------
# Tool schema (OpenAI function-calling format)
# ---------------------------------------------------------------------------

MEMORY_GRAPH_SCHEMA = {
    "name": "memory_graph",
    "description": (
        "Durable graph memory backed by nanograph. Use alongside the built-in "
        "memory tool — memory for always-on context, memory_graph for deep "
        "recall and structured storage.\n\n"
        "ACTIONS:\n"
        "• recall   — Full-text recall of facts matching a query.\n"
        "• about    — All facts concerning a named entity (graph traversal).\n"
        "• recent   — Facts written during a session.\n"
        "• remember — Store a durable fact the user would expect you to keep.\n\n"
        "Before answering questions about the user or project, recall first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["recall", "about", "recent", "remember"],
            },
            "query": {"type": "string", "description": "Search text (for 'recall')."},
            "entity": {"type": "string", "description": "Entity slug (for 'about')."},
            "content": {"type": "string", "description": "Fact statement (for 'remember')."},
            "kind": {
                "type": "string",
                "description": "Fact kind for 'remember'.",
                "enum": ["preference", "decision", "fact", "event"],
            },
        },
        "required": ["action"],
    },
}


def _load_plugin_config() -> dict:
    """Read plugins.nanograph from $HERMES_HOME/config.yaml (best-effort)."""
    try:
        import yaml
        from hermes_constants import get_hermes_home
        from hermes_cli.config import cfg_get

        config_path = get_hermes_home() / "config.yaml"
        if not config_path.exists():
            return {}
        with open(config_path, encoding="utf-8-sig") as f:
            all_config = yaml.safe_load(f) or {}
        return cfg_get(all_config, "plugins", "nanograph", default={}) or {}
    except Exception:
        return {}


class NanographMemoryProvider(MemoryProvider):
    """On-device property-graph memory backed by nanograph."""

    def __init__(self, config: Optional[dict] = None):
        self._config = config or _load_plugin_config()
        self._db = None
        self._session_id = ""
        self._writes_enabled = True
        self._recall_limit = int(self._config.get("recall_limit", 6))
        self._persist_turns = bool(self._config.get("persist_turns", True))
        # Recall strategy: fulltext (default, offline) | semantic | hybrid.
        self._recall_mode = str(self._config.get("recall_mode", "fulltext")).lower()
        self._semantic = self._recall_mode in _RECALL_QUERY
        self._recall_query = _RECALL_QUERY.get(self._recall_mode, "recall")
        # Embedding provider (OpenAI-compatible local endpoint, e.g. omlx).
        self._embed_dim = int(self._config.get("embed_dim", 1024))
        self._embed_model = str(self._config.get("embed_model", ""))
        self._embed_base_url = str(self._config.get("embed_base_url", "http://localhost:8000/v1"))
        self._embed_api_key = str(self._config.get("embed_api_key", ""))

    @property
    def name(self) -> str:
        return "nanograph"

    # -- Core lifecycle ------------------------------------------------------

    def is_available(self) -> bool:
        # No network: just confirm the in-process binding imports.
        import importlib.util
        return importlib.util.find_spec("nanograph_py") is not None

    def initialize(self, session_id: str, **kwargs) -> None:
        import nanograph_py

        self._session_id = session_id
        # Skip writes for non-primary contexts (cron/subagent) to avoid
        # corrupting the user's memory with system-prompt material.
        self._writes_enabled = kwargs.get("agent_context", "primary") == "primary"

        hermes_home = kwargs.get("hermes_home")
        if not hermes_home:  # lazy fallback only if the manager didn't pass it
            from hermes_constants import get_hermes_home
            hermes_home = str(get_hermes_home())

        db_path = self._config.get("db_path") or f"{hermes_home}/nanograph/memory.nano"
        db_path = (
            str(db_path)
            .replace("$HERMES_HOME", str(hermes_home))
            .replace("${HERMES_HOME}", str(hermes_home))
        )
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Semantic/hybrid: point nanograph's OpenAI-compatible provider at the
        # local endpoint (env-driven; nanograph reads these at embed/query time)
        # and inject an embedding column into the schema. Fulltext stays offline.
        if self._semantic:
            os.environ.setdefault("NANOGRAPH_EMBED_PROVIDER", "lmstudio")
            os.environ["LMSTUDIO_BASE_URL"] = self._embed_base_url
            if self._embed_api_key:
                os.environ["LMSTUDIO_API_KEY"] = self._embed_api_key
            if self._embed_model:
                os.environ["NANOGRAPH_EMBED_MODEL"] = self._embed_model
            schema = _SCHEMA.replace(
                _SEMANTIC_MARKER,
                f"embedding: Vector({self._embed_dim})? @embed(statement) @index",
            )
        else:
            schema = _SCHEMA.replace(_SEMANTIC_MARKER, "")

        # Open existing, else create from schema-as-code.
        if Path(db_path).exists():
            self._db = nanograph_py.Db.open(db_path)
        else:
            self._db = nanograph_py.Db.init(db_path, schema)
        logger.info("nanograph memory ready at %s (recall=%s)", db_path, self._recall_mode)

    def system_prompt_block(self) -> str:
        if not self._db:
            return ""
        try:
            total = len(self._run("all_facts"))
        except Exception:
            total = 0
        head = "# nanograph Memory\nActive — local property graph (full-text + graph recall)."
        if total == 0:
            return (
                head + " Empty store.\n"
                "Proactively store durable facts with memory_graph(action='remember'); "
                "recall before answering questions about the user or project."
            )
        return (
            head + f" {total} facts stored.\n"
            "Use memory_graph to recall, traverse entities, or remember new facts."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._db or not query.strip():
            return ""
        try:
            rows = self._run(self._recall_query, {"q": query})[: self._recall_limit]
        except Exception as e:
            logger.debug("nanograph prefetch failed: %s", e)
            return ""
        if not rows:
            return ""
        lines = [f"- ({r.get('kind', 'fact')}) {r.get('statement', '')}" for r in rows]
        return "## nanograph Memory (recalled)\n" + "\n".join(lines)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if not self._db or not self._writes_enabled or not self._persist_turns:
            return
        sess = session_id or self._session_id
        statement = f"User: {user_content}\nAssistant: {assistant_content}"[:2000]

        def _write():
            try:
                # GIL is released inside the binding's block_on, so this daemon
                # thread does not stall the agent loop.
                self._run("remember", {
                    "slug": f"turn-{uuid.uuid4().hex[:12]}",
                    "statement": statement,
                    "kind": "turn",
                    "session": sess,
                    "ts": self._now(),
                })
                self._backfill()
            except Exception as e:
                logger.debug("nanograph sync_turn write failed: %s", e)

        threading.Thread(target=_write, name="nanograph-sync", daemon=True).start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [MEMORY_GRAPH_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != "memory_graph":
            return tool_error(f"Unknown tool: {tool_name}")
        if not self._db:
            return tool_error("nanograph memory not initialized")
        try:
            action = args["action"]
            if action == "recall":
                rows = self._run(self._recall_query, {"q": args["query"]})[: self._recall_limit]
                return json.dumps({"results": rows, "count": len(rows)})
            if action == "about":
                rows = self._run("facts_about", {"entity": args["entity"]})
                return json.dumps({"results": rows, "count": len(rows)})
            if action == "recent":
                rows = self._run("recent", {"session": self._session_id})
                return json.dumps({"results": rows, "count": len(rows)})
            if action == "remember":
                slug = f"fact-{uuid.uuid4().hex[:12]}"
                res = self._run("remember", {
                    "slug": slug,
                    "statement": args["content"],
                    "kind": args.get("kind", "fact"),
                    "session": self._session_id,
                    "ts": self._now(),
                })
                self._backfill()
                return json.dumps({"slug": slug, "status": "stored", "result": res})
            return tool_error(f"Unknown action: {action}")
        except KeyError as exc:
            return tool_error(f"Missing required argument: {exc}")
        except Exception as exc:
            return tool_error(str(exc))

    # -- Optional hooks ------------------------------------------------------

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mirror built-in memory writes into the graph as Facts."""
        if action != "add" or not self._db or not self._writes_enabled or not content:
            return
        try:
            self._run("remember", {
                "slug": f"mem-{uuid.uuid4().hex[:12]}",
                "statement": content,
                "kind": "preference" if target == "user" else "memory",
                "session": self._session_id,
                "ts": self._now(),
            })
            self._backfill()
        except Exception as e:
            logger.debug("nanograph on_memory_write mirror failed: %s", e)

    def shutdown(self) -> None:
        if self._db:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None

    # -- Config wizard -------------------------------------------------------

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "db_path", "description": "nanograph database path",
             "default": "$HERMES_HOME/nanograph/memory.nano"},
            {"key": "recall_mode", "description": "Recall strategy",
             "default": "fulltext", "choices": ["fulltext", "semantic", "hybrid"]},
            {"key": "recall_limit", "description": "Max facts injected per prefetch",
             "default": "6"},
            {"key": "persist_turns", "description": "Store each turn as a Fact",
             "default": "true", "choices": ["true", "false"]},
            # Embedding provider (semantic/hybrid only) — OpenAI-compatible
            # local endpoint such as omlx. API key, if any, is non-secret here
            # because it's a local key; move to env for shared deployments.
            {"key": "embed_model", "description": "Embedding model id served by the endpoint (e.g. Qwen3-Embedding-0.6B)",
             "default": ""},
            {"key": "embed_dim", "description": "Embedding dimension (must match the model: Qwen3-Embedding-0.6B=1024, nomic=768)",
             "default": "1024"},
            {"key": "embed_base_url", "description": "OpenAI-compatible embeddings base URL",
             "default": "http://localhost:8000/v1"},
            {"key": "embed_api_key", "description": "API key for the local endpoint (omlx default: 1234)",
             "default": ""},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing = {}
            if config_path.exists():
                with open(config_path, encoding="utf-8-sig") as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["nanograph"] = values
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception as e:
            logger.debug("nanograph save_config failed: %s", e)

    # -- Internals -----------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _backfill(self) -> None:
        """Embed any rows missing a vector (semantic/hybrid mode only).

        Inserts via mutation don't auto-embed, so new facts get their vector
        here. In real mode this calls the embedding endpoint (omlx); it's run
        inline for tool writes and on the daemon thread for sync_turn.
        """
        if not self._semantic or not self._db:
            return
        try:
            self._db.embed('{"onlyNull": true}')
        except Exception as e:
            logger.debug("nanograph embed backfill failed: %s", e)

    def _run(self, query_name: str, params: Optional[dict] = None) -> Any:
        """Run a named query from queries.gq; return parsed rows / result."""
        raw = self._db.run(_QUERIES, query_name, json.dumps(params) if params else None)
        return json.loads(raw)


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register the nanograph memory provider with the plugin system."""
    config = _load_plugin_config()
    ctx.register_memory_provider(NanographMemoryProvider(config=config))
