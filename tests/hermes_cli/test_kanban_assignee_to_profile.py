"""Tests for D1 Task 2 — assignee_to_profile resolution (swarm-as-persona)."""
from __future__ import annotations

from unittest.mock import patch
import pytest


# ============================================================================
# _load_assignee_map
# ============================================================================

def test_load_assignee_map_default_is_swarm_worker(monkeypatch):
    """No config key → default {'*': 'worker'} (swarm-as-persona default)."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {}},
    )
    m = kanban_db._load_assignee_map()
    assert m == {"*": "worker"}


def test_load_assignee_map_empty_dict_is_swarm_default(monkeypatch):
    """Empty assignee_to_profile dict still yields the swarm default."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {"assignee_to_profile": {}}},
    )
    m = kanban_db._load_assignee_map()
    assert m == {"*": "worker"}


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
    """If load_config raises, return the swarm default — don't crash workers."""
    from hermes_cli import kanban_db

    def _raise(*a, **kw):
        raise RuntimeError("config broken")

    monkeypatch.setattr("hermes_cli.config.load_config", _raise)
    m = kanban_db._load_assignee_map()
    assert m == {"*": "worker"}


def test_load_assignee_map_returns_default_for_invalid_type(monkeypatch):
    """If kanban.assignee_to_profile is not a dict, fall back to default."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"kanban": {"assignee_to_profile": "not-a-dict"}},
    )
    m = kanban_db._load_assignee_map()
    assert m == {"*": "worker"}


# ============================================================================
# _resolve_assignee_to_profile
# ============================================================================

def test_resolve_default_collapses_to_worker(monkeypatch):
    """With default map, every assignee tag → 'worker'."""
    from hermes_cli import kanban_db

    monkeypatch.setattr(kanban_db, "_load_assignee_map", lambda: {"*": "worker"})
    assert kanban_db._resolve_assignee_to_profile("researcher") == "worker"
    assert kanban_db._resolve_assignee_to_profile("analyst") == "worker"
    assert kanban_db._resolve_assignee_to_profile("anything-else") == "worker"


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
