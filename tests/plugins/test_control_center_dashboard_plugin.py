"""Tests for the Control Center dashboard plugin backend."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_router():
    repo_root = Path(__file__).resolve().parents[2]
    plugin_file = (
        repo_root / "plugins" / "control-center" / "dashboard" / "plugin_api.py"
    )
    assert plugin_file.exists()
    spec = importlib.util.spec_from_file_location(
        "hermes_dashboard_plugin_control_center_test", plugin_file
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.router


@pytest.fixture
def client(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("WIKI_PATH", str(tmp_path / "wiki"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    app = FastAPI()
    app.include_router(_load_router(), prefix="/api/plugins/control-center")
    return TestClient(app)


def test_init_list_pages_and_read_meta(client):
    r = client.post(
        "/api/plugins/control-center/wikis/init",
        json={"domain": "AI research"},
    )
    assert r.status_code == 200, r.text
    wiki = r.json()["wiki"]
    assert wiki["initialized"] is True
    assert wiki["schema"] is True

    r = client.get("/api/plugins/control-center/wikis")
    assert r.status_code == 200
    assert any(w["path"] == wiki["path"] for w in r.json()["wikis"])

    r = client.get(
        "/api/plugins/control-center/wiki/page",
        params={"path": wiki["path"], "file": "index.md"},
    )
    assert r.status_code == 200
    assert "# Wiki Index" in r.json()["content"]


def test_write_page_rejects_path_traversal_and_lints(client):
    wiki = client.post(
        "/api/plugins/control-center/wikis/init",
        json={"domain": "AI research"},
    ).json()["wiki"]
    bad = client.put(
        "/api/plugins/control-center/wiki/page",
        params={"path": wiki["path"]},
        json={"path": "../escape.md", "content": "nope"},
    )
    assert bad.status_code == 400

    good = client.put(
        "/api/plugins/control-center/wiki/page",
        params={"path": wiki["path"]},
        json={
            "path": "concepts/test-page.md",
            "content": (
                "---\n"
                "title: Test Page\n"
                "created: 2026-01-01\n"
                "updated: 2026-01-01\n"
                "type: concept\n"
                "tags: [concept]\n"
                "sources: []\n"
                "---\n\n"
                "Links to [[missing-page]].\n"
            ),
        },
    )
    assert good.status_code == 200, good.text

    pages = client.get(
        "/api/plugins/control-center/wiki/pages",
        params={"path": wiki["path"], "q": "test"},
    ).json()["pages"]
    assert any(p["path"] == "concepts/test-page.md" for p in pages)

    lint = client.get(
        "/api/plugins/control-center/wiki/lint",
        params={"path": wiki["path"]},
    ).json()
    assert lint["counts"]["broken_links"] == 1


def test_prompt_library_crud_and_search(client):
    create = client.post(
        "/api/plugins/control-center/prompts",
        json={
            "command": "/synthesis",
            "name": "Grand Synthesis",
            "content": (
                "Integrate {{topic}} across systems thinking and information theory."
            ),
            "tags": ["research", "synthesis"],
        },
    )
    assert create.status_code == 200, create.text
    prompt = create.json()["prompt"]
    assert prompt["command"] == "/synthesis"
    assert prompt["name"] == "Grand Synthesis"

    listed = client.get(
        "/api/plugins/control-center/prompts",
        params={"q": "systems"},
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["prompts"][0]["id"] == prompt["id"]

    updated = client.put(
        f"/api/plugins/control-center/prompts/{prompt['id']}",
        json={"name": "Grand Synthesis v2", "tags": ["research"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["prompt"]["name"] == "Grand Synthesis v2"

    deleted = client.delete(f"/api/plugins/control-center/prompts/{prompt['id']}")
    assert deleted.status_code == 200, deleted.text
    assert client.get("/api/plugins/control-center/prompts").json()["total"] == 0


def test_imports_open_webui_prompts_from_sqlite(client, tmp_path, monkeypatch):
    data_dir = tmp_path / "open-webui" / "data"
    data_dir.mkdir(parents=True)
    db = data_dir / "webui.db"
    con = sqlite3.connect(db)
    con.execute(
        "create table prompt ("
        "id text primary key, command text, user_id text, name text, "
        "content text, data text, meta text, is_active integer, "
        "version_id text, tags text, created_at integer, updated_at integer"
        ")"
    )
    now = int(time.time())
    con.execute(
        "insert into prompt values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "owui-1",
            "/daily",
            "u1",
            "Daily Brief",
            "Summarize today's inputs.",
            "{}",
            "{}",
            1,
            None,
            json.dumps(["briefing"]),
            now,
            now,
        ),
    )
    con.commit()
    con.close()
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    preview = client.get("/api/plugins/control-center/prompts/open-webui")
    assert preview.status_code == 200, preview.text
    assert preview.json()["total"] == 1

    imported = client.post("/api/plugins/control-center/prompts/import-open-webui")
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported"] == 1

    listed = client.get(
        "/api/plugins/control-center/prompts",
        params={"q": "daily"},
    ).json()
    assert listed["total"] == 1
    assert listed["prompts"][0]["source"] == "open-webui"


def test_dashboard_bundle_registers_with_plugin_registry():
    repo_root = Path(__file__).resolve().parents[2]
    bundle = (
        repo_root / "plugins" / "control-center" / "dashboard" / "dist" / "index.js"
    )
    js = bundle.read_text(encoding="utf-8")
    assert 'window.__HERMES_PLUGINS__.register("control-center", ControlCenter)' in js
    assert "Projects Kanban" in js
    assert "LLM Wikis" in js
    assert "Prompt Library" in js
