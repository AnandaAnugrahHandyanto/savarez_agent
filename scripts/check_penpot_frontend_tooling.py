#!/usr/bin/env python3
"""Report Penpot/frontend design-to-code tooling availability.

This script is intentionally read-only. It checks local tools and project
markers, then prints setup guidance. It does not install packages, write config,
start MCP servers, or mutate project files.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


def command_version(name: str) -> dict[str, str | None]:
    path = shutil.which(name)
    if not path:
        return {"status": "missing", "path": None, "version": None}
    try:
        proc = subprocess.run(
            [path, "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        version = (proc.stdout or proc.stderr).strip().splitlines()[0]
    except Exception as exc:  # pragma: no cover - defensive reporting only
        version = f"version check failed: {exc}"
    return {"status": "present", "path": path, "version": version}


def check_penpot_local(url: str) -> dict[str, str]:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=2) as response:
            return {"status": "reachable", "url": url, "http_status": str(response.status)}
    except urllib.error.HTTPError as exc:
        return {"status": "reachable", "url": url, "http_status": str(exc.code)}
    except Exception as exc:
        return {"status": "not_running", "url": url, "detail": exc.__class__.__name__}


def build_report(project: Path, penpot_url: str) -> dict:
    project = project.resolve()
    has_components = (project / "components.json").is_file()
    has_storybook = any(
        (project / candidate).exists()
        for candidate in (".storybook", "storybook", "src/stories")
    )
    playwright_available = importlib.util.find_spec("playwright") is not None

    return {
        "project": str(project),
        "mutates": False,
        "checks": {
            "node": command_version("node"),
            "npm": command_version("npm"),
            "npx": command_version("npx"),
            "penpot_local_mcp": check_penpot_local(penpot_url),
            "playwright_python": {
                "status": "present" if playwright_available else "missing"
            },
            "shadcn": {
                "status": "present" if has_components else "missing",
                "marker": "components.json",
            },
            "storybook": {
                "status": "present" if has_storybook else "missing",
                "markers": [".storybook", "storybook", "src/stories"],
            },
        },
        "guidance": [
            "This script is read-only and does not install packages or mutate project files.",
            "Use Penpot remote MCP when available; use local MCP at http://localhost:4401/mcp as fallback.",
            "Start Penpot local MCP with scripts/start_penpot_mcp.ps1 on Windows, or npx -y @penpot/mcp@stable where supported.",
            "Do not store MCP keys or URLs containing userToken in repo files.",
            "Use shadcn/Radix/Tailwind for new polished web UI unless the project already has a design system.",
            "Add Storybook MCP only after reusable components exist.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project directory to inspect")
    parser.add_argument("--penpot-url", default="http://localhost:4401/mcp")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(Path(args.project), args.penpot_url)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
