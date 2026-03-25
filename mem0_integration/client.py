"""Mem0 client initialization and configuration.

Resolution order for config file:
  1. $HERMES_HOME/mem0.json   (instance-local)
  2. ~/.hermes/mem0.json      (global)
  3. Environment variables    (MEM0_API_KEY)
"""

from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mem0 import MemoryClient

logger = logging.getLogger(__name__)

GLOBAL_CONFIG_PATH = Path.home() / ".hermes" / "mem0.json"
HOST = "hermes"

_VALID_RECALL_MODES = {"hybrid", "context", "tools"}


def _get_hermes_home() -> Path:
    """Get HERMES_HOME without importing hermes_cli (avoids circular deps)."""
    return Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))


def resolve_config_path() -> Path:
    """Return the active Mem0 config path.

    Checks $HERMES_HOME/mem0.json first (instance-local), then falls back
    to ~/.hermes/mem0.json (global).  Returns the global path if neither
    exists (for first-time setup writes).
    """
    local_path = _get_hermes_home() / "mem0.json"
    if local_path.exists():
        return local_path
    return GLOBAL_CONFIG_PATH


@dataclass
class Mem0ClientConfig:
    """Configuration for Mem0 client, resolved for a specific host."""

    host: str = HOST
    api_key: str | None = None
    # Identity
    user_id: str | None = None
    agent_id: str = "hermes"
    # Toggles
    enabled: bool = False
    # memoryMode: "hybrid" (Mem0 + local files) / "mem0" (Mem0 only)
    memory_mode: str = "hybrid"
    # Recall mode: "hybrid" / "context" / "tools"
    recall_mode: str = "hybrid"
    # Session resolution
    session_strategy: str = "per-directory"
    # Retrieval quality
    rerank: bool = True            # +150-200ms, better accuracy
    keyword_search: bool = True    # +~10ms, better recall
    # Extraction control
    custom_instructions: str | None = None

    @classmethod
    def from_env(cls) -> Mem0ClientConfig:
        """Create config from environment variables (fallback)."""
        api_key = os.environ.get("MEM0_API_KEY")
        return cls(
            api_key=api_key,
            enabled=bool(api_key),
        )

    @classmethod
    def from_global_config(
        cls,
        host: str = HOST,
        config_path: Path | None = None,
    ) -> Mem0ClientConfig:
        """Create config from the resolved Mem0 config path.

        Resolution: $HERMES_HOME/mem0.json -> ~/.hermes/mem0.json -> env vars.
        """
        path = config_path or resolve_config_path()
        if not path.exists():
            logger.debug("No Mem0 config at %s, falling back to env", path)
            return cls.from_env()

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read %s: %s, falling back to env", path, e)
            return cls.from_env()

        host_block = (raw.get("hosts") or {}).get(host, {})

        api_key = (
            host_block.get("apiKey")
            or raw.get("apiKey")
            or os.environ.get("MEM0_API_KEY")
        )

        # Auto-enable when API key is present (unless explicitly disabled)
        host_enabled = host_block.get("enabled")
        root_enabled = raw.get("enabled")
        if host_enabled is not None:
            enabled = host_enabled
        elif root_enabled is not None:
            enabled = root_enabled
        else:
            enabled = bool(api_key)

        recall_raw = (
            host_block.get("recallMode")
            or raw.get("recallMode")
            or "hybrid"
        )
        recall_mode = recall_raw if recall_raw in _VALID_RECALL_MODES else "hybrid"

        # Boolean fields: host wins, root fallback, then default
        def _bool(key: str, default: bool) -> bool:
            host_val = host_block.get(key)
            if host_val is not None:
                return bool(host_val)
            root_val = raw.get(key)
            if root_val is not None:
                return bool(root_val)
            return default

        return cls(
            host=host,
            api_key=api_key,
            user_id=host_block.get("userId") or raw.get("userId"),
            agent_id=host_block.get("agentId") or raw.get("agentId") or "hermes",
            enabled=enabled,
            memory_mode=host_block.get("memoryMode") or raw.get("memoryMode", "hybrid"),
            recall_mode=recall_mode,
            session_strategy=(
                host_block.get("sessionStrategy")
                or raw.get("sessionStrategy", "per-directory")
            ),
            rerank=_bool("rerank", True),
            keyword_search=_bool("keywordSearch", True),
            custom_instructions=(
                host_block.get("customInstructions")
                or raw.get("customInstructions")
            ),
        )


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_mem0_client: MemoryClient | None = None


def get_mem0_client(config: Mem0ClientConfig | None = None) -> MemoryClient:
    """Get or create the Mem0 MemoryClient singleton."""
    global _mem0_client

    if _mem0_client is not None:
        return _mem0_client

    if config is None:
        config = Mem0ClientConfig.from_global_config()

    if not config.api_key:
        raise ValueError(
            "Mem0 API key not found. "
            "Get your key at https://app.mem0.ai, "
            "then run 'hermes mem0 setup' or set MEM0_API_KEY."
        )

    try:
        from mem0 import MemoryClient
    except ImportError:
        raise ImportError(
            "mem0ai is required for Mem0 integration. "
            "Install it with: pip install mem0ai"
        )

    logger.info("Initializing Mem0 client (user: %s, agent: %s)",
                config.user_id, config.agent_id)

    _mem0_client = MemoryClient(api_key=config.api_key)
    return _mem0_client


def reset_mem0_client() -> None:
    """Reset the Mem0 client singleton (useful for testing)."""
    global _mem0_client
    _mem0_client = None
