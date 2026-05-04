"""LangMem memory plugin — MemoryProvider interface.

LLM-powered memory extraction and consolidation via the LangMem library,
with Hermes-managed local SQLite persistence and FTS5 retrieval.

LangMem handles: extraction, update decisions, delete decisions.
Hermes handles: persistence, retrieval, user scoping.

Config (via env vars or $HERMES_HOME/langmem.json):
  LANGMEM_MODEL        — LLM for extraction (default: anthropic:claude-3-5-haiku-latest)
  LANGMEM_ENABLE_DELETES — Allow delete decisions during consolidation (default: true)
  LANGMEM_MAX_EXISTING — Max existing memories passed into extraction (default: 50)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)


def _build_metadata(
    *,
    lane: str,
    source_type: str,
    session_id: str,
    tags: Optional[List[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> dict:
    """Build a standard metadata payload for persisted LangMem rows."""
    payload = {
        "lane": lane,
        "source_type": source_type,
        "first_seen_session_id": session_id,
        "last_seen_session_id": session_id,
        "confirmation_count": 1,
        "tags": tags or [],
    }
    if extra:
        payload.update(extra)
    return payload


class HermesUserProfile(BaseModel):
    """Stable per-user profile Hermes can inject directly without search."""

    name: Optional[str] = None
    preferred_name: Optional[str] = None
    timezone: Optional[str] = None
    communication_style: Optional[str] = None
    verbosity_preference: Optional[str] = None
    preferred_tools: List[str] = Field(default_factory=list)
    active_projects: List[str] = Field(default_factory=list)
    dislikes: List[str] = Field(default_factory=list)
    correction_patterns: List[str] = Field(default_factory=list)
    recurring_workflows: List[str] = Field(default_factory=list)


class HermesEpisode(BaseModel):
    """Reusable successful interaction pattern extracted from a turn."""

    observation: str
    thoughts: str
    action: str
    result: str


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load config from env vars, with $HERMES_HOME/langmem.json overrides."""
    from hermes_constants import get_hermes_home

    config = {
        "model": os.environ.get("LANGMEM_MODEL", "anthropic:claude-3-5-haiku-latest"),
        "enable_deletes": os.environ.get("LANGMEM_ENABLE_DELETES", "true").lower() == "true",
        "max_existing": int(os.environ.get("LANGMEM_MAX_EXISTING", "50")),
        "debounce_seconds": float(os.environ.get("LANGMEM_DEBOUNCE_SECONDS", "20")),
    }

    config_path = get_hermes_home() / "langmem.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            for k, v in file_cfg.items():
                if v is None or v == "":
                    continue
                if k == "enable_deletes":
                    config[k] = str(v).lower() in ("true", "1", "yes")
                elif k == "max_existing":
                    config[k] = int(v)
                elif k == "debounce_seconds":
                    config[k] = float(v)
                else:
                    config[k] = v
        except Exception:
            pass

    return config


# ---------------------------------------------------------------------------
# Normalizer — isolate LangMem API shape changes to one function
# ---------------------------------------------------------------------------

def _normalize_memory(mem: Any) -> dict:
    """Normalize a LangMem memory object into a plain dict.

    LangMem's internal object shape has changed across versions — keep
    all version-specific access here so the rest of the provider is stable.
    """
    mem_id = getattr(mem, "id", None)
    action = getattr(mem, "action", None)

    # Some versions use .type or .op instead of .action
    if action is None:
        action = getattr(mem, "type", None) or getattr(mem, "op", None)

    # Try to extract content — LangMem wraps it in various ways
    content_attr = getattr(mem, "content", None)
    if hasattr(content_attr, "content"):
        # Older versions: content is an object with a .content str
        text = content_attr.content
    elif isinstance(content_attr, str):
        text = content_attr
    elif isinstance(content_attr, dict):
        # Some versions return content as a dict — pull "content" key or skip.
        # Dicts with only "json_doc_id" are internal LangMem metadata — skip them.
        if "json_doc_id" in content_attr and len(content_attr) == 1:
            text = ""
        else:
            text = content_attr.get("content") or content_attr.get("text") or ""
    elif content_attr is not None:
        text = str(content_attr)
    else:
        text = str(mem)

    # Filter out LangMem internal metadata artifacts.
    # These appear as strings like "json_doc_id='<uuid>'" and carry no user-facing value.
    _stripped = text.strip()
    if (not _stripped
            or _stripped.startswith("json_doc_id=")
            or _stripped.startswith("json_doc_id =")):
        text = ""

    return {
        "id": mem_id,
        "content": text,
        "action": action,
    }


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

