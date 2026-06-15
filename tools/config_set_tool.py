#!/usr/bin/env python3
"""
config_set_tool.py — Whitelisted agent-accessible config editor for Hermes.

Addresses:
  #28024  Feature: Whitelisted config_set tool for agent self-configuration
  #42727  Bug: agent-led self-configuration can persist redacted credentials

Provides ``hermes_config_set`` tool that wraps ``hermes config set`` with:
  - Explicit whitelist of safe config keys agents may modify
  - Explicit blacklist of security/infrastructure keys agents must not touch
  - Credential-shape guard that blocks suspiciously-key-like values on the
    whitelist (lesson from #42727)
  - Audit log at ``~/.hermes/logs/config_changes.log``
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whitelist / Blacklist  (see #28024 for design rationale)
# ---------------------------------------------------------------------------

# Patterns allowed to be set by the agent.
# Each entry is a glob-friendly prefix checked against the dotted key path.
# Sub-keys under a prefix are implicitly allowed (e.g. "mcp_servers.*" allows
# "mcp_servers.context7.command").
WHITELIST_PREFIXES: list[str] = [
    # MCP servers (command, args, env values — non-credential only)
    "mcp_servers",
    # Speech-to-text
    "stt",
    # Text-to-speech
    "tts",
    # Display / UI
    "display",
    # Compression
    "compression",
    # Auxiliary model overrides (vision, compression, etc.) — except api_key
    "auxiliary",
    # Custom providers non-credential fields
    "custom_providers",
    # Context engine
    "context_engine",
    # Skills (skill directories, not security)
    "skills",
    # Platform display
    "platform_toolsets",
    # Webhook safe tools
    "webhook",
    # Session reset policy
    "session_reset",
]

# Sub-keys explicitly blocked even under a whitelisted prefix.
BLACKLIST_SUFFIXES: list[str] = [
    # Security approvals — agent must never weaken its own guardrails
    "approvals.mode",
    "approvals.require_approval_for",
    "approvals.auto_approve_patterns",
    # Security redaction / tirith
    "security.redact",
    "security.tirith",
    # Terminal backend (could brick agent connectivity)
    "terminal.backend",
    "terminal.cwd",
    # Delegation depth/concurrency (affects orchestration)
    "delegation.max_spawn_depth",
    "delegation.max_concurrent_children",
    # Model default (agent must not switch its own model)
    "model.default",
    "model.provider",
    "model.base_url",
    "model.api_key",
    # Main model api key env vars
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN",
]

# Credential-shaped values: any value matching these patterns is rejected
# on the whitelist (even if the key is whitelisted).  Prevents agent from
# persisting redacted placeholders (#42727) or injecting real secrets.
_CREDENTIAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"^sk-[A-Za-z0-9_-]{8,}"),              # OpenAI / Anthropic style
    re.compile(r"^ghp_[A-Za-z0-9]{20,}"),               # GitHub PAT
    re.compile(r"^\*\*\*"),                               # Redacted marker
    re.compile(r"^\[REDACTED\]"),                         # Explicit redacted
    re.compile(r"^[A-Za-z0-9_-]{32,}$"),                 # Long opaque token
    re.compile(r"^(xoxb-|xoxp-|xapp-)"),                 # Slack tokens
    re.compile(r"^bot\d+:"),                              # Telegram bot tokens
    re.compile(r"^[A-Za-z0-9]{24,}$"),                   # Generic long hex-ish
]


def _is_credential_shaped(value: str) -> bool:
    """Return True if *value* looks like it contains a credential."""
    v = value.strip()
    if not v:
        return False
    for pat in _CREDENTIAL_PATTERNS:
        if pat.search(v):
            return True
    return False


def _key_matches_any(key: str, patterns: list[str]) -> bool:
    """Return True if *key* equals or is a child of any pattern in *patterns*.

    Matching rules:
      - Exact match: "model.default" matches "model.default"
      - Prefix match: "mcp_servers.context7.command" matches "mcp_servers"
      - Wildcard segment: "custom_providers.0.api_key" matches "custom_providers"
    """
    key_lower = key.lower()
    for pat in patterns:
        pat_lower = pat.lower()
        if key_lower == pat_lower:
            return True
        # Prefix: "mcp_servers" matches "mcp_servers.anything.else"
        if key_lower.startswith(pat_lower + "."):
            return True
    return False


def _is_blacklisted(key: str) -> bool:
    """Return True if *key* falls under any blacklist rule.

    Uses prefix matching (same semantics as _is_whitelisted): a blacklist
    entry ``"approvals"`` blocks ``approvals``, ``approvals.mode``, and
    ``approvals.mode.auto_approve``.
    """
    key_lower = key.lower()
    for bl in BLACKLIST_SUFFIXES:
        bl_lower = bl.lower()
        if key_lower == bl_lower or key_lower.startswith(bl_lower + "."):
            return True
    return False


def _is_whitelisted(key: str) -> bool:
    """Return True if *key* is allowed by the whitelist."""
    for prefix in WHITELIST_PREFIXES:
        prefix_lower = prefix.lower()
        if key.lower().startswith(prefix_lower):
            return True
    return False


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _audit_log(key: str, old_value: str, new_value: str, session_id: Optional[str] = None):
    """Append a change record to the audit log."""
    try:
        log_dir = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "config_changes.log"
        ts = datetime.now(timezone.utc).isoformat()
        sid = session_id or os.environ.get("HERMES_SESSION_ID", "unknown")
        # Never log raw credential values
        safe_new = "***REDACTED***" if _is_credential_shaped(str(new_value)) else repr(new_value)
        safe_old = "***REDACTED***" if _is_credential_shaped(str(old_value)) else repr(old_value)
        entry = (
            f"[{ts}] session={sid}  key={key!r}  "
            f"old={safe_old}  new={safe_new}\n"
        )
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as exc:
        logger.warning("config_set audit log failed: %s", exc)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def config_set_value(key: str, value: str, *, session_id: Optional[str] = None) -> str:
    """Set a config value with whitelist/blacklist/credential guards.

    Returns a JSON result string.
    """
    from hermes_cli.config import get_config_path, set_config_value

    # 1. Blacklist check (takes precedence)
    if _is_blacklisted(key):
        return json.dumps({
            "error": f"Key '{key}' is blocked: security/infrastructure settings cannot "
                     f"be modified by the agent. Use `hermes config set {key} <value>` "
                     f"from the host terminal instead.",
            "blocked": True,
            "suggestion": f"hermes config set {key} <value>",
        }, ensure_ascii=False)

    # 2. Whitelist check
    if not _is_whitelisted(key):
        return json.dumps({
            "error": f"Key '{key}' is not in the agent-writable whitelist. "
                     f"Whitelisted prefixes: {WHITELIST_PREFIXES}. "
                     f"Use `hermes config set {key} <value>` from the host terminal.",
            "not_whitelisted": True,
            "whitelist": WHITELIST_PREFIXES,
        }, ensure_ascii=False)

    # 3. Credential-shape guard (even on whitelisted keys)
    if _is_credential_shaped(value):
        return json.dumps({
            "error": f"Value for '{key}' looks like a credential or redacted placeholder. "
                     f"Blocked to prevent #42727 (persisting redacted credentials). "
                     f"If you truly need to set this, use `hermes config set {key} <value>` "
                     f"from the host terminal.",
            "credential_blocked": True,
            "issue_ref": "#42727",
        }, ensure_ascii=False)

    # 4. Read old value for audit (best-effort)
    old_value = "N/A"
    try:
        config_path = get_config_path()
        if config_path.exists():
            import yaml as _yaml
            with open(config_path, encoding="utf-8") as f:
                cfg = _yaml.safe_load(f) or {}
            # Walk dotted key
            parts = key.split(".")
            node = cfg
            for p in parts:
                if isinstance(node, dict) and p in node:
                    node = node[p]
                else:
                    node = None
                    break
            if node is not None:
                old_value = str(node)
    except Exception:
        pass

    # 5. Delegate to hermes config set
    try:
        set_config_value(key, value)
    except Exception as exc:
        return json.dumps({"error": f"Failed to set {key}: {exc}"}, ensure_ascii=False)

    # 6. Audit
    _audit_log(key, old_value, value, session_id=session_id)

    return json.dumps({
        "success": True,
        "key": key,
        "message": f"✓ Set {key} = {value}. "
                   f"Note: changes take effect on next gateway restart (`hermes gateway restart`).",
        "requires_restart": True,
        "audit_logged": True,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool schema + handler
# ---------------------------------------------------------------------------

CONFIG_SET_TOOL_SCHEMA = {
    "name": "hermes_config_set",
    "description": (
        "Set a Hermes configuration value from within the agent session. "
        "Only whitelisted keys are accepted (mcp_servers, stt, tts, display, "
        "compression, auxiliary, custom_providers, context_engine, skills, "
        "session_reset, platform_toolsets, webhook). "
        "Security-sensitive keys (approvals, security, terminal.backend, "
        "model.default/provider/api_key) are blocked. "
        "Credential-shaped values are also blocked to prevent persisting "
        "redacted placeholders (see #42727). "
        "Changes are audit-logged and require a gateway restart to take effect."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": (
                    "Configuration key in dotted notation (e.g. "
                    "'mcp_servers.context7.command', 'stt.enabled', 'display.skin')."
                ),
            },
            "value": {
                "type": "string",
                "description": (
                    "Value to set. Booleans: 'true'/'false'. "
                    "Numbers: plain digits. Strings: unquoted."
                ),
            },
        },
        "required": ["key", "value"],
    },
}


def _config_set_handler(args: dict, **kw) -> str:
    key = args.get("key", "")
    value = args.get("value", "")
    session_id = kw.get("session_id")
    return config_set_value(key, value, session_id=session_id)


def check_config_set_available() -> bool:
    """config_set tool is always available (no external deps)."""
    return True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

from tools.registry import registry, tool_error  # noqa: E402

registry.register(
    name="hermes_config_set",
    toolset="config",
    schema=CONFIG_SET_TOOL_SCHEMA,
    handler=_config_set_handler,
    check_fn=check_config_set_available,
    description="Whitelisted agent-accessible config editor with audit log",
    emoji="⚙️",
)
