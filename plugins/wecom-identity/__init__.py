"""
wecom-identity plugin — tracks WeCom user identities per chat session.

Wires:
1. pre_llm_call hook — intercepts self-introduction patterns from the user
   and stores user_id -> name mapping persistently.
2. Also injects known identity context into every LLM call so the agent
   knows who's who without relying on shared conversation history.
3. Maintains shared knowledge (spreadsheet IDs, doc links, etc.) across
   users in the same group chat.

Identity is stored per session in HERMES_HOME/memories/wecom-identity/<session>.json.
Shared knowledge is stored in HERMES_HOME/memories/wecom-identity/shared/<chat_id>.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MEMORIES_DIR = "memories/wecom-identity"
_SHARED_DIR = _MEMORIES_DIR + "/shared"

# Patterns that indicate a user is declaring their own name
_SELF_INTRO_PATTERNS = [
    # 我叫张三
    re.compile(r"^我叫(.+)$"),
    # 我是张三
    re.compile(r"^我是(.+)$"),
    # 我的名字是张三
    re.compile(r"^我的名字(?:是|叫)(.+)$"),
    # 叫我张三就好
    re.compile(r"^(?:叫我|喊我|叫我就|叫我好)(.+?)(?:就好?|就行|[嘛啊]?)$"),
    # 直接说名字作为回应
    re.compile(r"^(?:大家好|各位好|我是)(?:.+?，)?(.+?)(?:[,，]?请多关照|[,，]?多多指教|[,，]?你们好)?$"),
]

# Patterns asking "who am I" or "do you remember me"
_WHOAMI_PATTERNS = [
    re.compile(r"^我是谁$"),
    re.compile(r"^你记得我是谁吗$"),
    re.compile(r"^你认识我吗$"),
    re.compile(r"^我是哪位$"),
]

# Patterns for shared knowledge extraction (things users mention that others might need to know)
_SHARED_PATTERNS = [
    # 表格/电子表格 references
    re.compile(r"(?:表格|电子表格|电子表|spreadsheet|sheet)[^\s]*?[:：]?\s*([^\s，,。！!?]{10,})"),
    # 文档 references
    re.compile(r"(?:文档|doc|文档链接)[^\s]*?[:：]?\s*([^\s，,。！!?]{10,})"),
    # URLs
    re.compile(r"https?://[^\s，,。！!?]+"),
    # 工作表/sheet ID
    re.compile(r"(?:sheet|工作表|表格)[^\d]*(\d{6,})"),
    # 文件名 with extension
    re.compile(r"[\w\-一-龥]+\.(?:xlsx|csv|docx|pdf|xls|doc|pptx|ppt)[^\s]*"),
]

# In-memory cache: session_id -> {user_id -> name}
_cache: Dict[str, Dict[str, str]] = {}
_cache_lock = threading.Lock()

# Shared knowledge cache: chat_id -> {"updated_at": str, "entries": [{"type": str, "value": str, "user": str}]}
_shared_cache: Dict[str, Dict[str, Any]] = {}
_shared_cache_lock = threading.Lock()


def _memories_dir() -> Path:
    home = Path(os.getenv("HERMES_HOME", os.path.expanduser("~/.hermes")))
    d = home / _MEMORIES_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _shared_dir() -> Path:
    home = Path(os.getenv("HERMES_HOME", os.path.expanduser("~/.hermes")))
    d = home / _SHARED_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_file(session_id: str) -> Path:
    safe = session_id.replace("/", "_").replace(":", "_")
    return _memories_dir() / f"{safe}.json"


def _chat_shared_file(chat_id: str) -> Path:
    safe = chat_id.replace("/", "_").replace(":", "_")
    return _shared_dir() / f"{safe}.json"


def _load_identity(session_id: str) -> Dict[str, str]:
    path = _session_file(session_id)
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
            return data.get("identities", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _save_identity(session_id: str, identities: Dict[str, str]) -> None:
    path = _session_file(session_id)
    meta = {
        "session_id": session_id,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "identities": identities,
    }
    try:
        with open(path, "w") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.debug("Failed to save identity for %s: %s", session_id, exc)


def _load_shared(chat_id: str) -> Dict[str, Any]:
    path = _chat_shared_file(chat_id)
    if not path.exists():
        return {"updated_at": None, "entries": []}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"updated_at": None, "entries": []}


def _save_shared(chat_id: str, data: Dict[str, Any]) -> None:
    path = _chat_shared_file(chat_id)
    try:
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.debug("Failed to save shared knowledge for %s: %s", chat_id, exc)


def _extract_self_intro(text: str) -> Optional[Tuple[str, str]]:
    """Try to extract (pattern_type, name) from a self-introduction sentence."""
    text = text.strip()
    for i, pattern in enumerate(_SELF_INTRO_PATTERNS):
        m = pattern.match(text)
        if m:
            name = m.group(1).strip()
            if name and 1 < len(name) <= 20:
                return (f"intro_{i}", name)
    return None


def _is_whoami_question(text: str) -> bool:
    """Check if the message is a 'who am I' question."""
    text = text.strip()
    return any(p.match(text) for p in _WHOAMI_PATTERNS)


def _extract_shared_knowledge(text: str, sender_id: str) -> List[Dict[str, str]]:
    """Extract things worth sharing across users in the same chat."""
    text = text.strip()
    all_candidates: list[tuple[str, str, str]] = []  # (norm_key, display_value, type)

    # Pre-scan text for a full URL to use as origin for relative-path fixup
    import re as _re
    url_in_text = _re.search(r"https?://[^\s，,。！!?]+", text)
    origin: str | None = None
    if url_in_text:
        try:
            from urllib.parse import urlparse
            up = urlparse(url_in_text.group(0))
            origin = f"{up.scheme}://{up.netloc}"
        except Exception:
            pass

    for i, pattern in enumerate(_SHARED_PATTERNS):
        for m in pattern.finditer(text):
            raw = m.group(0).strip()
            if len(raw) < 5:
                continue

            # Build a dedup key: extract pure URL if present, else lowercase
            if "://" in raw:
                try:
                    from urllib.parse import urlparse
                    url_match = _re.search(r"https?://[^\s，,。！!?]+", raw)
                    url_part = url_match.group(0) if url_match else raw
                    parsed = urlparse(url_part)
                    norm_key = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/") or raw.lower()
                except Exception:
                    norm_key = raw.lower()
            else:
                norm_key = raw.lower()
                # Fixup: if text contains a full URL, use its origin to
                # reconstruct the full URL for partial/spreadsheet matches
                if origin and (raw.startswith("/") or "/" in raw):
                    norm_key = f"{origin}{'/' if not raw.startswith('/') else ''}{raw}".rstrip("/")

            all_candidates.append((norm_key, raw, f"shared_{i}"))

    # Global dedup by norm_key, preferring entries with shorter display value
    # (so "表格: https://x.com" and "https://x.com" collapse to the shorter one)
    seen: set[str] = set()
    entries: list[dict[str, str]] = []
    for norm_key, display_val, etype in sorted(all_candidates, key=lambda x: len(x[1])):
        if norm_key not in seen:
            seen.add(norm_key)
            entries.append({"type": etype, "value": display_val, "user": sender_id})

    return entries


def _build_identity_context(identities: Dict[str, str], current_user_id: str) -> str:
    """Build a context string about known identities in this chat."""
    if not identities:
        return ""

    lines = []
    for uid, name in sorted(identities.items()):
        marker = " ← 你是这个人" if uid == current_user_id else ""
        lines.append(f"  [{name}] (id={uid}){marker}")

    header = "[此群中已知身份]\n"
    return header + "\n".join(lines) + "\n"


def _build_shared_context(chat_id: str, entries: List[Dict[str, Any]]) -> str:
    """Build a context string about shared knowledge in this chat."""
    if not entries:
        return ""

    lines = []
    for e in entries:
        lines.append(f"  {e['value']} (由 {e.get('user', '?')} 提到)")

    header = "[此群中共享信息]\n"
    return header + "\n".join(lines) + "\n"


def _on_pre_llm_call(
    session_id: str = "",
    user_message: str = "",
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    sender_id: str = "",
    platform: str = "",
    chat_id: str = "",
    **_: Any,
) -> List[Any]:
    """pre_llm_call hook — record self-introductions, shared knowledge, and inject context."""
    global _cache, _shared_cache

    if not session_id or platform != "wecom":
        return []

    # Load or get cached identity map for this session
    with _cache_lock:
        if session_id not in _cache:
            _cache[session_id] = _load_identity(session_id)
        identities = _cache[session_id]

    results: List[Any] = []

    # 1. Try to record a self-introduction from the current user
    name_info = _extract_self_intro(user_message)
    if name_info and sender_id:
        pattern_key, name = name_info
        key = sender_id
        if key not in identities or pattern_key.startswith("intro_0"):
            identities[key] = name
            _save_identity(session_id, identities)
            logger.debug("wecom-identity: recorded %s -> %s", key, name)

    # 2. Extract and save shared knowledge
    shared_entries = _extract_shared_knowledge(user_message, sender_id)
    if shared_entries and chat_id:
        with _shared_cache_lock:
            if chat_id not in _shared_cache:
                _shared_cache[chat_id] = _load_shared(chat_id)
            existing = _shared_cache[chat_id]
            existing_values = {e["value"] for e in existing.get("entries", [])}
            for entry in shared_entries:
                if entry["value"] not in existing_values:
                    existing.setdefault("entries", []).append(entry)
                    existing_values.add(entry["value"])
            if shared_entries:
                existing["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
                _save_shared(chat_id, existing)
                logger.debug("wecom-identity: saved %d shared entries for %s", len(shared_entries), chat_id)

    # 3. Inject identity + shared context so the agent knows who's in the chat
    ctx_parts = []
    if identities:
        ctx_parts.append(_build_identity_context(identities, sender_id))

    if chat_id:
        with _shared_cache_lock:
            if chat_id not in _shared_cache:
                _shared_cache[chat_id] = _load_shared(chat_id)
            shared = _shared_cache[chat_id]
        if shared.get("entries"):
            ctx_parts.append(_build_shared_context(chat_id, shared["entries"]))

    if ctx_parts:
        combined = "\n".join(ctx_parts)
        results.append({"context": combined})

    return results


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    logger.info("wecom-identity plugin loaded (pre_llm_call)")
