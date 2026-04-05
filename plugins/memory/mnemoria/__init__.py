"""Mnemoria — local-first markdown-native memory plugin for hermes-agent.

This plugin wraps the ``mnemoria`` npm package as a pluggable MemoryProvider,
giving the agent persistent, git-friendly memory stored as plain markdown files
in a vault directory.

Architecture
------------
Mnemoria uses a four-layer stack:

  Layer 4: MCP Server (14 tools, 5 resources) — any agent talks to this
  Layer 3: Three-Signal Retrieval Engine      — semantic + keyword + graph
  Layer 2: Knowledge Graph + Vitality Model   — wiki-links, ACT-R decay,
                                                spreading activation
  Layer 1: Markdown files on disk             — git-friendly, portable

Three vault spaces with different decay rates:

  self/   (0.1x decay)  — who the agent IS (identity, goals, personality)
  notes/  (1.0x decay)  — what the agent KNOWS (ideas, decisions, learnings)
  ops/    (3.0x decay)  — what the agent is DOING (tasks, session state)

Quick start
-----------
  npm install -g mnemoria
  mnemoria init ~/.hermes/mnemoria-vault
  mnemoria health

Then configure hermes-agent (config.yaml)::

  plugins:
    mnemoria:
      vault: ~/.hermes/mnemoria-vault
      llm_provider: anthropic
      llm_model: claude-haiku-4-5
      llm_api_key_env: ANTHROPIC_API_KEY

Or via environment variables::

  export MNEMORIA_VAULT=~/.hermes/mnemoria-vault
  export MNEMORIA_LLM_PROVIDER=anthropic
  export MNEMORIA_LLM_MODEL=claude-haiku-4-5
  export ANTHROPIC_API_KEY=sk-ant-...

Benchmark adapter
-----------------
The benchmark adapter is at ``benchmarks/backends/mnemoria_adapter.py``.
It exercises the real mnemoria CLI via subprocess calls::

  python -m benchmarks --backend mnemoria --suite suite_a

Availability check
------------------
The provider checks for the ``mnemoria`` binary at import time.  If the npm
package is not installed, ``is_available()`` returns ``False`` and the runner
falls back gracefully.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability guard — checked before importing heavier dependencies
# ---------------------------------------------------------------------------

_MNEMORIA_FALLBACK_PATHS: tuple[Path, ...] = (
    Path.home() / ".npm-global" / "bin" / "mnemoria",
    Path.home() / ".local" / "share" / "npm" / "bin" / "mnemoria",
    Path("/usr/local/bin/mnemoria"),
    Path("/usr/bin/mnemoria"),
)


def _find_mnemoria_binary() -> Optional[str]:
    """Return the path to the mnemoria binary, or None if not found."""
    on_path = shutil.which("mnemoria")
    if on_path:
        return on_path
    for candidate in _MNEMORIA_FALLBACK_PATHS:
        if candidate.is_file() and shutil.os.access(candidate, shutil.os.X_OK):
            return str(candidate)
    # Respect an explicit override set by config / env
    override = os.environ.get("MNEMORIA_BIN", "").strip()
    if override:
        p = Path(override)
        if p.is_file():
            return str(p)
    return None


# ---------------------------------------------------------------------------
# Plugin provider
# ---------------------------------------------------------------------------

try:
    from agent.memory_provider import MemoryProvider as _MemoryProvider
    _HAS_MEMORY_PROVIDER = True
except ImportError:
    # Running outside hermes-agent (e.g. during benchmarks or unit tests)
    _HAS_MEMORY_PROVIDER = False
    _MemoryProvider = object  # type: ignore[misc,assignment]


class MnemoriaMemoryProvider(_MemoryProvider):
    """Hermes-agent MemoryProvider backed by the mnemoria npm package.

    Wraps the ``mnemoria`` CLI via subprocess calls.  The MCP server mode
    (``mnemoria serve --mcp``) is used for the tool-call interface, while
    direct CLI commands are used for system-prompt pre-fetching.

    If the ``mnemoria`` binary is not installed this provider reports itself
    as unavailable and hermes-agent will skip it silently.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._binary: Optional[str] = _find_mnemoria_binary()
        self._vault: Optional[Path] = None
        self._proc: Optional[subprocess.Popen] = None  # MCP server process

    # ------------------------------------------------------------------
    # MemoryProvider identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "mnemoria"

    def is_available(self) -> bool:
        """Return True only if the mnemoria binary is reachable."""
        if self._binary is None:
            self._binary = _find_mnemoria_binary()
        return self._binary is not None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "vault",
                "description": "Path to the Mnemoria vault directory",
                "default": str(Path.home() / ".hermes" / "mnemoria-vault"),
            },
            {
                "key": "llm_provider",
                "description": "LLM provider for auto-promotion (anthropic, openai, …)",
                "default": "",
            },
            {
                "key": "llm_model",
                "description": "LLM model name (e.g. claude-haiku-4-5)",
                "default": "",
            },
            {
                "key": "llm_api_key_env",
                "description": "Env-var name that holds the LLM API key",
                "default": "",
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: Any) -> None:
        """Persist config values into config.yaml under plugins.mnemoria."""
        config_path = Path(str(hermes_home)) / "config.yaml"
        try:
            import yaml  # type: ignore[import]
            existing: Dict[str, Any] = {}
            if config_path.exists():
                with open(config_path) as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["mnemoria"] = values
            with open(config_path, "w") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception as exc:
            logger.warning("Could not save mnemoria config: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        """Set up the vault and ensure it is initialised."""
        if not self.is_available():
            logger.warning(
                "Mnemoria binary not found; provider is disabled for this session."
            )
            return

        vault_str = (
            self._config.get("vault")
            or os.environ.get("MNEMORIA_VAULT", "")
            or str(Path.home() / ".hermes" / "mnemoria-vault")
        )
        self._vault = Path(vault_str).expanduser()
        self._vault.mkdir(parents=True, exist_ok=True)

        # Init vault if not already initialised (idempotent)
        if not (self._vault / ".mnemoria").exists():
            try:
                subprocess.run(
                    [self._binary, "--vault", str(self._vault), "init", str(self._vault)],
                    timeout=60,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("Mnemoria vault initialised at %s", self._vault)
            except subprocess.CalledProcessError as exc:
                logger.error("mnemoria init failed: %s", exc.stderr)
            except subprocess.TimeoutExpired:
                logger.error("mnemoria init timed out (vault=%s)", self._vault)

        self._session_id = session_id

    def shutdown(self) -> None:
        """Terminate the MCP server process if one was started."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None

    # ------------------------------------------------------------------
    # MemoryProvider hooks
    # ------------------------------------------------------------------

    def system_prompt_block(self) -> str:
        """Return a short status block for the system prompt."""
        if not self.is_available() or self._vault is None:
            return ""
        vault_exists = self._vault.is_dir()
        if not vault_exists:
            return ""
        # Count markdown notes as a rough measure of vault size
        try:
            note_count = len(list(self._vault.rglob("*.md")))
        except Exception:
            note_count = 0
        if note_count == 0:
            return (
                "# Mnemoria Memory\n"
                "Active. Empty vault — capture thoughts with mnemoria_add."
            )
        return (
            f"# Mnemoria Memory\n"
            f"Active. {note_count} notes stored across self/, notes/, ops/.\n"
            f"Use mnemoria_query_ranked to retrieve relevant context."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Run a ranked query and return formatted results for context injection."""
        if not self.is_available() or self._vault is None or not query:
            return ""
        try:
            result = subprocess.run(
                [
                    self._binary,
                    "--vault", str(self._vault),
                    "query", "ranked", query,
                    "--limit", "5",
                ],
                timeout=15,
                capture_output=True,
                text=True,
            )
            raw = result.stdout.strip()
            if not raw:
                return ""
            # Parse JSON array if possible
            if raw.startswith("["):
                try:
                    import json
                    items = json.loads(raw)
                    lines = []
                    for item in items[:5]:
                        if isinstance(item, dict):
                            content = item.get("content") or item.get("title") or ""
                            score = item.get("score", "")
                            score_str = f" [{score:.2f}]" if isinstance(score, float) else ""
                            if content:
                                lines.append(f"- {content.strip()}{score_str}")
                        elif isinstance(item, str):
                            lines.append(f"- {item.strip()}")
                    if lines:
                        return "## Mnemoria Memory\n" + "\n".join(lines)
                except Exception:
                    pass
            # Plain-text fallback
            lines = [f"- {ln.strip()}" for ln in raw.splitlines() if ln.strip()]
            if lines:
                return "## Mnemoria Memory\n" + "\n".join(lines[:5])
        except Exception as exc:
            logger.debug("Mnemoria prefetch error: %s", exc)
        return ""

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
    ) -> None:
        """No-op — Mnemoria uses explicit add calls for memory capture."""
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return MCP-compatible tool schemas for mnemoria_add and mnemoria_query_ranked."""
        return [
            {
                "name": "mnemoria_add",
                "description": (
                    "Capture a note or fact into the Mnemoria vault. "
                    "Use for decisions, learnings, preferences, and any knowledge "
                    "the agent should remember across sessions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The text to remember.",
                        },
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "mnemoria_query_ranked",
                "description": (
                    "Retrieve memories relevant to a query using three-signal ranked search "
                    "(semantic + keyword + graph). Returns the top matching notes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language search string.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 10).",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
        ]

    def handle_tool_call(
        self, tool_name: str, args: Dict[str, Any], **kwargs: Any
    ) -> str:
        """Execute a mnemoria tool call and return the result as a string."""
        import json as _json

        if tool_name == "mnemoria_add":
            return self._tool_add(args)
        elif tool_name == "mnemoria_query_ranked":
            return self._tool_query_ranked(args)
        return _json.dumps({"error": f"Unknown tool: {tool_name}"})

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """No-op — vault persistence is automatic."""
        pass

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_add(self, args: Dict[str, Any]) -> str:
        import json as _json

        content = args.get("content", "").strip()
        if not content:
            return _json.dumps({"error": "content is required"})
        if not self.is_available() or self._vault is None:
            return _json.dumps({"error": "mnemoria is not available"})
        try:
            subprocess.run(
                [self._binary, "--vault", str(self._vault), "add", content],
                timeout=60,
                check=True,
                capture_output=True,
                text=True,
            )
            return _json.dumps({"status": "added"})
        except subprocess.CalledProcessError as exc:
            return _json.dumps({"error": exc.stderr or str(exc)})
        except subprocess.TimeoutExpired:
            return _json.dumps({"error": "mnemoria add timed out"})

    def _tool_query_ranked(self, args: Dict[str, Any]) -> str:
        import json as _json

        query = args.get("query", "").strip()
        if not query:
            return _json.dumps({"error": "query is required"})
        limit = int(args.get("limit", 10))
        if not self.is_available() or self._vault is None:
            return _json.dumps({"error": "mnemoria is not available"})
        try:
            result = subprocess.run(
                [
                    self._binary,
                    "--vault", str(self._vault),
                    "query", "ranked", query,
                    "--limit", str(limit),
                ],
                timeout=30,
                check=False,
                capture_output=True,
                text=True,
            )
            raw = result.stdout.strip()
            # Return raw JSON if valid, otherwise wrap in a results object
            if raw.startswith("[") or raw.startswith("{"):
                try:
                    _json.loads(raw)  # validate
                    return raw
                except _json.JSONDecodeError:
                    pass
            return _json.dumps({"results": raw.splitlines() if raw else []})
        except subprocess.TimeoutExpired:
            return _json.dumps({"error": "mnemoria query timed out"})
        except Exception as exc:
            return _json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Plugin entry point (called by hermes-agent plugin loader)
# ---------------------------------------------------------------------------

def register(ctx: Any) -> None:  # type: ignore[type-arg]
    """Register the Mnemoria memory provider with the plugin system."""
    # Load plugin-level config from config.yaml if available
    config: Dict[str, Any] = {}
    try:
        from hermes_constants import get_hermes_home  # type: ignore[import]
        import yaml  # type: ignore[import]
        config_path = get_hermes_home() / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                all_config = yaml.safe_load(f) or {}
            config = all_config.get("plugins", {}).get("mnemoria", {}) or {}
    except Exception:
        pass

    provider = MnemoriaMemoryProvider(config=config)
    if not provider.is_available():
        logger.warning(
            "Mnemoria plugin: binary not found, skipping registration. "
            "Install with: npm install -g mnemoria"
        )
        return
    ctx.register_memory_provider(provider)


__all__ = ["MnemoriaMemoryProvider", "register"]
