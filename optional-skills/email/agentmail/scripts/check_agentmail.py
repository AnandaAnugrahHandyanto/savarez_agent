#!/usr/bin/env python3
"""Minimal config validation helper for the AgentMail optional skill."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from hermes_constants import get_hermes_home


def _candidate_config_paths() -> list[Path]:
    candidates = [get_hermes_home() / "config.yaml", Path.home() / ".hermes" / "config.yaml"]
    seen = set()
    ordered = []
    for path in candidates:
        resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(path)
    return ordered


def _load_config_text() -> str:
    candidates = _candidate_config_paths()

    for path in candidates:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if "agentmail:" in text and "agentmail-mcp" in text:
                return text
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def _probe_agentmail_server(npx_path: str) -> tuple[bool, dict]:
    cmd = [npx_path, "-y", "agentmail-mcp"]
    started_at = time.time()
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        env=os.environ.copy(),
    )
    try:
        time.sleep(8)
        rc = proc.poll()
        payload = {
            "agentmail_server_probe_exit_code": rc,
            "probe_stdout_preview": "",
            "probe_stderr_preview": "",
            "probe_runtime_seconds": round(time.time() - started_at, 2),
        }

        if rc is None:
            return True, payload
        return False, payload
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def main() -> int:
    config_text = _load_config_text()
    npx_path = shutil.which("npx")

    result = {
        "ok": False,
        "npx_found": bool(npx_path),
        "agentmail_configured": False,
        "config_path_checked": [str(path) for path in _candidate_config_paths()],
    }

    if not npx_path:
        result["error"] = "missing_npx"
        result["message"] = "Node.js/npm (npx) is required for agentmail-mcp."
        print(json.dumps(result, ensure_ascii=False))
        return 1

    result["agentmail_configured"] = "agentmail:" in config_text and "agentmail-mcp" in config_text
    result["ok"] = result["agentmail_configured"]

    if not result["agentmail_configured"]:
        result["error"] = "agentmail_not_configured"
        result["message"] = "No agentmail MCP block found in config.yaml."
        print(json.dumps(result, ensure_ascii=False))
        return 2

    try:
        probe_ok, payload = _probe_agentmail_server(npx_path)
    except subprocess.TimeoutExpired:
        result["agentmail_server_probe_exit_code"] = None
        result["probe_stdout_preview"] = ""
        result["probe_stderr_preview"] = ""
        result["error"] = "agentmail_probe_timeout"
        result["message"] = "Config exists, but agentmail-mcp did not stabilize before timeout."
        print(json.dumps(result, ensure_ascii=False))
        return 4

    result.update(payload)
    result["ok"] = probe_ok

    if not probe_ok:
        result["error"] = "agentmail_probe_failed"
        result["message"] = "Config exists, but agentmail-mcp exited during stdio startup probe."
        print(json.dumps(result, ensure_ascii=False))
        return 3

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
