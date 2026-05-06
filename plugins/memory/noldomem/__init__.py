"""NoldoMem memory plugin using the MemoryProvider interface.

NoldoMem is an external long-term memory service with semantic recall,
structured memory types, decay, and optional reranking. Hermes talks to it
through the public HTTP API and keeps storage, embeddings, and reranking in
NoldoMem instead of duplicating that logic locally.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "http://127.0.0.1:8787"
_DEFAULT_AGENT = "hermes"
_DEFAULT_NAMESPACE = "default"
_DEFAULT_TIMEOUT = 2.0
_DEFAULT_MAX_RECALL_RESULTS = 5
_DEFAULT_MAX_CONTEXT_CHARS = 4000
_VALID_MEMORY_TYPES = ("fact", "preference", "rule", "conversation", "lesson", "other")
_SKIP_WRITE_CONTEXTS = {"cron", "subagent", "flush"}
_CONTEXT_TAG_RE = re.compile(r"</?\s*memory-context\s*>", re.IGNORECASE)


def _as_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except Exception:
        return default


def _as_float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except Exception:
        return default


def _clean_text(text: str) -> str:
    return _CONTEXT_TAG_RE.sub("", str(text or "")).strip()


def _load_config(hermes_home: str | None = None) -> dict:
    """Load env defaults plus optional profile-local config.

    ``hermes memory setup`` stores non-secret values in ``noldomem.json`` and
    secrets in ``.env``. Runtime availability therefore needs to merge both.
    """
    config = {
        "api_url": os.environ.get("NOLDOMEM_API_URL", ""),
        "api_key": os.environ.get("NOLDOMEM_API_KEY", ""),
        "agent": os.environ.get("NOLDOMEM_AGENT", ""),
        "namespace": os.environ.get("NOLDOMEM_NAMESPACE", ""),
        "api_timeout": os.environ.get("NOLDOMEM_API_TIMEOUT", ""),
        "max_recall_results": os.environ.get("NOLDOMEM_MAX_RECALL_RESULTS", ""),
        "max_context_chars": os.environ.get("NOLDOMEM_MAX_CONTEXT_CHARS", ""),
    }

    config_home = hermes_home
    if not config_home:
        try:
            from hermes_constants import get_hermes_home

            config_home = str(get_hermes_home())
        except Exception:
            config_home = ""

    if config_home:
        config_path = Path(config_home) / "noldomem.json"
        if config_path.exists():
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    config.update({k: v for k, v in raw.items() if v not in (None, "")})
            except Exception:
                logger.debug("Failed to parse NoldoMem config", exc_info=True)

    return config


def _normalize_memory_type(value: Any) -> str:
    memory_type = str(value or "").strip().lower()
    return memory_type if memory_type in _VALID_MEMORY_TYPES else "other"


def _unwrap_results(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        results = response.get("results", [])
    elif isinstance(response, list):
        results = response
    else:
        results = []
    return [item for item in results if isinstance(item, dict)]


def _result_text(item: dict[str, Any]) -> str:
    for key in ("text", "memory", "content", "document"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_text(value)
    return ""


def _format_recall_results(results: list[dict[str, Any]], *, max_chars: int) -> str:
    lines = []
    for item in results:
        text = _result_text(item)
        if not text:
            continue
        memory_type = item.get("memory_type") or item.get("category") or "other"
        score_parts = []
        if item.get("semantic_score") is not None:
            score_parts.append(f"semantic={item['semantic_score']}")
        if item.get("rerank_score") is not None:
            score_parts.append(f"rerank={item['rerank_score']}")
        score_suffix = f" ({', '.join(score_parts)})" if score_parts else ""
        lines.append(f"- [{memory_type}] {text}{score_suffix}")

    if not lines:
        return ""

    rendered = "## NoldoMem recalled context\n" + "\n".join(lines)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max_chars - 3].rstrip() + "..."


RECALL_SCHEMA = {
    "name": "noldomem_recall",
    "description": (
        "Search NoldoMem long-term memory by meaning. Use for prior facts, "
        "preferences, rules, lessons, and operational context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "limit": {"type": "integer", "description": "Maximum results, default 5."},
            "memory_type": {
                "type": "string",
                "enum": list(_VALID_MEMORY_TYPES),
                "description": "Optional memory type filter.",
            },
            "namespace": {"type": "string", "description": "Optional namespace override."},
        },
        "required": ["query"],
    },
}

STORE_SCHEMA = {
    "name": "noldomem_store",
    "description": "Store an important memory in NoldoMem.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Memory text to store."},
            "memory_type": {
                "type": "string",
                "enum": list(_VALID_MEMORY_TYPES),
                "description": "Memory type, default other.",
            },
            "namespace": {"type": "string", "description": "Optional namespace override."},
        },
        "required": ["text"],
    },
}

PIN_SCHEMA = {
    "name": "noldomem_pin",
    "description": "Pin a NoldoMem memory so decay and cleanup do not remove it.",
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "string", "description": "Memory ID to pin."},
            "namespace": {"type": "string", "description": "Optional namespace override."},
        },
        "required": ["memory_id"],
    },
}


class NoldoMemMemoryProvider(MemoryProvider):
    """Hermes memory provider backed by a NoldoMem HTTP service."""

    def __init__(self) -> None:
        self._api_url = ""
        self._api_key = ""
        self._agent = _DEFAULT_AGENT
        self._namespace = _DEFAULT_NAMESPACE
        self._api_timeout = _DEFAULT_TIMEOUT
        self._max_recall_results = _DEFAULT_MAX_RECALL_RESULTS
        self._max_context_chars = _DEFAULT_MAX_CONTEXT_CHARS
        self._agent_context = "primary"
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: threading.Thread | None = None
        self._sync_thread: threading.Thread | None = None

    @property
    def name(self) -> str:
        return "noldomem"

    def is_available(self) -> bool:
        config = _load_config()
        return bool(config.get("api_url") and config.get("api_key"))

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home) / "noldomem.json"
        existing: dict[str, Any] = {}
        if config_path.exists():
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    existing = raw
            except Exception:
                existing = {}
        sanitized = {k: v for k, v in values.items() if k != "api_key"}
        existing.update(sanitized)
        config_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "api_url",
                "description": "NoldoMem API URL",
                "required": True,
                "default": _DEFAULT_API_URL,
            },
            {
                "key": "api_key",
                "description": "NoldoMem API key",
                "secret": True,
                "required": True,
                "env_var": "NOLDOMEM_API_KEY",
            },
            {"key": "agent", "description": "NoldoMem agent scope", "default": _DEFAULT_AGENT},
            {"key": "namespace", "description": "NoldoMem namespace", "default": _DEFAULT_NAMESPACE},
            {"key": "max_recall_results", "description": "Maximum auto-recall results", "default": "5"},
        ]

    def initialize(self, session_id: str, **kwargs) -> None:
        hermes_home = str(kwargs.get("hermes_home") or "")
        config = _load_config(hermes_home)
        self._api_url = str(config.get("api_url") or _DEFAULT_API_URL).rstrip("/")
        self._api_key = str(config.get("api_key") or "")
        self._agent = str(
            config.get("agent")
            or kwargs.get("agent_identity")
            or kwargs.get("user_id")
            or _DEFAULT_AGENT
        )
        self._namespace = str(
            config.get("namespace")
            or kwargs.get("agent_workspace")
            or _DEFAULT_NAMESPACE
        )
        self._api_timeout = _as_float(
            config.get("api_timeout"), _DEFAULT_TIMEOUT, minimum=0.2, maximum=30.0
        )
        self._max_recall_results = _as_int(
            config.get("max_recall_results"),
            _DEFAULT_MAX_RECALL_RESULTS,
            minimum=1,
            maximum=20,
        )
        self._max_context_chars = _as_int(
            config.get("max_context_chars"),
            _DEFAULT_MAX_CONTEXT_CHARS,
            minimum=500,
            maximum=20000,
        )
        self._agent_context = str(kwargs.get("agent_context") or "primary")

    def system_prompt_block(self) -> str:
        return (
            "# NoldoMem Memory\n"
            "Active. Use noldomem_recall for long-term memory search, "
            "noldomem_store for important facts/preferences/rules/lessons, "
            "and noldomem_pin for critical memory IDs."
        )

    def _request_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self._api_url or not self._api_key:
            return {}
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self._api_url}{path}",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self._api_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._api_timeout) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.debug("NoldoMem request failed for %s: %s", path, exc)
            return {}
        try:
            parsed = json.loads(raw) if raw else {}
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            logger.debug("NoldoMem returned invalid JSON for %s", path)
            return {}

    def _recall(self, query: str, *, namespace: str | None = None, limit: int | None = None) -> str:
        query = _clean_text(query)
        if not query:
            return ""
        body = {
            "query": query,
            "agent": self._agent,
            "namespace": namespace or self._namespace,
            "limit": limit or self._max_recall_results,
        }
        response = self._request_json("/v1/recall", body)
        results = _unwrap_results(response)[: body["limit"]]
        return _format_recall_results(results, max_chars=self._max_context_chars)

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=self._api_timeout)
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        return result

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        query = _clean_text(query)
        if not query or not self._api_key:
            return

        def worker() -> None:
            result = self._recall(query)
            with self._prefetch_lock:
                self._prefetch_result = result

        self._prefetch_thread = threading.Thread(target=worker, daemon=True)
        self._prefetch_thread.start()

    def _store(self, text: str, memory_type: str = "conversation", *, namespace: str | None = None) -> dict[str, Any]:
        text = _clean_text(text)
        if not text:
            return {}
        body = {
            "text": text,
            "agent": self._agent,
            "namespace": namespace or self._namespace,
            "memory_type": _normalize_memory_type(memory_type),
        }
        return self._request_json("/v1/store", body)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if self._agent_context in _SKIP_WRITE_CONTEXTS:
            return
        user = _clean_text(user_content)
        assistant = _clean_text(assistant_content)
        if not user and not assistant:
            return
        text = f"[role: user]\n{user}\n[user:end]\n[role: assistant]\n{assistant}\n[assistant:end]"

        def worker() -> None:
            self._store(text, "conversation")

        self._sync_thread = threading.Thread(target=worker, daemon=True)
        self._sync_thread.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [RECALL_SCHEMA, STORE_SCHEMA, PIN_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name == "noldomem_recall":
            query = _clean_text(str(args.get("query") or ""))
            limit = _as_int(args.get("limit"), self._max_recall_results, minimum=1, maximum=20)
            namespace = str(args.get("namespace") or self._namespace)
            body = {"query": query, "agent": self._agent, "namespace": namespace, "limit": limit}
            memory_type = args.get("memory_type")
            if memory_type:
                body["memory_type"] = _normalize_memory_type(memory_type)
            response = self._request_json("/v1/recall", body)
            results = _unwrap_results(response)
            return json.dumps(
                {
                    "count": len(results),
                    "result": _format_recall_results(results[:limit], max_chars=self._max_context_chars),
                    "results": results,
                }
            )

        if tool_name == "noldomem_store":
            text = _clean_text(str(args.get("text") or ""))
            namespace = str(args.get("namespace") or self._namespace)
            response = self._store(text, args.get("memory_type") or "other", namespace=namespace)
            return json.dumps(response)

        if tool_name == "noldomem_pin":
            memory_id = _clean_text(str(args.get("memory_id") or args.get("id") or ""))
            namespace = str(args.get("namespace") or self._namespace)
            body = {"id": memory_id, "agent": self._agent, "namespace": namespace}
            response = self._request_json("/v1/pin", body)
            return json.dumps(response)

        return json.dumps({"error": f"NoldoMem does not handle tool '{tool_name}'"})

    def shutdown(self) -> None:
        for thread in (self._prefetch_thread, self._sync_thread):
            if thread and thread.is_alive():
                thread.join(timeout=self._api_timeout)


def register(ctx) -> None:
    ctx.register_memory_provider(NoldoMemMemoryProvider())
