#!/usr/bin/env python3
"""Shared path resolution for Obsidian and the persistent markdown wiki."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional


LEGACY_WIKI_ROOT = Path(os.path.expanduser("~/hermes-kb"))


def _load_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if config is not None:
        return config

    try:
        from hermes_cli.config import load_config

        return load_config()
    except Exception:
        return {}


def _knowledge_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _load_config(config).get("knowledge", {})


def resolve_agent_prefix(config: Optional[Dict[str, Any]] = None) -> str:
    return _knowledge_config(config).get("agent_prefix", "Hermes")


def resolve_obsidian_vault_path(config: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    kn_config = _knowledge_config(config)
    candidate = os.environ.get("OBSIDIAN_VAULT_PATH") or kn_config.get("vault_path")
    if not candidate:
        return None
    return Path(os.path.expanduser(candidate))


def resolve_llm_wiki_path(config: Optional[Dict[str, Any]] = None) -> Path:
    """Resolve the root directory for the persistent markdown wiki.

    Resolution order:
    1. `LLM_WIKI_PATH`
    2. `knowledge.wiki_path` in config
    3. Legacy `~/hermes-kb` if it already exists
    4. Obsidian-integrated path: `<vault>/<agent_prefix>/Wiki`
    5. Fallback legacy root `~/hermes-kb`
    """

    kn_config = _knowledge_config(config)
    explicit = os.environ.get("LLM_WIKI_PATH") or kn_config.get("wiki_path")
    if explicit:
        return Path(os.path.expanduser(explicit))

    if LEGACY_WIKI_ROOT.exists():
        return LEGACY_WIKI_ROOT

    vault_path = resolve_obsidian_vault_path(config)
    if vault_path:
        return vault_path / resolve_agent_prefix(config) / "Wiki"

    return LEGACY_WIKI_ROOT
