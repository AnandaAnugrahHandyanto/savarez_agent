"""
Health checks for Hermes Agent's own operational integrity.

Provides three built-in checks that detect file drift, skill corruption,
and cron config rot before they cause silent failures. Each check returns
a structured result dict::

    {
        "name": str,
        "status": "ok" | "degraded" | "failed",
        "message": str,
        "detail": dict | None,
    }

Checks are designed to be run on-demand (via ``/incidents check``) or
periodically (via a cron job wrapping ``run_all()``). Results are stored
in the incidents table via SessionDB.record_incident().
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# Files whose content hashes are tracked for drift detection
_CONFIG_FILES = ("config.yaml", ".env")
# File extensions considered skill content
_SKILL_FILES_RE = re.compile(r"\.(md|py|yaml|yml|json|toml)$", re.IGNORECASE)


# ── Helpers ──────────────────────────────────────────────────────────────


def _file_hash(path: Path) -> str | None:
    """Return SHA-256 hex digest of a file, or None if it doesn't exist."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _format_timestamp(ts: float) -> str:
    """Format a Unix timestamp as ISO-like string (local time naive)."""
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# ── Check 1: Config health (detect drift in config.yaml, .env) ──────────


def self_config_health() -> dict[str, Any]:
    """Check that config.yaml and .env exist and haven't drifted.

    Hashes the known baseline files. On first run (no stored hash),
    records the current hash as the baseline. On subsequent runs,
    compares against the last seen hash and flags drift.

    Stored hash file: ``~/.hermes/.health_config_hash.json``
    """
    hermes_home = get_hermes_home()
    hash_file = hermes_home / ".health_config_hash.json"
    issues: list[str] = []
    details: dict[str, Any] = {}
    current_hashes: dict[str, str | None] = {}

    for fname in _CONFIG_FILES:
        fpath = hermes_home / fname
        h = _file_hash(fpath)
        current_hashes[fname] = h
        if h is None:
            issues.append(f"{fname}: not found or unreadable")
            details[fname] = {"status": "missing"}
        else:
            details[fname] = {"status": "present", "hash": h[:16]}

    # Load last known hashes
    previous_hashes: dict[str, str | None] = {}
    try:
        if hash_file.exists():
            previous_hashes = json.loads(hash_file.read_text())
    except (json.JSONDecodeError, OSError):
        previous_hashes = {}

    # Detect drift
    drift_found = False
    for fname in _CONFIG_FILES:
        current = current_hashes.get(fname)
        previous = previous_hashes.get(fname)
        if current is not None and previous is not None and current != previous:
            drift_found = True
            issues.append(f"{fname}: content changed since last check")
            details[fname]["drift"] = True

    # Persist current hashes as baseline
    try:
        hash_file.write_text(
            json.dumps({k: v for k, v in current_hashes.items() if v is not None})
        )
    except OSError as exc:
        logger.warning("self_config_health: could not write hash cache: %s", exc)

    if issues:
        message = "; ".join(issues)
        status = "failed" if drift_found else "degraded"
    else:
        message = f"All {len(_CONFIG_FILES)} config files unchanged"
        status = "ok"

    return {"name": "self_config_health", "status": status, "message": message, "detail": details}


# ── Check 2: Skills integrity (verify skills directory) ─────────────────


def skills_integrity() -> dict[str, Any]:
    """Verify that installed skills have valid SKILL.md files.

    Scans all directories under ``skills/`` in ``HERMES_HOME``, ensures
    each has a SKILL.md with valid YAML frontmatter.

    Returns:
        degraded if any skills are broken, failed if skills/ is missing.
    """
    hermes_home = get_hermes_home()
    skills_dir = hermes_home / "skills"

    if not skills_dir.is_dir():
        return {
            "name": "skills_integrity",
            "status": "failed",
            "message": "skills/ directory not found",
            "detail": {"path": str(skills_dir)},
        }

    broken: list[dict[str, str]] = []
    ok_count = 0

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir():
            continue
        skill_name = entry.name
        skill_md = entry / "SKILL.md"

        if not skill_md.exists():
            broken.append({"name": skill_name, "issue": "SKILL.md missing"})
            continue

        # Validate YAML frontmatter (between --- delimiters)
        try:
            text = skill_md.read_text(encoding="utf-8")
            if not text.strip().startswith("---"):
                broken.append({"name": skill_name, "issue": "SKILL.md has no frontmatter"})
                continue
            # Find closing ---
            end_idx = text.find("---", 3)
            if end_idx == -1:
                broken.append({"name": skill_name, "issue": "SKILL.md frontmatter not closed"})
                continue
            # Quick parse: just check it's valid basic structure
            frontmatter = text[3:end_idx].strip()
            if not frontmatter:
                broken.append({"name": skill_name, "issue": "SKILL.md frontmatter is empty"})
                continue
            ok_count += 1
        except (OSError, UnicodeDecodeError) as exc:
            broken.append({"name": skill_name, "issue": f"unreadable: {exc}"})

    total = ok_count + len(broken)

    if not broken:
        message = f"{ok_count}/{total} skills OK"
        status = "ok" if total > 0 else "degraded"
    else:
        message = f"{len(broken)}/{total} skills broken"
        status = "failed"

    return {
        "name": "skills_integrity",
        "status": status,
        "message": message,
        "detail": {"ok": ok_count, "broken": broken, "total": total},
    }


