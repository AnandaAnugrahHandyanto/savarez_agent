"""Regression tests for executable Hermes home defaults.

Legacy ``~/.hermes`` references are still allowed in docs, tests, migration code,
and remote/container compatibility paths. Local executable defaults must not
recreate or fall back to the legacy user home. New defaults belong under
``~/.hermes-recommended``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

ACTIVE_PATH_ROOTS = (
    "acp_adapter",
    "agent",
    "cron",
    "gateway",
    "hermes_cli",
    "plugins",
    "scripts",
    "skills",
    "optional-skills",
    "nix",
    "tools",
    "tui_gateway",
    "ui-tui",
)

ACTIVE_ROOT_FILES = (
    "cli.py",
    "hermes_constants.py",
    "hermes_logging.py",
    "hermes_time.py",
    "mcp_serve.py",
    "run_agent.py",
    "setup-hermes.sh",
    "utils.py",
)

CODE_SUFFIXES = {
    ".py",
    ".sh",
    ".bash",
    ".ps1",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".tmpl",
}

FORBIDDEN_LIVE_HOME_PATTERNS = (
    re.compile(r"os\.environ\.setdefault\(\s*[\"']HERMES_HOME[\"'][^\n]*[\"']\.hermes[\"']"),
    re.compile(r"\bHERMES_HOME=.*\$\{HERMES_HOME:-\$HOME/\.hermes\}"),
    re.compile(r"\b[A-Z_]*(?:FILE|DIR|HOME)=.*\$HOME/\.hermes(?:/|[\"'])"),
    re.compile(r"\$HOME/\.hermes/"),
    re.compile(r"HOME/\.hermes/"),
    re.compile(r"\$\{HERMES_HOME:-\$HOME/\.hermes\}"),
    re.compile(r"%h/\.hermes/"),
    re.compile(r"\bPath\.home\(\)\s*/\s*[\"']\.hermes[\"']"),
    re.compile(r"\b_Path\.home\(\)\s*/\s*[\"']\.hermes[\"']"),
    re.compile(r"\bPath\.home\(\)\.joinpath\([\"']\.hermes[\"']"),
    re.compile(r"\bos\.path\.expanduser\([\"']~/\.hermes[\"']\)"),
    re.compile(r"\bexpanduser\([\"']~/\.hermes[\"']\)"),
    re.compile(r"\bos\.getenv\([\"']HERMES_HOME[\"'][^\n]*Path\.home\(\)\s*/\s*[\"']\.hermes[\"']"),
    re.compile(r"\bos\.environ\.get\([\"']HERMES_HOME[\"'][^\n]*Path\.home\(\)\s*/\s*[\"']\.hermes[\"']"),
    re.compile(r"\bos\.environ\.get\([\"']HERMES_HOME[\"'][^\n]*[\"']~/\.hermes[\"']"),
    re.compile(r"\bos\.path\.join\([^\n]*os\.path\.expanduser\([\"']~[\"']\)[^\n]*[\"']\.hermes[\"']"),
    re.compile(r"\bpath\.join\([^\n]*process\.env\.HOME[^\n]*[\"']\.hermes[\"']"),
    re.compile(r"\bjoin\([^\n]*homedir\(\)[^\n]*[\"']\.hermes[\"']"),
)

ALLOWLIST = {
    # Compatibility/migration plugin intentionally names the old home while
    # migrating OpenClaw/Hermes installations.
    "hermes_cli/codex_runtime_plugin_migration.py",
    # Remote/container paths are not local user-home defaults and intentionally
    # preserve mounted/sandbox paths used by execution backends.
    "tools/credential_files.py",
    "tools/environments/daytona.py",
    "tools/environments/file_sync.py",
    "tools/environments/modal.py",
    "tools/environments/ssh.py",
    "tools/environments/vercel_sandbox.py",
}


def _active_files() -> list[Path]:
    files: list[Path] = []
    for root in ACTIVE_PATH_ROOTS:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or not _is_executable_code_file(path):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in ALLOWLIST or "web_dist" in rel:
                continue
            if rel.startswith("tests/") and rel != "tests/test_no_legacy_live_home_paths.py":
                continue
            files.append(path)
    for name in ACTIVE_ROOT_FILES:
        path = REPO_ROOT / name
        if path.exists():
            files.append(path)
    return sorted(files)


def _is_executable_code_file(path: Path) -> bool:
    if path.suffix in CODE_SUFFIXES:
        return True
    if os.access(path, os.X_OK):
        return True
    try:
        return path.read_bytes().startswith(b"#!")
    except OSError:
        return False


def test_active_code_does_not_reference_legacy_live_home() -> None:
    """Guard against reintroducing live/default ``~/.hermes`` fallbacks."""
    offenders: list[str] = []
    for path in _active_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*")):
                continue
            if any(pattern.search(line) for pattern in FORBIDDEN_LIVE_HOME_PATTERNS):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, "legacy live Hermes home references found:\n" + "\n".join(offenders)
