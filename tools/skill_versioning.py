"""Skill version history — track changes to user skills and enable rollback.

Stores version snapshots under ``~/.hermes/skills/.history/<skill-name>/``.
Each version is a numbered subdirectory containing the full ``SKILL.md``
content.  A ``meta.json`` manifest tracks version metadata (timestamp,
origin, action).

Designed to be called from ``skill_manager_tool``'s create/edit/patch hooks
and from the CLI via ``hermes skills log`` / ``hermes skills revert``.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_cli.config import cfg_get, load_config

logger = logging.getLogger(__name__)

# ── History directory ─────────────────────────────────────────────────────

HISTORY_DIR_NAME = ".history"
MAX_VERSIONS_DEFAULT = 10


def _history_dir(name: str) -> Path:
    """Return the history directory for a named skill.

    Lives under ``SKILLS_DIR / ".history" / <name>``, making it invisible
    to normal skill scanning and tooling.
    """
    from tools.skill_manager_tool import SKILLS_DIR
    return SKILLS_DIR / HISTORY_DIR_NAME / name


def _meta_path(name: str) -> Path:
    """Path to the version manifest."""
    return _history_dir(name) / "meta.json"


def _version_dir(name: str, version_num: int) -> Path:
    """Path to a specific version's snapshot directory."""
    return _history_dir(name) / str(version_num)


def _current_ts() -> str:
    """ISO-8601 timestamp for version metadata."""
    return datetime.now(timezone.utc).isoformat()


def _max_versions() -> int:
    """Read ``skills.max_versions`` from config, fall back to default."""
    try:
        cfg = load_config()
        val = cfg_get(cfg, "skills", "max_versions")
        if val is not None:
            return max(1, int(val))
    except Exception:
        pass
    return MAX_VERSIONS_DEFAULT


# ── Version manifest helpers ──────────────────────────────────────────────


def _read_meta(name: str) -> list:
    """Read the version manifest, returning list of version dicts (oldest first).

    Returns an empty list when the manifest is missing or corrupt.
    """
    path = _meta_path(name)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("versions", [])
    except Exception:
        logger.warning("Corrupt meta.json for skill '%s'; resetting history.", name)
        path.unlink(missing_ok=True)
        return []


def _write_meta(name: str, versions: list) -> None:
    """Persist the version manifest to disk."""
    path = _meta_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"versions": versions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Write origin helper ───────────────────────────────────────────────────


def _current_origin() -> str:
    """Return the active write origin (foreground vs background_review).

    Falls back to ``"foreground"`` when the provenance module is unavailable
    or the ContextVar hasn't been set.
    """
    try:
        from tools.skill_provenance import get_current_write_origin
        return get_current_write_origin() or "foreground"
    except Exception:
        return "foreground"


# ── Core API ──────────────────────────────────────────────────────────────


def save_version(name: str, skill_dir: Path | None = None) -> bool:
    """Snapshot the current SKILL.md as a new version.

    Parameters
    ----------
    name : str
        Skill name (used for the history directory path).
    skill_dir : Path or None
        The skill's directory on disk.  When ``None`` (e.g. from CLI),
        the function looks up the skill via ``_find_skill``.

    Returns
    -------
    bool
        ``True`` when a snapshot was saved, ``False`` when the skill
        doesn't exist or has no SKILL.md on disk.

    Notes
    -----
    Call this *before* making any change you want to preserve the old
    state — the snapshot is taken from the live file.

    Oldest versions are pruned when the total exceeds ``skills.max_versions``
    (default 10), configurable in ``~/.hermes/config.yaml``.
    """
    if skill_dir is None:
        from tools.skill_manager_tool import _find_skill

        existing = _find_skill(name)
        if not existing:
            logger.debug("save_version: skill '%s' not found, skipping.", name)
            return False
        skill_dir = existing["path"]

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        logger.debug("save_version: no SKILL.md at %s, skipping.", skill_md)
        return False

    content = skill_md.read_text(encoding="utf-8")
    if not content.strip():
        return False

    # Determine the next version number
    versions = _read_meta(name)
    next_v = (versions[-1]["v"] + 1) if versions else 1

    # Write the full SKILL.md snapshot
    vdir = _version_dir(name, next_v)
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "SKILL.md").write_text(content, encoding="utf-8")

    # Update the version manifest
    origin = _current_origin()
    entry = {
        "v": next_v,
        "ts": _current_ts(),
        "action": "create" if next_v == 1 else "edit",
        "origin": origin,
    }
    versions.append(entry)
    _write_meta(name, versions)

    # Prune old versions when exceeding the configured limit
    _prune_old(name, versions)

    logger.debug("Saved version %d for skill '%s' (%s)", next_v, name, origin)
    return True


