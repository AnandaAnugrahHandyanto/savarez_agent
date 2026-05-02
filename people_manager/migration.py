from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CORE_ENTRIES = (
    "registry.json",
    "reports",
    "schedules",
    "prep-queue",
    "reminder-log",
    "session-notes",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _copy_entry(source_root: Path, destination_root: Path, relative_name: str) -> list[str]:
    source = source_root / relative_name
    if not source.exists():
        return []
    destination = destination_root / relative_name
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
        return [str(path.relative_to(destination_root)) for path in destination.rglob("*") if path.is_file()]
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return [relative_name]


def _destination_has_content(destination_root: Path) -> bool:
    return destination_root.exists() and any(destination_root.iterdir())


def _write_manifest(destination: Path, manifest: dict[str, Any]) -> None:
    manifest_dir = destination / "migrations"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / manifest["manifest_name"]).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sync_peopleos_from_profile_root(
    source_root: str | Path,
    destination_root: str | Path,
    *,
    synced_by: str = "jack3",
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    """Import reports that exist in a profile-scoped PeopleOS root but not canonical PeopleOS.

    This is intentionally conservative: existing canonical reports are skipped unless
    overwrite_existing=True, so WebUI edits are not clobbered by an old profile root.
    """
    source = Path(source_root).expanduser()
    destination = Path(destination_root).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"PeopleOS source root not found: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "reports").mkdir(parents=True, exist_ok=True)

    source_registry_path = source / "registry.json"
    destination_registry_path = destination / "registry.json"
    source_registry = json.loads(source_registry_path.read_text(encoding="utf-8")) if source_registry_path.exists() else {"reports": {}}
    destination_registry = json.loads(destination_registry_path.read_text(encoding="utf-8")) if destination_registry_path.exists() else {"version": 1, "reports": {}}
    destination_registry.setdefault("reports", {})

    imported: list[str] = []
    overwritten: list[str] = []
    skipped: list[str] = []
    for report_path in sorted((source / "reports").glob("*.json")):
        slug = report_path.stem
        dest_report_path = destination / "reports" / report_path.name
        exists = dest_report_path.exists()
        if exists and not overwrite_existing:
            skipped.append(slug)
            continue
        shutil.copy2(report_path, dest_report_path)
        source_meta = (source_registry.get("reports") or {}).get(slug) or {"slug": slug}
        destination_registry["reports"][slug] = source_meta
        (overwritten if exists else imported).append(slug)

    destination_registry["updated_at"] = _utc_now_iso()
    destination_registry_path.write_text(json.dumps(destination_registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    reports_dir = destination / "reports"
    manifest_name = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}-sync-profile-root.json"
    manifest = {
        "manifest_name": manifest_name,
        "synced_at": _utc_now_iso(),
        "synced_by": synced_by,
        "source_root": str(source),
        "destination_root": str(destination),
        "imported_reports": imported,
        "overwritten_reports": overwritten,
        "skipped_existing_reports": skipped,
        "profile_count": len(list(reports_dir.glob("*.json"))) if reports_dir.exists() else 0,
    }
    _write_manifest(destination, manifest)
    return manifest


def migrate_peopleos_from_miya(
    source_root: str | Path,
    destination_root: str | Path,
    *,
    force: bool = False,
    migrated_by: str = "jack3",
) -> dict[str, Any]:
    """Copy Miya's profile-scoped PeopleOS data into a canonical PeopleOS data root."""
    source = Path(source_root).expanduser()
    destination = Path(destination_root).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"PeopleOS source root not found: {source}")
    if _destination_has_content(destination):
        if not force:
            raise FileExistsError(f"Destination is not empty: {destination}")
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for entry in CORE_ENTRIES:
        copied_files.extend(_copy_entry(source, destination, entry))

    reports_dir = destination / "reports"
    profile_count = len(list(reports_dir.glob("*.json"))) if reports_dir.exists() else 0
    manifest_name = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}-from-miya-profile.json"
    manifest = {
        "manifest_name": manifest_name,
        "migrated_at": _utc_now_iso(),
        "migrated_by": migrated_by,
        "source_root": str(source),
        "destination_root": str(destination),
        "copied_files": sorted(copied_files),
        "profile_count": profile_count,
    }
    manifest_dir = destination / "migrations"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / manifest_name).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
