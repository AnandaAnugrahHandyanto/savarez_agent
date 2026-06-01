"""Tests for official MCP Registry metadata shipped with Hermes."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = ROOT / "server.json"


def _server_json() -> dict:
    return json.loads(SERVER_JSON.read_text(encoding="utf-8"))


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_server_json_matches_mcp_registry_identity_and_package():
    data = _server_json()
    pyproject = _pyproject()
    version = pyproject["project"]["version"]

    assert data["$schema"] == "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    assert data["name"] == "io.github.nousresearch/hermes-agent"
    assert data["title"] == "Hermes Agent"
    assert data["repository"] == {
        "url": "https://github.com/NousResearch/hermes-agent",
        "source": "github",
        "id": "1024554267",
    }
    assert data["version"] == version

    assert len(data["packages"]) == 1
    package = data["packages"][0]
    assert package["registryType"] == "pypi"
    assert package["registryBaseUrl"] == "https://pypi.org"
    assert package["identifier"] == "hermes-agent[mcp]"
    assert package["version"] == version
    assert package["runtimeHint"] == "uvx"
    assert package["transport"] == {"type": "stdio"}
    assert package["packageArguments"] == [
        {"type": "positional", "value": "mcp"},
        {"type": "positional", "value": "serve"},
    ]


def test_hermes_agent_console_script_can_launch_mcp_package_arguments():
    """Registry clients may execute the PyPI package's matching binary.

    Keep ``hermes-agent mcp serve`` equivalent to ``hermes mcp serve`` so the
    root ``server.json`` packageArguments start the MCP server instead of the
    legacy direct-agent runner.
    """

    scripts = _pyproject()["project"]["scripts"]
    assert scripts["hermes"] == "hermes_cli.main:main"
    assert scripts["hermes-agent"] == scripts["hermes"]


def test_publisher_provided_meta_stays_within_official_registry_limit():
    data = _server_json()
    publisher_meta = data["_meta"]["io.modelcontextprotocol.registry/publisher-provided"]

    encoded = json.dumps(publisher_meta, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= 4096