def list_versions(name: str) -> List[Dict[str, Any]]:
    """Return version history for a skill, newest first.

    Each entry has the shape::

        {"v": int, "ts": str, "action": str, "origin": str}

    Returns an empty list when the skill has no history.
    """
    return list(reversed(_read_meta(name)))


def get_version(name: str, version_num: int) -> Optional[str]:
    """Return the SKILL.md content of a specific version, or ``None``."""
    vdir = _version_dir(name, version_num)
    skill_md = vdir / "SKILL.md"
    if not skill_md.exists():
        return None
    return skill_md.read_text(encoding="utf-8")


def revert_skill(name: str, version_num: int) -> Dict[str, Any]:
    """Revert a skill to a previous version.

    The workflow is:

    1. Save the **current** live state as a new version (so the revert
       itself is reversible).
    2. Validate the target version's frontmatter.
    3. Copy the target version's ``SKILL.md`` back to the live skill
       directory.
    4. Run the security scan on the restored content.

    Returns
    -------
    dict
        ``{"success": True, "message": "...", "to_version": N}`` on
        success, or ``{"success": False, "error": "..."}`` on failure.
    """
    from tools.skill_manager_tool import (
        _atomic_write_text,
        _find_skill,
        _security_scan_skill,
        _skill_not_found_error,
        _validate_content_size,
        _validate_frontmatter,
    )

    # 1. Verify the target version exists
    content = get_version(name, version_num)
    if content is None:
        return {
            "success": False,
            "error": f"Version {version_num} not found for skill '{name}'.",
        }

    # 2. Find the skill on disk
    existing = _find_skill(name)
    if not existing:
        return {"success": False, "error": _skill_not_found_error(name)}

    # 3. Validate the old content (it should still be valid)
    err = _validate_frontmatter(content)
    if err:
        return {
            "success": False,
            "error": f"Cannot revert: version {version_num} has invalid frontmatter: {err}",
        }
    err = _validate_content_size(content)
    if err:
        return {
            "success": False,
            "error": f"Cannot revert: version {version_num} exceeds size limit: {err}",
        }

    # 4. Save the current live state as a new version (revert is reversible)
    save_version(name, skill_dir=existing["path"])

    # 5. Write the old content back
    skill_md = existing["path"] / "SKILL.md"
    _atomic_write_text(skill_md, content)

    # 6. Run the security scan on the restored content
    scan_error = _security_scan_skill(existing["path"])
    if scan_error:
        return {
            "success": False,
            "error": f"Revert applied but security scan blocked the result: {scan_error}",
        }

    logger.info("Skill '%s' reverted to version %d", name, version_num)
    return {
        "success": True,
        "message": f"Skill '{name}' reverted to version {version_num}.",
        "to_version": version_num,
    }


# ── Pruning ───────────────────────────────────────────────────────────────


def _prune_old(name: str, versions: list) -> None:
    """Remove the oldest on-disk versions when exceeding ``max_versions``.

    Mutates ``versions`` in place and persists the updated manifest.
    """
    max_v = _max_versions()
    while len(versions) > max_v:
        oldest = versions.pop(0)
        vdir = _version_dir(name, oldest["v"])
        if vdir.exists():
            shutil.rmtree(vdir, ignore_errors=True)
        logger.debug("Pruned version %d for skill '%s'", oldest["v"], name)
    _write_meta(name, versions)


# ── CLI helpers ───────────────────────────────────────────────────────────


def do_skills_log(name: str) -> None:
    """Print version history for a skill to stdout (CLI handler)."""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    versions = list_versions(name)
    if not versions:
        console.print(f"[yellow]No version history found for skill '{name}'.[/yellow]")
        console.print("Version history is created automatically when you edit a skill.")
        return

    table = Table(title=f"Version History: {name}")
    table.add_column("Version", style="cyan", no_wrap=True)
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="green")
    table.add_column("Origin")

    for v in versions:
        origin_label = v.get("origin", "foreground")
        origin_style = "yellow" if origin_label == "background_review" else "white"
        table.add_row(
            str(v["v"]),
            v.get("ts", "?"),
            v.get("action", "?"),
            f"[{origin_style}]{origin_label}[/{origin_style}]",
        )

    console.print(table)
    console.print(f"\nUse [bold]hermes skills revert {name} --to <N>[/bold] to restore a version.")


def do_skills_revert(name: str, to_version: int) -> None:
    """Revert a skill to a specific version (CLI handler)."""
    from rich.console import Console
    console = Console()

    result = revert_skill(name, to_version)
    if result.get("success"):
        console.print(f"[green]{result['message']}[/green]")
    else:
        console.print(f"[red]{result['error']}[/red]")
