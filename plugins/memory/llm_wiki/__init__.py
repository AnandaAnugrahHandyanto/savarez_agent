"""LLM Wiki memory provider.

First-class MemoryProvider wrapper for Hermes LLM Wiki. The provider is
intentionally read-first: rich durable memory should be retrieved explicitly
or via bounded prefetch, not dumped into every prompt.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

from agent.memory_provider import MemoryProvider


def _module_file(module: Any) -> Path | None:
    raw = getattr(module, "__file__", None)
    if not raw:
        return None
    try:
        return Path(str(raw)).resolve()
    except OSError:
        return None


def _purge_non_standalone_wiki_modules(root: Path) -> None:
    """Drop preloaded hermes_wiki modules that did not come from the standalone root."""
    for name, module in list(sys.modules.items()):
        if name != "hermes_wiki" and not name.startswith("hermes_wiki."):
            continue
        module_file = _module_file(module)
        if module_file is not None and root in module_file.parents:
            continue
        sys.modules.pop(name, None)


def _prefer_standalone_core_from_env() -> None:
    """Opt in to resolving core hermes_wiki from a source checkout."""
    configured = os.environ.get("HERMES_LLM_WIKI_STANDALONE_ROOT", "").strip()
    if not configured:
        return
    root = Path(configured).expanduser().resolve()
    if root.name == "hermes_wiki":
        root = root.parent
    package_init = root / "hermes_wiki" / "__init__.py"
    if not package_init.exists():
        raise RuntimeError(f"HERMES_LLM_WIKI_STANDALONE_ROOT does not contain hermes_wiki: {root}")
    root_text = str(root)
    sys.path[:] = [entry for entry in sys.path if Path(entry or ".").resolve() != root]
    sys.path.insert(0, root_text)
    _purge_non_standalone_wiki_modules(root)


_prefer_standalone_core_from_env()

_CORE_IMPORT_ERROR: Exception | None = None
WikiCapabilities = Any
LLMWikiToolAdapter = None
WikiEngine = None
capability_preset = None


def _load_core_symbols() -> bool:
    """Import standalone hermes_wiki symbols if the package is available."""
    global _CORE_IMPORT_ERROR, WikiCapabilities, LLMWikiToolAdapter, capability_preset
    if LLMWikiToolAdapter is not None and capability_preset is not None:
        return True
    try:
        from hermes_wiki.capabilities import WikiCapabilities as imported_capabilities
        from hermes_wiki.capabilities import capability_preset as imported_capability_preset
        from hermes_wiki.tool_adapter import LLMWikiToolAdapter as imported_adapter
    except Exception as exc:  # pragma: no cover - exact import failure shape is environment-specific
        _CORE_IMPORT_ERROR = exc
        return False
    WikiCapabilities = imported_capabilities
    LLMWikiToolAdapter = imported_adapter
    capability_preset = imported_capability_preset
    _CORE_IMPORT_ERROR = None
    return True


def _capability_preset(context: str):
    if _load_core_symbols() and capability_preset is not None:
        return capability_preset(context)
    return None


class _UnavailableCapabilities:
    can_read = False
    can_query = False
    can_lint = False
    can_ingest = False
    can_mutate_canonical = False

    def allows(self, _capability: str) -> bool:
        return False


class LLMWikiMemoryProvider(MemoryProvider):

    """MemoryProvider facade for the Hermes LLM Wiki."""

    def __init__(self) -> None:
        self._session_id = ""
        self._hermes_home = ""
        self._agent_context = "primary"
        self._capabilities: Any = _capability_preset("primary") or _UnavailableCapabilities()
        self.wiki_path = Path.home() / ".hermes" / "wiki" / "personal"
        self.wiki_name = "personal"
        self._engine_instance = None
        self.prefetch_limit = 3
        self.prefetch_max_chars = 1200
        self.search_max_limit = 20
        self.read_max_chars = 64_000

    @property
    def name(self) -> str:
        return "llm_wiki"

    def is_available(self) -> bool:
        try:
            if importlib.util.find_spec("hermes_wiki.engine") is not None:
                return True
        except ModuleNotFoundError:
            pass
        try:
            from tools.lazy_deps import LAZY_DEPS

            return "memory.llm_wiki" in LAZY_DEPS
        except Exception:
            return False

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = session_id
        self._hermes_home = str(kwargs.get("hermes_home") or "")
        self._agent_context = str(kwargs.get("agent_context") or "primary").strip().lower() or "primary"
        if self._agent_context in {"primary", "interactive", "owner", "trusted"}:
            self._ensure_optional_deps()
        _load_core_symbols()
        self._capabilities = _capability_preset(self._agent_context) or _UnavailableCapabilities()
        self._load_wiki_config()

    def system_prompt_block(self) -> str:
        return (
            "LLM Wiki memory is source-backed durable knowledge. Lean on it proactively: "
            "use wiki_search whenever durable memory could improve correctness, continuity, "
            "or personalization: preferences, prior decisions, project status, architecture, "
            "policies, goals, current/next work, or what's next. Do not wait for explicit "
            "memory requests. Prefetch snippets are only hints; use wiki_read/wiki_query for "
            "fuller context or synthesis. Reference wiki/source pages when memory materially "
            "shapes an answer. Keep the wiki current: trusted primary contexts use wiki_update "
            "for source-backed canonical updates; read-only contexts search/query/introspect "
            "without durable writes."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._capabilities.can_read:
            return ""
        query = (query or "").strip()
        if not query:
            return ""
        try:
            searcher = getattr(self._engine(), "search", None)
            if searcher is None:
                return ""
            results = searcher.search(query, limit=self.prefetch_limit, exclude_sources=True)
        except Exception:
            return ""
        return self._format_prefetch_results(results)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        return None

    def _format_prefetch_results(self, results: Any) -> str:
        if not results:
            return ""
        header = "LLM Wiki relevant context (source-backed hints; lean on wiki_search/wiki_read/wiki_query before final answers when memory may matter):"
        lines = [header]
        remaining = self.prefetch_max_chars - len(header) - 1
        for result in results:
            data = self._search_result_to_dict(result)
            page_path = data["page_path"]
            title = data["title"] or page_path or "Untitled"
            text = " ".join(data["text"].split())
            score = data["score"]
            score_text = f" score={score:.3f}" if isinstance(score, (int, float)) else ""
            prefix = f"- [{page_path}] {title}{score_text}: "
            if len(prefix) >= remaining:
                break
            snippet = text[: max(0, min(260, remaining - len(prefix) - 1))]
            line = prefix + snippet
            if len(line) > remaining:
                break
            lines.append(line)
            remaining -= len(line) + 1
            if remaining <= 40:
                break
        return "\n".join(lines)[: self.prefetch_max_chars]

    def _search_result_to_dict(self, result: Any) -> Dict[str, Any]:
        if isinstance(result, dict):
            return {
                "page_path": str(result.get("page_path", "")),
                "title": str(result.get("title", "")),
                "page_type": str(result.get("page_type", "")),
                "chunk_index": result.get("chunk_index", 0),
                "text": str(result.get("text", "")),
                "score": result.get("score"),
                "tags": result.get("tags", []),
            }
        return {
            "page_path": str(getattr(result, "page_path", "")),
            "title": str(getattr(result, "title", "")),
            "page_type": str(getattr(result, "page_type", "")),
            "chunk_index": getattr(result, "chunk_index", 0),
            "text": str(getattr(result, "text", "")),
            "score": getattr(result, "score", None),
            "tags": getattr(result, "tags", []),
        }

    def _load_wiki_config(self) -> None:
        config = self._wiki_config()
        self.wiki_name = config.wiki_name
        self.wiki_path = config.wiki_path

    def _config_path(self) -> Path:
        hermes_home = Path(self._hermes_home).expanduser() if self._hermes_home else Path.home() / ".hermes"
        return hermes_home / "config.yaml"

    def _load_config_data(self) -> Dict[str, Any]:
        config_path = self._config_path()
        if not config_path.exists():
            return {}
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}

    def _wiki_config(self):
        from hermes_wiki.config import WikiConfig

        data = self._load_config_data()
        if "wiki" not in data:
            hermes_home = Path(self._hermes_home).expanduser() if self._hermes_home else Path.home() / ".hermes"
            data = {"wiki": {"path": str(hermes_home / "wiki" / "personal"), "name": "personal"}}
        return WikiConfig.from_dict(data)

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "path", "description": "Filesystem path for the LLM Wiki", "default": "~/.hermes/wiki/personal"},
            {"key": "name", "description": "Wiki name used for vector collection suffix", "default": "personal"},
            {"key": "embedding_url", "description": "OpenAI-compatible embedding endpoint", "default": "http://localhost:8000"},
            {"key": "embedding_model", "description": "Embedding model name", "default": "text-embedding-3-small"},
            {"key": "embedding_dim", "description": "Embedding vector dimension", "default": 1536},
            {"key": "qdrant_url", "description": "Qdrant HTTP URL", "default": "http://localhost:6333"},
            {"key": "collection_prefix", "description": "Qdrant collection prefix", "default": "hermes_wiki"},
            {"key": "llm_url", "description": "OpenAI-compatible LLM endpoint for wiki_query", "default": "https://openrouter.ai/api/v1"},
            {"key": "llm_model", "description": "LLM model used by wiki_query", "default": "openai/gpt-5.5"},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        config_path = Path(hermes_home).expanduser() / "config.yaml"
        data: Dict[str, Any] = {}
        if config_path.exists():
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            data = loaded if isinstance(loaded, dict) else {}

        wiki = data.setdefault("wiki", {})
        if not isinstance(wiki, dict):
            wiki = {}
            data["wiki"] = wiki

        def set_if_present(key: str, section: Dict[str, Any], dest: str | None = None, *, cast=None) -> None:
            if key not in values or values[key] in (None, ""):
                return
            value = values[key]
            if cast is not None:
                value = cast(value)
            section[dest or key] = value

        set_if_present("path", wiki)
        set_if_present("name", wiki)
        embedding = wiki.setdefault("embedding", {})
        vector = wiki.setdefault("vector_store", {})
        llm = wiki.setdefault("llm", {})
        set_if_present("embedding_url", embedding, "url")
        set_if_present("embedding_model", embedding, "model")
        set_if_present("embedding_dim", embedding, "dim", cast=int)
        set_if_present("qdrant_url", vector, "url")
        set_if_present("collection_prefix", vector)
        set_if_present("llm_url", llm, "url")
        set_if_present("llm_model", llm, "model")

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def _ensure_optional_deps(self) -> None:
        try:
            from tools.lazy_deps import ensure as lazy_ensure

            lazy_ensure("memory.llm_wiki", prompt=False)
        except ImportError:
            return

    def _engine(self):
        if self._engine_instance is None:
            if self._writes_allowed():
                self._ensure_optional_deps()
            engine_cls = WikiEngine
            if engine_cls is None:
                try:
                    from hermes_wiki.engine import WikiEngine as imported_engine
                except Exception as exc:  # pragma: no cover - exercised by integration tests later
                    raise RuntimeError("LLM Wiki engine is not importable") from exc
                engine_cls = imported_engine
            self._engine_instance = engine_cls(self._wiki_config(), read_only=not self._writes_allowed())
        return self._engine_instance

    def _adapter(self):
        if not _load_core_symbols() or LLMWikiToolAdapter is None:
            raise RuntimeError("LLM Wiki core package is not importable")
        return LLMWikiToolAdapter(
            config=self._wiki_config(),
            engine_factory=self._engine,
            capabilities=self._capabilities,
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
        schemas = self._adapter().tool_schemas()
        names = {schema.get("name") for schema in schemas}
        if "wiki_read" not in names and self._capabilities.can_read:
            read_schema = {
                "name": "wiki_read",
                "description": "Read a wiki page by slug or relative path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "string", "description": "Page slug or relative markdown path."},
                    },
                    "required": ["page"],
                },
            }
            insert_at = next(
                (idx + 1 for idx, schema in enumerate(schemas) if schema.get("name") == "wiki_search"),
                len(schemas),
            )
            schemas.insert(insert_at, read_schema)
        return schemas

    @staticmethod
    def _as_bool(value: Any, default: bool = False) -> bool:
        """Parse bool-like tool arguments without accidental truthiness escalation."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                return default
            return value != 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on", "enabled", "enable", "allow", "allowed"}:
                return True
            if normalized in {"0", "false", "no", "n", "off", "disabled", "disable", "deny", "denied", ""}:
                return False
        return default

    def _clamp_limit(self, value: Any, default: int = 5) -> int:
        try:
            limit = int(value)
        except (TypeError, ValueError, OverflowError):
            limit = default
        return max(1, min(self.search_max_limit, limit))

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): LLMWikiMemoryProvider._jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [LLMWikiMemoryProvider._jsonable(item) for item in value]
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        return value

    @classmethod
    def _json_dumps(cls, value: Any) -> str:
        return json.dumps(cls._jsonable(value), indent=2, default=str, allow_nan=False)

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs: Any) -> str:
        args = args or {}
        if tool_name == "wiki_capabilities":
            result = self._adapter().call("wiki_capabilities", args)
            # The shared adapter reports its agent-agnostic surface. Hermes adds
            # a native wiki_read wrapper in get_tool_schemas(); report the
            # actual Hermes provider surface so tool availability diagnostics do
            # not lie to the model/operator.
            result["exposed_tools"] = [schema["name"] for schema in self.get_tool_schemas()]
            return self._json_dumps(result)
        if tool_name == "wiki_update":
            try:
                return self._json_dumps(self._adapter().call("wiki_update", args))
            except (PermissionError, ValueError, FileNotFoundError) as exc:
                return f"Error: {exc}"
        if tool_name == "wiki_status":
            if not self._capabilities.allows("status"):
                return self._capability_blocked("wiki_status", "status")
            return self._json_dumps(self._engine().status())
        if tool_name == "wiki_orient":
            if not self._capabilities.allows("read"):
                return self._capability_blocked("wiki_orient", "read")
            return str(self._engine().orient())
        if tool_name == "wiki_query":
            if not self._capabilities.allows("query"):
                return self._capability_blocked("wiki_query", "query")
            question = str(args.get("question") or "").strip()
            if not question:
                return "Error: question is required"
            file_result = self._as_bool(args.get("file_result"), False)
            log_query = self._as_bool(args.get("log_query"), False)
            if (file_result or log_query) and not self._writes_allowed():
                return self._write_blocked("wiki_query")
            return str(
                self._engine().query(
                    question,
                    file_result=file_result,
                    log_query=log_query,
                )
            )
        if tool_name == "wiki_introspect":
            query = str(args.get("query") or "").strip()
            if not query:
                return "Error: query is required"
            try:
                return self._json_dumps(self._adapter().call("wiki_introspect", args))
            except (PermissionError, ValueError) as exc:
                return f"Error: {exc}"
        if tool_name == "wiki_read":
            if not self._capabilities.allows("read"):
                return self._capability_blocked("wiki_read", "read")
            page = str(args.get("page") or "").strip()
            if not page:
                return "Error: page is required"
            return self._read_page(page)
        if tool_name == "wiki_search":
            query = str(args.get("query") or "").strip()
            if not query:
                return "Error: query is required"
            adapter = LLMWikiToolAdapter(
                config=self._wiki_config(),
                engine_factory=self._engine,
                capabilities=self._capabilities,
            )
            try:
                results = adapter.call(
                    "wiki_search",
                    {
                        "query": query,
                        "limit": args.get("limit", 5),
                        "exclude_sources": args.get("exclude_sources", False),
                        "search_mode": args.get("search_mode", "dense"),
                    },
                )
            except (PermissionError, ValueError) as exc:
                return f"Error: {exc}"
            return self._json_dumps(results)
        if tool_name == "wiki_lint":
            if not self._capabilities.allows("read"):
                return self._capability_blocked("wiki_lint", "read")
            write_log = self._as_bool(args.get("write_log"), False)
            if write_log and not self._writes_allowed():
                return self._write_blocked("wiki_lint")
            return self._json_dumps(self._engine().lint(write_log=write_log))
        if tool_name == "wiki_ingest":
            file_path = str(args.get("file_path") or "").strip()
            if not file_path:
                return "Error: file_path is required"
            if not self._writes_allowed():
                return self._write_blocked("wiki_ingest")
            dry_run = self._as_bool(args.get("dry_run"), True)
            return self._json_dumps(self._engine().ingest_file(file_path, dry_run=dry_run))
        return super().handle_tool_call(tool_name, args, **kwargs)

    def _writes_allowed(self) -> bool:
        return self._capabilities.can_mutate_canonical or self._capabilities.can_ingest

    def _write_blocked(self, operation: str) -> str:
        return (
            f"Blocked {operation}: LLM Wiki file ingest and durable writes are disabled in "
            f"agent_context={self._agent_context!r}; use a primary agent context."
        )

    def _capability_blocked(self, operation: str, capability: str) -> str:
        return (
            f"Error: LLM Wiki capability denied: {capability} for {operation} "
            f"in agent_context={self._agent_context!r}."
        )

    def _read_page(self, page: str) -> str:
        path = self._resolve_page_path(page)
        if path is None:
            return f"Error: wiki page not found: {page}"
        text = path.read_text(encoding="utf-8")
        if len(text) <= self.read_max_chars:
            return text
        return text[: self.read_max_chars] + f"\n\n[truncated: {len(text) - self.read_max_chars} additional characters omitted]"

    def _resolve_page_path(self, page: str) -> Path | None:
        raw = str(page or "").strip()
        if not raw:
            return None

        requested = Path(raw)
        candidates: list[Path]
        if requested.is_absolute():
            candidates = [requested]
        else:
            candidates = [self.wiki_path / requested]
            if requested.suffix == "":
                candidates.append(self.wiki_path / f"{raw}.md")
            if len(requested.parts) == 1:
                slug = requested.stem if requested.suffix == ".md" else raw
                for subdir in ("entities", "concepts", "comparisons", "queries"):
                    candidates.append(self.wiki_path / subdir / f"{slug}.md")

        wiki_root = self.wiki_path.resolve()
        for candidate in candidates:
            resolved = candidate.resolve()
            if wiki_root not in resolved.parents and resolved != wiki_root:
                return None
            if resolved.exists() and resolved.is_file():
                return resolved
        return None


def register(ctx: Any) -> None:
    """Register the LLM Wiki memory provider with Hermes plugin context."""

    ctx.register_memory_provider(LLMWikiMemoryProvider())
