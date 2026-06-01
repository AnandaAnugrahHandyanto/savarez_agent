"""
WhatsApp platform adapter.

WhatsApp integration is more complex than Telegram/Discord because:
- No official bot API for personal accounts
- Business API requires Meta Business verification
- Most solutions use web-based automation

This adapter supports multiple backends:
1. WhatsApp Business API (requires Meta verification)
2. whatsapp-web.js (via Node.js subprocess) - for personal accounts
3. Baileys (via Node.js subprocess) - alternative for personal accounts

For simplicity, we'll implement a generic interface that can work
with different backends via a bridge pattern.
"""

import asyncio
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

_IS_WINDOWS = platform.system() == "Windows"
from pathlib import Path
from typing import Dict, Optional, Any

from hermes_constants import get_hermes_dir

logger = logging.getLogger(__name__)


def _kill_port_process(port: int) -> None:
    """Kill any process listening on the given TCP port."""
    try:
        if _IS_WINDOWS:
            # Use netstat to find the PID bound to this port, then taskkill
            result = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[3] == "LISTENING":
                    local_addr = parts[1]
                    if local_addr.endswith(f":{port}"):
                        try:
                            subprocess.run(
                                ["taskkill", "/PID", parts[4], "/F"],
                                capture_output=True, timeout=5,
                            )
                        except subprocess.SubprocessError:
                            pass
        else:
            # Try fuser first (Linux), fall back to lsof (macOS / WSL2)
            killed = False
            try:
                result = subprocess.run(
                    ["fuser", f"{port}/tcp"],
                    capture_output=True, timeout=5,
                )
                if result.returncode == 0:
                    subprocess.run(
                        ["fuser", "-k", f"{port}/tcp"],
                        capture_output=True, timeout=5,
                    )
                    killed = True
            except FileNotFoundError:
                pass  # fuser not installed

            if not killed:
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{port}"],
                        capture_output=True, text=True, timeout=5,
                    )
                    for pid_str in result.stdout.strip().splitlines():
                        try:
                            os.kill(int(pid_str), signal.SIGTERM)
                        except (ValueError, ProcessLookupError, PermissionError):
                            pass
                except FileNotFoundError:
                    pass  # lsof not installed either
    except Exception:
        pass


def _kill_stale_bridge_by_pidfile(session_path: Path) -> None:
    """Kill a bridge process recorded in a PID file from a previous run.

    The bridge writes ``bridge.pid`` into the session directory when it
    starts.  If the gateway crashed without a clean shutdown the old bridge
    process becomes orphaned — this helper finds and kills it.
    """
    pid_file = session_path / "bridge.pid"
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError, TypeError):
        try:
            pid_file.unlink()
        except OSError:
            pass
        return
    # ``os.kill(pid, 0)`` is NOT a no-op on Windows (bpo-14484) — use the
    # cross-platform existence check before sending a real signal.
    from gateway.status import _pid_exists
    if _pid_exists(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("[whatsapp] Killed stale bridge PID %d from pidfile", pid)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        pid_file.unlink()
    except OSError:
        pass


def _write_bridge_pidfile(session_path: Path, pid: int) -> None:
    """Write the bridge PID to a file for later cleanup."""
    try:
        (session_path / "bridge.pid").write_text(str(pid))
    except OSError:
        pass


def _terminate_bridge_process(proc, *, force: bool = False) -> None:
    """Terminate the bridge process using process-tree semantics where possible."""
    if _IS_WINDOWS:
        cmd = ["taskkill", "/PID", str(proc.pid), "/T"]
        if force:
            cmd.append("/F")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            if force:
                proc.kill()
            else:
                proc.terminate()
            return

        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            raise OSError(details or f"taskkill failed for PID {proc.pid}")
        return

    import psutil
    try:
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        if force:
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
        else:
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            parent.terminate()
    except psutil.NoSuchProcess:
        return

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    SUPPORTED_DOCUMENT_TYPES,
    cache_image_from_url,
    cache_audio_from_url,
)


