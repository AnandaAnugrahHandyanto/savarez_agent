"""Shared fixtures for the 018 eval tests.

Each eval run is a fresh subprocess so AnchorStateManager state never
crosses runs in practice; the autouse reset is defensive and cheap.
"""

import importlib

import pytest


@pytest.fixture(autouse=True)
def _reset_anchor_state_if_present() -> None:
    """Reset anchor tracker if talaria's hash-anchored edit module is importable.

    When 018 runs against the talaria agent the AnchorStateManager singleton
    can carry per-task state across pytest invocations launched from the
    same process. We never want that here.
    """
    try:
        mod = importlib.import_module("talaria.tools._anchor_state")
    except ModuleNotFoundError:
        return None
    mgr = getattr(mod, "AnchorStateManager", None)
    if mgr is not None and hasattr(mgr, "reset"):
        mgr.reset()
    return None
