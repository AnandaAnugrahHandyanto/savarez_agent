"""Tests for layered OpenClaw vendor sync helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MERGE_TOOLS = Path(__file__).resolve().parents[2] / "scripts" / "merge_tools"
if str(MERGE_TOOLS) not in sys.path:
    sys.path.insert(0, str(MERGE_TOOLS))

from openclaw_layered_sync import load_layers_config, overlay_relpaths  # noqa: E402


def test_layers_config_loads():
    path = MERGE_TOOLS / "openclaw_vendor_layers.json"
    cfg = load_layers_config(path)
    assert "hypura-harness" in cfg["extensions"]
    assert cfg["extensions"]["hypura-harness"]["base"] == "openclaw-sync"
    assert cfg["extensions"]["hypura-harness"]["overlay"] == "clawdbot-main"


def test_overlay_prefers_changed_python():
    base = {"scripts/a.py": "1", "README.md": "x"}
    overlay = {"scripts/a.py": "2", "scripts/new.py": "3", "README.md": "y"}
    rels = overlay_relpaths(
        "hypura-harness",
        base,
        overlay,
        overlay_paths=["scripts/new.py"],
        prefer_overlay_for_changed=["scripts/**/*.py"],
    )
    assert "scripts/a.py" in rels
    assert "scripts/new.py" in rels
    assert "README.md" not in rels
