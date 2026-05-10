#!/usr/bin/env python3
"""Verify OpenClaw profile-local cron jobs were migrated to global jobs.json.

Checks the known imported OpenClaw profiles under ~/.hermes/profiles/*/cron/jobs.json:
- every profile-local job id exists in ~/.hermes/cron/jobs.json
- the global copy has canonical `profile` equal to the source profile
- profile-local duplicates are neutralized (not enabled/scheduled)
- the existing global Haven watchdog remains present
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from hermes_constants import get_default_hermes_root

PROFILES = [
    "dev",
    "knox",
    "atlas",
    "vector",
    "orion",
    "nova",
    "canon",
    "halo",
    "snip",
    "haven",
    "elon",
    "sterling",
]
HAVEN_WATCHDOG_ID = "698ce0ffa615"


def load_jobs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("jobs", []))


def is_neutralized(job: dict) -> bool:
    return job.get("enabled") is False or job.get("state") in {
        "migrated_to_global",
        "paused",
        "disabled",
    }


def main() -> int:
    root = get_default_hermes_root()
    global_path = root / "cron" / "jobs.json"
    global_jobs = load_jobs(global_path)
    global_by_id = {job.get("id"): job for job in global_jobs if job.get("id")}

    errors: list[str] = []
    checked = 0

    if HAVEN_WATCHDOG_ID not in global_by_id:
        errors.append(f"existing global Haven watchdog missing: {HAVEN_WATCHDOG_ID}")

    for profile in PROFILES:
        local_path = root / "profiles" / profile / "cron" / "jobs.json"
        for local in load_jobs(local_path):
            job_id = local.get("id")
            if not job_id:
                errors.append(f"{local_path}: job missing id")
                continue
            checked += 1
            migrated = global_by_id.get(job_id)
            if not migrated:
                errors.append(f"{profile}:{job_id} remains only in profile-local cron file")
                continue
            if migrated.get("profile") != profile:
                errors.append(
                    f"{profile}:{job_id} global profile mismatch: "
                    f"expected {profile!r}, got {migrated.get('profile')!r}"
                )
            if not is_neutralized(local):
                errors.append(f"{profile}:{job_id} profile-local duplicate is still active")

    if errors:
        print("Cron profile migration verification FAILED:")
        for error in errors:
            print(f"- {error}")
        print(f"Checked profile-local jobs: {checked}")
        print(f"Global jobs: {len(global_jobs)}")
        return 1

    print("Cron profile migration verification OK")
    print(f"Checked profile-local jobs: {checked}")
    print(f"Global jobs: {len(global_jobs)}")
    print("Canonical assignment field: profile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
