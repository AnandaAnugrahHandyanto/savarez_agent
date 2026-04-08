"""
WeChat platform state management — context tokens and sync buffer persistence.

Context tokens are issued per-message by the WeChat getUpdates API and must be
echoed verbatim in every outbound send. Tokens are cached in-memory and persisted
to disk so they survive gateway restarts.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


def _wechat_state_dir() -> Path:
    """Return (and create) the WeChat state directory under HERMES_HOME."""
    d = get_hermes_home() / "wechat"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Sync buffer (poll cursor) persistence
# ---------------------------------------------------------------------------

def _sync_buf_path(account_id: str) -> Path:
    d = _wechat_state_dir() / "sync"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{account_id}.buf"


def load_sync_buf(account_id: str) -> str:
    """Load the last getUpdates sync buffer for an account."""
    if not account_id:
        return ""
    p = _sync_buf_path(account_id)
    try:
        return p.read_text("utf-8").strip() if p.exists() else ""
    except Exception:
        return ""


def save_sync_buf(account_id: str, buf: str) -> None:
    """Persist the getUpdates sync buffer for resume after restart."""
    if not account_id:
        return
    try:
        _sync_buf_path(account_id).write_text(buf, "utf-8")
    except Exception as e:
        logger.warning("[WeChat] Failed to save sync buf: %s", e)


# ---------------------------------------------------------------------------
# Context token persistence
# ---------------------------------------------------------------------------

def _context_tokens_path() -> Path:
    return _wechat_state_dir() / "context_tokens.json"


def load_context_tokens() -> Dict[str, str]:
    """Load persisted context tokens from disk.

    Called at adapter startup so tokens survive gateway restarts —
    users don't need to re-message before the bot can reply.
    """
    p = _context_tokens_path()
    try:
        if p.exists():
            data = json.loads(p.read_text("utf-8"))
            if isinstance(data, dict):
                count = len(data)
                if count:
                    logger.info("[WeChat] Loaded %d context tokens from disk", count)
                return {k: v for k, v in data.items() if isinstance(v, str)}
    except Exception as e:
        logger.warning("[WeChat] Failed to load context tokens: %s", e)
    return {}


def save_context_tokens(tokens: Dict[str, str]) -> None:
    """Persist all context tokens to disk with restricted permissions."""
    try:
        p = _context_tokens_path()
        p.write_text(json.dumps(tokens), "utf-8")
        p.chmod(0o600)
    except Exception as e:
        logger.debug("[WeChat] Failed to persist context_tokens: %s", e)


def clear_context_tokens() -> None:
    """Remove all persisted context tokens (called on session expiry)."""
    try:
        p = _context_tokens_path()
        if p.exists():
            p.unlink()
            logger.info("[WeChat] Cleared persisted context tokens")
    except Exception as e:
        logger.warning("[WeChat] Failed to clear context tokens: %s", e)


