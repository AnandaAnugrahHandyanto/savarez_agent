"""XMemo provider configuration loader.

Reads settings from (highest to lowest priority):
  1. $HERMES_HOME/xmemo.json
  2. Environment variables: XMEMO_KEY, XMEMO_URL, XMEMO_AGENT_ID,
     XMEMO_AGENT_INSTANCE_ID
  3. Legacy aliases: MEMORY_OS_API_KEY, MEMORY_OS_URL
"""

from __future__ import annotations

import json
import logging
import os
import platform
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://xmemo.dev"
DEFAULT_BUCKET = "work"
DEFAULT_SCOPE = "hermes/default"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_PREFETCH_MAX_ITEMS = 5
DEFAULT_PREFETCH_MAX_TOKENS = 900


def _default_agent_instance_id(profile: str = "default") -> str:
    """Generate a stable, non-secret device/install identifier.

    The value is derived from machine-level stable inputs so it survives
    restarts, but it is hashed so the raw inputs are not exposed.
    """
    seed_parts = [
        platform.node() or "unknown-node",
        platform.system() or "unknown-os",
        os.environ.get("USER") or os.environ.get("USERNAME") or "unknown-user",
        profile,
    ]
    seed = "\0".join(seed_parts)
    return uuid.uuid5(uuid.NAMESPACE_OID, seed).hex


def _config_path() -> Path:
    return get_hermes_home() / "xmemo.json"


def load_config() -> Dict[str, Any]:
    """Load XMemo provider configuration.

    Non-secret values are read from xmemo.json and overlaid with env vars.
    Secrets (api_key) are read from env only and never persisted to JSON.
    """
    # Start with xmemo.json if present
    file_cfg: Dict[str, Any] = {}
    cfg_path = _config_path()
    if cfg_path.exists():
        try:
            file_cfg = json.loads(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.debug("Failed to read %s: %s", cfg_path, exc)

    # Environment variables take precedence for non-secret values too
    env_overrides: Dict[str, Any] = {}

    api_key = (
        os.environ.get("XMEMO_KEY")
        or os.environ.get("MEMORY_OS_API_KEY")
        or file_cfg.get("api_key", "")
    )

    base_url = (
        os.environ.get("XMEMO_URL")
        or os.environ.get("MEMORY_OS_URL")
        or file_cfg.get("base_url", "")
        or DEFAULT_BASE_URL
    )

    agent_id = os.environ.get("XMEMO_AGENT_ID") or file_cfg.get("agent_id", "hermes")

    agent_instance_id = (
        os.environ.get("XMEMO_AGENT_INSTANCE_ID")
        or file_cfg.get("agent_instance_id", "")
    )

    bucket = os.environ.get("XMEMO_BUCKET") or file_cfg.get("bucket", DEFAULT_BUCKET)
    scope = os.environ.get("XMEMO_SCOPE") or file_cfg.get("scope", DEFAULT_SCOPE)

    timeout = file_cfg.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if "XMEMO_TIMEOUT_SECONDS" in os.environ:
        try:
            timeout = float(os.environ["XMEMO_TIMEOUT_SECONDS"])
        except ValueError:
            pass

    prefetch_max_items = file_cfg.get(
        "prefetch_max_items", DEFAULT_PREFETCH_MAX_ITEMS
    )
    if "XMEMO_PREFETCH_MAX_ITEMS" in os.environ:
        try:
            prefetch_max_items = int(os.environ["XMEMO_PREFETCH_MAX_ITEMS"])
        except ValueError:
            pass

    prefetch_max_tokens = file_cfg.get(
        "prefetch_max_tokens", DEFAULT_PREFETCH_MAX_TOKENS
    )
    if "XMEMO_PREFETCH_MAX_TOKENS" in os.environ:
        try:
            prefetch_max_tokens = int(os.environ["XMEMO_PREFETCH_MAX_TOKENS"])
        except ValueError:
            pass

    config = {
        "api_key": api_key,
        "base_url": base_url,
        "agent_id": agent_id,
        "agent_instance_id": agent_instance_id,
        "bucket": bucket,
        "scope": scope,
        "timeout_seconds": timeout,
        "prefetch_max_items": prefetch_max_items,
        "prefetch_max_tokens": prefetch_max_tokens,
    }

    # Generate a stable instance id if still missing and persist it
    if not config["agent_instance_id"]:
        profile = os.environ.get("HERMES_PROFILE", "default")
        config["agent_instance_id"] = _default_agent_instance_id(profile)
        try:
            save_config(config)
        except Exception as exc:
            logger.debug("Failed to persist generated agent_instance_id: %s", exc)

    return config


def save_config(values: Dict[str, Any], hermes_home: Optional[str] = None) -> None:
    """Persist non-secret XMemo config to $HERMES_HOME/xmemo.json."""
    if hermes_home:
        cfg_path = Path(hermes_home) / "xmemo.json"
    else:
        cfg_path = _config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    existing: Dict[str, Any] = {}
    if cfg_path.exists():
        try:
            existing = json.loads(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    # Never write secrets to disk
    safe_values = {k: v for k, v in values.items() if k != "api_key"}
    existing.update(safe_values)

    cfg_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
