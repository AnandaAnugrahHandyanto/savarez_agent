import json
from pathlib import Path


def test_cursor_mcp_configs_use_portable_hermes_launcher():
    repo_root = Path(__file__).resolve().parents[1]

    for rel_path in (".cursor/mcp.json", "cursor-mcp-config.json"):
        config = json.loads((repo_root / rel_path).read_text(encoding="utf-8"))
        server = config["mcpServers"]["hermes"]

        assert server.get("command") == "${workspaceFolder}/hermes-mcp-serve"
        assert server.get("args") == []
        assert "/home/" not in server["command"]
