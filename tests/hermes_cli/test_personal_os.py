from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from hermes_cli.personal_os import cli_main
from hermes_cli.personal_os_index import PersonalOSIndex, path_allowed_for_scope


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_indexes_and_searches_markdown_with_citations(tmp_path):
    vault = tmp_path / "personal OS"
    db = tmp_path / "index.db"
    _write(
        vault / "HOME.md",
        "# Home\n\nPractical command centre. Kadri attic documents live in Areas/Personal.",
    )
    _write(
        vault / "Areas" / "Personal" / "Kadri apartment.md",
        "---\ntags: [home, legal]\ntitle: Kadri apartment attic\n---\n# Kadri apartment attic\n\nAdamsoni 22 pööning ownership and legal-status notes.",
    )

    idx = PersonalOSIndex(vault_root=vault, db_path=db)
    stats = idx.index_changed()

    assert stats.indexed_files == 2
    result = idx.search("Adamsoni pööning", scope="default", limit=5)
    assert result["matches"]
    best = result["matches"][0]
    assert best["path"] == "Areas/Personal/Kadri apartment.md"
    assert best["title"] == "Kadri apartment attic"
    assert "Adamsoni" in best["snippet"]
    assert best["tags"] == ["home", "legal"]


def test_default_scope_excludes_health_and_family_sensitive_notes(tmp_path):
    vault = tmp_path / "vault"
    db = tmp_path / "index.db"
    _write(vault / "Areas" / "Personal" / "Health" / "Headache.md", "# Headache\n\nMigraine medicine notes.")
    _write(vault / "Areas" / "Personal" / "Family Milene.md", "# Milene\n\nSchool logistics.")
    _write(vault / "Family.md", "# Family\n\nSchool calendar root note.")
    _write(vault / "health.md", "# health\n\nMedical root note.")
    _write(vault / "Areas" / "Personal" / "Bike.md", "# Bike\n\n6KU brake pads.")

    idx = PersonalOSIndex(vault_root=vault, db_path=db)
    idx.index_changed()

    default_paths = {m["path"] for m in idx.search("notes school brake medical", scope="default", limit=10)["matches"]}
    assert "Areas/Personal/Bike.md" in default_paths
    assert "Areas/Personal/Health/Headache.md" not in default_paths
    assert "Areas/Personal/Family Milene.md" not in default_paths
    assert "Family.md" not in default_paths
    assert "health.md" not in default_paths

    health_paths = {m["path"] for m in idx.search("Migraine", scope="health", limit=10)["matches"]}
    assert health_paths == {"Areas/Personal/Health/Headache.md"}


def test_scope_rules_include_root_files_and_reject_unknown_scope():
    assert path_allowed_for_scope("HOME.md", "default")
    assert path_allowed_for_scope("Open Loops.md", "family")
    assert not path_allowed_for_scope("Areas/Personal/Health/Headache.md", "default")
    with pytest.raises(ValueError):
        path_allowed_for_scope("HOME.md", "bogus")


def test_zero_byte_files_are_skipped_as_possibly_unsynced(tmp_path):
    vault = tmp_path / "vault"
    db = tmp_path / "index.db"
    _write(vault / "Real.md", "# Real\n\nSearchable content.")
    _write(vault / "Unsynced.md", "")

    idx = PersonalOSIndex(vault_root=vault, db_path=db)
    stats = idx.index_changed()

    assert stats.indexed_files == 1
    assert stats.skipped_files == 1
    assert stats.warnings == [{"path": "Unsynced.md", "reason": "zero_byte_possibly_unsynced"}]
    result = idx.search("Searchable", scope="all")
    assert result["warnings"] == [
        {
            "rel_path": "Unsynced.md",
            "reason": "zero_byte_possibly_unsynced",
            "detail": "",
            "skipped_at": result["warnings"][0]["skipped_at"],
        }
    ]


def test_skipped_file_deletes_previous_indexed_content(tmp_path):
    vault = tmp_path / "vault"
    db = tmp_path / "index.db"
    note = vault / "Note.md"
    _write(note, "# Note\n\nUnique old searchable content.")
    idx = PersonalOSIndex(vault_root=vault, db_path=db)
    idx.index_changed()
    assert idx.search("Unique old", scope="all")["matches"]

    note.write_text("", encoding="utf-8")
    stats = idx.index_changed()

    assert stats.skipped_files == 1
    assert idx.search("Unique old", scope="all")["matches"] == []


def test_scope_filter_applies_before_limited_retrieval(tmp_path):
    vault = tmp_path / "vault"
    db = tmp_path / "index.db"
    for i in range(30):
        _write(vault / "Areas" / "Personal" / "Health" / f"Sensitive {i}.md", f"# Sensitive {i}\n\nneedle private health note {i}.")
    _write(vault / "Areas" / "Personal" / "Bike.md", "# Bike\n\nneedle public bike note.")
    idx = PersonalOSIndex(vault_root=vault, db_path=db)
    idx.index_changed()

    result = idx.search("needle", scope="default", limit=1)

    assert [m["path"] for m in result["matches"]] == ["Areas/Personal/Bike.md"]


def test_db_path_inside_vault_is_rejected(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(ValueError, match="must not be inside the vault"):
        PersonalOSIndex(vault_root=vault, db_path=vault / ".personal-os-index.db")


def test_index_db_permissions_are_restrictive(tmp_path):
    vault = tmp_path / "vault"
    db = tmp_path / "cache" / "index.db"
    _write(vault / "Note.md", "# Note\n\npermissions")

    idx = PersonalOSIndex(vault_root=vault, db_path=db)
    idx.index_changed()

    assert stat.S_IMODE(db.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(db.stat().st_mode) == 0o600


def test_cli_index_and_search_json(tmp_path, capsys):
    vault = tmp_path / "vault"
    db = tmp_path / "index.db"
    _write(vault / "Shopping list.md", "# Shopping\n\nBuy oat milk and printer paper.")

    assert cli_main(["index", "--vault-root", str(vault), "--db-path", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["indexed_files"] == 1

    assert cli_main(["search", "oat milk", "--scope", "shopping", "--vault-root", str(vault), "--db-path", str(db), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["matches"][0]["path"] == "Shopping list.md"


def test_cli_search_missing_vault_returns_error_json(tmp_path, capsys):
    db = tmp_path / "index.db"

    assert cli_main(["search", "anything", "--vault-root", str(tmp_path / "missing"), "--db-path", str(db), "--json"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "vault_root_missing"


def test_doctor_reports_missing_vault(tmp_path):
    idx = PersonalOSIndex(vault_root=tmp_path / "missing", db_path=tmp_path / "index.db")

    report = idx.doctor()

    assert report["vault_exists"] is False
    assert report["indexed_files"] == 0