PROFILE_SCHEMA = {
    "name": "langmem_profile",
    "description": (
        "Retrieve all stored memories about the user — preferences, facts, "
        "project context. Use at conversation start for a full overview."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SEARCH_SCHEMA = {
    "name": "langmem_search",
    "description": (
        "Search durable memories by keyword. Returns relevant facts ranked by "
        "FTS relevance. Use to find specific remembered facts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "top_k": {"type": "integer", "description": "Max results (default: 10)."},
        },
        "required": ["query"],
    },
}

CONCLUDE_SCHEMA = {
    "name": "langmem_conclude",
    "description": (
        "Store a durable fact about the user verbatim — bypasses LLM extraction. "
        "Use for explicit preferences, corrections, or decisions the user stated directly."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "conclusion": {"type": "string", "description": "The fact to store."},
        },
        "required": ["conclusion"],
    },
}


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------

class LangMemMemoryProvider(MemoryProvider):
    """LangMem extraction + Hermes SQLite persistence."""

    def __init__(self):
        self._config: Optional[dict] = None
        self._store = None          # LangMemStore
        self._store_path = None     # Path to langmem.sqlite3
        self._manager = None        # LangMem memory manager
        self._profile_manager = None
        self._episode_manager = None
        self._manager_lock = threading.Lock()
        self._user_id = "hermes-user"
        self._session_id = ""
        self._model = "anthropic:claude-3-5-haiku-latest"
        self._enable_deletes = True
        self._max_existing = 50
        self._debounce_seconds = 20.0
        self._sync_thread: Optional[threading.Thread] = None
        self._pending_sync_payload: Optional[Dict[str, Any]] = None
        self._pending_sync_deadline = 0.0
        self._pending_sync_lock = threading.Lock()
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: Optional[threading.Thread] = None

    @property
    def name(self) -> str:
        return "langmem"

    def is_available(self) -> bool:
        try:
            import langmem  # noqa: F401
            return True
        except Exception:
            return False

    def get_config_schema(self):
        return [
            {
                "key": "model",
                "description": "LangMem extraction model",
                "default": "anthropic:claude-3-5-haiku-latest",
            },
            {
                "key": "enable_deletes",
                "description": "Allow delete decisions during consolidation",
                "default": "true",
                "choices": ["true", "false"],
            },
            {
                "key": "max_existing",
                "description": "Max existing memories to pass into extraction",
                "default": "50",
            },
            {
                "key": "debounce_seconds",
                "description": "Seconds to wait before processing background memory sync",
                "default": "20",
            },
        ]

    def save_config(self, values: dict, hermes_home: str) -> None:
        """Write config to $HERMES_HOME/langmem.json."""
        from pathlib import Path
        config_path = Path(hermes_home) / "langmem.json"
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
            except Exception:
                pass
        existing.update(values)
        config_path.write_text(json.dumps(existing, indent=2))

    def _get_manager(self):
        """Thread-safe lazy manager accessor."""
        with self._manager_lock:
            if self._manager is not None:
                return self._manager
            try:
                from langmem import create_memory_manager
                self._manager = create_memory_manager(
                    self._model,
                    enable_inserts=True,
                    enable_updates=True,
                    enable_deletes=self._enable_deletes,
                )
                return self._manager
            except ImportError:
                raise RuntimeError(
                    "langmem package not installed. Run: "
                    "uv pip install langmem==0.0.30 langgraph==1.1.9"
                )

    def _get_profile_manager(self):
        """Thread-safe lazy profile manager accessor."""
        with self._manager_lock:
            if self._profile_manager is not None:
                return self._profile_manager
            try:
                from langmem import create_memory_manager
                self._profile_manager = create_memory_manager(
                    self._model,
                    schemas=[HermesUserProfile],
                    instructions="Extract durable user profile information for Hermes.",
                    enable_inserts=False,
                    enable_updates=True,
                    enable_deletes=False,
                )
                return self._profile_manager
            except ImportError:
                raise RuntimeError(
                    "langmem package not installed. Run: "
                    "uv pip install langmem==0.0.30 langgraph==1.1.9"
                )

    def _get_episode_manager(self):
        """Thread-safe lazy episodic manager accessor."""
        with self._manager_lock:
            if self._episode_manager is not None:
                return self._episode_manager
            try:
                from langmem import create_memory_manager
                self._episode_manager = create_memory_manager(
                    self._model,
                    schemas=[HermesEpisode],
                    instructions="Extract successful reusable interaction patterns for Hermes.",
                    enable_inserts=True,
                    enable_updates=False,
                    enable_deletes=False,
                )
                return self._episode_manager
            except ImportError:
                raise RuntimeError(
                    "langmem package not installed. Run: "
                    "uv pip install langmem==0.0.30 langgraph==1.1.9"
                )

    def initialize(self, session_id: str, **kwargs) -> None:
        self._config = _load_config()
        self._session_id = session_id
        # Prefer gateway-provided user_id for per-user scoping;
        # fall back to config default for CLI (single-user) sessions.
        self._user_id = kwargs.get("user_id") or self._config.get("user_id", "hermes-user")
        self._model = self._config.get("model", "anthropic:claude-3-5-haiku-latest")
        self._enable_deletes = self._config.get("enable_deletes", True)
        self._max_existing = int(self._config.get("max_existing", 50))
        self._debounce_seconds = float(self._config.get("debounce_seconds", 20.0))

        # Open the local store
        try:
            from hermes_constants import get_hermes_home
            from plugins.memory.langmem.store import LangMemStore
            self._store_path = get_hermes_home() / "langmem.sqlite3"
            self._store = LangMemStore(self._store_path)
        except Exception as e:
            logger.warning("LangMem store init failed: %s", e)
            self._store = None

    def system_prompt_block(self) -> str:
        return (
            "# LangMem Memory\n"
            f"Active. User: {self._user_id}.\n"
            "Use langmem_search to search durable memories, "
            "langmem_profile for a full snapshot, and langmem_conclude for explicit facts."
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [PROFILE_SCHEMA, SEARCH_SCHEMA, CONCLUDE_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if self._store is None:
            return tool_error("LangMem store not initialized.")

        if tool_name == "langmem_profile":
            try:
                profile = self._store.get_profile(self._user_id)
                if profile:
                    return json.dumps({"result": profile, "kind": "profile"})
                rows = self._store.list_memories(self._user_id, limit=200)
                if not rows:
                    return json.dumps({"result": "No memories stored yet."})
                lines = [r["content"] for r in rows if r.get("content")]
                return json.dumps({"result": "\n".join(f"- {l}" for l in lines), "count": len(lines)})
            except Exception as e:
                return tool_error(f"Failed to fetch profile: {e}")

        elif tool_name == "langmem_search":
            query = args.get("query", "")
            if not query:
                return tool_error("Missing required parameter: query")
            top_k = int(args.get("top_k", 10))
            try:
                rows = self._store.search_memories(self._user_id, query, limit=top_k)
                if not rows:
                    return json.dumps({"result": "No relevant memories found."})
                items = [{"memory": r["content"], "id": r["id"]} for r in rows]
                return json.dumps({"results": items, "count": len(items)})
            except Exception as e:
                return tool_error(f"Search failed: {e}")

        elif tool_name == "langmem_conclude":
            conclusion = args.get("conclusion", "")
            if not conclusion:
                return tool_error("Missing required parameter: conclusion")
            try:
                mem_id = str(uuid.uuid4())
                self._store.upsert_many(
                    self._user_id,
                    [{
                        "id": mem_id,
                        "content": conclusion,
                        "source": "conclude",
                        "metadata": _build_metadata(
                            lane="preferences",
                            source_type="conclude",
                            session_id=self._session_id,
                            tags=["explicit", "user-stated"],
                        ),
                    }],
                    session_id=self._session_id,
                )
                return json.dumps({"result": "Fact stored.", "id": mem_id})
            except Exception as e:
                return tool_error(f"Failed to store conclusion: {e}")

        return tool_error(f"Unknown tool: {tool_name}")

    def _should_extract_episode(self, user_content: str, assistant_content: str) -> bool:
        """Return True when the turn looks like a reusable successful pattern."""
        user_text = (user_content or "").strip()
        assistant_text = (assistant_content or "").strip()
        if not user_text or not assistant_text:
            return False
        if len(user_text) < 12:
            return False
        if user_text.lower() in {"ok", "thanks", "thank you", "proceed", "continue"}:
            return False
        assistant_lower = assistant_text.lower()
        failure_markers = (
            "error",
            "failed",
            "failure",
            "unable",
            "cannot",
            "can't",
            "refuse",
            "refused",
            "missing dependency",
            "tool_error",
        )
        return not any(marker in assistant_lower for marker in failure_markers)

    def _normalize_episode(self, episode: Any) -> Optional[dict]:
        """Normalize a LangMem episode object into a plain dict payload."""
        payload = getattr(episode, "content", episode)
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        if not isinstance(payload, dict):
            return None
        required = ("observation", "thoughts", "action", "result")
        if not all(payload.get(key) for key in required):
            return None
        return {key: str(payload[key]) for key in required}

    def _run_single_sync(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Run one LangMem sync pass immediately."""
        try:
            manager = self._get_manager()

            existing_rows = self._store.list_memories(self._user_id, limit=self._max_existing)
            existing = [(row["id"], row["content"]) for row in existing_rows]

            result = manager.invoke(
                {
                    "messages": [
                        {"role": "user", "content": user_content},
                        {"role": "assistant", "content": assistant_content},
                    ],
                    "existing": existing,
                }
            )

            upserts: List[Dict[str, Any]] = []
            delete_ids: List[str] = []

            if isinstance(result, dict):
                memories = result.get("memories") or result.get("results") or []
            elif isinstance(result, list):
                memories = result
            else:
                memories = []

            logger.debug(
                "LangMem raw result type=%s keys=%s len=%s",
                type(result).__name__,
                list(result.keys()) if isinstance(result, dict) else "n/a",
                len(memories),
            )

            for mem in memories:
                try:
                    normalized = _normalize_memory(mem)
                except Exception as e:
                    logger.debug("LangMem normalize failed: %s", e)
                    continue

                action = (normalized.get("action") or "").lower()
                content = normalized.get("content", "")
                mem_id = normalized.get("id")

                if not content or content.strip().startswith("json_doc_id="):
                    continue

                if action in ("delete", "remove"):
                    if mem_id:
                        delete_ids.append(mem_id)
                else:
                    upserts.append({
                        "id": mem_id or str(uuid.uuid4()),
                        "content": content,
                        "metadata": _build_metadata(
                            lane="preferences",
                            source_type="sync_turn",
                            session_id=session_id or self._session_id,
                            tags=["background"],
                        ),
                    })

            self._store.reconcile_many(
                self._user_id,
                upserts,
                delete_ids,
                session_id=session_id or self._session_id,
            )

            try:
                profile_manager = self._get_profile_manager()
                profile_result = profile_manager.invoke(
                    {
                        "messages": [
                            {"role": "user", "content": user_content},
                            {"role": "assistant", "content": assistant_content},
                        ]
                    }
                )
                if profile_result:
                    first = profile_result[0]
                    profile_content = getattr(first, "content", first)
                    if hasattr(profile_content, "model_dump"):
                        self._store.upsert_profile(
                            self._user_id,
                            profile_content.model_dump(),
                            session_id=session_id or self._session_id,
                        )
            except Exception as e:
                logger.debug("LangMem profile sync failed: %s", e)

            try:
                if self._should_extract_episode(user_content, assistant_content):
                    episode_manager = self._get_episode_manager()
                    episode_result = episode_manager.invoke(
                        {
                            "messages": [
                                {"role": "user", "content": user_content},
                                {"role": "assistant", "content": assistant_content},
                            ]
                        }
                    )
                    episode_upserts: List[Dict[str, Any]] = []
                    for episode in episode_result or []:
                        payload = self._normalize_episode(episode)
                        if not payload:
                            continue
                        episode_upserts.append(
                            {
                                "id": str(uuid.uuid4()),
                                "kind": "episode",
                                "content": json.dumps(payload, sort_keys=True),
                                "source": "langmem-episode",
                                "metadata": _build_metadata(
                                    lane="episodes",
                                    source_type="episode_sync",
                                    session_id=session_id or self._session_id,
                                    tags=["episode", "background"],
                                ),
                            }
                        )
                    if episode_upserts:
                        self._store.upsert_many(
                            self._user_id,
                            episode_upserts,
                            session_id=session_id or self._session_id,
                        )
            except Exception as e:
                logger.debug("LangMem episode sync failed: %s", e)

            logger.debug(
                "LangMem sync_turn: %d upserts, %d deletes for user %s",
                len(upserts), len(delete_ids), self._user_id,
            )

        except Exception as e:
            logger.warning("LangMem sync_turn failed: %s", e)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Extract and consolidate memories from the completed turn (debounced, non-blocking)."""
        if self._store is None:
            return

        payload = {
            "user_content": user_content,
            "assistant_content": assistant_content,
            "session_id": session_id,
        }

        with self._pending_sync_lock:
            self._pending_sync_payload = payload
            self._pending_sync_deadline = time.time() + max(0.0, float(self._debounce_seconds))
            already_running = self._sync_thread is not None and self._sync_thread.is_alive()

        if already_running:
            return

        def _runner():
            while True:
                with self._pending_sync_lock:
                    deadline = self._pending_sync_deadline
                remaining = deadline - time.time()
                if remaining > 0:
                    time.sleep(min(remaining, 0.05))
                    continue

                with self._pending_sync_lock:
                    current = self._pending_sync_payload
                    self._pending_sync_payload = None
                    self._pending_sync_deadline = 0.0

                if current is None:
                    return

                self._run_single_sync(
                    current["user_content"],
                    current["assistant_content"],
                    session_id=current.get("session_id", ""),
                )

                with self._pending_sync_lock:
                    if self._pending_sync_payload is None:
                        return

        self._sync_thread = threading.Thread(target=_runner, daemon=True, name="langmem-sync")
        self._sync_thread.start()

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Return prefetched memories for this turn's query."""
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        if not result:
            return ""
        return f"## LangMem Memory\n{result}"

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Fire a background FTS search so results are ready for the next turn."""
        if self._store is None or not query:
            return

        def _run():
            try:
                rows = self._store.search_memories(self._user_id, query, limit=5)
                if rows:
                    lines = [r["content"] for r in rows if r.get("content")]
                    with self._prefetch_lock:
                        self._prefetch_result = "\n".join(f"- {l}" for l in lines)
            except Exception as e:
                logger.debug("LangMem prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(target=_run, daemon=True, name="langmem-prefetch")
        self._prefetch_thread.start()

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Wait for any pending sync before session closes."""
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=15.0)

    def shutdown(self) -> None:
        for t in (self._prefetch_thread, self._sync_thread):
            if t and t.is_alive():
                t.join(timeout=5.0)
        if self._store:
            self._store.close()
        with self._manager_lock:
            self._manager = None
            self._profile_manager = None
            self._episode_manager = None


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register LangMem as a memory provider plugin."""
    ctx.register_memory_provider(LangMemMemoryProvider())
