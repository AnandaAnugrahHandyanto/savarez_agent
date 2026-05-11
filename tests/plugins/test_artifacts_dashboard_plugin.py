"""Tests for the Artifacts dashboard plugin MVP.

The plugin mounts as /api/plugins/artifacts/ inside the dashboard. These tests
attach the router to a bare FastAPI app and use an isolated HERMES_HOME so the
artifact store can be exercised without running the full dashboard.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_FILE = REPO_ROOT / "plugins" / "artifacts" / "dashboard" / "plugin_api.py"
STORE_FILE = REPO_ROOT / "plugins" / "artifacts" / "store.py"
BUNDLE_FILE = REPO_ROOT / "plugins" / "artifacts" / "dashboard" / "dist" / "index.js"
MANIFEST_FILE = REPO_ROOT / "plugins" / "artifacts" / "dashboard" / "manifest.json"


def _load_module(name: str, path: Path):
    assert path.exists(), f"missing module: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_plugin_router():
    return _load_module("hermes_dashboard_plugin_artifacts_test", PLUGIN_FILE).router


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return home


@pytest.fixture
def artifact_root(hermes_home):
    root = hermes_home / "artifacts"
    root.mkdir()
    return root


def write_artifact(
    root: Path,
    artifact_id: str = "hello-card",
    *,
    version: int = 1,
    title: str = "Hello Card",
    content_type: str = "text/html",
    entrypoint: str = "index.html",
    body: str = "<html><body>Hello artifact</body></html>",
):
    version_dir = root / artifact_id / "versions" / str(version)
    version_dir.mkdir(parents=True)
    (version_dir / entrypoint).write_text(body, encoding="utf-8")
    manifest = {
        "id": artifact_id,
        "title": title,
        "description": "Fixture artifact",
        "contentType": content_type,
        "latestVersion": version,
        "createdAt": "2026-05-10T12:00:00Z",
        "updatedAt": "2026-05-10T12:00:00Z",
        "versions": [
            {
                "version": version,
                "entrypoint": entrypoint,
                "contentType": content_type,
                "createdAt": "2026-05-10T12:00:00Z",
            }
        ],
    }
    (root / artifact_id / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


@pytest.fixture
def client(artifact_root):
    app = FastAPI()
    app.include_router(_load_plugin_router(), prefix="/api/plugins/artifacts")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Store/API happy path
# ---------------------------------------------------------------------------


def test_store_lists_manifests_from_controlled_hermes_root(artifact_root):
    write_artifact(artifact_root, "hello-card")
    store = _load_module("hermes_artifacts_store_test", STORE_FILE)

    artifacts = store.list_artifacts()

    assert [a["id"] for a in artifacts] == ["hello-card"]
    assert artifacts[0]["title"] == "Hello Card"
    assert artifacts[0]["latestVersion"] == 1
    assert artifacts[0]["previewUrl"] == "/api/plugins/artifacts/preview/hello-card/versions/1/index.html"


def test_api_lists_artifacts_and_serves_preview(client, artifact_root):
    write_artifact(artifact_root, "hello-card")

    listing = client.get("/api/plugins/artifacts/list")
    assert listing.status_code == 200, listing.text
    assert listing.json()["artifacts"][0]["id"] == "hello-card"

    preview = client.get("/api/plugins/artifacts/preview/hello-card/versions/1/index.html")
    assert preview.status_code == 200, preview.text
    assert "Hello artifact" in preview.text
    assert preview.headers["content-type"].startswith("text/html")
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in preview.headers["content-security-policy"]


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_path",
    [
        "../manifest.json",
        "..%2Fmanifest.json",
        "%2e%2e/manifest.json",
        "/etc/passwd",
        "assets/../../manifest.json",
        "assets\\..\\..\\manifest.json",
    ],
)
def test_preview_rejects_traversal_and_absolute_paths(client, artifact_root, bad_path):
    write_artifact(artifact_root, "hello-card")

    r = client.get(f"/api/plugins/artifacts/preview/hello-card/versions/1/{bad_path}")

    assert r.status_code in {400, 404, 422}
    assert "Hello artifact" not in r.text


def test_preview_rejects_symlink_escape(client, artifact_root, tmp_path):
    write_artifact(artifact_root, "hello-card")
    outside_secret = tmp_path / "outside.env"
    outside_secret.write_text("TOKEN=do-not-serve", encoding="utf-8")
    link = artifact_root / "hello-card" / "versions" / "1" / "leak.env"
    link.symlink_to(outside_secret)

    r = client.get("/api/plugins/artifacts/preview/hello-card/versions/1/leak.env")

    assert r.status_code in {400, 403, 404}
    assert "do-not-serve" not in r.text


@pytest.mark.parametrize("dotfile", [".env", ".secret", "assets/.env"])
def test_preview_rejects_dotfiles(client, artifact_root, dotfile):
    write_artifact(artifact_root, "hello-card")
    target = artifact_root / "hello-card" / "versions" / "1" / dotfile
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("SECRET=do-not-serve", encoding="utf-8")

    r = client.get(f"/api/plugins/artifacts/preview/hello-card/versions/1/{dotfile}")

    assert r.status_code in {400, 403, 404}
    assert "do-not-serve" not in r.text


def test_preview_rejects_invalid_artifact_id(client, artifact_root):
    write_artifact(artifact_root, "hello-card")

    r = client.get("/api/plugins/artifacts/preview/../../bad/versions/1/index.html")

    assert r.status_code in {400, 404}


# ---------------------------------------------------------------------------
# Dashboard bundle invariants
# ---------------------------------------------------------------------------


def test_dashboard_manifest_declares_artifacts_tab_and_api():
    data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))

    assert data["name"] == "artifacts"
    assert data["tab"]["path"] == "/artifacts"
    assert data["entry"] == "dist/index.js"
    assert data["css"] == "dist/style.css"
    assert data["api"] == "plugin_api.py"


def test_dashboard_bundle_uses_real_plugin_registry_and_sdk_fetch_client():
    js = BUNDLE_FILE.read_text(encoding="utf-8")

    assert "window.__HERMES_PLUGINS__" in js
    assert 'REGISTRY.register("artifacts", ArtifactsPage)' in js
    assert "registerPage" not in js
    assert "SDK.fetchJSON(API_BASE + path)" in js


def test_dashboard_bundle_uses_sandboxed_iframe_not_inner_html():
    js = BUNDLE_FILE.read_text(encoding="utf-8")

    assert 'API_BASE = "/api/plugins/artifacts"' in js
    assert 'api("/list")' in js
    assert "iframe" in js
    assert "sandbox" in js
    assert "allow-scripts" in js
    assert "allow-same-origin" not in js
    assert "dangerouslySetInnerHTML" not in js
    assert "referrerPolicy" in js
    assert "no-referrer" in js


def test_dashboard_auth_middleware_allows_artifact_preview_prefix_only():
    source = (REPO_ROOT / "hermes_cli" / "web_server.py").read_text(encoding="utf-8")

    assert '"/api/plugins/artifacts/preview/"' in source
    assert "path.startswith(_PUBLIC_API_PREFIXES)" in source
    assert '"/api/plugins/artifacts/list"' not in source
