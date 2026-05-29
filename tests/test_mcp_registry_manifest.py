"""Regression tests for the MCP Registry server.json manifest."""

import json
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _load_manifest() -> dict:
    return json.loads((ROOT / "server.json").read_text(encoding="utf-8"))


def test_mcp_registry_manifest_matches_package_version_and_launch_args():
    manifest = _load_manifest()
    pyproject = _load_pyproject()
    version = pyproject["project"]["version"]

    assert manifest["$schema"] == "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    assert manifest["name"] == "io.github.nousresearch/hermes-agent"
    assert manifest["version"] == version

    package = manifest["packages"][0]
    assert package["registryType"] == "pypi"
    assert package["registryBaseUrl"] == "https://pypi.org"
    assert package["identifier"] == pyproject["project"]["name"]
    assert package["version"] == version
    assert package["runtimeHint"] == "uvx"
    assert package["transport"] == {"type": "stdio"}
    assert package["packageArguments"] == [
        {"type": "positional", "value": "mcp"},
        {"type": "positional", "value": "serve"},
    ]


def test_pypi_distribution_name_cli_alias_dispatches_main_hermes_cli():
    """Registry launchers may infer `hermes-agent` from the PyPI package name."""

    scripts = _load_pyproject()["project"]["scripts"]
    assert scripts["hermes"] == "hermes_cli.main:main"
    assert scripts["hermes-agent"] == scripts["hermes"]


def test_mcp_sdk_available_for_plain_pypi_registry_install():
    """server.json advertises plain `hermes-agent`, so MCP cannot be extra-only."""

    project = _load_pyproject()["project"]
    assert "mcp==1.26.0" in project["dependencies"]
    assert "mcp" in project["optional-dependencies"]
    assert project["optional-dependencies"]["mcp"] == []


def test_readme_contains_mcp_registry_ownership_marker():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "<!-- mcp-name: io.github.nousresearch/hermes-agent -->" in readme
