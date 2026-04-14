"""ClawMem memory plugin — MemoryProvider interface.

GitHub Issues-backed long-term memory with semantic search, conversation
mirroring, and multi-agent collaboration via git.clawmem.ai.

Memories are stored as GitHub Issues (type:memory label, flat YAML body).
Sessions are mirrored as GitHub Issues (type:conversation) with comments.
Deduplication by SHA-256 of normalized detail text.

Config in $HERMES_HOME/config.yaml (profile-scoped):
  memory:
    provider: clawmem
  clawmem:
    base_url: https://git.clawmem.ai/api/v3
    token: ""
    default_repo: ""
    auth_scheme: token
    auto_recall_limit: 3
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import re
import threading
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://git.clawmem.ai/api/v3"
_MEMORY_TITLE_PREFIX = "Memory: "
_MEMORY_LABEL = "type:memory"
_CONVERSATION_LABEL = "type:conversation"

# ── Tool schemas ─────────────────────────────────────────────────────────

MEMORY_RECALL_SCHEMA = {
    "name": "memory_recall",
    "description": (
        "Search long-term memory for relevant context. Returns matching memories "
        "ranked by relevance. Use before answering when past decisions, preferences, "
        "or learned patterns could help."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "limit": {"type": "integer", "description": "Max results (default: 5)."},
        },
        "required": ["query"],
    },
}

MEMORY_STORE_SCHEMA = {
    "name": "memory_store",
    "description": (
        "Store a durable memory. One fact per memory, keep detail concise. "
        "Automatically deduplicates by content hash.\n\n"
        "Use for: user preferences, decisions, conventions, lessons learned, "
        "recurring patterns, task context.\n"
        "Do NOT store: session logs, temporary state, raw data dumps."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "detail": {"type": "string", "description": "The memory content. One clear fact."},
            "title": {"type": "string", "description": "Optional short title."},
            "kind": {
                "type": "string",
                "enum": ["core-fact", "convention", "lesson", "skill", "task"],
                "description": "Memory classification.",
            },
            "topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Topic tags (kebab-case).",
            },
        },
        "required": ["detail"],
    },
}

MEMORY_UPDATE_SCHEMA = {
    "name": "memory_update",
    "description": "Update an existing memory by issue number.",
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer", "description": "Issue number of the memory."},
            "detail": {"type": "string", "description": "New detail text."},
            "title": {"type": "string", "description": "New title."},
            "kind": {"type": "string", "description": "New kind label."},
            "topics": {"type": "array", "items": {"type": "string"}, "description": "New topic tags."},
        },
        "required": ["memory_id"],
    },
}

MEMORY_FORGET_SCHEMA = {
    "name": "memory_forget",
    "description": "Mark a memory as stale (soft-delete by closing the issue).",
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer", "description": "Issue number of the memory."},
        },
        "required": ["memory_id"],
    },
}

MEMORY_GET_SCHEMA = {
    "name": "memory_get",
    "description": "Retrieve a single memory by issue number.",
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {"type": "integer", "description": "Issue number."},
        },
        "required": ["memory_id"],
    },
}

MEMORY_LIST_SCHEMA = {
    "name": "memory_list",
    "description": "List memories with optional filters.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "stale", "all"], "description": "Filter by status (default: active)."},
            "kind": {"type": "string", "description": "Filter by kind label."},
            "topic": {"type": "string", "description": "Filter by topic label."},
            "limit": {"type": "integer", "description": "Max results (default: 20)."},
        },
    },
}

MEMORY_LABELS_SCHEMA = {
    "name": "memory_labels",
    "description": "List existing kind and topic labels (the memory schema).",
    "parameters": {"type": "object", "properties": {}},
}

MEMORY_REPOS_SCHEMA = {
    "name": "memory_repos",
    "description": "List accessible memory repos. Shows which repo is the current default.",
    "parameters": {"type": "object", "properties": {}},
}

MEMORY_REPO_CREATE_SCHEMA = {
    "name": "memory_repo_create",
    "description": "Create a new memory repo (e.g. for a separate project or team).",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Repo name (kebab-case)."},
            "description": {"type": "string", "description": "Short description."},
            "private": {"type": "boolean", "description": "Private repo (default: true)."},
        },
        "required": ["name"],
    },
}

ALL_TOOL_SCHEMAS = [
    MEMORY_RECALL_SCHEMA,
    MEMORY_STORE_SCHEMA,
    MEMORY_UPDATE_SCHEMA,
    MEMORY_FORGET_SCHEMA,
    MEMORY_GET_SCHEMA,
    MEMORY_LIST_SCHEMA,
    MEMORY_LABELS_SCHEMA,
    MEMORY_REPOS_SCHEMA,
    MEMORY_REPO_CREATE_SCHEMA,
]

# ── Helpers ──────────────────────────────────────────────────────────────


def _memory_hash(detail: str) -> str:
    normalized = re.sub(r"\s+", " ", detail.strip())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _today() -> str:
    return datetime.date.today().isoformat()


def _build_memory_body(detail: str, date: str | None = None) -> str:
    h = _memory_hash(detail)
    d = date or _today()
    # Flat YAML matching ClawMem's format
    lines = [f"memory_hash: {h}", f"date: {d}"]
    if "\n" in detail:
        lines.append("detail: |-")
        for line in detail.split("\n"):
            lines.append(f"  {line}")
    else:
        lines.append(f"detail: {detail}")
    return "\n".join(lines)


def _parse_memory_body(body: str) -> dict:
    """Parse flat YAML body into dict."""
    result: Dict[str, str] = {}
    current_key = ""
    multiline_lines: list[str] = []
    in_multiline = False

    for raw_line in (body or "").split("\n"):
        if in_multiline:
            if raw_line.startswith("  "):
                multiline_lines.append(raw_line[2:])
                continue
            else:
                result[current_key] = "\n".join(multiline_lines)
                in_multiline = False
                multiline_lines = []

        m = re.match(r"^([A-Za-z0-9_]+):\s?(.*)", raw_line)
        if m:
            key, value = m.group(1), m.group(2)
            if value == "|-":
                current_key = key
                in_multiline = True
            else:
                result[key] = value.strip()

    if in_multiline:
        result[current_key] = "\n".join(multiline_lines)

    return result


def _build_labels(kind: str | None, topics: list[str] | None) -> list[str]:
    labels = [_MEMORY_LABEL]
    if kind:
        labels.append(f"kind:{kind}")
    for t in topics or []:
        labels.append(f"topic:{t}")
    return labels


def _parse_issue_to_memory(issue: dict) -> dict:
    """Convert a GitHub issue dict to a memory record."""
    parsed = _parse_memory_body(issue.get("body", ""))
    label_names = [l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])]
    kind = None
    topics = []
    for ln in label_names:
        if ln.startswith("kind:"):
            kind = ln[5:]
        elif ln.startswith("topic:"):
            topics.append(ln[6:])
    return {
        "memory_id": issue.get("number"),
        "title": (issue.get("title") or "").removeprefix(_MEMORY_TITLE_PREFIX),
        "detail": parsed.get("detail", ""),
        "kind": kind,
        "topics": topics,
        "date": parsed.get("date", ""),
        "status": "stale" if issue.get("state") == "closed" else "active",
    }


def _sanitize_query(text: str) -> str:
    """Strip platform metadata and prior recall injection from query text."""
    text = re.sub(r"<clawmem-context>.*?</clawmem-context>", "", text, flags=re.DOTALL)
    text = re.sub(r"^\[?(telegram|whatsapp|discord|slack)\]?\s*", "", text, flags=re.IGNORECASE)
    return text.strip()[:1500]


# ── Config ───────────────────────────────────────────────────────────────


def _load_plugin_config() -> dict:
    from hermes_constants import get_hermes_home
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path) as f:
            all_config = yaml.safe_load(f) or {}
        return all_config.get("clawmem", {}) or {}
    except Exception:
        return {}


# ── MemoryProvider ───────────────────────────────────────────────────────


class ClawMemProvider(MemoryProvider):
    """ClawMem: GitHub Issues-backed long-term memory."""

    def __init__(self, config: dict | None = None):
        self._config = config or _load_plugin_config()
        self._client = None
        self._repo = ""
        self._session_id = ""
        self._session_issue_number: int | None = None
        self._session_lock = threading.Lock()
        self._first_user_message: str = ""
        self._is_primary = False  # only mirror conversations for primary agent
        self._auto_recall_limit = int(self._config.get("auto_recall_limit", 3))

    @property
    def name(self) -> str:
        return "clawmem"

    def is_available(self) -> bool:
        token = self._config.get("token", "")
        base_url = self._config.get("base_url", _DEFAULT_BASE_URL)
        # Available if we have a token, or a base_url to try auto-provision
        return bool(token) or bool(base_url)

    def get_config_schema(self) -> list:
        return [
            {
                "key": "base_url",
                "description": "ClawMem API base URL",
                "default": _DEFAULT_BASE_URL,
            },
            {
                "key": "token",
                "description": "API token (auto-provisioned on first use if empty)",
                "secret": True,
                "env_var": "CLAWMEM_TOKEN",
            },
            {
                "key": "default_repo",
                "description": "Default memory repo (owner/name, auto-created if empty)",
            },
            {
                "key": "auth_scheme",
                "description": "Auth scheme",
                "default": "token",
                "choices": ["token", "bearer"],
            },
            {
                "key": "auto_recall_limit",
                "description": "Max memories to auto-recall per turn",
                "default": "3",
            },
        ]

    def save_config(self, values: dict, hermes_home: str) -> None:
        from pathlib import Path
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing = {}
            if config_path.exists():
                with open(config_path) as f:
                    existing = yaml.safe_load(f) or {}
            existing["clawmem"] = values
            with open(config_path, "w") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception as e:
            logger.warning("Failed to save clawmem config: %s", e)

    def initialize(self, session_id: str, **kwargs) -> None:
        from .client import GitHubIssueClient

        self._session_id = session_id
        self._is_primary = kwargs.get("agent_context", "primary") == "primary"
        base_url = self._config.get("base_url", _DEFAULT_BASE_URL)
        token = self._config.get("token", "")
        auth_scheme = self._config.get("auth_scheme", "token")
        self._repo = self._config.get("default_repo", "")

        # Derive agent login prefix from hermes profile identity
        agent_identity = kwargs.get("agent_identity", "hermes")
        prefix_login = re.sub(r"[^a-z0-9-]", "-", (agent_identity or "hermes").lower())[:32]

        if not token:
            tmp_client = GitHubIssueClient(base_url)
            # Primary: POST /agents
            try:
                result = tmp_client.register_agent(
                    prefix_login=prefix_login,
                    default_repo_name="memory",
                )
                token = result.get("token", "")
                self._repo = result.get("repo_full_name", self._repo)
            except Exception as e:
                err_msg = str(e)
                # Fallback: POST /anonymous/session on 404/405/501
                if any(f"HTTP {c}" in err_msg for c in ("404", "405", "501")):
                    try:
                        result = tmp_client.anonymous_session()
                        token = result.get("token", "")
                        self._repo = result.get("repo_full_name", self._repo)
                    except Exception as e2:
                        logger.warning("ClawMem anonymous fallback failed: %s", e2)
                else:
                    logger.warning("ClawMem auto-provision failed: %s", e)

            if token:
                self._config["token"] = token
                self._config["default_repo"] = self._repo
                self._config["base_url"] = base_url
                self._config["auth_scheme"] = auth_scheme
                # Persist to config.yaml so token survives restarts
                hermes_home = kwargs.get("hermes_home", "")
                if hermes_home:
                    self.save_config(self._config, str(hermes_home))
                logger.info("ClawMem auto-provisioned: repo=%s", self._repo)

        if not token:
            logger.warning("ClawMem: no token available, provider inactive")
            return

        self._client = GitHubIssueClient(base_url, token, auth_scheme)

        # Ensure core labels exist
        if self._repo:
            self._ensure_labels()

    def _ensure_labels(self) -> None:
        """Create core labels if they don't exist yet."""
        if not self._client or not self._repo:
            return
        try:
            core_labels = [
                (_MEMORY_LABEL, "1d76db"),
                (_CONVERSATION_LABEL, "1d76db"),
                ("kind:core-fact", "5319e7"),
                ("kind:convention", "5319e7"),
                ("kind:lesson", "5319e7"),
                ("kind:skill", "5319e7"),
                ("kind:task", "5319e7"),
            ]
            for label_name, color in core_labels:
                self._client.ensure_label(self._repo, label_name, color)
        except Exception as e:
            logger.debug("ClawMem label setup: %s", e)

    def system_prompt_block(self) -> str:
        if not self._client:
            return ""
        return (
            "# ClawMem\n"
            "Long-term memory active. Memories persist across sessions as structured issues.\n"
            "Use memory_recall before answering when past context could help.\n"
            "Use memory_store to save durable facts (one fact per memory, concise).\n"
            "Use memory_forget to mark outdated memories as stale."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._client or not self._repo or not query:
            return ""
        sanitized = _sanitize_query(query)
        if not sanitized:
            return ""
        try:
            issues = self._client.search_issues(
                sanitized,
                self._repo,
                extra_qualifiers='state:open label:"type:memory"',
            )
            if not issues:
                return ""
            lines = ["ClawMem relevant memories:"]
            for issue in issues[: self._auto_recall_limit]:
                mem = _parse_issue_to_memory(issue)
                mid = mem["memory_id"]
                detail = mem["detail"][:200]
                lines.append(f"- [{mid}] {detail}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug("ClawMem prefetch failed: %s", e)
            return ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Mirror turn to conversation issue in a background thread."""
        if not self._client or not self._repo or not self._is_primary:
            return

        # Capture first user message for session title
        if not self._first_user_message and user_content:
            self._first_user_message = user_content[:120]

        def _mirror():
            try:
                # Create session issue on first turn (lock prevents duplicate creation)
                with self._session_lock:
                    if self._session_issue_number is None:
                        body = "\n".join([
                            "type: conversation",
                            f"session_id: {self._session_id}",
                            f"date: {_today()}",
                        ])
                        issue = self._client.create_issue(
                            self._repo,
                            title=f"Session: {self._session_id[:8]}",
                            body=body,
                            labels=[_CONVERSATION_LABEL, f"session:{self._session_id[:8]}"],
                        )
                        self._session_issue_number = issue.get("number")

                if self._session_issue_number:
                    if user_content:
                        self._client.create_comment(
                            self._repo,
                            self._session_issue_number,
                            f"role: user\n\n{user_content[:4000]}",
                        )
                    if assistant_content:
                        self._client.create_comment(
                            self._repo,
                            self._session_issue_number,
                            f"role: assistant\n\n{assistant_content[:4000]}",
                        )
            except Exception as e:
                logger.debug("ClawMem sync_turn failed: %s", e)

        t = threading.Thread(target=_mirror, daemon=True)
        t.start()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        if not self._client:
            return []
        return ALL_TOOL_SCHEMAS

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if not self._client:
            return tool_error("ClawMem not initialized")
        try:
            handler = {
                "memory_recall": self._handle_recall,
                "memory_store": self._handle_store,
                "memory_update": self._handle_update,
                "memory_forget": self._handle_forget,
                "memory_get": self._handle_get,
                "memory_list": self._handle_list,
                "memory_labels": self._handle_labels,
                "memory_repos": self._handle_repos,
                "memory_repo_create": self._handle_repo_create,
            }.get(tool_name)
            if not handler:
                return tool_error(f"Unknown tool: {tool_name}")
            return handler(args)
        except Exception as e:
            return tool_error(str(e))

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Update conversation issue title from first user message, then close."""
        if not self._client or not self._repo or not self._session_issue_number or not self._is_primary:
            return
        try:
            # Derive a meaningful title from the first user message
            title = None
            if self._first_user_message:
                summary = self._first_user_message.split("\n")[0][:80].strip()
                if summary:
                    title = f"Session: {summary}"
            self._client.update_issue(
                self._repo,
                self._session_issue_number,
                title=title,
                state="closed",
            )
        except Exception as e:
            logger.debug("ClawMem session close failed: %s", e)

    def shutdown(self) -> None:
        # Close session issue if still open
        if self._client and self._repo and self._session_issue_number:
            try:
                self._client.update_issue(
                    self._repo,
                    self._session_issue_number,
                    state="closed",
                )
            except Exception:
                pass
        self._client = None

    # ── Tool handlers ────────────────────────────────────────────────────

    def _handle_recall(self, args: dict) -> str:
        query = args.get("query", "")
        if not query:
            return tool_error("'query' is required")
        limit = int(args.get("limit", 5))
        issues = self._client.search_issues(
            _sanitize_query(query),
            self._repo,
            extra_qualifiers='state:open label:"type:memory"',
        )
        memories = [_parse_issue_to_memory(i) for i in issues[:limit]]
        return json.dumps({"memories": memories, "count": len(memories)})

    def _handle_store(self, args: dict) -> str:
        detail = args.get("detail", "").strip()
        if not detail:
            return tool_error("'detail' is required")

        # Dedup check
        h = _memory_hash(detail)
        existing = self._client.search_issues(
            f'"{h}"',
            self._repo,
            extra_qualifiers='state:open label:"type:memory"',
        )
        if existing:
            mem = _parse_issue_to_memory(existing[0])
            return json.dumps({
                "status": "duplicate",
                "existing_memory_id": mem["memory_id"],
                "message": "A memory with identical content already exists.",
            })

        title_text = args.get("title") or detail[:80]
        kind = args.get("kind")
        topics = args.get("topics")
        labels = _build_labels(kind, topics)
        body = _build_memory_body(detail)

        # Ensure topic labels exist
        for t in topics or []:
            self._client.ensure_label(self._repo, f"topic:{t}", "fbca04")

        issue = self._client.create_issue(
            self._repo,
            title=f"{_MEMORY_TITLE_PREFIX}{title_text}",
            body=body,
            labels=labels,
        )
        return json.dumps({
            "status": "stored",
            "memory_id": issue.get("number"),
            "title": title_text,
        })

    def _handle_update(self, args: dict) -> str:
        memory_id = int(args["memory_id"])
        issue = self._client.get_issue(self._repo, memory_id)
        if not issue:
            return tool_error(f"Memory #{memory_id} not found")

        current = _parse_memory_body(issue.get("body", ""))
        new_detail = args.get("detail", current.get("detail", ""))
        new_title = args.get("title")

        # Rebuild body
        body = _build_memory_body(new_detail, date=current.get("date"))

        # Rebuild labels
        kind = args.get("kind")
        topics = args.get("topics")
        if kind is not None or topics is not None:
            # Get current labels to preserve non-managed ones
            current_labels = [
                (l["name"] if isinstance(l, dict) else l)
                for l in issue.get("labels", [])
            ]
            # Remove old kind/topic, keep others
            preserved = [l for l in current_labels if not l.startswith("kind:") and not l.startswith("topic:")]
            if kind:
                preserved.append(f"kind:{kind}")
            else:
                # Keep existing kind
                for l in current_labels:
                    if l.startswith("kind:"):
                        preserved.append(l)
                        break
            for t in topics or []:
                preserved.append(f"topic:{t}")
                self._client.ensure_label(self._repo, f"topic:{t}", "fbca04")

            self._client.update_issue(
                self._repo, memory_id,
                title=f"{_MEMORY_TITLE_PREFIX}{new_title}" if new_title else None,
                body=body,
                labels=preserved,
            )
        else:
            self._client.update_issue(
                self._repo, memory_id,
                title=f"{_MEMORY_TITLE_PREFIX}{new_title}" if new_title else None,
                body=body,
            )

        return json.dumps({"status": "updated", "memory_id": memory_id})

    def _handle_forget(self, args: dict) -> str:
        memory_id = int(args["memory_id"])
        self._client.update_issue(self._repo, memory_id, state="closed")
        return json.dumps({"status": "forgotten", "memory_id": memory_id})

    def _handle_get(self, args: dict) -> str:
        memory_id = int(args["memory_id"])
        issue = self._client.get_issue(self._repo, memory_id)
        if not issue:
            return tool_error(f"Memory #{memory_id} not found")
        return json.dumps(_parse_issue_to_memory(issue))

    def _handle_list(self, args: dict) -> str:
        status = args.get("status", "active")
        state = "open" if status == "active" else ("closed" if status == "stale" else "all")
        limit = min(int(args.get("limit", 20)), 50)

        label_parts = [_MEMORY_LABEL]
        if args.get("kind"):
            label_parts.append(f"kind:{args['kind']}")
        if args.get("topic"):
            label_parts.append(f"topic:{args['topic']}")

        issues = self._client.list_issues(
            self._repo,
            labels=",".join(label_parts),
            state=state,
            per_page=limit,
        )
        memories = [_parse_issue_to_memory(i) for i in issues]
        return json.dumps({"memories": memories, "count": len(memories)})

    def _handle_labels(self, args: dict) -> str:
        labels = self._client.list_labels(self._repo)
        kinds = []
        topics = []
        for l in labels:
            name = l["name"] if isinstance(l, dict) else l
            if name.startswith("kind:"):
                kinds.append(name[5:])
            elif name.startswith("topic:"):
                topics.append(name[6:])
        return json.dumps({"kinds": kinds, "topics": topics})

    def _handle_repos(self, args: dict) -> str:
        repos = self._client.list_repos()
        result = []
        for r in repos:
            full_name = r.get("full_name", "")
            result.append({
                "full_name": full_name,
                "description": r.get("description", ""),
                "private": r.get("private", True),
                "is_default": full_name == self._repo,
            })
        return json.dumps({"repos": result, "default_repo": self._repo})

    def _handle_repo_create(self, args: dict) -> str:
        name = args.get("name", "").strip()
        if not name:
            return tool_error("'name' is required")
        repo = self._client.create_repo(
            name=name,
            description=args.get("description", ""),
            private=args.get("private", True),
        )
        return json.dumps({
            "status": "created",
            "full_name": repo.get("full_name", ""),
        })


# ── Plugin entry point ───────────────────────────────────────────────────


def register(ctx) -> None:
    """Register the ClawMem memory provider with the plugin system."""
    config = _load_plugin_config()
    provider = ClawMemProvider(config=config)
    ctx.register_memory_provider(provider)
