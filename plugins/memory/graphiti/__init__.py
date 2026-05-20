"""Graphiti memory provider for Hermes.

Local-first defaults:
- Kuzu graph database under $HERMES_HOME/graphiti/graph.kuzu
- Ollama embeddings, default qwen3-embedding:4b
- OpenRouter-compatible LLM extraction, default deepseek/deepseek-v4-flash

Secrets are read from environment variables only. This provider never prints
API keys in status/tool output.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

try:  # Optional plugin deps; is_available() reports false when missing.
    from graphiti_core.embedder.client import EmbedderClient
    from graphiti_core.cross_encoder.client import CrossEncoderClient
    from graphiti_core.llm_client.client import LLMClient, ModelSize
    from graphiti_core.llm_client.config import LLMConfig
except Exception:  # pragma: no cover - exercised when deps are absent on user machines
    EmbedderClient = object  # type: ignore
    CrossEncoderClient = object  # type: ignore
    LLMClient = object  # type: ignore
    ModelSize = None  # type: ignore
    LLMConfig = None  # type: ignore

logger = logging.getLogger(__name__)

_BREAKER_THRESHOLD = 5
_BREAKER_COOLDOWN_SECS = 120


def _expand_path(value: str, hermes_home: str) -> str:
    if not value:
        return str(Path(hermes_home) / "graphiti" / "graph.kuzu")
    value = value.replace("$HERMES_HOME", hermes_home)
    return str(Path(value).expanduser())


def _load_config(hermes_home: str | None = None) -> dict:
    if hermes_home is None:
        from hermes_constants import get_hermes_home

        hermes_home = str(get_hermes_home())

    try:
        from hermes_cli.env_loader import load_hermes_dotenv

        load_hermes_dotenv(hermes_home=Path(hermes_home))
    except Exception:
        # The agent runtime normally loads .env before plugins initialize. This
        # fallback keeps standalone plugin tests usable without exposing secrets.
        pass

    cfg = {
        "backend": os.environ.get("GRAPHITI_BACKEND", "kuzu"),
        "kuzu_path": os.environ.get("GRAPHITI_KUZU_PATH", str(Path(hermes_home) / "graphiti" / "graph.kuzu")),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        "embedding_model": os.environ.get("GRAPHITI_EMBEDDING_MODEL", "qwen3-embedding:4b"),
        "embedding_dim": int(os.environ.get("GRAPHITI_EMBEDDING_DIM", "2560")),
        "llm_base_url": os.environ.get("GRAPHITI_LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        "llm_model": os.environ.get("GRAPHITI_LLM_MODEL", "deepseek/deepseek-v4-flash"),
        "llm_small_model": os.environ.get("GRAPHITI_LLM_SMALL_MODEL", "deepseek/deepseek-v4-flash"),
        "llm_temperature": float(os.environ.get("GRAPHITI_LLM_TEMPERATURE", "0")),
        "group_id": os.environ.get("GRAPHITI_GROUP_ID", "hermes-default"),
        "sync_turns": os.environ.get("GRAPHITI_SYNC_TURNS", "true").lower() not in {"0", "false", "no"},
        "prefetch_top_k": int(os.environ.get("GRAPHITI_PREFETCH_TOP_K", "5")),
    }

    config_path = Path(hermes_home) / "graphiti.json"
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8"))
            for k, v in file_cfg.items():
                if v is None:
                    continue
                if v == "" and k != "group_id":
                    continue
                cfg[k] = v
        except Exception as exc:
            logger.warning("Failed to read graphiti.json: %s", exc)

    cfg["kuzu_path"] = _expand_path(str(cfg.get("kuzu_path", "")), hermes_home)
    cfg["embedding_dim"] = int(cfg.get("embedding_dim") or 2560)
    cfg["prefetch_top_k"] = int(cfg.get("prefetch_top_k") or 5)
    return cfg


class OllamaEmbedder(EmbedderClient):
    """Graphiti EmbedderClient-compatible wrapper for Ollama embeddings."""

    def __init__(self, *, model: str, base_url: str, embedding_dim: int):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.embedding_dim = embedding_dim

    async def create(self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]) -> list[float]:
        texts = input_data if isinstance(input_data, list) else [str(input_data)]
        embeddings = await self.create_batch([str(t) for t in texts])
        return embeddings[0]

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": input_data_list},
            )
            response.raise_for_status()
            payload = response.json()
        vectors = payload.get("embeddings") or []
        if not vectors:
            raise RuntimeError("Ollama returned no embeddings")
        return [list(map(float, vector[: self.embedding_dim])) for vector in vectors]


class OpenRouterJSONClient(LLMClient):
    """Minimal Graphiti LLMClient-compatible JSON client using chat completions.

    Graphiti's bundled OpenAI client uses the OpenAI Responses parse API for
    structured outputs. OpenRouter is OpenAI-compatible for chat completions, so
    this client asks the model for strict JSON and validates with Pydantic.
    """

    def __init__(self, *, api_key: str, base_url: str, model: str, small_model: str, temperature: float = 0.0):
        if LLMConfig is None:
            raise RuntimeError("graphiti-core is not installed")
        super().__init__(LLMConfig(api_key=api_key, model=model, small_model=small_model, base_url=base_url, temperature=temperature), cache=False)
        self.api_key = api_key
        self.base_url = base_url

    async def _generate_response(self, messages, response_model=None, max_tokens=None, model_size=None):
        return await self.generate_response(messages, response_model=response_model, max_tokens=max_tokens, model_size=model_size)

    async def generate_response(self, messages, response_model=None, max_tokens=None, model_size=None, group_id=None, prompt_name=None):
        from openai import AsyncOpenAI

        selected_model = self.small_model if ModelSize is not None and model_size == ModelSize.small else self.model
        openai_messages = []
        for msg in messages:
            role = "system" if getattr(msg, "role", "user") == "system" else "user"
            openai_messages.append({"role": role, "content": getattr(msg, "content", str(msg))})

        if response_model is not None:
            schema = response_model.model_json_schema()
            openai_messages.append({
                "role": "user",
                "content": (
                    "Return ONLY valid JSON matching this JSON Schema. "
                    "No markdown, no commentary.\n"
                    + json.dumps(schema, ensure_ascii=False)
                ),
            })
        else:
            openai_messages.append({"role": "user", "content": "Return ONLY valid JSON."})

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        response = await client.chat.completions.create(
            model=selected_model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=max_tokens or self.max_tokens or 4096,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or "{}"
        data = _extract_json(text)
        if response_model is not None:
            return response_model.model_validate(data).model_dump()
        return data


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


class PassthroughCrossEncoder(CrossEncoderClient):
    """Graphiti CrossEncoderClient-compatible no-op reranker.

    Keeps retrieval local-first and avoids a hidden OpenAI reranker dependency.
    """

    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        if not passages:
            return []
        # Preserve upstream order with a gentle descending score.
        total = max(len(passages), 1)
        return [(passage, (total - idx) / total) for idx, passage in enumerate(passages)]


SEARCH_SCHEMA = {
    "name": "graphiti_search",
    "description": "Search Graphiti temporal graph memory for relevant facts, relationships, and prior events.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Memory query."},
            "top_k": {"type": "integer", "description": "Maximum results, default 5, max 20."},
        },
        "required": ["query"],
    },
}

REMEMBER_SCHEMA = {
    "name": "graphiti_remember",
    "description": "Store an explicit durable fact or event in Graphiti memory. Use only for stable, useful memory.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Fact/event to remember."},
            "name": {"type": "string", "description": "Optional short episode name."},
        },
        "required": ["content"],
    },
}

STATUS_SCHEMA = {
    "name": "graphiti_status",
    "description": "Show Graphiti provider status and non-secret configuration.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


class GraphitiMemoryProvider(MemoryProvider):
    def __init__(self):
        self._cfg: dict[str, Any] = {}
        self._hermes_home = ""
        self._session_id = ""
        self._user_id = "hermes-user"
        self._group_id = "hermes-default"
        self._graphiti = None
        self._lock = threading.Lock()
        self._prefetch_result = ""
        self._prefetch_thread: threading.Thread | None = None
        self._sync_thread: threading.Thread | None = None
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0
        self._initialized = False

    @property
    def name(self) -> str:
        return "graphiti"

    def is_available(self) -> bool:
        if not self._cfg:
            try:
                self._cfg = _load_config(self._hermes_home or None)
            except Exception:
                pass
        if not (os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GRAPHITI_LLM_API_KEY")):
            return False
        try:
            import graphiti_core  # noqa: F401
            import kuzu  # noqa: F401
            import openai  # noqa: F401
        except Exception:
            return False
        return True

    def get_config_schema(self):
        return [
            {"key": "llm_api_key", "description": "OpenRouter or OpenAI-compatible API key", "secret": True, "required": True, "env_var": "OPENROUTER_API_KEY", "url": "https://openrouter.ai/keys"},
            {"key": "llm_model", "description": "OpenRouter model id", "default": "deepseek/deepseek-v4-flash"},
            {"key": "embedding_model", "description": "Ollama embedding model", "default": "qwen3-embedding:4b"},
            {"key": "kuzu_path", "description": "Local Kuzu graph path", "default": "$HERMES_HOME/graphiti/graph.kuzu"},
        ]

    def save_config(self, values, hermes_home):
        path = Path(hermes_home) / "graphiti.json"
        existing = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        existing.update(values)
        existing.pop("llm_api_key", None)
        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def initialize(self, session_id: str, **kwargs) -> None:
        self._hermes_home = str(kwargs.get("hermes_home") or Path.home() / ".hermes")
        self._session_id = session_id
        self._user_id = str(kwargs.get("user_id") or "hermes-user")
        self._cfg = _load_config(self._hermes_home)
        self._group_id = self._cfg.get("group_id") or None
        Path(self._cfg["kuzu_path"]).parent.mkdir(parents=True, exist_ok=True)
        self._initialized = True

    def _is_breaker_open(self) -> bool:
        if self._consecutive_failures < _BREAKER_THRESHOLD:
            return False
        if time.monotonic() >= self._breaker_open_until:
            self._consecutive_failures = 0
            return False
        return True

    def _record_success(self):
        self._consecutive_failures = 0

    def _record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= _BREAKER_THRESHOLD:
            self._breaker_open_until = time.monotonic() + _BREAKER_COOLDOWN_SECS

    async def _get_graphiti(self):
        if self._graphiti is not None:
            return self._graphiti
        from graphiti_core import Graphiti
        from graphiti_core.driver.kuzu_driver import KuzuDriver

        api_key = os.environ.get("GRAPHITI_LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY or GRAPHITI_LLM_API_KEY is required")

        driver = KuzuDriver(db=self._cfg["kuzu_path"])
        embedder = OllamaEmbedder(
            model=self._cfg["embedding_model"],
            base_url=self._cfg["ollama_base_url"],
            embedding_dim=int(self._cfg["embedding_dim"]),
        )
        llm_client = OpenRouterJSONClient(
            api_key=api_key,
            base_url=self._cfg["llm_base_url"],
            model=self._cfg["llm_model"],
            small_model=self._cfg["llm_small_model"],
            temperature=float(self._cfg.get("llm_temperature", 0)),
        )
        self._graphiti = Graphiti(graph_driver=driver, llm_client=llm_client, embedder=embedder, cross_encoder=PassthroughCrossEncoder())
        await self._graphiti.build_indices_and_constraints()
        await self._ensure_kuzu_fulltext_indices(driver)
        return self._graphiti

    async def _ensure_kuzu_fulltext_indices(self, driver) -> None:
        """Create Kuzu FTS indices that current graphiti-core's driver no-op can miss."""
        try:
            from graphiti_core.driver.driver import GraphProvider
            from graphiti_core.graph_queries import get_fulltext_indices

            for query in get_fulltext_indices(GraphProvider.KUZU):
                try:
                    await driver.client.execute(query)
                except Exception as exc:
                    # Kuzu may report if an index already exists or an installed
                    # binary lacks FTS support. Let actual search/add expose hard
                    # failures; don't prevent provider initialization.
                    logger.debug("Graphiti Kuzu FTS index query skipped: %s", exc)
        except Exception as exc:
            logger.debug("Graphiti Kuzu FTS index setup unavailable: %s", exc)

    def system_prompt_block(self) -> str:
        model = self._cfg.get("llm_model", "deepseek/deepseek-v4-flash")
        embed = self._cfg.get("embedding_model", "qwen3-embedding:4b")
        return (
            "# Graphiti Temporal Memory\n"
            f"Active local-first memory. Graph backend: Kuzu. Embeddings: Ollama {embed}. LLM extraction: {model}.\n"
            "Use graphiti_search for durable recall and graphiti_remember only for stable facts/events."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=3.0)
        with self._lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        return f"## Graphiti Memory\n{result}" if result else ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if self._is_breaker_open() or not query:
            return

        def _run():
            try:
                result = asyncio.run(self._search(query, int(self._cfg.get("prefetch_top_k", 5))))
                if result:
                    with self._lock:
                        self._prefetch_result = result
                self._record_success()
            except Exception as exc:
                self._record_failure()
                logger.debug("Graphiti prefetch failed: %s", exc)

        self._prefetch_thread = threading.Thread(target=_run, daemon=True, name="graphiti-prefetch")
        self._prefetch_thread.start()

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if self._is_breaker_open() or not self._cfg.get("sync_turns", True):
            return
        body = f"User: {user_content}\nAssistant: {assistant_content}"

        def _run():
            try:
                asyncio.run(self._add_episode(body, name=f"turn-{session_id or self._session_id}"))
                self._record_success()
            except Exception as exc:
                self._record_failure()
                logger.warning("Graphiti sync failed: %s", exc)

        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)
        self._sync_thread = threading.Thread(target=_run, daemon=True, name="graphiti-sync")
        self._sync_thread.start()

    async def _add_episode(self, content: str, *, name: str = "manual-memory") -> None:
        from graphiti_core.nodes import EpisodeType

        graphiti = await self._get_graphiti()
        await graphiti.add_episode(
            name=name[:120],
            episode_body=content,
            source_description="Hermes Agent memory provider",
            reference_time=datetime.now(timezone.utc),
            source=EpisodeType.message,
            group_id=self._group_id,
        )

    async def _search(self, query: str, top_k: int) -> str:
        graphiti = await self._get_graphiti()
        kwargs = {"num_results": max(1, min(top_k, 20))}
        if self._group_id:
            kwargs["group_ids"] = [self._group_id]
        results = await graphiti.search(query, **kwargs)
        lines = []
        for item in results:
            fact = getattr(item, "fact", None) or getattr(item, "name", None) or str(item)
            score = getattr(item, "score", None)
            if score is not None:
                lines.append(f"- {fact} (score={score:.3f})")
            else:
                lines.append(f"- {fact}")
        if not lines:
            lines = await self._fallback_kuzu_search(query, top_k)
        return "\n".join(lines)

    async def _fallback_kuzu_search(self, query: str, top_k: int) -> list[str]:
        """Simple local fallback over Kuzu episode/entity text.

        Graphiti's edge search can be empty when no relationships were extracted
        yet. Hermes still needs recall from stored episodes and entity summaries.
        """
        if self._graphiti is None:
            return []
        query_terms = [t.casefold() for t in re.findall(r"[\w-]{3,}", query)][:12]
        if not query_terms:
            return []
        records: list[tuple[str, str]] = []
        searches = [
            ("episode", "MATCH (n:Episodic) RETURN n.name AS name, n.content AS text LIMIT 100"),
            ("entity", "MATCH (n:Entity) RETURN n.name AS name, n.summary AS text LIMIT 100"),
        ]
        for label, cypher in searches:
            try:
                rows, _, _ = await self._graphiti.driver.execute_query(cypher)
            except Exception as exc:
                logger.debug("Graphiti fallback %s search failed: %s", label, exc)
                continue
            for row in rows:
                text = str(row.get("text") or "")
                name = str(row.get("name") or label)
                haystack = f"{name} {text}".casefold()
                score = sum(1 for term in query_terms if term in haystack)
                if score:
                    records.append((f"- [{label}] {name}: {text}", score))
        records.sort(key=lambda item: item[1], reverse=True)
        return [line for line, _ in records[: max(1, min(top_k, 20))]]

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [SEARCH_SCHEMA, REMEMBER_SCHEMA, STATUS_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name == "graphiti_status":
            return json.dumps({
                "provider": "graphiti",
                "available": self.is_available(),
                "initialized": self._initialized,
                "backend": self._cfg.get("backend", "kuzu"),
                "kuzu_path": self._cfg.get("kuzu_path", ""),
                "embedding_model": self._cfg.get("embedding_model", "qwen3-embedding:4b"),
                "embedding_dim": self._cfg.get("embedding_dim", 2560),
                "llm_base_url": self._cfg.get("llm_base_url", "https://openrouter.ai/api/v1"),
                "llm_model": self._cfg.get("llm_model", "deepseek/deepseek-v4-flash"),
                "has_llm_key": bool(os.environ.get("OPENROUTER_API_KEY") or os.environ.get("GRAPHITI_LLM_API_KEY")),
            })

        if self._is_breaker_open():
            return tool_error("Graphiti temporarily unavailable after repeated failures; retry later.")

        if tool_name == "graphiti_search":
            query = args.get("query", "")
            if not query:
                return tool_error("Missing required parameter: query")
            try:
                top_k = int(args.get("top_k", 5) or 5)
                result = asyncio.run(self._search(query, top_k))
                self._record_success()
                return json.dumps({"result": result or "No relevant Graphiti memories found."})
            except Exception as exc:
                self._record_failure()
                return tool_error(f"Graphiti search failed: {exc}")

        if tool_name == "graphiti_remember":
            content = args.get("content", "")
            if not content:
                return tool_error("Missing required parameter: content")
            name = args.get("name") or "manual-memory"
            try:
                asyncio.run(self._add_episode(content, name=name))
                self._record_success()
                return json.dumps({"result": "Stored in Graphiti memory."})
            except Exception as exc:
                self._record_failure()
                return tool_error(f"Graphiti remember failed: {exc}")

        return tool_error(f"Unknown tool: {tool_name}")

    def shutdown(self) -> None:
        for thread in (self._prefetch_thread, self._sync_thread):
            if thread and thread.is_alive():
                thread.join(timeout=5.0)
        if self._graphiti is not None:
            try:
                asyncio.run(self._graphiti.close())
            except Exception:
                pass
            self._graphiti = None


def register(ctx) -> None:
    ctx.register_memory_provider(GraphitiMemoryProvider())
