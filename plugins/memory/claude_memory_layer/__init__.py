"""Claude Memory Layer project-context prefetch provider.

This memory provider is intentionally read-only. It calls the project-aware
``mem-context-pack`` MCP tool before each turn and injects the returned compact
context through Hermes' existing memory prefetch path.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from agent.memory_provider import MemoryProvider
from tools.registry import registry

logger = logging.getLogger(__name__)

_DEFAULT_CONTEXT_TOOL = "mcp_claude_memory_layer_mem_context_pack"
_DEFAULT_TOP_K = 5
_DEFAULT_RECENT_LIMIT = 30
_DEFAULT_SESSION_LIMIT = 5
_DEFAULT_MAX_CHARS = 6000


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_hermes_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _nested(mapping: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _setting(config: Dict[str, Any], key: str, env_name: str, default: Any) -> Any:
    env_value = os.environ.get(env_name)
    if env_value is not None and env_value != "":
        return env_value

    # Preferred colocated config:
    # memory:
    #   claude_memory_layer:
    #     top_k: 5
    memory_value = _nested(config, "memory", "claude_memory_layer", key)
    if memory_value is not None:
        return memory_value

    # Backward/standalone config convenience:
    # claude_memory_layer:
    #   top_k: 5
    root_value = _nested(config, "claude_memory_layer", key)
    if root_value is not None:
        return root_value

    return default


def _int_setting(config: Dict[str, Any], key: str, env_name: str, default: int) -> int:
    value = _setting(config, key, env_name, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        logger.warning("Invalid Claude Memory Layer setting %s=%r; using %s", key, value, default)
        return default
    return parsed if parsed > 0 else default


def _str_setting(config: Dict[str, Any], key: str, env_name: str, default: str = "") -> str:
    value = _setting(config, key, env_name, default)
    return str(value).strip() if value is not None else default


def _resolve_project_path(config: Dict[str, Any], init_kwargs: Dict[str, Any]) -> str:
    configured = _str_setting(
        config,
        "project_path",
        "CLAUDE_MEMORY_LAYER_PROJECT_PATH",
        "",
    )
    if configured:
        return configured

    # Gateway sessions set TERMINAL_CWD to the user's actual project cwd; the
    # gateway process itself often runs from the hermes-agent install dir.
    for candidate in (
        init_kwargs.get("project_path"),
        init_kwargs.get("cwd"),
        os.environ.get("TERMINAL_CWD"),
    ):
        if candidate:
            return str(candidate)

    try:
        return str(Path.cwd())
    except Exception:
        return ""


def _extract_tool_text(raw: str) -> str:
    """Extract model-facing text from a Hermes tool-dispatch JSON string."""
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return str(raw)

    if not isinstance(payload, dict):
        return str(payload)
    if payload.get("error"):
        return ""

    result = payload.get("result", "")
    if isinstance(result, str):
        return result
    if result is None:
        return ""
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except TypeError:
        return str(result)


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    keep = max(0, max_chars - len("\n...[truncated]"))
    return text[:keep].rstrip() + "\n...[truncated]"


class ClaudeMemoryLayerProvider(MemoryProvider):
    """Read-only provider that prefetches project context from claude-memory-layer."""

    def __init__(self) -> None:
        self._config = _load_hermes_config()
        self._context_tool = _str_setting(
            self._config,
            "context_tool",
            "CLAUDE_MEMORY_LAYER_CONTEXT_TOOL",
            _DEFAULT_CONTEXT_TOOL,
        )
        self._top_k = _int_setting(
            self._config,
            "top_k",
            "CLAUDE_MEMORY_LAYER_TOP_K",
            _DEFAULT_TOP_K,
        )
        self._recent_limit = _int_setting(
            self._config,
            "recent_limit",
            "CLAUDE_MEMORY_LAYER_RECENT_LIMIT",
            _DEFAULT_RECENT_LIMIT,
        )
        self._session_limit = _int_setting(
            self._config,
            "session_limit",
            "CLAUDE_MEMORY_LAYER_SESSION_LIMIT",
            _DEFAULT_SESSION_LIMIT,
        )
        self._max_chars = _int_setting(
            self._config,
            "max_chars",
            "CLAUDE_MEMORY_LAYER_MAX_CHARS",
            _DEFAULT_MAX_CHARS,
        )
        # Optional claude-memory-layer source-session filter. Deliberately NOT
        # defaulted to the live Hermes session_id; doing so would hide most
        # project memories because CML session IDs and Hermes runtime session IDs
        # are different namespaces.
        self._source_session_id = _str_setting(
            self._config,
            "session_id",
            "CLAUDE_MEMORY_LAYER_SESSION_ID",
            "",
        )
        self._project_path = ""

    @property
    def name(self) -> str:
        return "claude_memory_layer"

    def is_available(self) -> bool:
        return registry.get_entry(self._context_tool) is not None

    def initialize(self, session_id: str, **kwargs) -> None:
        self._project_path = _resolve_project_path(self._config, kwargs)

    def system_prompt_block(self) -> str:
        return (
            "# Claude Memory Layer\n"
            "Active. A privacy-safe project context pack is prefetched before each turn "
            "when the configured claude-memory-layer MCP tool is connected."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self.is_available():
            return ""

        clean_query = query.strip() if isinstance(query, str) else ""
        args: Dict[str, Any] = {
            "query": clean_query or "recent project context",
            "topK": self._top_k,
            "recentLimit": self._recent_limit,
            "sessionLimit": self._session_limit,
        }
        if self._project_path:
            args["projectPath"] = self._project_path
        if self._source_session_id:
            args["sessionId"] = self._source_session_id

        try:
            raw = registry.dispatch(self._context_tool, args)
        except Exception as exc:
            logger.debug("Claude Memory Layer prefetch failed: %s", exc)
            return ""

        text = _extract_tool_text(raw).strip()
        if not text:
            return ""

        text = _truncate(text, self._max_chars)
        return "## Claude Memory Layer Project Context\n" + text

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        # Read-only provider: claude-memory-layer ingestion is handled by its
        # own import/MCP paths. Do not mirror turns from Hermes here.
        return None

    def get_tool_schemas(self):
        # The MCP server already exposes navigation tools; this provider only
        # wires automatic pre-turn context injection.
        return []

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        raise NotImplementedError("claude_memory_layer does not expose provider tools")

    def get_config_schema(self):
        return [
            {
                "key": "context_tool",
                "description": "Hermes MCP tool name for claude-memory-layer mem-context-pack",
                "default": _DEFAULT_CONTEXT_TOOL,
            },
            {
                "key": "project_path",
                "description": "Optional fixed project path; defaults to TERMINAL_CWD or current directory",
                "default": "",
            },
            {"key": "top_k", "description": "Relevant memory count", "default": str(_DEFAULT_TOP_K)},
            {"key": "recent_limit", "description": "Recent event scan limit", "default": str(_DEFAULT_RECENT_LIMIT)},
            {"key": "session_limit", "description": "Recent session summary limit", "default": str(_DEFAULT_SESSION_LIMIT)},
            {"key": "max_chars", "description": "Maximum injected context characters", "default": str(_DEFAULT_MAX_CHARS)},
            {
                "key": "session_id",
                "description": "Optional claude-memory-layer source-session filter; empty means search across project sessions",
                "default": "",
            },
        ]


def register_memory_provider(ctx=None):
    return ClaudeMemoryLayerProvider()
