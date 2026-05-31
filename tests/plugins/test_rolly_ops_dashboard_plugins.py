"""Rolly ops dashboard tabs.

Source-backed backlog: Rolly wants Hermes dashboard tabs for Kanban,
People, Loops, and Workbench. Kanban ships as its own plugin; these tests
lock the companion Rolly ops tabs into the bundled plugin surface.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "plugins"


def _manifest(plugin: str) -> dict:
    path = PLUGINS / plugin / "dashboard" / "manifest.json"
    assert path.exists(), f"missing manifest for {plugin}"
    return json.loads(path.read_text())


def test_rolly_ops_dashboard_tabs_are_registered_after_kanban():
    expected = {
        "kanban": ("Kanban", "/kanban", "after:skills"),
        "rolly-people": ("People", "/people", "after:kanban"),
        "rolly-loops": ("Loops", "/loops", "after:people"),
        "rolly-workbench": ("Workbench", "/workbench", "after:loops"),
    }

    for plugin, (label, path, position) in expected.items():
        manifest = _manifest(plugin)
        assert manifest["label"] == label
        assert manifest["tab"]["path"] == path
        assert manifest["tab"]["position"] == position
        assert manifest["entry"] == "dist/index.js"


def test_rolly_ops_tabs_surface_activity_and_visibility_language():
    for plugin in ("rolly-people", "rolly-loops", "rolly-workbench"):
        bundle = PLUGINS / plugin / "dashboard" / "dist" / "index.js"
        assert bundle.exists(), f"missing dashboard bundle for {plugin}"
        text = bundle.read_text()
        assert "Activity" in text
        assert "Visibility" in text
        assert "Rolly" in text
