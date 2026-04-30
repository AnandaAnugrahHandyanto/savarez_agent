"""GBrain memory plugin — MemoryProvider interface.

Uses the local ``gbrain`` CLI as a durable, profile-scoped knowledge backend for
Hermes Agent. The provider follows the MemoryProvider plugin contract documented
at https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin.

Config is stored in $HERMES_HOME/config.yaml under ``plugins.gbrain``:
  brain_slug_prefix: agents/hermes/memory
  auto_sync_turns: "false"
  capture_on_pre_compress: "false"
  max_results: "5"
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from agent.memory_provider import MemoryProvider
from agent.redact import redact_sensitive_text
from tools.registry import tool_error

logger = logging.getLogger(__name__)

_DEFAULT_SLUG_PREFIX = "agents/hermes/memory"
_DEFAULT_MAX_RESULTS = 5
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9/_-]*$")
_SECRET_CAPTURE_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|passwd|credential|authorization|private[_-]?key)\s*[:=]|authorization\s+bearer\s+|-----BEGIN[A-Z ]*PRIVATE KEY-----"
)
_SECRET_ERROR_REPLACEMENTS = [
    re.compile(r"((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:\s]+:)([^@\s]+)(@)", re.IGNORECASE),
    re.compile(r"(Authorization:\s*Bearer\s+)(\S+)", re.IGNORECASE),
    re.compile(r"(Authorization\s+Bearer\s+)(\S+)", re.IGNORECASE),
    re.compile(r"([A-Z0-9_]{0,50}(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE[_-]?KEY)[A-Z0-9_]{0,50}\s*[=:]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,}|hf_[A-Za-z0-9]{10,}|xox[baprs]-[A-Za-z0-9-]{10,})"),
]

Runner = Callable[..., str]


SEARCH_SCHEMA = {
    "name": "gbrain_search",
    "description": "Keyword search GBrain's durable knowledge store. Returns raw matching pages/snippets.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search terms."},
            "limit": {"type": "integer", "description": "Maximum results, default from plugin config."},
        },
        "required": ["query"],
    },
}

QUERY_SCHEMA = {
    "name": "gbrain_query",
    "description": "Ask GBrain a semantic/hybrid query over durable knowledge.",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "Question to ask GBrain."},
            "limit": {"type": "integer", "description": "Maximum results, default from plugin config."},
            "no_expand": {"type": "boolean", "description": "Disable query expansion."},
        },
        "required": ["question"],
    },
}

GET_SCHEMA = {
    "name": "gbrain_get",
    "description": "Read a GBrain page by slug.",
    "parameters": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "GBrain page slug."},
        },
        "required": ["slug"],
    },
}

REMEMBER_SCHEMA = {
    "name": "gbrain_remember",
    "description": "Persist a durable fact, project note, or knowledge artifact into GBrain as markdown.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Content to remember."},
            "category": {"type": "string", "description": "Short category such as preference, project, person, concept, or agent."},
            "slug": {"type": "string", "description": "Optional explicit destination slug."},
            "source": {"type": "string", "description": "Optional source label."},
        },
        "required": ["content"],
    },
}

ALL_TOOL_SCHEMAS = [SEARCH_SCHEMA, QUERY_SCHEMA, GET_SCHEMA, REMEMBER_SCHEMA]


def _default_runner(args: list[str], *, input_text: str | None = None, timeout: float = 15.0) -> str:
    """Run a gbrain CLI command and return stdout.

    No shell is used, so arguments are not interpolated. Stderr is included in
    raised exceptions but not logged separately to avoid accidental secret leaks.
    """
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr or stdout or f"exit {result.returncode}"
        raise RuntimeError(f"gbrain command failed: {detail[:500]}")
    return result.stdout or ""


def _load_plugin_config() -> dict:
    try:
        from hermes_constants import get_hermes_home
        import yaml

        config_path = get_hermes_home() / "config.yaml"
        if not config_path.exists():
            return {}
        data = yaml.safe_load(config_path.read_text()) or {}
        return data.get("plugins", {}).get("gbrain", {}) or {}
    except Exception:
        return {}


def _parse_json_or_text(output: str) -> Any:
    text = (output or "").strip()
    if not text:
        return {"ok": True}
    try:
        return json.loads(text)
    except Exception:
        return {"text": text}


def _safe_slug_part(text: str, *, default: str = "note") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)[:80].strip("-")
    return slug or default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class GBrainMemoryProvider(MemoryProvider):
    """Hermes MemoryProvider backed by the local gbrain CLI."""

    def __init__(self, *, runner: Runner | None = None, config: dict | None = None):
        self._runner = runner or _default_runner
        self._config = config if config is not None else _load_plugin_config()
        self._hermes_home: Path | None = None
        self._session_id = ""
        self._user_id = "default"
        self._platform = "cli"
        self._prefetch_result = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_generation = 0
        self._prefetch_thread: Optional[threading.Thread] = None
        self._sync_thread: Optional[threading.Thread] = None
        self._last_capture_ok = False

    @property
    def name(self) -> str:
        return "gbrain"

    def is_available(self) -> bool:
        """Check local CLI availability only. No network calls."""
        return shutil.which("gbrain") is not None

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "brain_slug_prefix",
                "description": "GBrain slug prefix for Hermes-captured memory pages",
                "default": _DEFAULT_SLUG_PREFIX,
            },
            {
                "key": "auto_sync_turns",
                "description": "Automatically save completed turns to GBrain (usually keep false to avoid noise)",
                "default": "false",
                "choices": ["true", "false"],
            },
            {
                "key": "capture_on_pre_compress",
                "description": "Capture recent context before compression (usually keep false for privacy)",
                "default": "false",
                "choices": ["true", "false"],
            },
            {
                "key": "max_results",
                "description": "Default max search/query results",
                "default": str(_DEFAULT_MAX_RESULTS),
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write non-secret config to $HERMES_HOME/config.yaml."""
        import yaml

        config_path = Path(hermes_home) / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if config_path.exists():
            existing = yaml.safe_load(config_path.read_text()) or {}
        existing.setdefault("plugins", {})
        merged = dict(existing["plugins"].get("gbrain", {}) or {})
        merged.update(values)
        existing["plugins"]["gbrain"] = merged
        config_path.write_text(yaml.safe_dump(existing, sort_keys=False))

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._hermes_home = Path(str(kwargs.get("hermes_home") or ".")).expanduser()
        self._user_id = str(kwargs.get("user_id") or kwargs.get("user_name") or "default")
        self._platform = str(kwargs.get("platform") or "cli")

    def system_prompt_block(self) -> str:
        return (
            "# GBrain Memory\n"
            "Active. Use gbrain_query for durable knowledge recall, gbrain_search for keyword lookup, "
            "gbrain_get for exact pages, and gbrain_remember for durable facts/artifacts."
        )

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return ALL_TOOL_SCHEMAS

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        try:
            payload = self._dispatch(tool_name, args or {})
            return json.dumps(payload, ensure_ascii=False)
        except Exception as exc:
            return tool_error(self._sanitize_error(exc))

    def _dispatch(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "gbrain_search":
            query = str(args.get("query") or "").strip()
            if not query:
                return {"error": "query is required"}
            limit = self._bounded_limit(args.get("limit"))
            return self._run_json(["gbrain", "--json", "search", query, "--limit", str(limit)], timeout=10)

        if tool_name == "gbrain_query":
            question = str(args.get("question") or args.get("query") or "").strip()
            if not question:
                return {"error": "question is required"}
            cmd = ["gbrain", "--json", "query", question, "--limit", str(self._bounded_limit(args.get("limit")))]
            if args.get("no_expand"):
                cmd.append("--no-expand")
            return self._run_json(cmd, timeout=20)

        if tool_name == "gbrain_get":
            slug = self._validate_slug(args.get("slug"))
            out = self._runner(["gbrain", "get", slug], timeout=10)
            return {"slug": slug, "content": out}

        if tool_name == "gbrain_remember":
            content = str(args.get("content") or "").strip()
            if not content:
                return {"error": "content is required"}
            category = str(args.get("category") or "note").strip() or "note"
            source = str(args.get("source") or "gbrain_remember").strip() or "gbrain_remember"
            slug = self._validate_slug(str(args.get("slug") or "").strip() or self._build_slug(content, category))
            markdown = self._build_markdown(content=content, category=category, source=source)
            return self._put_markdown(slug, markdown)

        return {"error": f"Unknown tool: {tool_name}"}

    def _sanitize_error(self, exc: Exception) -> str:
        message = str(exc)
        for pattern in _SECRET_ERROR_REPLACEMENTS:
            message = pattern.sub(lambda m: (m.group(1) + "***" + (m.group(3) if len(m.groups()) >= 3 else "")) if len(m.groups()) >= 2 else "***", message)
        message = redact_sensitive_text(message)[:240]
        return message or "gbrain command failed"

    def _validate_slug(self, slug: str) -> str:
        slug = str(slug or "").strip().strip("/")
        if not slug:
            raise ValueError("slug is required")
        if slug.startswith("-") or ".." in slug.split("/") or not _SLUG_RE.fullmatch(slug):
            raise ValueError("invalid slug: use lowercase letters, digits, '/', '_' and '-' only")
        return slug

    def _should_capture_text(self, text: str) -> bool:
        return bool(text.strip()) and not _SECRET_CAPTURE_RE.search(text)

    def _run_json(self, cmd: list[str], *, timeout: float) -> Any:
        return _parse_json_or_text(self._runner(cmd, timeout=timeout))

    def _bounded_limit(self, value: Any) -> int:
        try:
            n = int(value) if value is not None else int(self._config.get("max_results", _DEFAULT_MAX_RESULTS))
        except Exception:
            n = _DEFAULT_MAX_RESULTS
        return max(1, min(n, 20))

    def _slug_prefix(self) -> str:
        prefix = str(self._config.get("brain_slug_prefix") or _DEFAULT_SLUG_PREFIX)
        try:
            return self._validate_slug(prefix)
        except ValueError:
            logger.warning("Invalid GBrain slug prefix %r; using default", prefix)
            return _DEFAULT_SLUG_PREFIX

    def _build_slug(self, content: str, category: str) -> str:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
        stem = _safe_slug_part(content[:72], default="memory")
        cat = _safe_slug_part(category, default="note")
        return f"{self._slug_prefix()}/{date}-{cat}-{stem}-{digest}"

    def _build_markdown(self, *, content: str, category: str, source: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        frontmatter = yaml.safe_dump(
            {
                "title": content.splitlines()[0][:80],
                "category": str(category)[:80],
                "source": str(source)[:120],
                "session_id": self._session_id,
                "user_id": self._user_id,
                "platform": self._platform,
                "created_at": now,
            },
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        return f"---\n{frontmatter}\n---\n\n{content}\n"

    def _put_markdown(self, slug: str, markdown: str) -> Any:
        result = self._runner(["gbrain", "put", slug, "--content"], input_text=markdown, timeout=10)
        parsed = _parse_json_or_text(result)
        if isinstance(parsed, dict):
            parsed.setdefault("slug", slug)
            parsed.setdefault("ok", True)
            return parsed
        return {"ok": True, "slug": slug, "result": parsed}

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        query = str(query or "").strip()
        if not query or query.startswith("/"):
            return
        with self._prefetch_lock:
            self._prefetch_generation += 1
            self._prefetch_result = ""
            generation = self._prefetch_generation
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=2.0)
        self._prefetch_thread = threading.Thread(
            target=self._prefetch_worker,
            args=(query, generation),
            name="gbrain-prefetch",
            daemon=True,
        )
        self._prefetch_thread.start()

    def _prefetch_worker(self, query: str, generation: int) -> None:
        try:
            result = self._run_json(["gbrain", "--json", "query", query, "--limit", str(self._bounded_limit(None))], timeout=20)
            block = self._format_context(result)
            if block:
                with self._prefetch_lock:
                    if generation == self._prefetch_generation:
                        self._prefetch_result = block
        except Exception as exc:
            logger.debug("GBrain prefetch failed: %s", self._sanitize_error(exc))

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""
        return result

    def _format_context(self, payload: Any) -> str:
        if not payload:
            return ""
        if isinstance(payload, str):
            body = payload.strip()
            return f"[GBrain Context]\n{body}" if body else ""
        if not isinstance(payload, dict):
            return f"[GBrain Context]\n{payload}"

        lines = ["[GBrain Context]"]
        answer = payload.get("answer") or payload.get("text") or payload.get("content")
        if answer:
            lines.append(str(answer).strip())

        sources = payload.get("sources") or payload.get("results") or []
        if isinstance(sources, list) and sources:
            lines.append("Sources:")
            for item in sources[: self._bounded_limit(None)]:
                if isinstance(item, dict):
                    slug = item.get("slug") or item.get("path") or item.get("title") or item.get("id")
                    snippet = item.get("snippet") or item.get("content") or item.get("text") or ""
                    if slug and snippet:
                        lines.append(f"- {slug}: {str(snippet)[:240]}")
                    elif slug:
                        lines.append(f"- {slug}")
                else:
                    lines.append(f"- {str(item)[:240]}")

        return "\n".join(line for line in lines if line).strip() if len(lines) > 1 else ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Optionally save completed turns. Non-blocking by default."""
        if not _truthy(self._config.get("auto_sync_turns", os.environ.get("GBRAIN_MEMORY_AUTO_SYNC", "false"))):
            return
        user_content = str(user_content or "").strip()
        assistant_content = str(assistant_content or "").strip()
        if not user_content:
            return
        content = f"User: {user_content}\n\nAssistant: {assistant_content}"
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=2.0)
        self._sync_thread = threading.Thread(
            target=self._safe_put_capture,
            args=(content, "conversation", "hermes-sync-turn"),
            name="gbrain-sync-turn",
            daemon=True,
        )
        self._sync_thread.start()

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        **kwargs,
    ) -> None:
        self._session_id = str(new_session_id or self._session_id)
        with self._prefetch_lock:
            self._prefetch_result = ""
            self._prefetch_generation += 1

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if action not in {"add", "replace"}:
            return
        text = str(content or "").strip()
        if not text:
            return
        category = "user" if target == "user" else "memory"
        self._safe_put_capture(text, category, "hermes-memory-tool")

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        if not _truthy(self._config.get("capture_on_pre_compress", os.environ.get("GBRAIN_MEMORY_PRE_COMPRESS", "false"))):
            return ""
        chunks: list[str] = []
        for msg in messages[-8:]:
            role = msg.get("role", "")
            if role not in {"user", "assistant"}:
                continue
            content = str(msg.get("content") or "").strip()
            if content:
                chunks.append(f"{role}: {content[:1000]}")
        if not chunks:
            return ""
        text = "\n\n".join(chunks)
        if self._safe_put_capture(text, "session", "hermes-pre-compress"):
            return "GBrain captured recent context before compression."
        return ""

    def _safe_put_capture(self, content: str, category: str, source: str) -> bool:
        self._last_capture_ok = False
        try:
            if not self._should_capture_text(content):
                return False
            slug = self._build_slug(content, category)
            markdown = self._build_markdown(content=content, category=category, source=source)
            self._put_markdown(slug, markdown)
            self._last_capture_ok = True
            return True
        except Exception as exc:
            logger.debug("GBrain capture failed: %s", self._sanitize_error(exc))
            return False

    def shutdown(self) -> None:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=5.0)
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5.0)


def register(ctx) -> None:
    """Register GBrain as a memory provider plugin."""
    ctx.register_memory_provider(GBrainMemoryProvider())
