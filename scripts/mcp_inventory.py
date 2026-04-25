#!/usr/bin/env python3
"""Generate a redacted MCP inventory from the current Hermes config.

Safe by design: this only reads config files and writes Markdown/JSON artifacts;
it does not start, enable, or connect to any MCP server.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_DEFAULT = Path.home() / ".hermes" / "config.yaml"
OUT_DEFAULT = Path.home() / ".hermes" / "reports" / "mcp_inventory.md"
SECRET_KEY_RE = re.compile(r"(token|key|secret|password|authorization|credential)", re.I)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise SystemExit(f"PyYAML is required to read {path}: {exc}")
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _redact(value: Any, key: str = "") -> Any:
    if SECRET_KEY_RE.search(key):
        return "<redacted>" if value not in (None, "") else value
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, key) for v in value]
    if isinstance(value, str) and re.search(r"(Bearer\s+\S+|sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,})", value):
        return "<redacted>"
    return value


def _classify(server: dict[str, Any]) -> str:
    if server.get("url"):
        return "http"
    if server.get("command"):
        return "stdio"
    return "unknown"


def render(config_path: Path, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    servers = config.get("mcp_servers") or {}
    if not isinstance(servers, dict):
        servers = {}
    inventory = {
        "config_path": str(config_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "server_count": len(servers),
        "servers": [],
    }
    lines = [
        "# Hermes MCP Inventory",
        "",
        f"Generated: {inventory['generated_at']}",
        f"Config: `{config_path}`",
        "",
        "Safety: this inventory is read-only and redacts credential-like values. No MCP server was started or enabled.",
        "",
        f"Configured servers: {len(servers)}",
        "",
    ]
    if not servers:
        lines += ["No `mcp_servers` are configured in the current Hermes config.", ""]
        return "\n".join(lines), inventory
    for name, raw in sorted(servers.items()):
        server = raw if isinstance(raw, dict) else {}
        redacted = _redact(server)
        transport = _classify(server)
        entry = {"name": name, "transport": transport, "config": redacted}
        inventory["servers"].append(entry)
        lines += [
            f"## {name}",
            "",
            f"- Transport: `{transport}`",
            f"- Command: `{redacted.get('command', '')}`" if transport == "stdio" else f"- URL: `{redacted.get('url', '')}`",
            f"- Timeout: `{redacted.get('timeout', 'default')}`",
            f"- Connect timeout: `{redacted.get('connect_timeout', 'default')}`",
            "",
            "```json",
            json.dumps(redacted, indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    return "\n".join(lines), inventory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_DEFAULT)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--json-out", type=Path, default=Path.home() / ".hermes" / "reports" / "mcp_inventory.json")
    args = parser.parse_args()
    config = _load_yaml(args.config)
    md, inventory = render(args.config, config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "server_count": inventory["server_count"], "output": str(args.out), "json_output": str(args.json_out)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
