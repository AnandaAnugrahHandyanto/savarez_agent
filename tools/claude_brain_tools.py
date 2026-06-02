#!/usr/bin/env python3
"""Claude Brain constrained file tools.

Narrow Claude-facing toolset for the Claude/XO collaboration lane. This module
intentionally does not expose terminal/process/browser or generic file write
operations. It provides:

- read/search inspection tools;
- Claude-Brain-only write/patch/delete tools;
- fail-closed path validation;
- durable audit logging for every write attempt;
- a one-time Commander override mechanism for explicit out-of-lane writes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml

from hermes_constants import get_hermes_home

from tools.registry import registry

COLLAB_ROOT = Path("/Users/rfais370/Documents/Obsidian/FFT Command HQ/90_Collaboration")
CLAUDE_BRAIN_ROOT = Path(os.getenv("HERMES_CLAUDE_BRAIN_ROOT", str(COLLAB_ROOT / "Claude-Brain")))
DEFAULT_WRITE_ROOTS = [CLAUDE_BRAIN_ROOT]
CLAUDE_XO_ROOT = COLLAB_ROOT / "Claude-XO"
AUDIT_LOG = CLAUDE_XO_ROOT / "sync" / "claude-brain-write-audit.jsonl"
OVERRIDE_FILE = CLAUDE_XO_ROOT / "commander-decisions" / "one-time-write-overrides.json"
MAX_READ_CHARS = 100_000
MAX_SEARCH_FILE_BYTES = 250_000
DEFAULT_REPO_ROOT = Path("/Users/rfais370/Projects/fft")
DEFAULT_TERMINAL_ALLOWLIST = {
    "git": ["status", "add", "commit", "diff", "log", "show", "restore", "checkout", "branch", "stash"],
    "pnpm": ["install", "build"],
}
SHELL_METACHARS_RE = re.compile(r"(;|&&|\|\||\||`|\$\(|>|<)")
SECRET_BASENAMES = {
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
    ".env.staging", ".envrc", "auth.json", "auth.lock", ".anthropic_oauth.json",
}
SECRET_DIRS = {".ssh", ".aws", ".gnupg", ".kube", "mcp-tokens"}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _configured_write_roots() -> list[Path]:
    """Return Commander-authorized write roots from persistent profile config.

    Fail-closed for malformed roots; default remains Claude-Brain only when the
    config key is absent for older deployments. Multiple roots support the
    website co-builder lane while keeping raw file/terminal tools unregistered.
    """
    roots: list[Path] = []
    cfg_path = Path(get_hermes_home()) / "config.yaml"
    try:
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        configured = (cfg.get("claude_brain") or {}).get("allowed_write_roots")
    except Exception:
        configured = None
    if configured is None:
        configured = [str(p) for p in DEFAULT_WRITE_ROOTS]
    if not isinstance(configured, list):
        return []
    for item in configured:
        try:
            root = Path(str(item)).expanduser().resolve(strict=True)
        except Exception:
            continue
        if _is_secret_path(root):
            continue
        roots.append(root)
    # De-duplicate preserving order.
    deduped: list[Path] = []
    for root in roots:
        if root not in deduped:
            deduped.append(root)
    return deduped


def _root() -> Path:
    # Compatibility for relative read/write paths: first configured root is
    # Claude-Brain. Resolve strictly; if it cannot be proven, fail closed.
    roots = _configured_write_roots()
    if not roots:
        raise RuntimeError("no valid configured Claude write roots")
    return roots[0]


def _claude_brain_config() -> dict[str, Any]:
    cfg_path = Path(get_hermes_home()) / "config.yaml"
    try:
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    section = cfg.get("claude_brain") or {}
    return section if isinstance(section, dict) else {}


def _terminal_config() -> tuple[Path, dict[str, list[str]]]:
    section = _claude_brain_config()
    term = section.get("repo_terminal") or {}
    if not isinstance(term, dict):
        term = {}
    try:
        workdir = Path(str(term.get("workdir", str(DEFAULT_REPO_ROOT)))).expanduser().resolve(strict=True)
    except Exception:
        workdir = DEFAULT_REPO_ROOT.resolve(strict=True)
    configured = term.get("allowlist", DEFAULT_TERMINAL_ALLOWLIST)
    allowlist: dict[str, list[str]] = {}
    if isinstance(configured, dict):
        for binary, subcommands in configured.items():
            if isinstance(binary, str) and isinstance(subcommands, list):
                allowlist[binary] = [str(s) for s in subcommands]
    if not allowlist:
        allowlist = {k: list(v) for k, v in DEFAULT_TERMINAL_ALLOWLIST.items()}
    return workdir, allowlist


def _audit_terminal(argv: list[str], allowed: bool, reason: str = "", exit_code: Optional[int] = None) -> None:
    _audit(
        "repo_terminal",
        json.dumps(argv, ensure_ascii=False),
        allowed,
        reason,
        str(DEFAULT_REPO_ROOT),
        False,
        {"exit_code": exit_code} if exit_code is not None else None,
    )


def _validate_repo_terminal_argv(argv: Any) -> tuple[Optional[list[str]], Optional[Path], Optional[str]]:
    if not isinstance(argv, list) or not argv:
        return None, None, "argv must be a non-empty array"
    clean: list[str] = []
    for arg in argv:
        if not isinstance(arg, str):
            return None, None, "all argv entries must be strings"
        if arg == "" or "\x00" in arg:
            return None, None, "empty arg or NUL byte denied"
        if SHELL_METACHARS_RE.search(arg):
            return None, None, f"shell metacharacter/chaining denied in arg: {arg}"
        clean.append(arg)
    workdir, allowlist = _terminal_config()
    binary = Path(clean[0]).name
    if clean[0] != binary or binary not in allowlist:
        return clean, workdir, f"binary denied: {clean[0]}"
    if len(clean) < 2:
        return clean, workdir, "subcommand required"
    subcmd = clean[1]
    if subcmd not in allowlist[binary]:
        return clean, workdir, f"subcommand denied: {binary} {subcmd}"
    # Lock cwd to repo and deny path arguments that resolve outside it. We keep
    # option flags and commit messages legal while blocking obvious path escapes.
    for arg in clean[2:]:
        if arg.startswith("-"):
            continue
        looks_pathlike = arg.startswith(("/", "./", "../", "~")) or "/" in arg or ".." in Path(arg).parts
        if looks_pathlike:
            try:
                candidate = Path(arg).expanduser()
                resolved = candidate.resolve(strict=False) if candidate.is_absolute() else (workdir / candidate).resolve(strict=False)
            except Exception as exc:
                return clean, workdir, f"cannot validate path arg {arg}: {exc}"
            if resolved != workdir and not str(resolved).startswith(str(workdir) + os.sep):
                return clean, workdir, f"path outside repo denied: {arg} -> {resolved}"
    return clean, workdir, None


def _matching_write_root(path: Path, roots: list[Path]) -> Optional[Path]:
    for root in roots:
        if path == root or str(path).startswith(str(root) + os.sep):
            return root
    return None


def _has_dotdot(raw: str) -> bool:
    return any(part == ".." for part in Path(raw).parts)


def _is_secret_path(path: Path) -> bool:
    return path.name in SECRET_BASENAMES or any(part in SECRET_DIRS for part in path.parts)


def _parent_chain(path: Path, stop: Path) -> Iterable[Path]:
    current = path
    while True:
        yield current
        if current == stop or current.parent == current:
            break
        current = current.parent


def _deny_if_symlink(path: Path, stop: Optional[Path] = None) -> Optional[str]:
    """Deny if any existing component from path up to stop/root is a symlink."""
    for node in _parent_chain(path, stop or path.anchor and Path(path.anchor) or path):
        try:
            if node.exists() and node.is_symlink():
                return f"symlink component denied: {node}"
        except OSError as exc:
            return f"cannot validate path component {node}: {exc}"
    return None


def _resolve_for_read(path: str) -> tuple[Optional[Path], Optional[str]]:
    if not path or "\x00" in path:
        return None, "empty path or NUL byte denied"
    if _has_dotdot(path):
        return None, ".. traversal denied"
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
    except Exception as exc:
        return None, f"cannot resolve read path: {exc}"
    if _is_secret_path(resolved):
        return None, f"secret-bearing path denied: {resolved.name}"
    return resolved, None


def _resolve_write_target(path: str, override_id: str = "") -> tuple[Optional[Path], bool, Optional[str]]:
    """Return (resolved_path, override_used, denial_reason)."""
    if not path or "\x00" in path:
        return None, False, "empty path or NUL byte denied"
    if _has_dotdot(path):
        return None, False, ".. traversal denied"
    roots = _configured_write_roots()
    if not roots:
        return None, False, "no valid configured Claude write roots"
    root = roots[0]

    raw = Path(path).expanduser()
    if raw.is_absolute():
        try:
            resolved = raw.resolve(strict=False)
        except Exception as exc:
            return None, False, f"cannot resolve absolute target: {exc}"
    else:
        try:
            resolved = (root / raw).resolve(strict=False)
        except Exception as exc:
            return None, False, f"cannot resolve relative target: {exc}"

    # Parent must already exist so validation does not create unknown path chains.
    parent = resolved.parent
    if not parent.exists() or not parent.is_dir():
        return None, False, f"parent directory does not exist or is not a directory: {parent}"
    matched_root = _matching_write_root(resolved, roots)
    if not matched_root:
        allowed = ", ".join(str(r) for r in roots)
        return None, False, f"out-of-lane write denied: {resolved} is outside allowed roots: {allowed}"
    symlink_reason = _deny_if_symlink(parent, matched_root)
    if symlink_reason:
        return None, False, symlink_reason
    if resolved.exists() and resolved.is_symlink():
        return None, False, f"target symlink denied: {resolved}"
    if _is_secret_path(resolved):
        return None, False, f"secret-bearing path denied: {resolved.name}"

    return resolved, False, None


def _load_overrides() -> list[dict[str, Any]]:
    if not OVERRIDE_FILE.exists():
        return []
    try:
        data = json.loads(OVERRIDE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_overrides(data: list[dict[str, Any]]) -> None:
    OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _consume_override(override_id: str, resolved_path: str) -> tuple[bool, str]:
    overrides = _load_overrides()
    now = _utc()
    for entry in overrides:
        if str(entry.get("id", "")) != override_id:
            continue
        if entry.get("used"):
            return False, "override already used"
        if entry.get("authorized_by") != "Commander":
            return False, "override missing Commander authorization"
        if str(Path(str(entry.get("path", ""))).expanduser().resolve(strict=False)) != resolved_path:
            return False, "override path does not exactly match target"
        expires_at = str(entry.get("expires_at", ""))
        if expires_at and expires_at < now:
            return False, "override expired"
        entry["used"] = True
        entry["used_at"] = now
        _save_overrides(overrides)
        return True, "override consumed"
    return False, "override id not found"


def _audit(action: str, requested_path: str, allowed: bool, reason: str = "", resolved_path: str = "", override_used: bool = False, extra: Optional[dict] = None) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": _utc(),
        "toolset": "claude_brain",
        "action": action,
        "requested_path": requested_path,
        "resolved_path": resolved_path,
        "allowed": bool(allowed),
        "override_used": bool(override_used),
        "reason": reason,
    }
    if extra:
        record.update(extra)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def claude_read_file(path: str, offset: int = 1, limit: int = 500) -> str:
    """Read a text file for Claude verification. Secret-like files are denied."""
    resolved, err = _resolve_for_read(path)
    if err:
        return _json({"success": False, "error": err})
    assert resolved is not None
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return _json({"success": False, "error": str(exc), "path": str(resolved)})
    lines = text.splitlines()
    start = max(1, int(offset or 1))
    lim = max(1, min(int(limit or 500), 2000))
    selected = lines[start - 1:start - 1 + lim]
    content = "\n".join(f"{i}|{line}" for i, line in enumerate(selected, start=start))
    if len(content) > MAX_READ_CHARS:
        content = content[:MAX_READ_CHARS] + "\n...[truncated]"
    return _json({"success": True, "path": str(resolved), "total_lines": len(lines), "content": content})


def claude_search_files(pattern: str, path: str, target: str = "content", limit: int = 50) -> str:
    """Search files by name or content without exposing shell execution."""
    base, err = _resolve_for_read(path)
    if err:
        return _json({"success": False, "error": err})
    assert base is not None
    lim = max(1, min(int(limit or 50), 100))
    matches: list[dict[str, Any]] = []
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return _json({"success": False, "error": f"invalid regex: {exc}"})
    files = [base] if base.is_file() else (p for p in base.rglob("*") if p.is_file())
    for p in files:
        if len(matches) >= lim:
            break
        if _is_secret_path(p):
            continue
        try:
            if p.stat().st_size > MAX_SEARCH_FILE_BYTES:
                continue
        except OSError:
            continue
        if target == "files":
            if rx.search(p.name) or rx.search(str(p)):
                matches.append({"path": str(p)})
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                matches.append({"path": str(p), "line": idx, "content": line[:500]})
                break
    return _json({"success": True, "base": str(base), "target": target, "count": len(matches), "matches": matches})


def claude_brain_write(path: str, content: str, override_id: str = "") -> str:
    """Write a complete file inside configured Commander-authorized write roots."""
    resolved, override_used, err = _resolve_write_target(path, override_id)
    if err:
        _audit("write", path, False, err)
        return _json({"success": False, "error": err})
    assert resolved is not None
    try:
        resolved.write_text(content, encoding="utf-8")
    except Exception as exc:
        _audit("write", path, False, str(exc), str(resolved), override_used)
        return _json({"success": False, "error": str(exc), "path": str(resolved)})
    _audit("write", path, True, "allowed", str(resolved), override_used, {"bytes": len(content.encode("utf-8"))})
    return _json({"success": True, "path": str(resolved), "override_used": override_used})


def claude_brain_patch(path: str, old_string: str, new_string: str, replace_all: bool = False, override_id: str = "") -> str:
    """Exact string replacement patch inside configured Commander-authorized write roots."""
    resolved, override_used, err = _resolve_write_target(path, override_id)
    if err:
        _audit("patch", path, False, err)
        return _json({"success": False, "error": err})
    assert resolved is not None
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
        count = text.count(old_string)
        if count == 0:
            raise ValueError("old_string not found")
        if not replace_all and count != 1:
            raise ValueError(f"old_string matched {count} times; set replace_all=true or provide unique context")
        updated = text.replace(old_string, new_string, -1 if replace_all else 1)
        resolved.write_text(updated, encoding="utf-8")
    except Exception as exc:
        _audit("patch", path, False, str(exc), str(resolved), override_used)
        return _json({"success": False, "error": str(exc), "path": str(resolved)})
    _audit("patch", path, True, "allowed", str(resolved), override_used, {"matches_replaced": count if replace_all else 1})
    return _json({"success": True, "path": str(resolved), "override_used": override_used, "matches_replaced": count if replace_all else 1})


def claude_brain_delete(path: str, override_id: str = "") -> str:
    """Delete a file inside configured Commander-authorized write roots. Directories are denied."""
    resolved, override_used, err = _resolve_write_target(path, override_id)
    if err:
        _audit("delete", path, False, err)
        return _json({"success": False, "error": err})
    assert resolved is not None
    try:
        if not resolved.exists():
            raise FileNotFoundError(str(resolved))
        if not resolved.is_file():
            raise IsADirectoryError(f"directory delete denied: {resolved}")
        resolved.unlink()
    except Exception as exc:
        _audit("delete", path, False, str(exc), str(resolved), override_used)
        return _json({"success": False, "error": str(exc), "path": str(resolved)})
    _audit("delete", path, True, "allowed", str(resolved), override_used)
    return _json({"success": True, "path": str(resolved), "override_used": override_used})


def claude_repo_terminal(argv: list[str], timeout: int = 120) -> str:
    """Run a tightly allowlisted repo command via argv with cwd locked to the FFT repo."""
    clean, workdir, err = _validate_repo_terminal_argv(argv)
    if err:
        _audit_terminal(clean or [], False, err)
        return _json({"success": False, "allowed": False, "error": err, "argv": clean or argv})
    assert clean is not None and workdir is not None
    try:
        completed = subprocess.run(
            clean,
            cwd=str(workdir),
            shell=False,
            text=True,
            capture_output=True,
            timeout=max(1, min(int(timeout or 120), 300)),
        )
    except subprocess.TimeoutExpired as exc:
        _audit_terminal(clean, False, "timeout", None)
        return _json({
            "success": False,
            "allowed": True,
            "error": "timeout",
            "argv": clean,
            "cwd": str(workdir),
            "stdout": (exc.stdout or "")[-20000:],
            "stderr": (exc.stderr or "")[-20000:],
        })
    except Exception as exc:
        _audit_terminal(clean, False, str(exc), None)
        return _json({"success": False, "allowed": True, "error": str(exc), "argv": clean, "cwd": str(workdir)})
    _audit_terminal(clean, True, "allowed", completed.returncode)
    return _json({
        "success": completed.returncode == 0,
        "allowed": True,
        "argv": clean,
        "cwd": str(workdir),
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-20000:],
        "stderr": completed.stderr[-20000:],
    })


registry.register(
    name="claude_read_file",
    toolset="claude_brain",
    schema={
        "name": "claude_read_file",
        "description": "Read a text file for Claude read-only verification. Secret-like files are denied. Does not provide shell or hashing.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer", "default": 1},
                "limit": {"type": "integer", "default": 500},
            },
            "required": ["path"],
        },
    },
    handler=lambda args, **kw: claude_read_file(args.get("path", ""), args.get("offset", 1), args.get("limit", 500)),
    description="Read text files with secret-deny protections",
)

registry.register(
    name="claude_search_files",
    toolset="claude_brain",
    schema={
        "name": "claude_search_files",
        "description": "Search file names or text content without shell execution. Secret-like files are skipped.",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Python regular expression"},
                "path": {"type": "string", "description": "Base file or directory to search"},
                "target": {"type": "string", "enum": ["content", "files"], "default": "content"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["pattern", "path"],
        },
    },
    handler=lambda args, **kw: claude_search_files(args.get("pattern", ""), args.get("path", ""), args.get("target", "content"), args.get("limit", 50)),
    description="Search files without terminal",
)

registry.register(
    name="claude_brain_write",
    toolset="claude_brain",
    schema={
        "name": "claude_brain_write",
        "description": "Write a complete file. Writes are restricted to configured Commander-authorized roots and are audited.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path under Claude-Brain, or absolute path under a configured allowed write root"},
                "content": {"type": "string"},
                "override_id": {"type": "string", "default": ""},
            },
            "required": ["path", "content"],
        },
    },
    handler=lambda args, **kw: claude_brain_write(args.get("path", ""), args.get("content", ""), args.get("override_id", "")),
    description="Configured-root audited writer",
)

registry.register(
    name="claude_brain_patch",
    toolset="claude_brain",
    schema={
        "name": "claude_brain_patch",
        "description": "Exact string replacement patch. Writes are restricted to configured Commander-authorized roots and are audited.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "replace_all": {"type": "boolean", "default": False},
                "override_id": {"type": "string", "default": ""},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    handler=lambda args, **kw: claude_brain_patch(args.get("path", ""), args.get("old_string", ""), args.get("new_string", ""), bool(args.get("replace_all", False)), args.get("override_id", "")),
    description="Configured-root audited patcher",
)

registry.register(
    name="claude_brain_delete",
    toolset="claude_brain",
    schema={
        "name": "claude_brain_delete",
        "description": "Delete a single file. Deletes are restricted to configured Commander-authorized roots, audited, and directories are denied.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "override_id": {"type": "string", "default": ""},
            },
            "required": ["path"],
        },
    },
    handler=lambda args, **kw: claude_brain_delete(args.get("path", ""), args.get("override_id", "")),
    description="Configured-root audited delete",
)

registry.register(
    name="claude_repo_terminal",
    toolset="claude_brain",
    schema={
        "name": "claude_repo_terminal",
        "description": "Run an allowlisted git or pnpm command in /Users/rfais370/Projects/fft via argv only. No shell, push, arbitrary scripts, or outside-repo paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command argv, e.g. ['git','status','--short'] or ['pnpm','build']",
                },
                "timeout": {"type": "integer", "default": 120},
            },
            "required": ["argv"],
        },
    },
    handler=lambda args, **kw: claude_repo_terminal(args.get("argv", []), args.get("timeout", 120)),
    description="FFT repo scoped git/pnpm terminal",
)
