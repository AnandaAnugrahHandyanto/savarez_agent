"""Shared fixtures for the enhanced-memory-plugin test suite.

This conftest configures imports so that plugin modules can be loaded
both as a standalone package and within the Hermes Agent tree.
"""
from __future__ import annotations

import sys
import os

# Add plugin root and hermes-agent to sys.path so imports work
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HERMES_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_PLUGIN_ROOT))))
for p in (_PLUGIN_ROOT, _HERMES_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from store import EnhancedMemoryStore
from condenser import FactCondenser


@pytest.fixture
def db_path(tmp_path):
    """Return a path to a temporary database file."""
    return str(tmp_path / "test_memory.db")


@pytest.fixture
def store(db_path):
    """Create a fresh EnhancedMemoryStore backed by a temp database."""
    s = EnhancedMemoryStore(db_path=db_path)
    yield s
    s.close()


@pytest.fixture
def condenser(store):
    """Create a FactCondenser bound to the temp store."""
    return FactCondenser(store)


@pytest.fixture
def populated_store(store):
    """Store pre-populated with a handful of raw facts across categories."""
    facts = [
        {"content": "User prefers dark mode in all editors", "category": "user_pref"},
        {"content": "User always uses vim keybindings", "category": "user_pref"},
        {"content": "The project uses Python 3.12", "category": "project"},
        {"content": "Server runs Ubuntu 22.04 LTS", "category": "env"},
        {"content": "API key stored in vault", "category": "security"},
        {"content": "We decided to use PostgreSQL", "category": "decision"},
        {"content": "Linting uses ruff with strict config", "category": "tool"},
        {"content": "General note about meeting schedule", "category": "general"},
    ]
    store.add_raw_facts_batch(facts)
    return store
