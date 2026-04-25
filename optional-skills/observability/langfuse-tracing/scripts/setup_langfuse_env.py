#!/usr/bin/env python3
"""Install the Langfuse tracing plugin from an external repo and persist env wiring."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hermes_cli.config import get_env_path, load_env, save_env_value
from hermes_constants import get_hermes_home

PLUGIN_NAME = "langfuse_tracing"
DEFAULT_FEATURE_REPO = "https://github.com/kshitijk4poor/hermes-langfuse-tracing.git"
DEFAULT_FEATURE_BRANCH = "main"
DEFAULT_PLUGIN_REF = "langfuse-plugin/main"
PLUGIN_FILES = ("__init__.py", "plugin.yaml")
PLUGIN_PATH_CANDIDATES = {
    "__init__.py": (
        "__init__.py",
        "langfuse_tracing/__init__.py",
        ".hermes/plugins/langfuse_tracing/__init__.py",
    ),
    "plugin.yaml": (
        "plugin.yaml",
        "langfuse_tracing/plugin.yaml",
        ".hermes/plugins/langfuse_tracing/plugin.yaml",
    ),
}


@dataclass(frozen=True)
class EnvSetting:
    name: str
    aliases: tuple[str, ...]
    required: bool = False


_SETTINGS = (
    EnvSetting("HERMES_LANGFUSE_ENABLED", ("HERMES_LANGFUSE_ENABLED", "TRACE_TO_LANGFUSE", "CC_LANGFUSE_ENABLED")),
    EnvSetting("HERMES_LANGFUSE_PUBLIC_KEY", ("HERMES_LANGFUSE_PUBLIC_KEY", "CC_LANGFUSE_PUBLIC_KEY", "LANGFUSE_PUBLIC_KEY"), required=True),
    EnvSetting("HERMES_LANGFUSE_SECRET_KEY", ("HERMES_LANGFUSE_SECRET_KEY", "CC_LANGFUSE_SECRET_KEY", "LANGFUSE_SECRET_KEY"), required=True),
    EnvSetting("HERMES_LANGFUSE_BASE_URL", ("HERMES_LANGFUSE_BASE_URL", "CC_LANGFUSE_BASE_URL", "LANGFUSE_BASE_URL")),
    EnvSetting("HERMES_LANGFUSE_ENV", ("HERMES_LANGFUSE_ENV", "LANGFUSE_ENV")),
    EnvSetting("HERMES_LANGFUSE_RELEASE", ("HERMES_LANGFUSE_RELEASE", "LANGFUSE_RELEASE")),
    EnvSetting("HERMES_LANGFUSE_SAMPLE_RATE", ("HERMES_LANGFUSE_SAMPLE_RATE",)),
    EnvSetting("HERMES_LANGFUSE_MAX_CHARS", ("HERMES_LANGFUSE_MAX_CHARS",)),
    EnvSetting("HERMES_LANGFUSE_DEBUG", ("HERMES_LANGFUSE_DEBUG", "CC_LANGFUSE_DEBUG")),
)

_ARG_TO_SETTING = {
    "enable_tracing": "HERMES_LANGFUSE_ENABLED",
    "public_key": "HERMES_LANGFUSE_PUBLIC_KEY",
    "secret_key": "HERMES_LANGFUSE_SECRET_KEY",
    "base_url": "HERMES_LANGFUSE_BASE_URL",
    "environment": "HERMES_LANGFUSE_ENV",
    "release": "HERMES_LANGFUSE_RELEASE",
    "sample_rate": "HERMES_LANGFUSE_SAMPLE_RATE",
    "max_chars": "HERMES_LANGFUSE_MAX_CHARS",
    "debug": "HERMES_LANGFUSE_DEBUG",
}

_DEFAULTS = {
    "HERMES_LANGFUSE_ENABLED": "true",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _plugin_dir() -> Path:
    return get_hermes_home() / "plugins" / PLUGIN_NAME


def _nonempty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _run(argv: list[str], *, cwd: Path | None = None, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _git_ref_exists(ref: str) -> bool:
    try:
        _run(["git", "rev-parse", "--verify", ref], cwd=_repo_root())
        return True
    except subprocess.CalledProcessError:
        return False


def _feature_repo(args: argparse.Namespace) -> str:
    return _nonempty(getattr(args, "feature_repo", None)) or _nonempty(os.environ.get("HERMES_LANGFUSE_FEATURE_REPO")) or DEFAULT_FEATURE_REPO


def _feature_branch(args: argparse.Namespace) -> str:
    return _nonempty(getattr(args, "feature_branch", None)) or _nonempty(os.environ.get("HERMES_LANGFUSE_FEATURE_BRANCH")) or DEFAULT_FEATURE_BRANCH


def _plugin_ref(args: argparse.Namespace) -> str:
    return _nonempty(getattr(args, "plugin_ref", None)) or _nonempty(os.environ.get("HERMES_LANGFUSE_PLUGIN_REF")) or DEFAULT_PLUGIN_REF


def _fetch_plugin_ref(feature_repo: str, feature_branch: str, plugin_ref: str) -> dict[str, Any]:
    if _git_ref_exists(plugin_ref):
        return {"plugin_ref": plugin_ref, "fetched": False, "feature_repo": feature_repo, "feature_branch": feature_branch}

    fetch_ref = f"{feature_branch}:refs/remotes/{plugin_ref}"
    _run(["git", "fetch", feature_repo, fetch_ref], cwd=_repo_root())
    return {"plugin_ref": plugin_ref, "fetched": True, "feature_repo": feature_repo, "feature_branch": feature_branch}


def _read_git_file(plugin_ref: str, candidates: tuple[str, ...]) -> str:
    last_error: subprocess.CalledProcessError | None = None
    for git_path in candidates:
        try:
            result = _run(["git", "show", f"{plugin_ref}:{git_path}"], cwd=_repo_root())
            return result.stdout
        except subprocess.CalledProcessError as exc:
            last_error = exc
    raise RuntimeError(f"Could not locate plugin file in {plugin_ref}. Tried: {', '.join(candidates)}") from last_error


def _write_git_file(plugin_ref: str, filename: str, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = _read_git_file(plugin_ref, PLUGIN_PATH_CANDIDATES[filename])
    destination.write_text(content, encoding="utf-8")
    return str(destination)


def _ensure_langfuse_dependency() -> dict[str, Any]:
    try:
        import langfuse  # noqa: F401
        return {"installed": True, "changed": False}
    except Exception:
        _run([sys.executable, "-m", "pip", "install", "langfuse"], cwd=_repo_root())
        return {"installed": True, "changed": True}


def ensure_langfuse_plugin(args: argparse.Namespace | None = None) -> dict[str, Any]:
    args = args or argparse.Namespace()
    feature_repo = _feature_repo(args)
    feature_branch = _feature_branch(args)
    plugin_ref = _plugin_ref(args)
    fetch_result = _fetch_plugin_ref(feature_repo, feature_branch, plugin_ref)

    plugin_dir = _plugin_dir()
    plugin_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for filename in PLUGIN_FILES:
        files.append(_write_git_file(plugin_ref, filename, plugin_dir / filename))

    return {
        "plugin_dir": str(plugin_dir),
        "plugin_ref": plugin_ref,
        "feature_repo": feature_repo,
        "feature_branch": feature_branch,
        "fetched": fetch_result["fetched"],
        "files": files,
    }


def _existing_alias(setting: EnvSetting, dotenv: dict[str, str]) -> str | None:
    for key in setting.aliases:
        if key in dotenv:
            return key
    return None


def _resolve_value(setting: EnvSetting, args: argparse.Namespace) -> str | None:
    for arg_name, setting_name in _ARG_TO_SETTING.items():
        if setting_name != setting.name:
            continue
        value = _nonempty(getattr(args, arg_name, None))
        if value is not None:
            return value

    for key in setting.aliases:
        value = _nonempty(os.environ.get(key))
        if value is not None:
            return value

    return _DEFAULTS.get(setting.name)


def ensure_langfuse_env(args: argparse.Namespace | None = None) -> dict[str, Any]:
    args = args or argparse.Namespace()
    dotenv = load_env()

    added: dict[str, str] = {}
    preserved: dict[str, str] = {}
    missing: list[str] = []

    for setting in _SETTINGS:
        existing_key = _existing_alias(setting, dotenv)
        if existing_key is not None:
            preserved[setting.name] = existing_key
            continue

        value = _resolve_value(setting, args)
        if value is None:
            if setting.required:
                missing.append(setting.name)
            continue

        save_env_value(setting.name, value)
        dotenv[setting.name] = value
        added[setting.name] = value

    return {
        "success": True,
        "env_path": str(get_env_path()),
        "added": sorted(added.keys()),
        "preserved": preserved,
        "missing": missing,
    }


def _hermes_executable() -> str | None:
    hermes = shutil.which("hermes")
    if hermes:
        return hermes

    candidate = _repo_root() / ".venv" / "bin" / "hermes"
    if candidate.exists():
        return str(candidate)
    return None


def verify_plugin_discovery() -> dict[str, Any]:
    hermes = _hermes_executable()
    if not hermes:
        return {"success": False, "error": "hermes executable not found"}

    result = _run([hermes, "plugins", "list"], cwd=_repo_root())
    output = result.stdout.strip()
    return {"success": PLUGIN_NAME in output, "hermes": hermes, "output": output}


def verify_langfuse_health(base_url: str | None) -> dict[str, Any]:
    resolved = _nonempty(base_url) or _nonempty(os.environ.get("HERMES_LANGFUSE_BASE_URL")) or _nonempty(os.environ.get("LANGFUSE_BASE_URL"))
    if not resolved:
        return {"success": False, "skipped": True, "error": "base_url missing"}

    url = resolved.rstrip("/") + "/api/public/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
        return {"success": True, "url": url, "body": body[:500]}
    except urllib.error.URLError as exc:
        return {"success": False, "url": url, "error": str(exc)}


def ensure_langfuse_setup(args: argparse.Namespace | None = None) -> dict[str, Any]:
    args = args or argparse.Namespace()
    dependency = _ensure_langfuse_dependency()
    plugin = ensure_langfuse_plugin(args)
    env = ensure_langfuse_env(args)
    verification = {
        "plugin_discovery": verify_plugin_discovery(),
        "langfuse_health": verify_langfuse_health(_resolve_value(EnvSetting("HERMES_LANGFUSE_BASE_URL", ("HERMES_LANGFUSE_BASE_URL",)), args)),
    }
    success = not env["missing"] and verification["plugin_discovery"].get("success", False)
    return {
        "success": success,
        "dependency": dependency,
        "plugin": plugin,
        "env": env,
        "verification": verification,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-repo")
    parser.add_argument("--feature-branch")
    parser.add_argument("--plugin-ref")
    parser.add_argument("--public-key")
    parser.add_argument("--secret-key")
    parser.add_argument("--base-url")
    parser.add_argument("--environment")
    parser.add_argument("--release")
    parser.add_argument("--sample-rate")
    parser.add_argument("--max-chars")
    parser.add_argument("--debug")
    parser.add_argument("--enable-tracing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = ensure_langfuse_setup(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
