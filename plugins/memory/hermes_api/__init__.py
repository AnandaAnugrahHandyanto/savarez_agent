"""Hermes API memory provider.

Provides contact-aware memory by resolving the current gateway user against a
local Hermes API people graph, injecting that contact's profile/memory into the
agent context, recalling relevant interactions, writing completed turns back to
Hermes API, and exposing lightweight contact/routing/followup tools.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://127.0.0.1:4000"
_TIMEOUT_SECONDS = 5
_MAX_CONTEXT_CHARS = 6000
_SKIP_SYNC_CONTEXTS = {"cron", "subagent", "flush"}
_MESSAGING_PLATFORMS = {"whatsapp", "telegram", "discord", "slack", "signal", "matrix"}
_ACCESS_TIER = {
    "self": "admin",
    "cofounder": "core",
    "partner": "core",
    "family": "trusted",
    "friend": "trusted",
    "colleague": "trusted",
    "mentor": "trusted",
    "mentee": "trusted",
    "client": "external",
    "vendor": "external",
    "investor": "external",
    "collaborator": "external",
    "advisor": "external",
    "contact": "unknown",
}


def _config_path(hermes_home: str) -> Path:
    return Path(hermes_home) / "hermes_api_memory.json"


def _load_config(hermes_home: Optional[str] = None) -> Dict[str, Any]:
    if hermes_home is None:
        try:
            from hermes_constants import get_hermes_home

            hermes_home = str(get_hermes_home())
        except Exception:
            hermes_home = ""
    if not hermes_home:
        return {}
    path = _config_path(hermes_home)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        logger.debug("Failed to parse Hermes API memory config at %s", path, exc_info=True)
        return {}


def _save_config(values: Dict[str, Any], hermes_home: str) -> None:
    clean = {}
    base_url = str(values.get("base_url") or "").strip().rstrip("/")
    if base_url:
        clean["base_url"] = base_url
    path = _config_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _base_url() -> str:
    env_value = os.environ.get("HERMES_API_BASE_URL", "").strip()
    if env_value:
        return env_value.rstrip("/")
    config_value = str(_load_config().get("base_url") or "").strip()
    return (config_value or _DEFAULT_BASE_URL).rstrip("/")


def _request_json(
    method: str,
    path: str,
    *,
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = _TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    url = f"{_base_url()}{path}"
    if query:
        clean_query = {k: v for k, v in query.items() if v is not None}
        url = f"{url}?{urllib.parse.urlencode(clean_query)}"

    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Hermes API {method} {path} failed with HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Hermes API unavailable at {_base_url()}: {exc.reason}") from exc

    if not raw.strip():
        return {}
    return json.loads(raw)


def _data(payload: Dict[str, Any]) -> Any:
    return payload.get("data") if isinstance(payload, dict) else None


def _result(success: bool, **kwargs: Any) -> str:
    return json.dumps({"success": success, **kwargs}, ensure_ascii=False)


def _quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _contact_label(contact: Dict[str, Any]) -> str:
    return str(contact.get("name") or contact.get("username") or contact.get("id") or "unknown")


def _truncate(text: str, limit: int = 2048) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_identity(identity: Dict[str, Any]) -> str:
    kind = identity.get("kind") or "unknown"
    value = identity.get("value") or identity.get("normalizedValue") or identity.get("id") or ""
    label = identity.get("label")
    primary = " primary" if identity.get("isPrimary") else ""
    label_text = f" ({label})" if label else ""
    return f"- {kind}: {value}{label_text}{primary}".rstrip()


def _format_whoami_context(whoami: Dict[str, Any]) -> str:
    contact = whoami.get("contact") if isinstance(whoami.get("contact"), dict) else None
    role = whoami.get("role") if isinstance(whoami.get("role"), dict) else None
    identities = whoami.get("identities") if isinstance(whoami.get("identities"), list) else []
    matched_by = whoami.get("matchedBy") or "none"
    candidates = whoami.get("candidates") if isinstance(whoami.get("candidates"), list) else []

    if not contact:
        parts = ["## Hermes API Memory", f"matchedBy: {matched_by}"]
        if candidates:
            parts.append("Ambiguous candidates:")
            for cand in candidates[:5]:
                parts.append(f"- {_contact_label(cand)} ({cand.get('username') or cand.get('id')})")
        return "\n".join(parts)

    parts = [f"## Current contact: {_contact_label(contact)}"]
    username = contact.get("username")
    email = contact.get("email")
    tags = contact.get("tags") or []
    if username:
        parts.append(f"username: {username}")
    if email:
        parts.append(f"email: {email}")
    if role:
        role_slug = str(role.get("slug") or "")
        access_tier = _ACCESS_TIER.get(role_slug, "unknown")
        parts.append(f"role: {role.get('name')} ({role_slug})")
        parts.append(f"access tier: {access_tier}")
    if tags:
        parts.append("tags: " + ", ".join(str(t) for t in tags))
    parts.append(f"matchedBy: {matched_by}")

    if identities:
        parts.append("### Identities\n" + "\n".join(_format_identity(i) for i in identities[:12]))

    contact_md = (contact.get("contactMd") or "").strip()
    memory_md = (contact.get("memoryMd") or "").strip()
    if contact_md:
        parts.append("### Contact profile\n" + contact_md)
    if memory_md:
        parts.append("### Contact memory\n" + memory_md)

    text = "\n\n".join(parts).strip()
    if len(text) > _MAX_CONTEXT_CHARS:
        text = text[: _MAX_CONTEXT_CHARS - 20].rstrip() + "\n…"
    return text


def _format_search_hits(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    parts = ["## Relevant contacts"]
    for row in rows[:5]:
        maybe_contact = row.get("contact")
        contact: Dict[str, Any] = maybe_contact if isinstance(maybe_contact, dict) else row
        maybe_role = row.get("role")
        role = maybe_role if isinstance(maybe_role, dict) else contact.get("role")
        maybe_identities = row.get("identities")
        identities = maybe_identities if isinstance(maybe_identities, list) else []
        line = f"- {_contact_label(contact)}"
        if contact.get("username"):
            line += f" (@{contact['username']})"
        if role:
            line += f" — {role.get('slug') or role.get('name')}"
        if identities:
            id_bits = [f"{i.get('kind')}:{i.get('value')}" for i in identities[:3]]
            line += " — " + ", ".join(id_bits)
        parts.append(line)
    return "\n".join(parts)


def _format_recall(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    parts = ["## Relevant past interactions"]
    for row in rows[:10]:
        summary = row.get("summary") or ""
        response = row.get("responseSummary") or ""
        score = row.get("score")
        score_text = f" score={score:.2f}" if isinstance(score, (int, float)) else ""
        line = f"- {summary}"
        if response:
            line += f" → {response}"
        if score_text:
            line += f" ({score_text.strip()})"
        parts.append(line)
    return "\n".join(parts)


def _extract_route_request(query: str) -> Optional[Dict[str, str]]:
    # Common gateway utterances: "send Disha on whatsapp", "message Anmol to telegram".
    match = re.search(
        r"\b(?:send|message|dm|text)\s+(.+?)\s+(?:on|to|via)\s+(whatsapp|telegram|discord|slack|signal|matrix)\b",
        query or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    name = match.group(1).strip(" ' \".,")
    platform = match.group(2).lower()
    if not name or platform not in _MESSAGING_PLATFORMS:
        return None
    return {"query": name, "platform": platform}


CONTACTS_SEARCH_SCHEMA = {
    "name": "hermes_api_contacts_search",
    "description": "Search contacts in Hermes API. Returns contact, joined role, and identities per hit.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search text."},
            "limit": {"type": "integer", "description": "Maximum hits.", "default": 5},
        },
        "required": ["query"],
    },
}

CONTACT_GET_SCHEMA = {
    "name": "hermes_api_contact_get",
    "description": "Get one Hermes API contact, including identities, contactMd, memoryMd, and joined role.",
    "parameters": {
        "type": "object",
        "properties": {"contact_id": {"type": "string", "description": "Contact id."}},
        "required": ["contact_id"],
    },
}

CONTACT_CREATE_SCHEMA = {
    "name": "hermes_api_contact_create",
    "description": "Create a Hermes API contact. Accepts role slug via `role`.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "username": {"type": "string"},
            "email": {"type": "string"},
            "role": {"type": "string", "description": "Role slug, e.g. cofounder/client/contact."},
            "tags": {"type": "array", "items": {"type": "string"}},
            "contactMd": {"type": "string"},
            "memoryMd": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": [],
    },
}

CONTACT_UPDATE_SCHEMA = {
    "name": "hermes_api_contact_update",
    "description": "Update a Hermes API contact. Accepts role slug via `role`.",
    "parameters": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string"},
            "name": {"type": "string"},
            "username": {"type": "string"},
            "email": {"type": "string"},
            "role": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "contactMd": {"type": "string"},
            "memoryMd": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["contact_id"],
    },
}

CONTACT_MEMORY_APPEND_SCHEMA = {
    "name": "hermes_api_contact_memory_append",
    "description": "Append a durable note to a contact's memoryMd in Hermes API.",
    "parameters": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string", "description": "Contact id."},
            "content": {"type": "string", "description": "Memory content to append."},
        },
        "required": ["contact_id", "content"],
    },
}

IDENTITY_RESOLVE_SCHEMA = {
    "name": "hermes_api_identity_resolve",
    "description": "Resolve a platform identity to a contact using Hermes API.",
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "description": "Identity kind, e.g. whatsapp, telegram, email."},
            "value": {"type": "string", "description": "Identity value to resolve."},
        },
        "required": ["kind", "value"],
    },
}

ROUTE_RESOLVE_SCHEMA = {
    "name": "hermes_api_route_resolve",
    "description": "Resolve a free-text contact query to an exact messaging platform target.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Contact query, e.g. Disha."},
            "platform": {"type": "string", "description": "Messaging platform, e.g. whatsapp."},
        },
        "required": ["query", "platform"],
    },
}

FOLLOWUP_CREATE_SCHEMA = {
    "name": "hermes_api_followup_create",
    "description": "Create a followup/reminder record in Hermes API.",
    "parameters": {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string"},
            "title": {"type": "string"},
            "due_at": {"type": "string", "description": "ISO datetime."},
            "status": {"type": "string", "enum": ["open", "done", "cancelled"]},
            "source_interaction_id": {"type": "string"},
            "metadata": {"type": "object"},
        },
        "required": ["title"],
    },
}

FOLLOWUP_LIST_SCHEMA = {
    "name": "hermes_api_followup_list",
    "description": "List followups from Hermes API.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["open", "done", "cancelled"]},
            "limit": {"type": "integer", "default": 20},
        },
        "required": [],
    },
}

FOLLOWUP_UPDATE_SCHEMA = {
    "name": "hermes_api_followup_update",
    "description": "Update a followup status/title/dueAt/metadata.",
    "parameters": {
        "type": "object",
        "properties": {
            "followup_id": {"type": "string"},
            "title": {"type": "string"},
            "due_at": {"type": "string"},
            "status": {"type": "string", "enum": ["open", "done", "cancelled"]},
            "metadata": {"type": "object"},
        },
        "required": ["followup_id"],
    },
}


class HermesApiMemoryProvider(MemoryProvider):
    """Contact-aware memory backed by the local Hermes API people graph."""

    def __init__(self) -> None:
        self._session_id = ""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._health_features: Optional[set[str]] = None
        self._lock = threading.RLock()
        self._workers: List[threading.Thread] = []

    @property
    def name(self) -> str:
        return "hermes_api"

    def is_available(self) -> bool:
        try:
            features = self._features()
        except Exception as exc:
            logger.debug("Hermes API health check failed: %s", exc)
            return False
        return "agent-whoami" in features

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "base_url",
                "description": "Hermes API base URL",
                "secret": False,
                "required": False,
                "default": _DEFAULT_BASE_URL,
                "env_var": "HERMES_API_BASE_URL",
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        _save_config(values, hermes_home)

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = session_id
        platform = str(kwargs.get("platform") or "")
        user_id = str(kwargs.get("user_id") or "")
        user_name = str(kwargs.get("user_name") or "")
        chat_id = str(kwargs.get("chat_id") or kwargs.get("chatId") or "")
        thread_id = str(kwargs.get("thread_id") or kwargs.get("threadId") or "")
        agent_context = str(kwargs.get("agent_context") or "primary")

        query = {"platform": platform or "cli", "userId": user_id or "unknown"}
        if user_name:
            query["userName"] = user_name

        whoami: Dict[str, Any]
        try:
            whoami = _data(_request_json("GET", "/api/v1/agent/whoami", query=query)) or {}
            if not isinstance(whoami, dict):
                whoami = {}
        except Exception as exc:
            logger.debug("Hermes API whoami failed: %s", exc)
            whoami = {"contact": None, "role": None, "identities": [], "matchedIdentity": None, "matchedBy": "none"}

        with self._lock:
            self._cache[session_id] = {
                "platform": platform,
                "user_id": user_id,
                "user_name": user_name,
                "chatId": chat_id,
                "threadId": thread_id,
                "agent_context": agent_context,
                "whoami": whoami,
            }

    def system_prompt_block(self) -> str:
        state = self._state_for(self._session_id)
        if not state:
            return (
                "# Hermes API Memory\n"
                f"Active. Base URL: {_base_url()}\n"
                "Provides contact-aware context from the Hermes API people graph."
            )
        return "# Hermes API Memory\n" + _format_whoami_context(state.get("whoami") or {})

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        sid = session_id or self._session_id
        state = self._state_for(sid)
        blocks: List[str] = []

        whoami = state.get("whoami") if state else {}
        contact = whoami.get("contact") if isinstance(whoami, dict) else None
        if isinstance(contact, dict) and contact.get("id"):
            try:
                recall = _data(
                    _request_json(
                        "GET",
                        f"/api/v1/contacts/{_quote(str(contact['id']))}/recall",
                        query={"q": query, "limit": "5"},
                    )
                )
                interactions = recall.get("interactions") if isinstance(recall, dict) else []
                recall_block = _format_recall(interactions if isinstance(interactions, list) else [])
                if recall_block:
                    blocks.append(recall_block)
            except Exception as exc:
                logger.debug("Hermes API recall failed: %s", exc)

        if query.strip():
            try:
                hits = _data(
                    _request_json(
                        "GET",
                        "/api/v1/contacts/search",
                        query={"q": query, "limit": "5"},
                    )
                )
                search_block = _format_search_hits(hits if isinstance(hits, list) else [])
                if search_block:
                    blocks.append(search_block)
            except Exception as exc:
                logger.debug("Hermes API contacts search failed: %s", exc)

            route_req = _extract_route_request(query)
            if route_req:
                try:
                    route = _data(_request_json("POST", "/api/v1/routes/resolve", body=route_req))
                    if isinstance(route, dict):
                        target = route.get("target") or ""
                        maybe_route_contact = route.get("contact")
                        route_contact: Dict[str, Any] = (
                            maybe_route_contact if isinstance(maybe_route_contact, dict) else {}
                        )
                        blocks.append(
                            "## Resolved route\n"
                            f"- {_contact_label(route_contact)} → {target}".rstrip()
                        )
                except Exception as exc:
                    logger.debug("Hermes API route resolve failed: %s", exc)

        if not blocks:
            return ""
        text = "\n\n".join(blocks)
        if len(text) > _MAX_CONTEXT_CHARS:
            text = text[: _MAX_CONTEXT_CHARS - 20].rstrip() + "\n…"
        return "<hermes-api-context>\n" + text + "\n</hermes-api-context>"

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        sid = session_id or self._session_id
        state = self._state_for(sid)
        if not state or str(state.get("agent_context") or "primary") in _SKIP_SYNC_CONTEXTS:
            return

        worker = threading.Thread(
            target=self._sync_turn_now,
            args=(sid, state, user_content, assistant_content),
            daemon=True,
        )
        worker.start()
        with self._lock:
            self._workers.append(worker)

    def shutdown(self) -> None:
        with self._lock:
            workers = list(self._workers)
            self._workers.clear()
        for worker in workers:
            worker.join(timeout=2)

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        **kwargs: Any,
    ) -> None:
        self._session_id = new_session_id
        if reset:
            with self._lock:
                self._cache.pop(new_session_id, None)

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if action not in {"add", "replace"} or target != "user":
            return
        contact = self._current_contact()
        if not contact or not contact.get("id"):
            return
        entry = content.strip()
        if not entry:
            return
        try:
            self._append_contact_memory(str(contact["id"]), entry)
        except Exception as exc:
            logger.debug("Hermes API memory mirror failed: %s", exc)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas_by_feature = [
            ("contact-search", CONTACTS_SEARCH_SCHEMA),
            ("contacts", CONTACT_GET_SCHEMA),
            ("contacts", CONTACT_CREATE_SCHEMA),
            ("contacts", CONTACT_UPDATE_SCHEMA),
            ("contact-memory-append", CONTACT_MEMORY_APPEND_SCHEMA),
            ("identities", IDENTITY_RESOLVE_SCHEMA),
            ("route-resolve", ROUTE_RESOLVE_SCHEMA),
            ("followups", FOLLOWUP_CREATE_SCHEMA),
            ("followups", FOLLOWUP_LIST_SCHEMA),
            ("followups", FOLLOWUP_UPDATE_SCHEMA),
        ]
        try:
            features = self._features()
        except Exception:
            # If health is temporarily unavailable after provider selection, keep
            # the schemas visible and let individual calls surface API errors.
            return [schema for _, schema in schemas_by_feature]
        return [schema for feature, schema in schemas_by_feature if feature in features]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs: Any) -> str:
        try:
            handlers = {
                "hermes_api_contacts_search": self._tool_contacts_search,
                "hermes_api_contact_get": self._tool_contact_get,
                "hermes_api_contact_create": self._tool_contact_create,
                "hermes_api_contact_update": self._tool_contact_update,
                "hermes_api_contact_memory_append": self._tool_contact_memory_append,
                "hermes_api_identity_resolve": self._tool_identity_resolve,
                "hermes_api_route_resolve": self._tool_route_resolve,
                "hermes_api_followup_create": self._tool_followup_create,
                "hermes_api_followup_list": self._tool_followup_list,
                "hermes_api_followup_update": self._tool_followup_update,
                # Backward-compatible aliases from the first local draft.
                "hermes_api_resolve_identity": self._tool_identity_resolve,
                "hermes_api_get_contact": self._tool_contact_get,
                "hermes_api_list_contacts": self._tool_contacts_search,
                "hermes_api_append_contact_memory": self._tool_contact_memory_append,
            }
            if tool_name in handlers:
                return handlers[tool_name](args)
        except Exception as exc:
            return tool_error(str(exc), tool=tool_name)
        raise NotImplementedError(f"Provider {self.name} does not handle tool {tool_name}")

    def _features(self) -> set[str]:
        with self._lock:
            if self._health_features is not None:
                return set(self._health_features)
        health = _data(_request_json("GET", "/api/health")) or {}
        if not isinstance(health, dict):
            return set()
        raw_features = health.get("features")
        features = {str(item) for item in raw_features} if isinstance(raw_features, list) else set()
        with self._lock:
            self._health_features = set(features)
        return features

    def _state_for(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            state = self._cache.get(session_id) or (self._cache.get(self._session_id) if self._session_id else None)
            return dict(state) if state else {}

    def _current_contact(self) -> Optional[Dict[str, Any]]:
        state = self._state_for(self._session_id)
        whoami = state.get("whoami") if state else None
        contact = whoami.get("contact") if isinstance(whoami, dict) else None
        return dict(contact) if isinstance(contact, dict) else None

    def _sync_turn_now(
        self,
        session_id: str,
        state: Dict[str, Any],
        user_content: str,
        assistant_content: str,
    ) -> None:
        maybe_whoami = state.get("whoami")
        whoami = maybe_whoami if isinstance(maybe_whoami, dict) else {}
        maybe_contact = whoami.get("contact")
        contact = maybe_contact if isinstance(maybe_contact, dict) else None
        maybe_matched_identity = whoami.get("matchedIdentity")
        matched_identity = maybe_matched_identity if isinstance(maybe_matched_identity, dict) else None

        body: Dict[str, Any] = {
            "platform": str(state.get("platform") or "unknown"),
            "sessionId": session_id,
            "direction": "inbound",
            "summary": _truncate(user_content),
            "responseSummary": _truncate(assistant_content),
            "metadata": {"source": "hermes_api_memory_provider"},
        }
        if contact and contact.get("id"):
            body["contactId"] = str(contact["id"])
        if matched_identity and matched_identity.get("id"):
            body["identityId"] = str(matched_identity["id"])
        if state.get("chatId"):
            body["chatId"] = str(state["chatId"])
        if state.get("threadId"):
            body["threadId"] = str(state["threadId"])

        try:
            _request_json("POST", "/api/v1/interactions", body=body)
        except Exception as exc:
            logger.debug("Hermes API interaction sync failed: %s", exc)

    def _get_contact(self, contact_id: str) -> Dict[str, Any]:
        contact = _data(_request_json("GET", f"/api/v1/contacts/{_quote(contact_id)}"))
        if not isinstance(contact, dict):
            raise RuntimeError(f"Contact not found: {contact_id}")
        return contact

    def _append_contact_memory(self, contact_id: str, content: str) -> Dict[str, Any]:
        if not content.strip():
            raise ValueError("content is empty")
        contact = _data(
            _request_json(
                "POST",
                f"/api/v1/contacts/{_quote(contact_id)}/memory/append",
                body={"content": content.strip()},
            )
        )
        if not isinstance(contact, dict):
            raise RuntimeError(f"Failed to append contact memory: {contact_id}")
        with self._lock:
            for state in self._cache.values():
                maybe_whoami = state.get("whoami")
                whoami = maybe_whoami if isinstance(maybe_whoami, dict) else {}
                maybe_current = whoami.get("contact")
                current = maybe_current if isinstance(maybe_current, dict) else None
                if current and current.get("id") == contact_id:
                    whoami["contact"] = contact
        return contact

    def _tool_contacts_search(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query") or args.get("q") or "").strip()
        if not query:
            return tool_error("query is required", tool="hermes_api_contacts_search")
        limit = str(max(1, min(int(args.get("limit") or 5), 25)))
        data = _data(_request_json("GET", "/api/v1/contacts/search", query={"q": query, "limit": limit})) or []
        return _result(True, data=data)

    def _tool_contact_get(self, args: Dict[str, Any]) -> str:
        contact_id = str(args.get("contact_id") or args.get("contactId") or "").strip()
        if not contact_id:
            return tool_error("contact_id is required", tool="hermes_api_contact_get")
        return _result(True, data=self._get_contact(contact_id))

    def _tool_contact_create(self, args: Dict[str, Any]) -> str:
        body = self._contact_write_body(args)
        data = _data(_request_json("POST", "/api/v1/contacts", body=body))
        return _result(True, data=data)

    def _tool_contact_update(self, args: Dict[str, Any]) -> str:
        contact_id = str(args.get("contact_id") or args.get("contactId") or "").strip()
        if not contact_id:
            return tool_error("contact_id is required", tool="hermes_api_contact_update")
        body = self._contact_write_body({k: v for k, v in args.items() if k not in {"contact_id", "contactId"}})
        data = _data(_request_json("PATCH", f"/api/v1/contacts/{_quote(contact_id)}", body=body))
        return _result(True, data=data)

    def _tool_contact_memory_append(self, args: Dict[str, Any]) -> str:
        contact_id = str(args.get("contact_id") or args.get("contactId") or "").strip()
        content = str(args.get("content") or "").strip()
        if not contact_id:
            return tool_error("contact_id is required", tool="hermes_api_contact_memory_append")
        return _result(True, data=self._append_contact_memory(contact_id, content))

    def _tool_identity_resolve(self, args: Dict[str, Any]) -> str:
        kind = str(args.get("kind") or "").strip()
        value = str(args.get("value") or "").strip()
        if not kind or not value:
            return tool_error("kind and value are required", tool="hermes_api_identity_resolve")
        data = _data(_request_json("GET", "/api/v1/identities", query={"kind": kind, "value": value})) or []
        return _result(True, data=data)

    def _tool_route_resolve(self, args: Dict[str, Any]) -> str:
        query = str(args.get("query") or "").strip()
        platform = str(args.get("platform") or "").strip()
        if not query or not platform:
            return tool_error("query and platform are required", tool="hermes_api_route_resolve")
        data = _data(_request_json("POST", "/api/v1/routes/resolve", body={"query": query, "platform": platform}))
        return _result(True, data=data)

    def _tool_followup_create(self, args: Dict[str, Any]) -> str:
        body: Dict[str, Any] = {"title": str(args.get("title") or "").strip()}
        if not body["title"]:
            return tool_error("title is required", tool="hermes_api_followup_create")
        mapping = {
            "contact_id": "contactId",
            "contactId": "contactId",
            "due_at": "dueAt",
            "dueAt": "dueAt",
            "status": "status",
            "source_interaction_id": "sourceInteractionId",
            "sourceInteractionId": "sourceInteractionId",
            "metadata": "metadata",
        }
        for src, dst in mapping.items():
            if src in args and args[src] is not None:
                body[dst] = args[src]
        data = _data(_request_json("POST", "/api/v1/followups", body=body))
        return _result(True, data=data)

    def _tool_followup_list(self, args: Dict[str, Any]) -> str:
        query: Dict[str, Any] = {}
        if args.get("status"):
            query["status"] = args["status"]
        if args.get("limit"):
            query["limit"] = str(max(1, min(int(args.get("limit") or 20), 100)))
        data = _data(_request_json("GET", "/api/v1/followups", query=query or None)) or []
        return _result(True, data=data)

    def _tool_followup_update(self, args: Dict[str, Any]) -> str:
        followup_id = str(args.get("followup_id") or args.get("followupId") or "").strip()
        if not followup_id:
            return tool_error("followup_id is required", tool="hermes_api_followup_update")
        body: Dict[str, Any] = {}
        mapping = {"title": "title", "due_at": "dueAt", "dueAt": "dueAt", "status": "status", "metadata": "metadata"}
        for src, dst in mapping.items():
            if src in args:
                body[dst] = args[src]
        data = _data(_request_json("PATCH", f"/api/v1/followups/{_quote(followup_id)}", body=body))
        return _result(True, data=data)

    @staticmethod
    def _contact_write_body(args: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"name", "username", "email", "role", "roleId", "tags", "contactMd", "memoryMd", "notes"}
        return {key: value for key, value in args.items() if key in allowed and value is not None}


# Backward-compatible exported schema names used by older tests/importers.
RESOLVE_IDENTITY_SCHEMA = IDENTITY_RESOLVE_SCHEMA
GET_CONTACT_SCHEMA = CONTACT_GET_SCHEMA
LIST_CONTACTS_SCHEMA = CONTACTS_SEARCH_SCHEMA
UPDATE_MEMORY_SCHEMA = CONTACT_UPDATE_SCHEMA
APPEND_MEMORY_SCHEMA = CONTACT_MEMORY_APPEND_SCHEMA


def register(ctx) -> None:
    """Register Hermes API as a memory provider plugin."""
    ctx.register_memory_provider(HermesApiMemoryProvider())