def check_whatsapp_requirements() -> bool:
    """
    Check if WhatsApp dependencies are available.
    
    WhatsApp requires a Node.js bridge for most implementations.
    """
    # Check for Node.js.  Resolve via shutil.which so we respect PATHEXT
    # (node.exe vs node) and get a meaningful "not installed" signal
    # instead of spawning a cmd flash on Windows.
    _node = shutil.which("node")
    if not _node:
        return False
    try:
        result = subprocess.run(
            [_node, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


class WhatsAppAdapter(BasePlatformAdapter):
    """
    WhatsApp adapter.
    
    This implementation uses a simple HTTP bridge pattern where:
    1. A Node.js process runs the WhatsApp Web client
    2. Messages are forwarded via HTTP/IPC to this Python adapter
    3. Responses are sent back through the bridge
    
    The actual Node.js bridge implementation can vary:
    - whatsapp-web.js based
    - Baileys based
    - Business API based
    
    Configuration:
    - bridge_script: Path to the Node.js bridge script
    - bridge_port: Port for HTTP communication (default: 3000)
    - session_path: Path to store WhatsApp session data
    - dm_policy: "open" | "allowlist" | "disabled" — how DMs are handled (default: "open")
    - allow_from: List of sender IDs allowed in DMs (when dm_policy="allowlist")
    - group_policy: "open" | "allowlist" | "disabled" — which groups are processed (default: "open")
    - group_allow_from: List of group JIDs allowed (when group_policy="allowlist")
    """
    
    # WhatsApp message limits — practical UX limit, not protocol max.
    # WhatsApp allows ~65K but long messages are unreadable on mobile.
    MAX_MESSAGE_LENGTH = 4096
    DEFAULT_REPLY_PREFIX = "⚕ *Hermes Agent*\n────────────\n"
    
    # Default bridge location relative to the hermes-agent install
    _DEFAULT_BRIDGE_DIR = Path(__file__).resolve().parents[2] / "scripts" / "whatsapp-bridge"

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.WHATSAPP)
        self._bridge_process: Optional[subprocess.Popen] = None
        self._bridge_port: int = config.extra.get("bridge_port", 3000)
        self._bridge_script: Optional[str] = config.extra.get(
            "bridge_script",
            str(self._DEFAULT_BRIDGE_DIR / "bridge.js"),
        )
        self._session_path: Path = Path(config.extra.get(
            "session_path",
            get_hermes_dir("platforms/whatsapp/session", "whatsapp/session")
        ))
        self._reply_prefix: Optional[str] = config.extra.get("reply_prefix")
        self._dm_policy = str(config.extra.get("dm_policy") or os.getenv("WHATSAPP_DM_POLICY", "open")).strip().lower()
        self._allow_from = self._coerce_allow_list(config.extra.get("allow_from") or config.extra.get("allowFrom"))
        self._group_policy = str(config.extra.get("group_policy") or os.getenv("WHATSAPP_GROUP_POLICY", "open")).strip().lower()
        self._group_allow_from = self._coerce_allow_list(config.extra.get("group_allow_from") or config.extra.get("groupAllowFrom"))
        self._mention_patterns = self._compile_mention_patterns()
        self._last_bot_reply_at_by_chat: Dict[str, float] = {}
        self._last_bot_reply_text_by_chat: Dict[str, str] = {}
        self._active_threads_path: Path = self._session_path / "active-threads.json"
        self._recent_group_messages_by_chat: Dict[str, list[Dict[str, Any]]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._bridge_log_fh = None
        self._bridge_log: Optional[Path] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._http_session: Optional["aiohttp.ClientSession"] = None
        # Set to True by disconnect() before we SIGTERM our child bridge so
        # _check_managed_bridge_exit() can distinguish an intentional
        # shutdown-time exit (returncode -15 / -2 / 0) from a real crash.
        # Without this, every graceful gateway shutdown/restart would log
        # "Fatal whatsapp adapter error" plus dispatch a fatal-error
        # notification before the normal "✓ whatsapp disconnected" fires.
        self._shutting_down: bool = False

    def _effective_reply_prefix(self) -> str:
        """Return the prefix the Node bridge will add in self-chat mode."""
        whatsapp_mode = os.getenv("WHATSAPP_MODE", "self-chat")
        if whatsapp_mode != "self-chat":
            return ""
        if self._reply_prefix is not None:
            return self._reply_prefix.replace("\\n", "\n")
        env_prefix = os.getenv("WHATSAPP_REPLY_PREFIX")
        if env_prefix is not None:
            return env_prefix.replace("\\n", "\n")
        return self.DEFAULT_REPLY_PREFIX

    def _outgoing_chunk_limit(self) -> int:
        """Reserve room for the bridge-side prefix so final WhatsApp text fits."""
        prefix_len = len(self._effective_reply_prefix())
        # Keep enough space for truncate_message's pagination indicator and
        # code-fence repair even if a user configures a very long prefix.
        return max(1024, self.MAX_MESSAGE_LENGTH - prefix_len)

    def _whatsapp_require_mention(self) -> bool:
        configured = self.config.extra.get("require_mention")
        if configured is not None:
            if isinstance(configured, str):
                return configured.lower() in {"true", "1", "yes", "on"}
            return bool(configured)
        return os.getenv("WHATSAPP_REQUIRE_MENTION", "false").lower() in {"true", "1", "yes", "on"}

    def _whatsapp_free_response_chats(self) -> set[str]:
        raw = self.config.extra.get("free_response_chats")
        if raw is None:
            raw = os.getenv("WHATSAPP_FREE_RESPONSE_CHATS", "")
        if isinstance(raw, list):
            return {str(part).strip() for part in raw if str(part).strip()}
        return {part.strip() for part in str(raw).split(",") if part.strip()}

    def _whatsapp_respond_when_likely_directed(self) -> bool:
        """Whether group messages may wake the bot via high-confidence intent heuristics."""
        configured = self.config.extra.get("respond_when_likely_directed")
        if configured is None:
            configured = self.config.extra.get("likely_directed_response")
        if configured is not None:
            if isinstance(configured, str):
                return configured.lower() in {"true", "1", "yes", "on"}
            return bool(configured)
        return os.getenv("WHATSAPP_RESPOND_WHEN_LIKELY_DIRECTED", "false").lower() in {"true", "1", "yes", "on"}

    @staticmethod
    def _coerce_allow_list(raw) -> set[str]:
        """Parse allow_from / group_allow_from from config or env var."""
        if raw is None:
            return set()
        if isinstance(raw, list):
            return {str(part).strip() for part in raw if str(part).strip()}
        return {part.strip() for part in str(raw).split(",") if part.strip()}

    @staticmethod
    def _is_broadcast_chat(chat_id: str) -> bool:
        """True for WhatsApp pseudo-chats that aren't real conversations.

        Covers Status updates (Stories) and Channel/Newsletter broadcasts.
        These show up as inbound messages on Baileys but the agent should
        never reply — answering a Story update spams the contact's status
        feed, and Channel posts aren't addressable in the first place.
        """
        if not chat_id:
            return False
        cid = chat_id.strip().lower()
        if cid == "status@broadcast":
            return True
        # @broadcast suffix covers status@broadcast plus any future
        # broadcast-list variants. @newsletter is the Channel JID suffix.
        if cid.endswith("@broadcast") or cid.endswith("@newsletter"):
            return True
        return False

    def _is_dm_allowed(self, sender_id: str) -> bool:
        """Check whether a DM from the given sender should be processed."""
        if self._dm_policy == "disabled":
            return False
        if self._dm_policy == "allowlist":
            return sender_id in self._allow_from
        # "open" — all DMs allowed
        return True

    def _is_group_allowed(self, chat_id: str) -> bool:
        """Check whether a group chat should be processed."""
        if self._group_policy == "disabled":
            return False
        if self._group_policy == "allowlist":
            return chat_id in self._group_allow_from
        # "open" — all groups allowed
        return True

    def _compile_mention_patterns(self):
        patterns = self.config.extra.get("mention_patterns")
        if patterns is None:
            raw = os.getenv("WHATSAPP_MENTION_PATTERNS", "").strip()
            if raw:
                try:
                    patterns = json.loads(raw)
                except Exception:
                    patterns = [part.strip() for part in raw.splitlines() if part.strip()]
                    if not patterns:
                        patterns = [part.strip() for part in raw.split(",") if part.strip()]
        if patterns is None:
            return []
        if isinstance(patterns, str):
            patterns = [patterns]
        if not isinstance(patterns, list):
            logger.warning("[%s] whatsapp mention_patterns must be a list or string; got %s", self.name, type(patterns).__name__)
            return []

        compiled = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern.strip():
                continue
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE))
            except re.error as exc:
                logger.warning("[%s] Invalid WhatsApp mention pattern %r: %s", self.name, pattern, exc)
        if compiled:
            logger.info("[%s] Loaded %d WhatsApp mention pattern(s)", self.name, len(compiled))
        return compiled

    @staticmethod
    def _normalize_whatsapp_id(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = str(value).strip()
        if ":" in normalized and "@" in normalized:
            normalized = normalized.replace(":", "@", 1)
        return normalized

    def _bot_ids_from_message(self, data: Dict[str, Any]) -> set[str]:
        bot_ids = set()
        for candidate in data.get("botIds") or []:
            normalized = self._normalize_whatsapp_id(candidate)
            if normalized:
                bot_ids.add(normalized)
        return bot_ids

    def _message_is_reply_to_bot(self, data: Dict[str, Any]) -> bool:
        quoted_participant = self._normalize_whatsapp_id(data.get("quotedParticipant"))
        if not quoted_participant:
            return False
        return quoted_participant in self._bot_ids_from_message(data)

    def _message_mentions_bot(self, data: Dict[str, Any]) -> bool:
        bot_ids = self._bot_ids_from_message(data)
        if not bot_ids:
            return False
        mentioned_ids = {
            nid
            for candidate in (data.get("mentionedIds") or [])
            if (nid := self._normalize_whatsapp_id(candidate))
        }
        if mentioned_ids & bot_ids:
            return True

        body = str(data.get("body") or "")
        lower_body = body.lower()
        for bot_id in bot_ids:
            bare_id = bot_id.split("@", 1)[0].lower()
            if bare_id and (f"@{bare_id}" in lower_body or bare_id in lower_body):
                return True
        return False

    def _message_matches_mention_patterns(self, data: Dict[str, Any]) -> bool:
        if not self._mention_patterns:
            return False
        body = str(data.get("body") or "")
        return any(pattern.search(body) for pattern in self._mention_patterns)

    def _message_is_ambiguous_third_party_check(self, body: str) -> bool:
        """Return True for group-chat "can you check if it/he/she/they..." ambiguity."""
        normalized = re.sub(r"\s+", " ", str(body or "")).strip().lower()
        return bool(re.match(
            r"^(?:can|could|would)\s+you\s+(?:please\s+)?check\s+(?:if|whether)\s+(?:it|it['’]s|he|she|they|that|this|the\b)",
            normalized,
        ))

    def _message_likely_directed_at_bot(self, data: Dict[str, Any]) -> bool:
        """High-confidence wake heuristic for WhatsApp groups.

        This is deliberately conservative. It is not free-response mode: normal
        group chatter such as "any ideas?" or "can you come over later?" should
        not wake the bot. It only accepts messages that look like assistant-style
        requests, or messages addressed to obvious bot/AI names.
        """
        if not self._whatsapp_respond_when_likely_directed():
            return False
        body = re.sub(r"\s+", " ", str(data.get("body") or "")).strip()
        if not body or body.startswith("/"):
            return False
        if self._message_is_ambiguous_third_party_check(body):
            return False
        lower = body.lower()

        # Natural name/wake-word, separate from platform @mention metadata.
        if re.search(r"\bhermes\b", lower):
            return True

        # Direct address to the bot as a role: "bot, ...", "AI can you ...".
        if re.match(r"^(?:hey|hi|yo|ok(?:ay)?|please\s+)?(?:bot|ai|assistant)\b", lower):
            return True

        assistant_verbs = (
            "look up", "lookup", "search", "google", "find", "summarize", "summarise", "summary", "recap",
            "explain", "translate", "draft", "write", "make", "create", "generate",
            "plan", "calculate", "compare", "recommend", "suggest", "remind", "remember",
            "forget", "save", "note", "list", "turn this into", "help me", "help us",
        )
        verb_pattern = "|".join(re.escape(v) for v in assistant_verbs)

        # "Can you check ..." is common human-to-human group phrasing. Only
        # wake on it when the object is clearly a bot-owned feature or public
        # object ID; ambiguous "check if/whether it/he/she/they..." should stay
        # silent unless WhatBot was named/mentioned or recently replied.
        check_feature_pattern = (
            r"(?:reminders?|todo(?:\s+list)?s?|poll(?:\s+results?)?|memory|notes?|images?|media|"
            r"TL-[A-Z0-9]{4,}|TI-[A-Z0-9]{4,}|N-[A-Z0-9]{4,}|M-[A-Z0-9]{4,}|I-[A-Z0-9]{4,}|gr-[A-Za-z0-9-]+)"
        )
        if re.match(rf"^(?:can|could|would)\s+you\s+(?:please\s+)?check\b.*\b{check_feature_pattern}\b", body, re.IGNORECASE):
            return True

        # High-confidence assistant request forms. Avoid broad "can you ..."
        # unless the requested action is a typical bot/assistant task.
        if re.match(rf"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:{verb_pattern})\b", lower):
            return True
        if re.match(rf"^please\s+(?:{verb_pattern})\b", lower):
            return True

        return False

    def _read_active_thread_store(self) -> Dict[str, Any]:
        try:
            path = getattr(self, "_active_threads_path", self._session_path / "active-threads.json")
            if not path.exists():
                return {"chats": {}}
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"chats": {}}
            data.setdefault("chats", {})
            return data
        except (OSError, json.JSONDecodeError, TypeError):
            return {"chats": {}}

    def _write_active_thread_store(self, store: Dict[str, Any]) -> None:
        try:
            path = getattr(self, "_active_threads_path", self._session_path / "active-threads.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            logger.debug("whatsapp active-thread store write failed: %s", exc)

    def _record_recent_group_message(self, data: Dict[str, Any]) -> None:
        chat_id = str(data.get("chatId") or "")
        body = re.sub(r"\s+", " ", str(data.get("body") or "")).strip()
        if not chat_id or not chat_id.endswith("@g.us") or not body:
            return
        sender = self._safe_whatsapp_display_name(data.get("senderName")) or "someone"
        entry = {
            "at": time.time(),
            "sender": sender,
            "body": self._sanitize_whatsapp_visible_ids(body)[:1000],
        }
        recent = list(getattr(self, "_recent_group_messages_by_chat", {}).get(chat_id, []))
        recent.append(entry)
        recent = recent[-20:]
        self._recent_group_messages_by_chat[chat_id] = recent
        store = self._read_active_thread_store()
        chat_state = store.setdefault("chats", {}).setdefault(chat_id, {})
        chat_state["recent_messages"] = recent
        self._write_active_thread_store(store)

    def _recent_messages_for_chat(self, chat_id: str) -> list[Dict[str, Any]]:
        recent = list(getattr(self, "_recent_group_messages_by_chat", {}).get(chat_id, []))
        if recent:
            return recent[-20:]
        store = self._read_active_thread_store()
        stored = store.get("chats", {}).get(chat_id, {}).get("recent_messages", [])
        if isinstance(stored, list):
            self._recent_group_messages_by_chat[chat_id] = stored[-20:]
            return stored[-20:]
        return []

    @staticmethod
    def _message_is_retroactive_bot_addressing_text(text: str) -> bool:
        """Return True when a user is pointing WhatBot at a recent prior message."""
        normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
        if not normalized:
            return False
        normalized = re.sub(r"^(?:what\s*bot|whatbot|hermes)[\s,.:;!-]*", "", normalized).strip()
        return bool(re.search(
            r"\b(?:"
            r"(?:the\s+)?last\s+message\s+(?:was|is)\s+for\s+you|"
            r"that\s+(?:was|is)\s+for\s+you|"
            r"i\s+meant\s+you|"
            r"forgot\s+to\s+(?:tag|mention)\s+you|"
            r"forgot\s+to\s+(?:say\s+)?(?:what\s*bot|whatbot|hermes)|"
            r"answer\s+(?:the\s+)?(?:above|previous\s+message)"
            r")\b",
            normalized,
        ))

    def _retroactive_target_recent_message(self, chat_id: str, current_body: str) -> Optional[Dict[str, Any]]:
        """Find the nearest prior human-visible group message for retroactive addressing."""
        current_clean = re.sub(r"\s+", " ", str(current_body or "")).strip()
        recent = self._recent_messages_for_chat(chat_id)
        candidates = recent[:-1] if recent and str(recent[-1].get("body") or "").strip() == current_clean else recent
        for item in reversed(candidates):
            body = re.sub(r"\s+", " ", str(item.get("body") or "")).strip()
            if not body:
                continue
            if self._message_is_retroactive_bot_addressing_text(body):
                continue
            return item
        return None

    def _rewrite_retroactive_bot_addressing_body(self, chat_id: str, body: str) -> str:
        """Inject the prior message when user says the previous message was for WhatBot."""
        if not self._message_is_retroactive_bot_addressing_text(body):
            return body
        target = self._retroactive_target_recent_message(chat_id, body)
        if not target:
            return body
        sender = str(target.get("sender") or "someone").strip() or "someone"
        target_body = str(target.get("body") or "").strip()
        return (
            "[Conversational repair]\n"
            f"The user is now directing this prior group message at WhatBot (from {sender}):\n"
            f"{target_body}\n\n"
            "[User repair message]\n"
            f"{body}"
        )

    @staticmethod
    def _infer_active_thread_type(text: str) -> str:
        lower = str(text or "").lower()
        if re.search(r"\b(remind|reminder)\b", lower):
            return "reminder_creation"
        if re.search(r"\b(plan|trip|event|bbq|party|dinner|lunch|breakfast)\b", lower):
            return "plan_creation"
        if re.search(r"\b(poll|vote|options?)\b", lower):
            return "poll_creation"
        if re.search(r"\b(todo|to-do|task|list)\b", lower):
            return "todo_update"
        if re.search(r"\b(prediction|predict|league|market)\b", lower):
            return "prediction_game"
        return "clarification"

    def _record_bot_group_reply(self, chat_id: str, text: str) -> None:
        chat_id = str(chat_id or "")
        if not chat_id.endswith("@g.us"):
            return
        clean = re.sub(r"\s+", " ", str(text or "")).strip()
        self._last_bot_reply_at_by_chat[chat_id] = time.monotonic()
        self._last_bot_reply_text_by_chat[chat_id] = clean
        if not self._bot_reply_looks_like_clarification(clean):
            self._close_active_thread(chat_id)
            return
        recent = self._recent_messages_for_chat(chat_id)
        joined_context = "\n".join(str(item.get("body") or "") for item in recent[-6:])
        now = time.time()
        thread = {
            "thread_id": f"T-{uuid.uuid4().hex[:8].upper()}",
            "thread_type": self._infer_active_thread_type(f"{joined_context}\n{clean}"),
            "status": "awaiting_user_input",
            "chat_id": chat_id,
            "last_bot_reply": clean,
            "created_at": now,
            "updated_at": now,
        }
        store = self._read_active_thread_store()
        chat_state = store.setdefault("chats", {}).setdefault(chat_id, {})
        chat_state["active_thread"] = thread
        chat_state["recent_messages"] = recent[-20:]
        self._write_active_thread_store(store)

    def _load_active_thread(self, chat_id: str) -> Optional[Dict[str, Any]]:
        chat_id = str(chat_id or "")
        store = self._read_active_thread_store()
        chat_state = store.get("chats", {}).get(chat_id, {})
        recent = chat_state.get("recent_messages")
        if isinstance(recent, list):
            self._recent_group_messages_by_chat[chat_id] = recent[-20:]
        thread = chat_state.get("active_thread")
        if not isinstance(thread, dict) or thread.get("status") != "awaiting_user_input":
            return None
        try:
            window = float(self.config.extra.get("followup_response_window_seconds", 300))
        except (TypeError, ValueError):
            window = 300.0
        updated_at = float(thread.get("updated_at") or thread.get("created_at") or 0)
        if window <= 0 or not updated_at or (time.time() - updated_at) > window:
            self._close_active_thread(chat_id)
            return None
        return thread

    def _close_active_thread(self, chat_id: str) -> None:
        chat_id = str(chat_id or "")
        store = self._read_active_thread_store()
        chat_state = store.setdefault("chats", {}).setdefault(chat_id, {})
        if "active_thread" in chat_state:
            chat_state.pop("active_thread", None)
            self._write_active_thread_store(store)

    def _message_is_followup_to_recent_bot_reply(self, data: Dict[str, Any]) -> bool:
        """Wake on a short-window follow-up after the bot just spoke in the group.

        Question-like follow-ups still use the cheap deterministic gate. If the
        bot's previous message was itself a clarification question, a local
        classifier may also wake on declarative answer-shaped replies such as
        "breakfast in 30 days".
        """
        if not self._whatsapp_respond_when_likely_directed():
            return False
        chat_id = str(data.get("chatId") or "")
        active_thread = self._load_active_thread(chat_id)
        last_reply_at = self._last_bot_reply_at_by_chat.get(chat_id)
        if not last_reply_at and not active_thread:
            return False
        try:
            window = float(self.config.extra.get("followup_response_window_seconds", 300))
        except (TypeError, ValueError):
            window = 300.0
        if last_reply_at and (window <= 0 or (time.monotonic() - last_reply_at) > window) and not active_thread:
            return False

        body = re.sub(r"\s+", " ", str(data.get("body") or "")).strip()
        if not body or body.startswith("/"):
            return False
        if self._message_is_ambiguous_third_party_check(body):
            return False
        lower = body.lower()
        last_bot_reply = self._last_bot_reply_text_by_chat.get(chat_id, "")
        if active_thread and not last_bot_reply:
            last_bot_reply = str(active_thread.get("last_bot_reply") or "")
        if "?" in body:
            return bool(active_thread or self._bot_reply_looks_like_clarification(last_bot_reply))
        if re.match(
            r"^(?:why|what|how|when|where|who|which|can|could|would|should|is|are|do|does|did|will)\b",
            lower,
        ):
            return bool(active_thread or self._bot_reply_looks_like_clarification(last_bot_reply))

        if last_bot_reply and (active_thread or self._bot_reply_looks_like_clarification(last_bot_reply)):
            return self._classify_followup_with_local_model(
                data,
                last_bot_reply=last_bot_reply,
                active_thread=active_thread,
                recent_messages=self._recent_messages_for_chat(chat_id),
            )
        return False

    @staticmethod
    def _bot_reply_looks_like_clarification(text: str) -> bool:
        clean = re.sub(r"\s+", " ", str(text or "")).strip()
        if not clean or "?" not in clean:
            return False
        lower = clean.lower()
        return bool(re.search(
            r"\b(which|what|when|where|who|confirm|clarify|exact|date|time|meal|options?|should i|do you want)\b",
            lower,
        ))

    def _classify_followup_with_local_model(
        self,
        data: Dict[str, Any],
        *,
        last_bot_reply: str,
        active_thread: Optional[Dict[str, Any]] = None,
        recent_messages: Optional[list[Dict[str, Any]]] = None,
    ) -> bool:
        """Use a local model to decide if a declarative message continues a bot thread.

        This is intentionally scoped to pending bot clarification questions so it
        does not turn WhatsApp groups into ambient free-response chats.
        """
        if not self.config.extra.get("local_followup_classifier", False):
            return False
        body = re.sub(r"\s+", " ", str(data.get("body") or "")).strip()
        if not body:
            return False
        model = str(self.config.extra.get("local_followup_classifier_model") or "qwen3.6:35b")
        base_url = str(self.config.extra.get("local_followup_classifier_base_url") or "http://localhost:11434").rstrip("/")
        if not self._is_local_model_base_url(base_url) and not self.config.extra.get("allow_remote_followup_classifier", False):
            logger.warning("whatsapp local followup classifier refused non-local base_url=%s", base_url)
            return False
        try:
            timeout = float(self.config.extra.get("local_followup_classifier_timeout", 45))
        except (TypeError, ValueError):
            timeout = 45.0
        recent_lines = []
        for item in (recent_messages or [])[-8:]:
            sender = str(item.get("sender") or "").strip()
            body_line = str(item.get("body") or "").strip()
            if body_line:
                recent_lines.append(f"- {sender + ': ' if sender else ''}{body_line}")
        thread_context = ""
        if active_thread:
            thread_context = (
                "Active WhatBot thread:\n"
                f"- id: {active_thread.get('thread_id', '')}\n"
                f"- type: {active_thread.get('thread_type', 'clarification')}\n"
                f"- status: {active_thread.get('status', '')}\n"
            )
        recent_context = "Recent group messages:\n" + "\n".join(recent_lines) + "\n" if recent_lines else ""
        prompt = (
            "You are a WhatsApp group wake-gate classifier for WhatBot. Decide whether the new message should wake WhatBot "
            "because it answers or directly continues a visible active WhatBot thread. Do not wake for general group chatter, "
            "topic similarity alone, or human-to-human replies. Return ONLY compact JSON with keys should_wake boolean, confidence number, and reason string.\n\n"
            f"{thread_context}"
            f"{recent_context}"
            f"Previous WhatBot message: {last_bot_reply}\n"
            f"New group message: {body}\n"
        )
        payload = {
            "model": model,
            "think": False,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "num_predict": 160},
        }
        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            outer = json.loads(raw)
            content = str((outer.get("message") or {}).get("content") or "").strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            decision = json.loads(match.group(0) if match else content)
            should_wake = bool(decision.get("should_wake"))
            logger.info(
                "whatsapp local followup classifier: chat=%s should_wake=%s reason=%s",
                data.get("chatId"),
                should_wake,
                str(decision.get("reason") or "")[:160],
            )
            return should_wake
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("whatsapp local followup classifier failed: %s", exc)
            return False

    def _local_conversation_router_enabled(self) -> bool:
        return bool(self.config.extra.get("local_conversation_router", False))

    @staticmethod
    def _is_local_model_base_url(base_url: str) -> bool:
        try:
            host = urllib.parse.urlparse(str(base_url or "")).hostname or ""
        except ValueError:
            return False
        return host.lower() in {"localhost", "127.0.0.1", "::1"}

    def _router_decision_cache_key(
        self,
        data: Dict[str, Any],
        *,
        recent_messages: list[Dict[str, Any]],
        active_thread: Optional[Dict[str, Any]],
        last_bot_reply: str,
    ) -> str:
        recent_signature = json.dumps(
            [
                {
                    "sender": str(item.get("sender") or "")[:80],
                    "body": str(item.get("body") or "")[:200],
                }
                for item in recent_messages[-10:]
            ],
            sort_keys=True,
            ensure_ascii=False,
        )
        thread_signature = json.dumps(
            {
                "thread_id": (active_thread or {}).get("thread_id", ""),
                "status": (active_thread or {}).get("status", ""),
                "updated_at": (active_thread or {}).get("updated_at", ""),
                "last_bot_reply": last_bot_reply[:300],
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return "\x1f".join([
            str(data.get("chatId") or ""),
            str(data.get("messageId") or ""),
            re.sub(r"\s+", " ", str(data.get("body") or "")).strip(),
            recent_signature,
            thread_signature,
        ])

    def _conversation_router_decision(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return a local LLM routing decision for ambiguous WhatsApp group messages."""
        if not self._local_conversation_router_enabled():
            return None
        chat_id = str(data.get("chatId") or "")
        body = re.sub(r"\s+", " ", str(data.get("body") or "")).strip()
        if not chat_id.endswith("@g.us") or not body or body.startswith("/"):
            return None
        active_thread = self._load_active_thread(chat_id)
        last_bot_reply = self._last_bot_reply_text_by_chat.get(chat_id, "")
        if active_thread and not last_bot_reply:
            last_bot_reply = str(active_thread.get("last_bot_reply") or "")
        recent_messages = self._recent_messages_for_chat(chat_id)
        key = self._router_decision_cache_key(
            data,
            recent_messages=recent_messages,
            active_thread=active_thread,
            last_bot_reply=last_bot_reply,
        )
        cache = getattr(self, "_conversation_router_decision_cache", None)
        if cache is None:
            cache = {}
            self._conversation_router_decision_cache = cache
        if key in cache:
            return cache[key]
        decision = self._classify_group_message_with_local_router(
            data,
            recent_messages=recent_messages,
            active_thread=active_thread,
            last_bot_reply=last_bot_reply,
        )
        if isinstance(decision, dict):
            decision["should_wake"] = bool(decision.get("should_wake"))
            cache[key] = decision
            return decision
        return None

    def _classify_group_message_with_local_router(
        self,
        data: Dict[str, Any],
        *,
        recent_messages: Optional[list[Dict[str, Any]]] = None,
        active_thread: Optional[Dict[str, Any]] = None,
        last_bot_reply: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Use local Ollama as a structured WhatsApp conversation router."""
        model = str(self.config.extra.get("local_conversation_router_model") or "qwen3.6:35b")
        base_url = str(self.config.extra.get("local_conversation_router_base_url") or "http://localhost:11434").rstrip("/")
        if not self._is_local_model_base_url(base_url) and not self.config.extra.get("allow_remote_conversation_router", False):
            logger.warning("whatsapp local conversation router refused non-local base_url=%s", base_url)
            return None
        try:
            timeout = float(self.config.extra.get("local_conversation_router_timeout", 45))
        except (TypeError, ValueError):
            timeout = 45.0
        body = re.sub(r"\s+", " ", str(data.get("body") or "")).strip()
        recent_slice = (recent_messages or [])[-10:]
        recent_lines = []
        for idx, item in enumerate(recent_slice, start=-len(recent_slice)):
            sender = str(item.get("sender") or "").strip()
            line = str(item.get("body") or "").strip()
            if line:
                recent_lines.append(f"{idx}: {sender + ': ' if sender else ''}{line}")
        thread_context = ""
        if active_thread:
            thread_context = (
                "Active WhatBot thread:\n"
                f"- type: {active_thread.get('thread_type', 'clarification')}\n"
                f"- status: {active_thread.get('status', '')}\n"
                f"- last_bot_reply: {active_thread.get('last_bot_reply', '')}\n"
            )
        prompt = (
            "You are WhatBot's WhatsApp group conversation router. Decide whether the new group message should wake WhatBot, "
            "what conversational role it has, and whether it points at a prior message. Be conservative: do not wake for ordinary "
            "human-to-human chatter. Wake for clear bot addressing, repair phrases like 'that was for you', direct continuations of "
            "visible active WhatBot threads, and assistant-style requests. Return ONLY compact JSON with keys: should_wake boolean, "
            "addressing_type string, confidence number, reason string, optional target_message_index integer where -1 means nearest prior "
            "recent message, and optional rewritten_user_intent string.\n\n"
            f"{thread_context}"
            "Recent group messages:\n" + "\n".join(recent_lines) + "\n"
            f"Previous WhatBot message: {last_bot_reply}\n"
            f"New group message: {body}\n"
        )
        payload = {
            "model": model,
            "think": False,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "num_predict": 220},
        }
        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            outer = json.loads(raw)
            content = str((outer.get("message") or {}).get("content") or "").strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            decision = json.loads(match.group(0) if match else content)
            if not isinstance(decision, dict):
                return None
            decision["should_wake"] = bool(decision.get("should_wake"))
            logger.info(
                "whatsapp local conversation router: chat=%s should_wake=%s type=%s reason=%s",
                data.get("chatId"),
                decision.get("should_wake"),
                str(decision.get("addressing_type") or "")[:80],
                str(decision.get("reason") or "")[:160],
            )
            return decision
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("whatsapp local conversation router failed: %s", exc)
            return None

    def _rewrite_group_message_body_with_router(self, chat_id: str, body: str, data: Dict[str, Any]) -> str:
        decision = self._conversation_router_decision(data)
        if not decision or not decision.get("should_wake"):
            return body
        addressing_type = str(decision.get("addressing_type") or "")
        if addressing_type not in {"retroactive_repair", "prior_message_repair", "message_repair"}:
            return body
        recent = self._recent_messages_for_chat(chat_id)
        current_clean = re.sub(r"\s+", " ", str(body or "")).strip()
        candidates = recent[:-1] if recent and str(recent[-1].get("body") or "").strip() == current_clean else recent
        target = None
        target_index = decision.get("target_message_index")
        if isinstance(target_index, int) and candidates:
            try:
                target = candidates[target_index]
            except IndexError:
                target = None
        if target is None:
            target = candidates[-1] if candidates else None
        if not target:
            return body
        sender = str(target.get("sender") or "someone").strip() or "someone"
        target_body = str(target.get("body") or "").strip()
        intent = str(decision.get("rewritten_user_intent") or "Answer the prior group message as if it was addressed to WhatBot.").strip()
        return (
            "[Conversation router repair]\n"
            f"Router decision: {intent}\n"
            f"Prior group message now being directed at WhatBot (from {sender}):\n"
            f"{target_body}\n\n"
            "[User repair message]\n"
            f"{body}"
        )

    def _clean_bot_mention_text(self, text: str, data: Dict[str, Any]) -> str:
        if not text:
            return text
        bot_ids = self._bot_ids_from_message(data)
        cleaned = text
        for bot_id in bot_ids:
            bare_id = bot_id.split("@", 1)[0]
            if bare_id:
                cleaned = re.sub(rf"@{re.escape(bare_id)}\b[,:\-]*\s*", "", cleaned)
        return cleaned.strip() or text

    @staticmethod
    def _safe_whatsapp_display_name(value: Any) -> str:
        """Return a one-line human display name suitable for agent-visible context."""
        name = re.sub(r"\s+", " ", str(value or "")).strip()
        if not name:
            return ""
        # Avoid leaking raw WhatsApp JIDs as user-facing names. The bridge only
        # fills quotedSenderName when it has an observed pushName/contact label.
        if "@" in name and ("whatsapp" in name.lower() or name.endswith("@lid") or name.endswith("@g.us")):
            return ""
        return name[:80]

    @staticmethod
    def _label_with_sender(label: str, sender_name: Any) -> str:
        sender = WhatsAppAdapter._safe_whatsapp_display_name(sender_name)
        if sender:
            if label.endswith("]"):
                return f"{label[:-1]} from {sender}]"
            return f"{label} from {sender}"
        return label

    @staticmethod
    def _sanitize_whatsapp_visible_ids(value: str) -> str:
        """Hide raw WhatsApp/LID mention IDs from agent-visible quoted text."""
        text = str(value or "")
        # WhatsApp quoted text can contain bare Linked Identity ids rendered as
        # @139904986148944. Those are not useful to the group and can prompt the
        # model to repeat private-looking implementation IDs. If the bridge can
        # resolve a human name it should already have replaced the mention; this
        # is the safety fallback.
        return re.sub(r"@\d{8,}(?=\b)", "@someone", text)

    def _should_process_message(self, data: Dict[str, Any]) -> bool:
        chat_id_raw = str(data.get("chatId") or "")
        # WhatsApp uses pseudo-chats for Status updates (Stories) and
        # Channel/Newsletter broadcasts. These are not real conversations
        # and the agent should never reply to them — even in self-chat mode
        # where the bridge may surface them as "fromMe" events.
        if self._is_broadcast_chat(chat_id_raw):
            return False
        is_group = data.get("isGroup", False)
        if is_group:
            chat_id = chat_id_raw
            if not self._is_group_allowed(chat_id):
                return False
        else:
            sender_id = str(data.get("senderId") or data.get("from") or "")
            if not self._is_dm_allowed(sender_id):
                return False
            # DMs that pass the policy gate are always processed
            return True
        # Group messages: check mention / free-response settings
        chat_id = str(data.get("chatId") or "")
        if chat_id in self._whatsapp_free_response_chats():
            return True
        if not self._whatsapp_require_mention():
            return True
        body = str(data.get("body") or "").strip()
        if body.startswith("/"):
            return True
        if self._message_is_reply_to_bot(data):
            return True
        if self._message_mentions_bot(data):
            return True
        if self._message_matches_mention_patterns(data):
            return True
        router_decision = self._conversation_router_decision(data)
        if router_decision is not None:
            return bool(router_decision.get("should_wake"))
        if self._message_is_retroactive_bot_addressing_text(body) and self._retroactive_target_recent_message(chat_id, body):
            return True
        if self._message_is_followup_to_recent_bot_reply(data):
            return True
        return self._message_likely_directed_at_bot(data)
    
    async def connect(self) -> bool:
        """
        Start the WhatsApp bridge.
        
        This launches the Node.js bridge process and waits for it to be ready.
        """
        if not check_whatsapp_requirements():
            logger.warning("[%s] Node.js not found. WhatsApp requires Node.js.", self.name)
            self._set_fatal_error(
                "whatsapp_node_missing",
                "Node.js is not installed — install Node.js and re-run `hermes gateway`.",
                retryable=False,
            )
            return False
        
        bridge_path = Path(self._bridge_script)
        if not bridge_path.exists():
            logger.warning("[%s] Bridge script not found: %s", self.name, bridge_path)
            self._set_fatal_error(
                "whatsapp_bridge_missing",
                f"WhatsApp bridge script missing at {bridge_path}.",
                retryable=False,
            )
            return False

        # Pre-flight: skip the 30s bridge bootstrap entirely if the user
        # never finished pairing.  Without creds.json the bridge prints
        # QR codes to its log file and never reaches status:connected,
        # so every gateway restart paid the 30s timeout + queued WhatsApp
        # for indefinite retries.  Mark non-retryable so the user gets a
        # clear "run hermes whatsapp" message instead of the watcher
        # silently hammering an unconfigured platform.
        creds_path = self._session_path / "creds.json"
        if not creds_path.exists():
            logger.warning(
                "[%s] WhatsApp is enabled but not paired (no creds.json at %s). "
                "Run `hermes whatsapp` to pair, or remove WHATSAPP_ENABLED from "
                "your .env to disable.",
                self.name, creds_path,
            )
            self._set_fatal_error(
                "whatsapp_not_paired",
                "WhatsApp enabled but not paired — run `hermes whatsapp` to pair.",
                retryable=False,
            )
            return False

        logger.info("[%s] Bridge found at %s", self.name, bridge_path)
        
        # Acquire scoped lock to prevent duplicate sessions
        lock_acquired = False
        try:
            if not self._acquire_platform_lock('whatsapp-session', str(self._session_path), 'WhatsApp session'):
                return False
            lock_acquired = True
        except Exception as e:
            logger.warning("[%s] Could not acquire session lock (non-fatal): %s", self.name, e)

        try:
            # Auto-install npm dependencies if node_modules doesn't exist
            bridge_dir = bridge_path.parent
            if not (bridge_dir / "node_modules").exists():
                print(f"[{self.name}] Installing WhatsApp bridge dependencies...")
                # Resolve npm path so Windows can execute the .cmd shim.
                # shutil.which honours PATHEXT; on POSIX it returns the
                # plain executable path.
                _npm_bin = shutil.which("npm") or "npm"
                try:
                    # Read timeout from environment variable, default to 300 seconds (5 minutes)
                    # to accommodate slower systems like Unraid NAS
                    npm_install_timeout = int(os.environ.get("WHATSAPP_NPM_INSTALL_TIMEOUT", "300"))
                    install_result = subprocess.run(
                        [_npm_bin, "install", "--silent"],
                        cwd=str(bridge_dir),
                        capture_output=True,
                        text=True,
                        timeout=npm_install_timeout,
                    )
                    if install_result.returncode != 0:
                        print(f"[{self.name}] npm install failed: {install_result.stderr}")
                        return False
                    print(f"[{self.name}] Dependencies installed")
                except Exception as e:
                    print(f"[{self.name}] Failed to install dependencies: {e}")
                    return False

            # Ensure session directory exists
            self._session_path.mkdir(parents=True, exist_ok=True)
            
            # Check if bridge is already running and connected
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://127.0.0.1:{self._bridge_port}/health",
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            bridge_status = data.get("status", "unknown")
                            if bridge_status == "connected":
                                print(f"[{self.name}] Using existing bridge (status: {bridge_status})")
                                self._mark_connected()
                                self._bridge_process = None  # Not managed by us
                                self._http_session = aiohttp.ClientSession()
                                self._poll_task = asyncio.create_task(self._poll_messages())
                                return True
                            else:
                                print(f"[{self.name}] Bridge found but not connected (status: {bridge_status}), restarting")
            except Exception:
                pass  # Bridge not running, start a new one
            
            # Kill any orphaned bridge from a previous gateway run
            _kill_stale_bridge_by_pidfile(self._session_path)
            _kill_port_process(self._bridge_port)
            await asyncio.sleep(1)
            
            # Start the bridge process in its own process group.
            # Route output to a log file so QR codes, errors, and reconnection
            # messages are preserved for troubleshooting.
            whatsapp_mode = os.getenv("WHATSAPP_MODE", "self-chat")
            self._bridge_log = self._session_path.parent / "bridge.log"
            bridge_log_fh = open(self._bridge_log, "a", encoding="utf-8")
            self._bridge_log_fh = bridge_log_fh

            # Build bridge subprocess environment.
            # Pass WHATSAPP_REPLY_PREFIX from config.yaml so the Node bridge
            # can use it without the user needing to set a separate env var.
            bridge_env = os.environ.copy()
            if self._reply_prefix is not None:
                bridge_env["WHATSAPP_REPLY_PREFIX"] = self._reply_prefix

            self._bridge_process = subprocess.Popen(
                [
                    "node",
                    str(bridge_path),
                    "--port", str(self._bridge_port),
                    "--session", str(self._session_path),
                    "--mode", whatsapp_mode,
                ],
                stdout=bridge_log_fh,
                stderr=bridge_log_fh,
                preexec_fn=None if _IS_WINDOWS else os.setsid,
                env=bridge_env,
            )
            _write_bridge_pidfile(self._session_path, self._bridge_process.pid)
            
            # Wait for the bridge to connect to WhatsApp.
            # Phase 1: wait for the HTTP server to come up (up to 15s).
            # Phase 2: wait for WhatsApp status: connected (up to 15s more).
            import aiohttp
            http_ready = False
            data = {}
            for attempt in range(15):
                await asyncio.sleep(1)
                if self._bridge_process.poll() is not None:
                    print(f"[{self.name}] Bridge process died (exit code {self._bridge_process.returncode})")
                    print(f"[{self.name}] Check log: {self._bridge_log}")
                    self._close_bridge_log()
                    return False
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"http://127.0.0.1:{self._bridge_port}/health",
                            timeout=aiohttp.ClientTimeout(total=2)
                        ) as resp:
                            if resp.status == 200:
                                http_ready = True
                                data = await resp.json()
                                if data.get("status") == "connected":
                                    print(f"[{self.name}] Bridge ready (status: connected)")
                                    break
                except Exception:
                    continue

            if not http_ready:
                print(f"[{self.name}] Bridge HTTP server did not start in 15s")
                print(f"[{self.name}] Check log: {self._bridge_log}")
                self._close_bridge_log()
                return False
            
            # Phase 2: HTTP is up but WhatsApp may still be connecting.
            # Give it more time to authenticate with saved credentials.
            if data.get("status") != "connected":
                print(f"[{self.name}] Bridge HTTP ready, waiting for WhatsApp connection...")
                for attempt in range(15):
                    await asyncio.sleep(1)
                    if self._bridge_process.poll() is not None:
                        print(f"[{self.name}] Bridge process died during connection")
                        print(f"[{self.name}] Check log: {self._bridge_log}")
                        self._close_bridge_log()
                        return False
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                f"http://127.0.0.1:{self._bridge_port}/health",
                                timeout=aiohttp.ClientTimeout(total=2)
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    if data.get("status") == "connected":
                                        print(f"[{self.name}] Bridge ready (status: connected)")
                                        break
                    except Exception:
                        continue
                else:
                    # Still not connected — warn but proceed (bridge may
                    # auto-reconnect later, e.g. after a code 515 restart).
                    print(f"[{self.name}] ⚠ WhatsApp not connected after 30s")
                    print(f"[{self.name}]   Bridge log: {self._bridge_log}")
                    print(f"[{self.name}]   If session expired, re-pair: hermes whatsapp")
            
            # Create a persistent HTTP session for all bridge communication
            self._http_session = aiohttp.ClientSession()

            # Start message polling task
            self._poll_task = asyncio.create_task(self._poll_messages())
            
            self._mark_connected()
            print(f"[{self.name}] Bridge started on port {self._bridge_port}")
            return True
            
        except Exception as e:
            logger.error("[%s] Failed to start bridge: %s", self.name, e, exc_info=True)
            return False
        finally:
            if not self._running:
                if lock_acquired:
                    self._release_platform_lock()
                self._close_bridge_log()
    
    def _close_bridge_log(self) -> None:
        """Close the bridge log file handle if open."""
        if self._bridge_log_fh:
            try:
                self._bridge_log_fh.close()
            except Exception:
                pass
            self._bridge_log_fh = None

    async def _check_managed_bridge_exit(self) -> Optional[str]:
        """Return a fatal error message if the managed bridge child exited."""
        if self._bridge_process is None:
            return None

        returncode = self._bridge_process.poll()
        if returncode is None:
            return None

        # Planned shutdown: disconnect() sets _shutting_down before it sends
        # SIGTERM to the bridge, so a returncode of -15 (SIGTERM), -2 (SIGINT),
        # or 0 (clean exit) at that point is expected, not a crash. Treat it
        # as informational and skip the fatal-error path.
        # getattr-with-default keeps tests that construct the adapter via
        # ``WhatsAppAdapter.__new__`` (bypassing __init__) working without
        # every _make_adapter() helper having to seed the attribute.
        if getattr(self, "_shutting_down", False) and returncode in {0, -2, -15}:
            logger.info(
                "[%s] Bridge exited during shutdown (code %d).",
                self.name,
                returncode,
            )
            return None

        message = f"WhatsApp bridge process exited unexpectedly (code {returncode})."
        if not self.has_fatal_error:
            logger.error("[%s] %s", self.name, message)
            self._set_fatal_error("whatsapp_bridge_exited", message, retryable=True)
            self._close_bridge_log()
            await self._notify_fatal_error()
        return self.fatal_error_message or message

    async def disconnect(self) -> None:
        """Stop the WhatsApp bridge and clean up any orphaned processes."""
        # Flip the shutdown flag BEFORE signalling the child so the exit-check
        # path (which runs from other tasks like send() and the poll loop)
        # doesn't race us and report the intentional termination as fatal.
        self._shutting_down = True
        if self._bridge_process:
            try:
                try:
                    _terminate_bridge_process(self._bridge_process, force=False)
                except (ProcessLookupError, PermissionError):
                    self._bridge_process.terminate()
                await asyncio.sleep(1)
                if self._bridge_process.poll() is None:
                    try:
                        _terminate_bridge_process(self._bridge_process, force=True)
                    except (ProcessLookupError, PermissionError):
                        self._bridge_process.kill()
            except Exception as e:
                print(f"[{self.name}] Error stopping bridge: {e}")
        else:
            # Bridge was not started by us, don't kill it
            print(f"[{self.name}] Disconnecting (external bridge left running)")

        # Clean up PID file
        try:
            (self._session_path / "bridge.pid").unlink(missing_ok=True)
        except OSError:
            pass

        # Cancel the poll task explicitly
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except (asyncio.CancelledError, Exception):
                pass
        self._poll_task = None

        # Close the persistent HTTP session
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        self._http_session = None

        self._release_platform_lock()

        self._mark_disconnected()
        self._bridge_process = None
        self._close_bridge_log()
        print(f"[{self.name}] Disconnected")
    
    def format_message(self, content: str) -> str:
        """Convert standard markdown to WhatsApp-compatible formatting.

        WhatsApp supports: *bold*, _italic_, ~strikethrough~, ```code```,
        and monospaced `inline`. Standard markdown uses different syntax
        for bold/italic/strikethrough, so we convert here.

        Code blocks (``` fenced) and inline code (`) are protected from
        conversion via placeholder substitution.
        """
        if not content:
            return content

        # --- 1. Protect fenced code blocks from formatting changes ---
        _FENCE_PH = "\x00FENCE"
        fences: list[str] = []

        def _save_fence(m: re.Match) -> str:
            fences.append(m.group(0))
            return f"{_FENCE_PH}{len(fences) - 1}\x00"

        result = re.sub(r"```[\s\S]*?```", _save_fence, content)

        # --- 2. Protect inline code ---
        _CODE_PH = "\x00CODE"
        codes: list[str] = []

        def _save_code(m: re.Match) -> str:
            codes.append(m.group(0))
            return f"{_CODE_PH}{len(codes) - 1}\x00"

        result = re.sub(r"`[^`\n]+`", _save_code, result)

        # --- 3. Convert markdown formatting to WhatsApp syntax ---
        # Bold: **text** or __text__ → *text*
        result = re.sub(r"\*\*(.+?)\*\*", r"*\1*", result)
        result = re.sub(r"__(.+?)__", r"*\1*", result)
        # Strikethrough: ~~text~~ → ~text~
        result = re.sub(r"~~(.+?)~~", r"~\1~", result)
        # Italic: *text* is already WhatsApp italic — leave as-is
        # _text_ is already WhatsApp italic — leave as-is

        # --- 4. Convert markdown headers to bold text ---
        # # Header → *Header*
        result = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", result, flags=re.MULTILINE)

        # --- 5. Convert markdown links: [text](url) → text (url) ---
        result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", result)

        # --- 6. Restore protected sections ---
        for i, fence in enumerate(fences):
            result = result.replace(f"{_FENCE_PH}{i}\x00", fence)
        for i, code in enumerate(codes):
            result = result.replace(f"{_CODE_PH}{i}\x00", code)

        return result

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SendResult:
        """Send a message via the WhatsApp bridge.

        Formats markdown for WhatsApp, splits long messages into chunks
        that preserve code block boundaries, and sends each chunk sequentially.
        """
        if not self._running or not self._http_session:
            return SendResult(success=False, error="Not connected")
        bridge_exit = await self._check_managed_bridge_exit()
        if bridge_exit:
            return SendResult(success=False, error=bridge_exit)

        if not content or not content.strip():
            return SendResult(success=True, message_id=None)

        try:
            import aiohttp

            # Format and chunk the message
            formatted = self.format_message(content)
            chunks = self.truncate_message(formatted, self._outgoing_chunk_limit())

            last_message_id = None
            for chunk in chunks:
                payload: Dict[str, Any] = {
                    "chatId": chat_id,
                    "message": chunk,
                }
                if reply_to and last_message_id is None:
                    # Only reply-to on the first chunk
                    payload["replyTo"] = reply_to

                async with self._http_session.post(
                    f"http://127.0.0.1:{self._bridge_port}/send",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        last_message_id = data.get("messageId")
                    else:
                        error = await resp.text()
                        return SendResult(success=False, error=error)

                # Small delay between chunks to avoid rate limiting
                if len(chunks) > 1:
                    await asyncio.sleep(0.3)

            if str(chat_id).endswith("@g.us"):
                self._record_bot_group_reply(str(chat_id), formatted)
            return SendResult(
                success=True,
                message_id=last_message_id,
            )
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        content: str,
        *,
        finalize: bool = False,
    ) -> SendResult:
        """Edit a previously sent message via the WhatsApp bridge."""
        if not self._running or not self._http_session:
            return SendResult(success=False, error="Not connected")
        bridge_exit = await self._check_managed_bridge_exit()
        if bridge_exit:
            return SendResult(success=False, error=bridge_exit)
        try:
            import aiohttp
            async with self._http_session.post(
                f"http://127.0.0.1:{self._bridge_port}/edit",
                json={
                    "chatId": chat_id,
                    "messageId": message_id,
                    "message": content,
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    return SendResult(success=True, message_id=message_id)
                else:
                    error = await resp.text()
                    return SendResult(success=False, error=error)
        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def _send_media_to_bridge(
        self,
        chat_id: str,
        file_path: str,
        media_type: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> SendResult:
        """Send any media file via bridge /send-media endpoint."""
        if not self._running or not self._http_session:
            return SendResult(success=False, error="Not connected")
        bridge_exit = await self._check_managed_bridge_exit()
        if bridge_exit:
            return SendResult(success=False, error=bridge_exit)
        try:
            import aiohttp

            if not os.path.exists(file_path):
                return SendResult(success=False, error=f"File not found: {file_path}")

            payload: Dict[str, Any] = {
                "chatId": chat_id,
                "filePath": file_path,
                "mediaType": media_type,
            }
            if caption:
                payload["caption"] = caption
            if file_name:
                payload["fileName"] = file_name

            async with self._http_session.post(
                f"http://127.0.0.1:{self._bridge_port}/send-media",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return SendResult(
                        success=True,
                        message_id=data.get("messageId"),
                        raw_response=data,
                    )
                else:
                    error = await resp.text()
                    return SendResult(success=False, error=error)

        except Exception as e:
            return SendResult(success=False, error=str(e))

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> SendResult:
        """Download image URL to cache, send natively via bridge."""
        try:
            local_path = await cache_image_from_url(image_url)
            return await self._send_media_to_bridge(chat_id, local_path, "image", caption)
        except Exception:
            return await super().send_image(chat_id, image_url, caption, reply_to)

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a local image file natively via bridge."""
        return await self._send_media_to_bridge(chat_id, image_path, "image", caption)

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a video natively via bridge — plays inline in WhatsApp."""
        return await self._send_media_to_bridge(chat_id, video_path, "video", caption)

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send an audio file as a WhatsApp voice message via bridge."""
        return await self._send_media_to_bridge(chat_id, audio_path, "audio", caption)

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a document/file as a downloadable attachment via bridge."""
        return await self._send_media_to_bridge(
            chat_id, file_path, "document", caption,
            file_name or os.path.basename(file_path),
        )

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """Send typing indicator via bridge."""
        if not self._running or not self._http_session:
            return
        if await self._check_managed_bridge_exit():
            return
        
        try:
            import aiohttp

            # Must wrap in `async with` — a bare `await session.post(...)`
            # leaves the response object alive until GC, holding its TCP
            # socket in CLOSE_WAIT. See #18451.
            async with self._http_session.post(
                f"http://127.0.0.1:{self._bridge_port}/typing",
                json={"chatId": chat_id},
                timeout=aiohttp.ClientTimeout(total=5)
            ):
                pass
        except Exception:
            pass  # Ignore typing indicator failures
    
    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Get information about a WhatsApp chat."""
        if not self._running or not self._http_session:
            return {"name": "Unknown", "type": "dm"}
        if await self._check_managed_bridge_exit():
            return {"name": chat_id, "type": "dm"}
        
        try:
            import aiohttp

            async with self._http_session.get(
                f"http://127.0.0.1:{self._bridge_port}/chat/{chat_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "name": data.get("name", chat_id),
                        "type": "group" if data.get("isGroup") else "dm",
                        "participants": data.get("participants", []),
                    }
        except Exception as e:
            logger.debug("Could not get WhatsApp chat info for %s: %s", chat_id, e)
        
        return {"name": chat_id, "type": "dm"}
    
    async def _poll_messages(self) -> None:
        """Poll the bridge for incoming messages."""
        import aiohttp

        while self._running:
            if not self._http_session:
                break
            bridge_exit = await self._check_managed_bridge_exit()
            if bridge_exit:
                print(f"[{self.name}] {bridge_exit}")
                break
            try:
                async with self._http_session.get(
                    f"http://127.0.0.1:{self._bridge_port}/messages",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        messages = await resp.json()
                        for msg_data in messages:
                            event = await self._build_message_event(msg_data)
                            if event:
                                await self.handle_message(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                bridge_exit = await self._check_managed_bridge_exit()
                if bridge_exit:
                    print(f"[{self.name}] {bridge_exit}")
                    break
                print(f"[{self.name}] Poll error: {e}")
                await asyncio.sleep(5)
            
            await asyncio.sleep(1)  # Poll interval
    
    async def _build_message_event(self, data: Dict[str, Any]) -> Optional[MessageEvent]:
        """Build a MessageEvent from bridge message data, downloading images to cache."""
        try:
            if data.get("isGroup") and not self._is_group_allowed(str(data.get("chatId") or "")):
                return None
            if data.get("isGroup"):
                self._record_recent_group_message(data)
            should_process = self._should_process_message(data)

            # Determine message type
            msg_type = MessageType.TEXT
            if data.get("hasMedia"):
                media_type = data.get("mediaType", "")
                if "image" in media_type:
                    msg_type = MessageType.PHOTO
                elif "video" in media_type:
                    msg_type = MessageType.VIDEO
                elif "audio" in media_type or "ptt" in media_type:  # ptt = voice note
                    msg_type = MessageType.VOICE
                else:
                    msg_type = MessageType.DOCUMENT
            
            # Determine chat type
            is_group = data.get("isGroup", False)
            chat_type = "group" if is_group else "dm"
            
            # Build source
            source = self.build_source(
                chat_id=data.get("chatId", ""),
                chat_name=data.get("chatName"),
                chat_type=chat_type,
                user_id=data.get("senderId"),
                user_name=data.get("senderName"),
            )
            
            # Download media URLs to the local cache so agent tools
            # can access them reliably regardless of URL expiration.
            raw_urls = data.get("mediaUrls", [])
            cached_urls = []
            media_types = []
            for url in raw_urls:
                if msg_type == MessageType.PHOTO and url.startswith(("http://", "https://")):
                    try:
                        cached_path = await cache_image_from_url(url, ext=".jpg")
                        cached_urls.append(cached_path)
                        media_types.append("image/jpeg")
                        print(f"[{self.name}] Cached user image: {cached_path}", flush=True)
                    except Exception as e:
                        print(f"[{self.name}] Failed to cache image: {e}", flush=True)
                        cached_urls.append(url)
                        media_types.append("image/jpeg")
                elif msg_type == MessageType.PHOTO and os.path.isabs(url):
                    # Local file path — bridge already downloaded the image
                    cached_urls.append(url)
                    media_types.append("image/jpeg")
                    print(f"[{self.name}] Using bridge-cached image: {url}", flush=True)
                elif msg_type == MessageType.VOICE and url.startswith(("http://", "https://")):
                    try:
                        cached_path = await cache_audio_from_url(url, ext=".ogg")
                        cached_urls.append(cached_path)
                        media_types.append("audio/ogg")
                        print(f"[{self.name}] Cached user voice: {cached_path}", flush=True)
                    except Exception as e:
                        print(f"[{self.name}] Failed to cache voice: {e}", flush=True)
                        cached_urls.append(url)
                        media_types.append("audio/ogg")
                elif msg_type == MessageType.VOICE and os.path.isabs(url):
                    # Local file path — bridge already downloaded the audio
                    cached_urls.append(url)
                    media_types.append("audio/ogg")
                    print(f"[{self.name}] Using bridge-cached audio: {url}", flush=True)
                elif msg_type == MessageType.DOCUMENT and os.path.isabs(url):
                    # Local file path — bridge already downloaded the document
                    cached_urls.append(url)
                    ext = Path(url).suffix.lower()
                    mime = SUPPORTED_DOCUMENT_TYPES.get(ext, "application/octet-stream")
                    media_types.append(mime)
                    print(f"[{self.name}] Using bridge-cached document: {url}", flush=True)
                elif msg_type == MessageType.VIDEO and os.path.isabs(url):
                    cached_urls.append(url)
                    media_types.append("video/mp4")
                    print(f"[{self.name}] Using bridge-cached video: {url}", flush=True)
                else:
                    cached_urls.append(url)
                    media_types.append("unknown")

            # For text-readable documents, inject file content directly into
            # the message text so the agent can read it inline.
            # Cap at 100KB to match Telegram/Discord/Slack behaviour.
            body = data.get("body", "")
            if data.get("isGroup"):
                body = self._clean_bot_mention_text(body, data)
                body = self._rewrite_group_message_body_with_router(str(data.get("chatId") or ""), body, data)
                body = self._rewrite_retroactive_bot_addressing_body(str(data.get("chatId") or ""), body)

            quoted_body = self._sanitize_whatsapp_visible_ids(str(data.get("quotedBody") or "").strip())
            if quoted_body:
                quoted_label = self._label_with_sender("[Quoted message]", data.get("quotedSenderName"))
                if data.get("quotedHasMedia"):
                    quoted_type = str(data.get("quotedType") or "media").replace("Message", "").strip() or "media"
                    quoted_label = self._label_with_sender(f"[Quoted {quoted_type}]", data.get("quotedSenderName"))
                user_label = self._label_with_sender("[User message]", data.get("senderName"))
                user_body = body or "[no additional text]"
                body = f"{quoted_label}\n{quoted_body}\n\n{user_label}\n{user_body}"

            # Let plugins observe allowlisted group messages before the
            # reply/wake gate drops ordinary chatter. This supports passive
            # same-group archives while keeping response behavior conservative.
            observed_event = MessageEvent(
                text=body,
                message_type=msg_type,
                source=source,
                raw_message=data,
                message_id=data.get("messageId"),
                media_urls=list(data.get("mediaUrls", []) or []),
                media_types=[],
            )
            try:
                from hermes_cli.plugins import invoke_hook as _invoke_hook
                _invoke_hook(
                    "platform_message_observed",
                    event=observed_event,
                    will_process=should_process,
                    adapter=self,
                )
            except Exception as hook_exc:
                logger.debug("[%s] platform_message_observed hook failed: %s", self.name, hook_exc)

            if not should_process:
                return None

            MAX_TEXT_INJECT_BYTES = 100 * 1024
            if msg_type == MessageType.DOCUMENT and cached_urls:
                for doc_path in cached_urls:
                    ext = Path(doc_path).suffix.lower()
                    if ext in {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml", ".log", ".py", ".js", ".ts", ".html", ".css"}:
                        try:
                            file_size = Path(doc_path).stat().st_size
                            if file_size > MAX_TEXT_INJECT_BYTES:
                                print(f"[{self.name}] Skipping text injection for {doc_path} ({file_size} bytes > {MAX_TEXT_INJECT_BYTES})", flush=True)
                                continue
                            content = Path(doc_path).read_text(encoding="utf-8", errors="replace")
                            fname = Path(doc_path).name
                            # Remove the doc_<hex>_ prefix for display
                            display_name = fname
                            if "_" in fname:
                                parts = fname.split("_", 2)
                                if len(parts) >= 3:
                                    display_name = parts[2]
                            injection = f"[Content of {display_name}]:\n{content}"
                            if body:
                                body = f"{injection}\n\n{body}"
                            else:
                                body = injection
                            print(f"[{self.name}] Injected text content from: {doc_path}", flush=True)
                        except Exception as e:
                            print(f"[{self.name}] Failed to read document text: {e}", flush=True)

            return MessageEvent(
                text=body,
                message_type=msg_type,
                source=source,
                raw_message=data,
                message_id=data.get("messageId"),
                media_urls=cached_urls,
                media_types=media_types,
            )
        except Exception as e:
            print(f"[{self.name}] Error building event: {e}")
            return None
