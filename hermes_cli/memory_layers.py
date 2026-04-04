"""hermes memory layers — private Hermes memory upgrade manager.

Manages the stack of memory-layer repos (honcho, ori-mnemos-ref, and any
custom overlays) that live alongside hermes-agent. Provides:

    hermes memory layers init     — write a starter config (auto-detects repos)
    hermes memory layers apply    — run the unified-memory migration
    hermes memory layers update  — git-pull all layers + apply unified-memory

The config file (~/.hermes/memory-layers.json) lists each memory layer
with its repo path and the sync/apply commands to run on update.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Config path
# ---------------------------------------------------------------------------

MEMORY_LAYERS_DIR = Path.home() / ".hermes"
DEFAULT_CONFIG_PATH = MEMORY_LAYERS_DIR / "memory-layers.json"
DEFAULT_UNIFIED_DB = Path.home() / ".hermes" / "unified_memory.db"


# ---------------------------------------------------------------------------
# Repo discovery
# ---------------------------------------------------------------------------

def _find_git_repo(candidates: list[Path]) -> Optional[Path]:
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate
    return None


def _git_pull_repo(repo: Path, label: str) -> tuple[bool, str]:
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo, capture_output=True, text=True, check=True,
        )
        branch = branch_result.stdout.strip()
        behind_result = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
            cwd=repo, capture_output=True, text=True, check=True,
        )
        behind = int((behind_result.stdout or "0").strip() or "0")
        if behind == 0:
            return True, f"{label}: already up to date on {branch}"
        subprocess.run(
            ["git", "pull", "--ff-only", "origin", branch],
            cwd=repo, check=True, capture_output=True, text=True,
        )
        return True, f"{label}: pulled {behind} commit(s) on {branch}"
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else str(exc)
        return False, f"{label}: git update failed — {detail}"


# ---------------------------------------------------------------------------
# Hermes Python resolver (for running migrations in hermes-agent's venv)
# ---------------------------------------------------------------------------

def _resolve_hermes_python(repo: Optional[Path]) -> Optional[str]:
    candidates = []
    if repo is not None:
        candidates.extend([
            repo / ".venv" / "bin" / "python",
            repo / ".venv-host" / "bin" / "python",
        ])
    system_python = shutil.which("python3") or shutil.which("python")
    if system_python:
        candidates.append(Path(system_python))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _resolve_hermes_repo() -> Optional[Path]:
    return _find_git_repo([
        Path.home() / ".hermes" / "hermes-agent",
        Path.home() / "hermes-agent",
        Path("/workspace/Projects/hermes-agent"),
    ])


# ---------------------------------------------------------------------------
# Unified-memory migration
# ---------------------------------------------------------------------------

def _apply_unified_memory_migration(unified_db: Path) -> tuple[bool, list[str]]:
    repo = _resolve_hermes_repo()
    if repo is None:
        return False, ["⚠ Could not find hermes-agent repo for unified-memory migration"]
    python_bin = _resolve_hermes_python(repo)
    if python_bin is None:
        return False, ["⚠ Could not find a Python interpreter for hermes-agent migration"]

    unified_db = Path(unified_db).expanduser()
    unified_db.parent.mkdir(parents=True, exist_ok=True)

    migration_script = (
        f"import sys; "
        f"sys.path.insert(0, {str(repo)!r}); "
        "from unified_memory.migrate import run_migration; "
        f"run_migration({str(unified_db)!r}, {str(Path.home() / '.hermes')!r})"
    )
    result = subprocess.run(
        [python_bin, "-c", migration_script],
        capture_output=True, text=True,
    )
    messages = [f"Unified memory target: {unified_db}"]
    if result.stdout:
        messages.extend(
            line for line in result.stdout.rstrip().splitlines() if line.strip()
        )
    if result.returncode != 0:
        if result.stderr:
            messages.append(result.stderr.rstrip())
        return False, messages
    return True, messages


# ---------------------------------------------------------------------------
# Config template / load / write
# ---------------------------------------------------------------------------

def _memory_layer_defaults() -> list[dict]:
    return [
        {
            "name": "honcho",
            "repo_candidates": [
                "/workspace/Projects/honcho",
                str(Path.home() / ".hermes" / "honcho"),
                str(Path.home() / "honcho"),
            ],
            "sync_commands": [["uv", "sync"]],
            "apply_commands": [],
        },
        {
            "name": "ori-mnemos-ref",
            "repo_candidates": [
                "/workspace/Projects/ori-mnemos-ref",
                str(Path.home() / ".hermes" / "ori-mnemos-ref"),
                str(Path.home() / "ori-mnemos-ref"),
            ],
            "sync_commands": [],
            "apply_commands": [],
        },
    ]


def _default_memory_layers() -> list[dict]:
    detected = []
    for layer in _memory_layer_defaults():
        repo = _find_git_repo([Path(path) for path in layer["repo_candidates"]])
        if repo is None:
            continue
        detected.append({
            "name": layer["name"],
            "repo": str(repo),
            "sync_commands": layer["sync_commands"],
            "apply_commands": layer["apply_commands"],
        })
    return detected


def _stack_config_template() -> dict:
    layers = _default_memory_layers()
    hermes_repo = _find_git_repo([
        Path.home() / ".hermes" / "hermes-agent",
        Path.home() / "hermes-agent",
        Path("/workspace/Projects/hermes-agent"),
    ])
    if hermes_repo is not None:
        layers.append({
            "name": "memory-overlay",
            "enabled": False,
            "repo": str(hermes_repo),
            "sync_commands": [],
            "apply_commands": [["uv", "run", "python", "scripts/apply_memoria_overlay.py"]],
        })
    return {"memory_layers": layers}


def _load_stack_update_config(config_path: Path) -> tuple[dict, bool]:
    if config_path.exists():
        return json.loads(config_path.read_text()), False
    return {"memory_layers": _default_memory_layers()}, True


def _write_stack_update_config(
    config_path: Path, force: bool = False
) -> tuple[bool, str]:
    if config_path.exists() and not force:
        return False, f"Config already exists: {config_path}"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(_stack_config_template(), indent=2) + "\n")
    return True, f"Wrote memory-layers config: {config_path}"


# ---------------------------------------------------------------------------
# Command execution helpers
# ---------------------------------------------------------------------------

def _command_display(command: list[str]) -> str:
    return " ".join(command)


def _run_configured_command(
    command: list[str], cwd: Optional[Path] = None
) -> tuple[bool, str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, _command_display(command)
    detail = (result.stderr or result.stdout or "unknown error").strip()
    return False, f"{_command_display(command)} — {detail[:240]}"


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

def run_memory_layer_updates(
    config_path: Path,
) -> tuple[bool, list[str]]:
    """Iterate all configured memory layers, git-pull and run their commands.

    Returns (success, messages).
    """
    config, generated = _load_stack_update_config(config_path)
    messages: list[str] = []
    failures = 0

    layers = config.get("memory_layers", [])
    if generated:
        messages.append(
            f"Using auto-detected memory layer config ({config_path} not found)"
        )
    if not layers:
        messages.append("No memory layers configured — skipping memory upgrades")
        return True, messages

    for layer in layers:
        if layer.get("enabled", True) is False:
            continue
        name = layer.get("name", "memory-layer")
        repo_value = layer.get("repo")
        if not repo_value:
            failures += 1
            messages.append(f"⚠ {name}: missing 'repo' in stack config")
            continue
        repo = Path(repo_value).expanduser()
        if not (repo / ".git").exists():
            failures += 1
            messages.append(f"⚠ {name}: repo not found at {repo}")
            continue

        ok, detail = _git_pull_repo(repo, name)
        messages.append(detail)
        if not ok:
            failures += 1
            continue

        for command in layer.get("sync_commands", []):
            ok, detail = _run_configured_command(command, cwd=repo)
            prefix = "✓" if ok else "⚠"
            messages.append(f"{prefix} {name}: {detail}")
            if not ok:
                failures += 1
                break
        else:
            for command in layer.get("apply_commands", []):
                ok, detail = _run_configured_command(command, cwd=repo)
                prefix = "✓" if ok else "⚠"
                messages.append(f"{prefix} {name}: {detail}")
                if not ok:
                    failures += 1
                    break

    return failures == 0, messages


# ---------------------------------------------------------------------------
# CLI command handlers (called from hermes_cli/main.py subparsers)
# ---------------------------------------------------------------------------

def cmd_layers_init(config_path: Path, force: bool) -> int:
    """hermes memory layers init"""
    ok, message = _write_stack_update_config(config_path, force=force)
    if ok:
        print(f"✓ {message}")
        print(
            "  Built-in unified-memory migration is ready; "
            "edit the disabled memory-overlay entry only if you have a custom overlay script."
        )
        return 0
    print(f"⚠ {message}")
    print("  Use --force to overwrite it.")
    return 1


def cmd_layers_apply(unified_db: Path) -> int:
    """hermes memory layers apply"""
    print("🧠 Applying Hermes memory upgrades...")
    ok, messages = _apply_unified_memory_migration(unified_db)
    for message in messages:
        print(f"  {message}")
    print()
    if ok:
        print("✓ hermes memory layers apply complete")
        return 0
    print("⚠ hermes memory layers apply failed")
    return 1


def cmd_layers_update(
    config_path: Path,
    unified_db: Path,
    skip_apply: bool,
) -> int:
    """hermes memory layers update"""
    print("🧠 Updating Hermes memory layers...")
    ok, messages = run_memory_layer_updates(config_path)
    for message in messages:
        print(f"  {message}")

    apply_ok = True
    if not skip_apply:
        print()
        print("→ Applying Hermes memory upgrades...")
        apply_ok, apply_messages = _apply_unified_memory_migration(unified_db)
        for message in apply_messages:
            print(f"  {message}")

    print()
    if ok and apply_ok:
        print("✓ hermes memory layers update complete")
        return 0
    print("⚠ hermes memory layers update failed")
    return 1
