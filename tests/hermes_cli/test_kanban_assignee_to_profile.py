"""Tests for D1 Task 2 — assignee_to_profile resolution (swarm-as-persona)."""
from __future__ import annotations

from unittest.mock import patch
import pytest


# ============================================================================
# _load_assignee_map
# ============================================================================

def test_load_assignee_map_default_is_empty(monkeypatch):
    """No config key → default {} (identity passthrough — Phase-8 P0 fix).

    The original D1 Task 2 default was {"*": "worker"}, but that broke
    existing installs that don't have a 'worker' profile on disk. The
    safe default is identity passthrough; operators opt-in to swarm
    collapse by setting the wildcard explicitly.
    """
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {}},
    )
    m = kanban_db._load_assignee_map()
    assert m == {}


def test_load_assignee_map_empty_dict_is_empty(monkeypatch):
    """Empty assignee_to_profile dict → empty map (identity passthrough)."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {"assignee_to_profile": {}}},
    )
    m = kanban_db._load_assignee_map()
    assert m == {}


def test_load_assignee_map_honors_user_overrides(monkeypatch):
    """User-set map is respected verbatim."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {
            "kanban": {
                "assignee_to_profile": {
                    "*": "worker",
                    "ops": "ops-special",
                    "researcher": "deep-thinker",
                }
            }
        },
    )
    m = kanban_db._load_assignee_map()
    assert m["*"] == "worker"
    assert m["ops"] == "ops-special"
    assert m["researcher"] == "deep-thinker"


def test_load_assignee_map_normalizes_str_types(monkeypatch):
    """Non-string keys/values get coerced to str."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {"assignee_to_profile": {1: 2, "*": "worker"}}},
    )
    m = kanban_db._load_assignee_map()
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in m.items())


def test_load_assignee_map_returns_default_on_config_error(monkeypatch):
    """If load_config raises, return the safe default ({}) — don't crash workers."""
    from hermes_cli import kanban_db

    def _raise(*a, **kw):
        raise RuntimeError("config broken")

    monkeypatch.setattr("hermes_cli.config.load_config", _raise)
    m = kanban_db._load_assignee_map()
    assert m == {}


def test_load_assignee_map_returns_default_for_invalid_type(monkeypatch):
    """If kanban.assignee_to_profile is not a dict, fall back to {}."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {"assignee_to_profile": "not-a-dict"}},
    )
    m = kanban_db._load_assignee_map()
    assert m == {}


def test_load_assignee_map_drops_none_values(monkeypatch):
    """Phase-8 P1 fix: None values in map are skipped (would produce
    'hermes -p None' argv otherwise)."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {"assignee_to_profile": {"*": "worker", "ops": None}}},
    )
    m = kanban_db._load_assignee_map()
    assert m == {"*": "worker"}
    assert "ops" not in m


def test_resolve_default_is_identity(monkeypatch):
    """With no config, every assignee passes through unchanged (Phase-8 P0 fix)."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(kanban_db, "_load_assignee_map", lambda: {})
    assert kanban_db._resolve_assignee_to_profile("researcher") == "researcher"
    assert kanban_db._resolve_assignee_to_profile("analyst") == "analyst"
    assert kanban_db._resolve_assignee_to_profile("worker") == "worker"


def test_resolve_swarm_collapse_when_wildcard_explicitly_set(monkeypatch):
    """When operator opts in by setting '*': 'worker', all tags collapse."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(kanban_db, "_load_assignee_map", lambda: {"*": "worker"})
    assert kanban_db._resolve_assignee_to_profile("researcher") == "worker"
    assert kanban_db._resolve_assignee_to_profile("analyst") == "worker"


def test_resolve_explicit_override_wins(monkeypatch):
    """Explicit map entry overrides the wildcard."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        kanban_db, "_load_assignee_map",
        lambda: {"*": "worker", "ops": "ops-special"},
    )
    assert kanban_db._resolve_assignee_to_profile("ops") == "ops-special"
    # Other tags still hit the wildcard
    assert kanban_db._resolve_assignee_to_profile("coder") == "worker"


def test_resolve_no_wildcard_falls_back_to_identity(monkeypatch):
    """If user removes wildcard, unknown assignees pass through verbatim
    (preserves pre-D1 behavior for explicit single-profile setups)."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        kanban_db, "_load_assignee_map",
        lambda: {"ops": "ops-special"},
    )
    # 'ops' resolves; 'unknown-tag' falls through unchanged
    assert kanban_db._resolve_assignee_to_profile("ops") == "ops-special"
    assert kanban_db._resolve_assignee_to_profile("unknown-tag") == "unknown-tag"


def test_resolve_is_deterministic(monkeypatch):
    from hermes_cli import kanban_db

    monkeypatch.setattr(kanban_db, "_load_assignee_map", lambda: {"*": "worker"})
    a = kanban_db._resolve_assignee_to_profile("xyz")
    b = kanban_db._resolve_assignee_to_profile("xyz")
    assert a == b == "worker"
