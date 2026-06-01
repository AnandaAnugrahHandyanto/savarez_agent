import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_server_json_registry_metadata_matches_project_version():
    server_path = ROOT / "server.json"
    assert server_path.is_file()

    metadata = json.loads(server_path.read_text())
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    version = pyproject["project"]["version"]

    assert metadata["$schema"] == "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    assert metadata["name"] == "io.github.NousResearch/hermes-agent"
    assert re.fullmatch(r"[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+", metadata["name"])
    assert metadata["description"]
    assert metadata["version"] == version

    repository = metadata["repository"]
    assert repository["url"] == "https://github.com/NousResearch/hermes-agent"
    assert repository["source"] == "github"

    packages = metadata["packages"]
    assert len(packages) == 1
    package = packages[0]
    assert package["registryType"] == "pypi"
    assert package["registryBaseUrl"] == "https://pypi.org"
    assert package["identifier"] == "hermes-agent"
    assert package["version"] == version
    assert package["transport"] == {"type": "stdio"}
    assert [arg["value"] for arg in package["packageArguments"]] == ["mcp", "serve"]
    assert all(arg["type"] == "positional" for arg in package["packageArguments"])

    readme = (ROOT / "README.md").read_text()
    assert f"mcp-name: {metadata['name']}" in readme
