"""Tests for the Projects + Ideas dashboard plugin backend."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_plugin_module():
    repo_root = Path(__file__).resolve().parents[2]
    plugin_file = repo_root / "plugins" / "projects-ideas" / "dashboard" / "plugin_api.py"
    assert plugin_file.exists(), f"plugin file missing: {plugin_file}"

    spec = importlib.util.spec_from_file_location(
        "hermes_dashboard_plugin_projects_ideas_test", plugin_file,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_snapshot_contains_required_portfolio_sections(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    memory = home / "memory"
    vault = home / "vault"
    memory.mkdir(parents=True)
    vault.mkdir(parents=True)
    (memory / "ideas-backlog.md").write_text("""
# Ideas backlog

## Kids sports highlight reel service
Use AI to package clips for families.

- Parking lot: old marketplace flipping variant
""", encoding="utf-8")
    (vault / "working-context.md").write_text("""
# Working context

## Church Portal
Next action is to decide whether this belongs in Life Church Hub.
""", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)

    mod = _load_plugin_module()
    data = mod.build_snapshot(include_linear=False)

    assert data["title"] == "Ryan Projects + Ideas"
    for section in ["Active", "Waiting/Blocked", "Paused", "Ideas", "Archived / Parking Lot", "Standing Lanes"]:
        assert section in data["sections"]
        assert section in data["counts"]

    names = {card["name"] for card in data["cards"]}
    assert "Life Church Hub" in names
    assert "Linear cleanup / agent ops" in names
    assert "Kids sports highlight reel service" in names
    assert "Church Portal" in names

    # The plugin should expose concise card summaries, not raw note dumps.
    idea = next(card for card in data["cards"] if card["name"] == "Kids sports highlight reel service")
    assert idea["kind"] == "idea"
    assert idea["next_action"]
    assert len(idea["summary"]) < 220


def test_snapshot_endpoint_and_refresh_endpoint(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    (home / "memory").mkdir(parents=True)
    (home / "memory" / "ideas-backlog.md").write_text("- Community volunteer matching tool\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)

    mod = _load_plugin_module()
    app = FastAPI()
    app.include_router(mod.router, prefix="/api/plugins/projects-ideas")
    client = TestClient(app)

    r = client.get("/api/plugins/projects-ideas/snapshot")
    assert r.status_code == 200
    data = r.json()
    assert any(card["name"] == "Community volunteer matching tool" for card in data["cards"])

    r = client.post("/api/plugins/projects-ideas/refresh")
    assert r.status_code == 200
    refreshed = r.json()
    assert refreshed["version"] == data["version"]
    assert refreshed["cards"]
