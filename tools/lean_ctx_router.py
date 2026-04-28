"""Internal lean-ctx routing for read and terminal-heavy Hermes tool calls.

Existing Hermes tools use this module to route context-heavy work through
lean-ctx when the native ``lean_ctx:`` config section is active. The visible
tool list remains the direct model action surface; routed results include
``lean_ctx`` metadata so callers can verify the path used.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 30.0
_SAFE_ENV_KEYS = {
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "LC_ALL",
    "TERM",
    "SHELL",
    "TMPDIR",
}
_LEAN_STATS_LOCK = threading.Lock()
_LEAN_STATS: dict[str, float | int] = {
    "calls": 0,
    "tokens_original": 0.0,
    "tokens_compressed": 0.0,
    "tokens_saved": 0.0,
}
_ARROW_STATS_RE = re.compile(
    r"(?P<original>\d+(?:\.\d+)?)\s*(?:→|->)\s*(?P<compressed>\d+(?:\.\d+)?)\s*tok",
    re.IGNORECASE,
)
_SAVED_STATS_RE = re.compile(
    r"(?P<saved>\d+(?:\.\d+)?)\s*tok(?:ens)?\s*saved(?:\s*\((?P<percent>\d+(?:\.\d+)?)%\))?",
    re.IGNORECASE,
)
_ELIGIBLE_TERMINAL_RE = re.compile(
    r"^\s*(?:"
    r"git\s+(?:status|log|diff|add|commit|push|pull|fetch|clone|branch|checkout|switch|merge|stash|tag|reset|remote|show|grep|ls-files)\b|"
    r"docker\s+(?:build|ps|images|logs|compose|exec|network|inspect)\b|"
    r"(?:npm|pnpm|yarn|bun)\s+(?:install|test|run|list|outdated|audit|build|lint)\b|"
    r"cargo\s+(?:build|test|check|clippy|fmt)\b|"
    r"gh\s+(?:pr|issue|run)\s+(?:list|view|create|status|checks)\b|"
    r"kubectl\s+(?:get|logs|describe|apply|top)\b|"
    r"(?:python|python3)\s+(?:-m\s+)?(?:pip|pytest|ruff|poetry|uv)\b|"
    r"(?:pip|pip3|poetry|uv)\s+(?:install|list|outdated|run|sync|lock|tree)\b|"
    r"(?:ruff|eslint|biome|prettier|golangci-lint)\s+(?:check|format|lint|run)?\b|"
    r"(?:tsc|next|vite)\s+(?:build|dev|lint|test)?\b|"
    r"(?:rubocop|bundle|rake|rails)\b|"
    r"(?:jest|vitest|pytest|go\s+test|playwright|rspec|minitest)\b|"
    r"terraform\s+(?:plan|validate|fmt|show|output|state\s+list)\b|"
    r"(?:make|mvn|maven|gradle|dotnet|flutter|dart)\b|"
    r"(?:curl|grep|rg|find|ls|wget|env|jq|pwd|tree|cat|head|tail)\b"
    r")"
)
_UNSAFE_TERMINAL_RE = re.compile(
    r"(^|\s)("
    r"lean-ctx|sudo|su|ssh|scp|sftp|rsync|dd|mkfs|shutdown|reboot|halt|"
    r"rm\s+-rf|git\s+reset\s+--hard|git\s+clean\b|"
    r"terraform\s+(?:apply|destroy)|kubectl\s+delete|docker\s+(?:rm|rmi|prune)|"
    r"gh\s+(?:auth|secret)\b"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LeanCtxRoutingConfig:
    enabled: bool = False
    command: str = "lean-ctx"
    env: dict[str, str] | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    route_file_tools: bool = True
    route_terminal: bool = True


def route_read_file(
    *,
    path: str,
    resolved_path: Path,
    offset: int,
    limit: int,
    cwd: Path,
) -> dict[str, Any] | None:
    cfg = _load_routing_config()
    if not cfg.enabled or not cfg.route_file_tools or not _available(cfg):
        return None
    end = max(offset, offset + max(limit, 1) - 1)
    mode = f"lines:{offset}-{end}"
    text = _call_mcp_tool(
        cfg,
        "ctx_read",
        {"path": str(resolved_path), "mode": mode},
        cwd=cwd,
    )
    if not text:
        return None
    _record_savings(text)
    return {
        "path": path,
        "resolved_path": str(resolved_path),
        "offset": offset,
        "limit": limit,
        "content": text,
        "lean_ctx": True,
        "tool": "ctx_read",
    }


def route_search_files(
    *,
    pattern: str,
    target: str,
    path: str,
    file_glob: str | None,
    limit: int,
    offset: int,
    output_mode: str,
    context: int,
    cwd: Path,
) -> dict[str, Any] | None:
    del offset, context
    cfg = _load_routing_config()
    if not cfg.enabled or not cfg.route_file_tools or not _available(cfg):
        return None
    if file_glob:
        return None
    if target == "content":
        text = _call_mcp_tool(
            cfg,
            "ctx_search",
            {
                "pattern": pattern,
                "path": str(_resolve_search_path(path, cwd)),
                "max_results": limit,
            },
            cwd=cwd,
        )
        tool = "ctx_search"
    elif target == "files":
        text = _run_lean_ctx_command(
            cfg,
            ["find", pattern, str(_resolve_search_path(path, cwd))],
            cwd=cwd,
        )
        tool = "lean-ctx find"
    else:
        return None
    if not text:
        return None
    _record_savings(text)
    return {
        "pattern": pattern,
        "target": target,
        "path": path,
        "output_mode": output_mode,
        "content": text,
        "lean_ctx": True,
        "tool": tool,
    }


def route_terminal_command(
    *,
    command: str,
    cwd: Path,
    timeout: int | float | None,
) -> str | None:
    cfg = _load_routing_config()
    if not cfg.enabled or not cfg.route_terminal or not _available(cfg):
        return None
    if not _is_safe_read_only_command(command):
        return None
    effective_timeout = timeout or cfg.timeout_seconds
    try:
        output = _run_lean_ctx_command(
            cfg,
            ["-c", command],
            cwd=cwd,
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "output": "",
                "exit_code": -1,
                "error": f"lean-ctx command timed out after {effective_timeout}s",
                "status": "timeout",
                "lean_ctx": True,
            },
            ensure_ascii=False,
        )
    if output is None:
        return None
    _record_savings(output)
    return json.dumps(
        {
            "output": output,
            "exit_code": 0,
            "error": "",
            "status": "success",
            "lean_ctx": True,
            "tool": "lean-ctx -c",
        },
        ensure_ascii=False,
    )


def _is_safe_read_only_command(command: str) -> bool:
    stripped = (command or "").strip()
    if not stripped:
        return False
    if _UNSAFE_TERMINAL_RE.search(stripped):
        return False
    return bool(_ELIGIBLE_TERMINAL_RE.match(stripped))


def get_session_savings() -> dict[str, int]:
    """Return current-process lean-ctx savings for compact CLI display."""
    with _LEAN_STATS_LOCK:
        original = int(_LEAN_STATS["tokens_original"])
        compressed = int(_LEAN_STATS["tokens_compressed"])
        saved = int(_LEAN_STATS["tokens_saved"])
        calls = int(_LEAN_STATS["calls"])
    rate = round((saved / original) * 100) if original > 0 else 0
    return {
        "calls": calls,
        "tokens_original": original,
        "tokens_compressed": compressed,
        "tokens_saved": saved,
        "compression_rate": max(0, min(100, rate)),
    }


def reset_session_savings() -> None:
    """Reset process-local counters when Hermes starts a fresh session."""
    with _LEAN_STATS_LOCK:
        for key in _LEAN_STATS:
            _LEAN_STATS[key] = 0


def run_diagnostic_command(kind: str, *, cwd: Path | None = None) -> dict[str, Any]:
    """Run an on-demand read-only lean-ctx diagnostic subcommand."""
    normalized = (kind or "status").strip().lower().replace("_", "-")
    if normalized == "savings":
        return {"ok": True, "kind": "savings", "data": get_session_savings()}

    cfg = _load_routing_config()
    if not cfg.enabled:
        return {"ok": False, "error": "lean_ctx is inactive in config"}
    if not shutil.which(cfg.command):
        return {"ok": False, "error": f"{cfg.command!r} not found on PATH"}

    commands: dict[str, list[str]] = {
        "status": ["status", "--json"],
        "token-report": ["token-report", "--json"],
        "report": ["token-report", "--json"],
        "gain": ["gain", "--json"],
        "cache": ["cache", "stats"],
        "doctor": ["doctor", "--json"],
    }
    if normalized not in commands:
        return {
            "ok": False,
            "error": "unknown diagnostic",
            "allowed": sorted(["savings", *commands]),
        }
    output = _run_lean_ctx_command(
        cfg,
        commands[normalized],
        cwd=(cwd or Path.cwd()).resolve(),
        timeout=cfg.timeout_seconds,
    )
    if output is None:
        return {"ok": False, "error": f"lean-ctx {normalized} failed"}
    try:
        data: Any = json.loads(output)
    except json.JSONDecodeError:
        data = output
    return {"ok": True, "kind": normalized, "data": data}


def _resolve_search_path(path: str, cwd: Path) -> Path:
    candidate = Path(path or ".").expanduser()
    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve()


def _record_savings(text: str | None) -> None:
    stats = _extract_savings(text or "")
    if not stats:
        return
    with _LEAN_STATS_LOCK:
        _LEAN_STATS["calls"] = int(_LEAN_STATS["calls"]) + 1
        _LEAN_STATS["tokens_original"] = float(_LEAN_STATS["tokens_original"]) + stats["original"]
        _LEAN_STATS["tokens_compressed"] = float(_LEAN_STATS["tokens_compressed"]) + stats["compressed"]
        _LEAN_STATS["tokens_saved"] = float(_LEAN_STATS["tokens_saved"]) + stats["saved"]


def _extract_savings(text: str) -> dict[str, float] | None:
    match = _ARROW_STATS_RE.search(text)
    if match:
        original = float(match.group("original"))
        compressed = float(match.group("compressed"))
        saved = max(0.0, original - compressed)
        if original > 0 and saved > 0:
            return {"original": original, "compressed": compressed, "saved": saved}

    match = _SAVED_STATS_RE.search(text)
    if not match:
        return None
    saved = float(match.group("saved"))
    percent_raw = match.group("percent")
    if saved <= 0:
        return None
    if percent_raw:
        percent = max(1.0, min(100.0, float(percent_raw)))
        original = saved / (percent / 100.0)
        compressed = max(0.0, original - saved)
    else:
        original = saved
        compressed = 0.0
    return {"original": original, "compressed": compressed, "saved": saved}


def _load_routing_config() -> LeanCtxRoutingConfig:
    try:
        from hermes_cli.config import load_config

        raw = load_config().get("lean_ctx")
    except Exception:
        raw = None
    if not isinstance(raw, dict):
        return LeanCtxRoutingConfig(enabled=False)
    command = str(raw.get("command") or "lean-ctx")
    enabled = raw.get("enabled", "auto")
    if enabled is False:
        return LeanCtxRoutingConfig(enabled=False)
    if isinstance(enabled, str) and enabled.strip().lower() == "auto" and not shutil.which(command):
        return LeanCtxRoutingConfig(enabled=False)
    env = {str(k): str(v) for k, v in (raw.get("env") or {}).items()}
    return LeanCtxRoutingConfig(
        enabled=True,
        command=command,
        env=env or None,
        timeout_seconds=float(raw.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS)),
        route_file_tools=bool(raw.get("route_file_tools", True)),
        route_terminal=bool(raw.get("route_terminal", True)),
    )


def _available(cfg: LeanCtxRoutingConfig) -> bool:
    if not shutil.which(cfg.command):
        return False
    try:
        import mcp  # noqa: F401
    except Exception:
        return False
    return True


def _build_env(extra: dict[str, str] | None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in _SAFE_ENV_KEYS}
    if extra:
        env.update({key: value for key, value in extra.items() if key.startswith("LEAN_CTX_")})
    return env


def _run_lean_ctx_command(
    cfg: LeanCtxRoutingConfig,
    args: list[str],
    *,
    cwd: Path,
    timeout: int | float | None = None,
) -> str | None:
    proc = subprocess.run(
        [cfg.command, *args],
        cwd=str(cwd),
        env=_build_env(cfg.env),
        text=True,
        capture_output=True,
        timeout=timeout or cfg.timeout_seconds,
        check=False,
    )
    output = (proc.stdout or "").strip()
    if proc.returncode != 0:
        logger.debug("lean-ctx command failed: %s", (proc.stderr or output).strip())
        return None
    return output


def _call_mcp_tool(
    cfg: LeanCtxRoutingConfig,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    cwd: Path,
) -> str:
    return _run_coro_sync(
        asyncio.wait_for(
            _call_mcp_tool_async(cfg, tool_name, arguments, cwd=cwd),
            timeout=cfg.timeout_seconds,
        ),
        timeout_seconds=cfg.timeout_seconds + 1.0,
    )


async def _call_mcp_tool_async(
    cfg: LeanCtxRoutingConfig,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    cwd: Path,
) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = StdioServerParameters(
        command=cfg.command,
        args=[],
        env=_build_env(cfg.env),
        cwd=str(cwd),
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            if getattr(result, "isError", False):
                return ""
            return _result_to_text(result)


def _result_to_text(result: Any) -> str:
    parts: list[str] = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _run_coro_sync(coro, *, timeout_seconds: float | None = None):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def _runner():
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise TimeoutError("lean-ctx routing call timed out")
    if "error" in result:
        raise result["error"]
    return result.get("value", "")