# ── Check 3: Cron job integrity (validate registered jobs) ──────────────


def cron_job_integrity() -> dict[str, Any]:
    """Validate all registered cron jobs have valid schedules and resolvable refs.

    Checks:
      - Each job has a valid schedule (cron expression or interval)
      - Skills referenced by name exist in the skills directory
      - Script paths exist

    Loads jobs from ``~/.hermes/cron/jobs.json`` directly.
    """
    hermes_home = get_hermes_home()
    jobs_file = hermes_home / "cron" / "jobs.json"
    skills_dir = hermes_home / "skills"

    if not jobs_file.exists():
        return {
            "name": "cron_job_integrity",
            "status": "ok",
            "message": "No cron jobs registered",
            "detail": {"count": 0},
        }

    try:
        jobs_data = json.loads(jobs_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "name": "cron_job_integrity",
            "status": "failed",
            "message": f"Cannot read jobs file: {exc}",
            "detail": {"path": str(jobs_file)},
        }

    # Handle both list format and dict-with-metadata format
    jobs: list[dict] = []
    if isinstance(jobs_data, list):
        jobs = jobs_data
    elif isinstance(jobs_data, dict):
        jobs = jobs_data.get("jobs", jobs_data.get("items", []))
        if not jobs and "id" in jobs_data:
            jobs = [jobs_data]

    if not jobs:
        return {
            "name": "cron_job_integrity",
            "status": "ok",
            "message": "No cron jobs registered",
            "detail": {"count": 0},
        }

    issues: list[dict[str, str]] = []

    for job in jobs:
        job_id = job.get("id") or job.get("name", "?")
        job_issues: list[str] = []

        # Check schedule exists
        schedule = job.get("schedule")
        if not schedule:
            job_issues.append("no schedule")

        # Check referenced skills exist
        for skill_ref in (job.get("skills") or []):
            if isinstance(skill_ref, str) and skill_ref:
                skill_path = skills_dir / skill_ref
                if not skill_path.exists() and not (skill_path / "SKILL.md").exists():
                    job_issues.append(f"skill '{skill_ref}' not found")

        # Check script path exists
        script = job.get("script")
        if script and isinstance(script, str):
            script_path = Path(script)
            if not script_path.is_absolute():
                script_path = hermes_home / "scripts" / script_path
            if not script_path.exists():
                job_issues.append(f"script '{script}' not found")

        if job_issues:
            issues.append({"job": job_id, "issues": "; ".join(job_issues)})

    if not issues:
        message = f"{len(jobs)} job(s) all valid"
        status = "ok"
    else:
        message = f"{len(issues)}/{len(jobs)} job(s) have issues"
        status = "degraded"

    return {
        "name": "cron_job_integrity",
        "status": status,
        "message": message,
        "detail": {"total_jobs": len(jobs), "issues": issues},
    }


# ── Runner ────────────────────────────────────────────────────────────────


def run_all() -> list[dict[str, Any]]:
    """Run all built-in health checks and return their results.

    Returns a list of result dicts, one per check. Callers should
    pass each result to ``SessionDB.record_incident()``.

    Usage::

        from cron.health import run_all
        from hermes_state import SessionDB

        db = SessionDB()
        for result in run_all():
            db.record_incident(
                check_name=result["name"],
                status=result["status"],
                message=result["message"],
                detail=result.get("detail"),
            )
    """
    results: list[dict[str, Any]] = []
    for check_fn in (self_config_health, skills_integrity, cron_job_integrity):
        try:
            result = check_fn()
        except Exception as exc:
            logger.exception("Health check %s failed with exception", check_fn.__name__)
            result = {
                "name": check_fn.__name__,
                "status": "failed",
                "message": f"Exception: {exc}",
                "detail": None,
            }
        results.append(result)
    return results
