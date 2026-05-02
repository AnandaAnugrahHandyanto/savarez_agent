import json
from pathlib import Path

import pytest

from people_manager.migration import migrate_peopleos_from_miya, sync_peopleos_from_profile_root


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_migrate_peopleos_from_miya_copies_core_data_and_writes_manifest(tmp_path):
    source = tmp_path / "miya" / "people-manager"
    dest = tmp_path / "PeopleOS" / "data"
    _write_json(source / "registry.json", {"reports": {"fiona-cao": {"slug": "fiona-cao"}}})
    _write_json(source / "reports" / "fiona-cao.json", {"slug": "fiona-cao", "name": "Fiona Cao"})
    _write_json(source / "schedules" / "one_on_ones.json", {"profiles": {"fiona-cao": {}}})
    (source / "reminder-log").mkdir(parents=True)
    (source / "reminder-log" / "2026-04.jsonl").write_text('{"slug":"fiona-cao"}\n', encoding="utf-8")
    (source / "session-notes").mkdir(parents=True)
    (source / "session-notes" / "note.md").write_text("note", encoding="utf-8")

    manifest = migrate_peopleos_from_miya(source, dest, migrated_by="test")

    assert (dest / "registry.json").exists()
    assert json.loads((dest / "reports" / "fiona-cao.json").read_text())["name"] == "Fiona Cao"
    assert (dest / "schedules" / "one_on_ones.json").exists()
    assert (dest / "reminder-log" / "2026-04.jsonl").read_text() == '{"slug":"fiona-cao"}\n'
    assert (dest / "session-notes" / "note.md").read_text() == "note"
    assert manifest["profile_count"] == 1
    assert manifest["source_root"] == str(source)
    assert manifest["destination_root"] == str(dest)
    manifest_path = dest / "migrations" / manifest["manifest_name"]
    assert json.loads(manifest_path.read_text())["migrated_by"] == "test"


def test_migrate_peopleos_from_miya_refuses_non_empty_destination_without_force(tmp_path):
    source = tmp_path / "miya" / "people-manager"
    dest = tmp_path / "PeopleOS" / "data"
    _write_json(source / "registry.json", {"reports": {}})
    dest.mkdir(parents=True)
    (dest / "existing.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        migrate_peopleos_from_miya(source, dest)


def test_migrate_peopleos_from_miya_force_overwrites_destination(tmp_path):
    source = tmp_path / "miya" / "people-manager"
    dest = tmp_path / "PeopleOS" / "data"
    _write_json(source / "registry.json", {"reports": {}})
    dest.mkdir(parents=True)
    (dest / "existing.txt").write_text("remove", encoding="utf-8")

    migrate_peopleos_from_miya(source, dest, force=True)

    assert not (dest / "existing.txt").exists()
    assert (dest / "registry.json").exists()


def test_sync_peopleos_from_profile_root_imports_new_reports_without_overwriting_existing(tmp_path):
    source = tmp_path / "miya" / "people-manager"
    dest = tmp_path / "PeopleOS" / "data"
    _write_json(source / "registry.json", {"reports": {
        "fiona-cao": {"slug": "fiona-cao", "name": "Fiona Cao from Miya"},
        "su": {"slug": "su", "name": "Su"},
    }})
    _write_json(source / "reports" / "fiona-cao.json", {"slug": "fiona-cao", "name": "Fiona Cao from Miya"})
    _write_json(source / "reports" / "su.json", {"slug": "su", "name": "Su", "profile_type": "external", "relationship_kind": "investor"})
    _write_json(dest / "registry.json", {"reports": {"fiona-cao": {"slug": "fiona-cao", "name": "Canonical Fiona"}}})
    _write_json(dest / "reports" / "fiona-cao.json", {"slug": "fiona-cao", "name": "Canonical Fiona"})

    manifest = sync_peopleos_from_profile_root(source, dest, synced_by="test")

    assert manifest["imported_reports"] == ["su"]
    assert manifest["skipped_existing_reports"] == ["fiona-cao"]
    assert json.loads((dest / "reports" / "fiona-cao.json").read_text())["name"] == "Canonical Fiona"
    assert json.loads((dest / "reports" / "su.json").read_text())["relationship_kind"] == "investor"
    registry = json.loads((dest / "registry.json").read_text())
    assert registry["reports"]["su"]["slug"] == "su"
    assert (dest / "migrations" / manifest["manifest_name"]).exists()
