"""Tests for the artifact_present agent tool."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _reset_artifact_tool_modules():
    for name in list(sys.modules):
        if name in {"tools.artifact_tool", "plugins.artifacts.store"}:
            sys.modules.pop(name, None)


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _reset_artifact_tool_modules()
    return home


@pytest.fixture
def artifact_tool(hermes_home):
    return importlib.import_module("tools.artifact_tool")


def _json(raw: str) -> dict:
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data


# ---------------------------------------------------------------------------
# Content registration
# ---------------------------------------------------------------------------


def test_artifact_present_registers_content_under_hermes_artifacts(artifact_tool, hermes_home):
    raw = artifact_tool.artifact_present(
        title="Revenue Dashboard",
        content="<html><body>Revenue</body></html>",
        filename="index.html",
        content_type="text/html",
    )

    data = _json(raw)
    assert data["success"] is True
    artifact = data["artifact"]
    assert artifact["id"] == "revenue-dashboard"
    assert artifact["version"] == 1
    assert artifact["title"] == "Revenue Dashboard"
    assert artifact["contentType"] == "text/html"
    assert artifact["url"] == "/api/plugins/artifacts/preview/revenue-dashboard/versions/1/index.html"

    path = Path(artifact["path"])
    assert path == hermes_home / "artifacts" / "revenue-dashboard" / "versions" / "1" / "index.html"
    assert path.read_text(encoding="utf-8") == "<html><body>Revenue</body></html>"

    manifest = json.loads((hermes_home / "artifacts" / "revenue-dashboard" / "manifest.json").read_text())
    assert manifest["id"] == "revenue-dashboard"
    assert manifest["latestVersion"] == 1
    assert manifest["versions"][0]["entrypoint"] == "index.html"


def test_artifact_present_increments_version_for_existing_artifact(artifact_tool, hermes_home):
    first = _json(artifact_tool.artifact_present(
        artifact_id="daily-report",
        title="Daily Report",
        content="one",
        filename="index.html",
    ))
    second = _json(artifact_tool.artifact_present(
        artifact_id="daily-report",
        title="Daily Report",
        content="two",
        filename="index.html",
    ))

    assert first["artifact"]["version"] == 1
    assert second["artifact"]["version"] == 2
    assert Path(second["artifact"]["path"]).read_text(encoding="utf-8") == "two"
    manifest = json.loads((hermes_home / "artifacts" / "daily-report" / "manifest.json").read_text())
    assert manifest["latestVersion"] == 2
    assert [v["version"] for v in manifest["versions"]] == [1, 2]


# ---------------------------------------------------------------------------
# Source file registration
# ---------------------------------------------------------------------------


def test_artifact_present_copies_existing_source_file(artifact_tool, hermes_home, tmp_path):
    source = tmp_path / "chart.svg"
    source.write_text("<svg><text>ok</text></svg>", encoding="utf-8")

    data = _json(artifact_tool.artifact_present(
        title="Chart",
        source_path=str(source),
        content_type="image/svg+xml",
    ))

    artifact = data["artifact"]
    assert artifact["id"] == "chart"
    assert artifact["contentType"] == "image/svg+xml"
    assert artifact["path"].endswith("/chart/versions/1/chart.svg")
    assert Path(artifact["path"]).read_text(encoding="utf-8") == "<svg><text>ok</text></svg>"
    assert Path(artifact["path"]).resolve() != source.resolve()


def test_artifact_present_relative_source_path_resolves_from_terminal_cwd(artifact_tool, hermes_home, tmp_path, monkeypatch):
    source = tmp_path / "report.md"
    source.write_text("# Report", encoding="utf-8")
    monkeypatch.chdir(REPO_ROOT)  # prove cwd is not the resolver

    data = _json(artifact_tool.artifact_present(title="Report", source_path="report.md"))

    artifact = data["artifact"]
    assert artifact["contentType"] == "text/markdown"
    assert Path(artifact["path"]).read_text(encoding="utf-8") == "# Report"


def test_artifact_present_allows_sources_under_hidden_hermes_workspace_parent(artifact_tool, hermes_home):
    workspace = hermes_home / "workspace"
    workspace.mkdir()
    source = workspace / "demo.html"
    source.write_text("<html>workspace</html>", encoding="utf-8")

    data = _json(artifact_tool.artifact_present(title="Workspace Demo", source_path=str(source)))

    assert data["success"] is True
    assert Path(data["artifact"]["path"]).read_text(encoding="utf-8") == "<html>workspace</html>"


# ---------------------------------------------------------------------------
# Safety / validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filename", ["../index.html", "/tmp/index.html", "assets/../../x.html", ".env"])
def test_artifact_present_rejects_unsafe_output_filenames(artifact_tool, filename):
    data = _json(artifact_tool.artifact_present(title="Bad", content="x", filename=filename))

    assert data["success"] is False
    assert "artifact" not in data


@pytest.mark.parametrize("source_name", [".env", "token.key", "private.pem", "id_rsa"])
def test_artifact_present_rejects_secret_like_source_files(artifact_tool, tmp_path, source_name):
    source = tmp_path / source_name
    source.write_text("SECRET=do-not-copy", encoding="utf-8")

    data = _json(artifact_tool.artifact_present(title="Secret", source_path=str(source)))

    assert data["success"] is False
    assert "do-not-copy" not in json.dumps(data)


def test_artifact_present_rejects_symlink_source_escape(artifact_tool, tmp_path):
    outside = tmp_path / "outside.html"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "link.html"
    link.symlink_to(outside)

    data = _json(artifact_tool.artifact_present(title="Link", source_path=str(link)))

    assert data["success"] is False
    assert "outside" not in json.dumps(data)


def test_artifact_present_requires_exactly_one_input_mode(artifact_tool, tmp_path):
    source = tmp_path / "x.html"
    source.write_text("x", encoding="utf-8")

    both = _json(artifact_tool.artifact_present(title="Both", content="x", source_path=str(source)))
    neither = _json(artifact_tool.artifact_present(title="Neither"))

    assert both["success"] is False
    assert neither["success"] is False


# ---------------------------------------------------------------------------
# Registry/toolset integration
# ---------------------------------------------------------------------------


def test_artifact_present_registers_tool_and_toolset(hermes_home):
    from tools.registry import registry
    import toolsets

    importlib.import_module("tools.artifact_tool")
    names = {entry.name for entry in registry._snapshot_entries()}

    assert "artifact_present" in names
    assert "artifacts" in toolsets.TOOLSETS
    assert "artifact_present" in toolsets.TOOLSETS["artifacts"]["tools"]
    assert "artifact_present" in toolsets._HERMES_CORE_TOOLS
