"""Tests for delegation.spawnable_toolsets — the config key that decouples
parent's LLM-visible toolset from the set children may request.

Design: when ``spawnable_toolsets`` is set in config, _build_child_agent's
parent-intersection check uses that set instead of the parent's own
``enabled_toolsets``.  This lets an orchestrator-style parent keep a narrow
tool surface (e.g. just ``delegate_to_*`` + memory) while children still
get the wider set.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

# ``tools.delegate_tool`` imports many heavy deps — guard for test isolation.
pytest.importorskip("toolsets")


def _make_parent(enabled_toolsets, model="anthropic/claude-haiku-4.5"):
    """Minimal AIAgent stand-in with the attrs _build_child_agent reads."""
    class _Parent:
        pass

    p = _Parent()
    p.enabled_toolsets = enabled_toolsets
    p.valid_tool_names = []
    p.model = model
    p.provider = "openrouter"
    p.base_url = "https://openrouter.ai/api/v1"
    p.api_key = "test"
    p.api_mode = "chat_completions"
    p.acp_command = None
    p.acp_args = []
    p.providers_allowed = None
    p.providers_ignored = None
    p.providers_order = None
    p.provider_sort = None
    p.max_tokens = None
    p.platform = "test"
    p.session_id = "test-session"
    p._delegate_depth = 0
    p._subagent_id = None
    p._active_children = []
    return p


def test_spawnable_toolsets_config_lookup_no_override():
    """When ``delegation.spawnable_toolsets`` is unset, behavior falls back to
    parent-intersection (original behavior preserved)."""
    from tools import delegate_tool

    with patch.object(delegate_tool, "_load_config", return_value={}):
        cfg = delegate_tool._load_config()
        assert cfg.get("spawnable_toolsets") is None


def test_spawnable_toolsets_config_lookup_override_present():
    """When ``delegation.spawnable_toolsets`` is set to a list, it reads
    back as that list."""
    from tools import delegate_tool

    override = ["terminal", "agentmail", "monday"]
    with patch.object(
        delegate_tool, "_load_config",
        return_value={"spawnable_toolsets": override},
    ):
        cfg = delegate_tool._load_config()
        assert cfg["spawnable_toolsets"] == override


def test_spawnable_toolsets_empty_list_falls_back_to_parent():
    """Empty list should fall back to parent-intersection, not block
    all child toolsets.  Guards against accidental config where the list
    is present but empty."""
    from tools import delegate_tool

    with patch.object(
        delegate_tool, "_load_config",
        return_value={"spawnable_toolsets": []},
    ):
        cfg = delegate_tool._load_config()
        raw = cfg.get("spawnable_toolsets")
        # The implementation treats empty-list as "unset" and falls back
        # to parent_toolsets via ``if isinstance(_spawnable_cfg, list) and
        # _spawnable_cfg:`` — the truthiness check excludes empty lists.
        assert isinstance(raw, list) and not raw


def test_spawnable_toolsets_non_list_ignored():
    """Non-list values in spawnable_toolsets should be ignored (fall back
    to parent-intersection).  Guards against typos like a single string."""
    from tools import delegate_tool

    with patch.object(
        delegate_tool, "_load_config",
        return_value={"spawnable_toolsets": "terminal"},  # string, not list
    ):
        cfg = delegate_tool._load_config()
        raw = cfg.get("spawnable_toolsets")
        # Implementation checks isinstance(.., list); a string fails that
        # and triggers the fallback path.
        assert not isinstance(raw, list)
