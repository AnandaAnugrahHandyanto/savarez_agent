from __future__ import annotations

import importlib
import sys
import types

import pytest


def test_search_hard_fails_when_vector_core_search_helpers_are_too_old(monkeypatch):
    """LLM Wiki has a hard vector-core dependency.

    Missing generic search helpers mean the installed vector-core is too old and
    should be upgraded, rather than silently falling back to duplicated LLM Wiki
    implementations.
    """

    fake_vector_core = types.ModuleType("vector_core")
    fake_search = types.ModuleType("vector_core.search")
    monkeypatch.setitem(sys.modules, "vector_core", fake_vector_core)
    monkeypatch.setitem(sys.modules, "vector_core.search", fake_search)
    sys.modules.pop("hermes_wiki.search", None)

    with pytest.raises(ImportError):
        importlib.import_module("hermes_wiki.search")
