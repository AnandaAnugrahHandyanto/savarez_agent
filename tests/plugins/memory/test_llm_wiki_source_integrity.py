"""Tests for explicit LLM Wiki raw-source hash audit/repair."""

from __future__ import annotations

import json

import pytest

from hermes_wiki.config import WikiConfig
from hermes_wiki.frontmatter import read_page, write_page
from hermes_wiki.source_integrity import (
    audit_source_hashes,
    repair_source_hashes,
    source_integrity_report_to_dict,
)
from hermes_wiki.source_integrity import (
    main as source_integrity_main,
)


def _config(tmp_path):
    return WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")


def _write_source(config, rel_path="raw/articles/source.md", body="# Source\n\nBody.", sha256="0" * 64):
    path = config.wiki_path / rel_path
    write_page(path, {"source_url": "", "ingested": "2026-01-01", "sha256": sha256}, body)
    return path


def test_audit_source_hashes_detects_drift_without_writing(tmp_path):
    config = _config(tmp_path)
    source_path = _write_source(config)
    before = source_path.read_text(encoding="utf-8")

    report = audit_source_hashes(config)

    assert report.total_sources == 1
    assert report.drifted_sources == 1
    assert report.records[0].relative_path == "raw/articles/source.md"
    assert report.records[0].status == "drifted"
    assert source_path.read_text(encoding="utf-8") == before


def test_repair_source_hashes_updates_only_raw_source_frontmatter(tmp_path):
    config = _config(tmp_path)
    source_path = _write_source(config)
    canonical = config.wiki_path / "concepts" / "canonical.md"
    write_page(
        canonical,
        {"title": "Canonical", "type": "concept", "created": "2026-01-01", "updated": "2026-01-01"},
        "Canonical body.",
    )
    canonical_before = canonical.read_text(encoding="utf-8")

    report = repair_source_hashes(config, write=True)
    fm, body = read_page(source_path)
    after = audit_source_hashes(config)

    assert report.updated_sources == 1
    assert fm["sha256"] == report.records[0].actual_sha256
    assert body == "# Source\n\nBody."
    assert canonical.read_text(encoding="utf-8") == canonical_before
    assert after.drifted_sources == 0


def test_repair_source_hashes_rejects_nonbool_write_flag(tmp_path):
    config = _config(tmp_path)
    source_path = _write_source(config)
    before = source_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="write"):
        repair_source_hashes(config, write={"enabled": True})  # type: ignore[arg-type]

    assert source_path.read_text(encoding="utf-8") == before


def test_source_integrity_report_to_dict_is_json_serializable(tmp_path):
    config = _config(tmp_path)
    _write_source(config)

    payload = source_integrity_report_to_dict(audit_source_hashes(config))

    assert json.loads(json.dumps(payload))["drifted_sources"] == 1
    assert payload["records"][0]["status"] == "drifted"


def test_audit_source_hashes_tolerates_non_mapping_frontmatter(tmp_path):
    config = _config(tmp_path)
    source = config.raw_dir / "articles" / "bad.md"
    source.parent.mkdir(parents=True)
    source.write_text("---\nscalar\n---\nsource body\n", encoding="utf-8")

    report = audit_source_hashes(config)

    assert report.total_sources == 1
    assert report.missing_hashes == 1


def test_audit_source_hashes_treats_nonscalar_sha256_as_missing(tmp_path):
    config = _config(tmp_path)
    source = config.wiki_path / "raw/articles/source.md"
    source.parent.mkdir(parents=True)
    source.write_text("---\nsource_url: ''\ningested: '2026-01-01'\nsha256:\n  bad: hash\n---\n\n# Source\n\nBody.\n", encoding="utf-8")

    report = audit_source_hashes(config)
    record = report.records[0]

    assert report.missing_hashes == 1
    assert record.status == "missing_hash"
    assert record.stored_sha256 is None


def test_audit_source_hashes_treats_malformed_scalar_sha256_as_missing(tmp_path):
    config = _config(tmp_path)
    source = _write_source(config, sha256="abc123")
    before = source.read_text(encoding="utf-8")

    report = audit_source_hashes(config)
    record = report.records[0]

    assert report.missing_hashes == 1
    assert report.drifted_sources == 0
    assert record.status == "missing_hash"
    assert record.stored_sha256 is None
    assert source.read_text(encoding="utf-8") == before


def test_explicit_config_loader_rejects_nonscalar_path():
    from hermes_wiki.source_integrity import _load_explicit_wiki_config

    with pytest.raises(ValueError, match="config_path"):
        _load_explicit_wiki_config({"path": "config.yaml"})  # type: ignore[arg-type]



def test_cli_audit_is_read_only_by_default(tmp_path, capsys):
    config = _config(tmp_path)
    source_path = _write_source(config)
    before = source_path.read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"wiki:\n  path: {config.wiki_path}\n  name: test\n", encoding="utf-8")

    code = source_integrity_main(["--config", str(config_path), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["drifted_sources"] == 1
    assert source_path.read_text(encoding="utf-8") == before


def test_cli_repair_requires_explicit_config(tmp_path, monkeypatch):
    ambient_home = tmp_path / "ambient"
    monkeypatch.setenv("LLM_WIKI_HOME", str(ambient_home))

    try:
        source_integrity_main(["--repair"])
    except SystemExit:
        pass

    assert not ambient_home.exists()


def test_cli_repair_updates_hash_with_explicit_config(tmp_path, capsys):
    config = _config(tmp_path)
    _write_source(config)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"wiki:\n  path: {config.wiki_path}\n  name: test\n", encoding="utf-8")

    code = source_integrity_main(["--config", str(config_path), "--repair", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["updated_sources"] == 1
    assert audit_source_hashes(config).drifted_sources == 0


class SourceIntegrityLeakyObject:
    def __str__(self):
        return "SOURCE-INTEGRITY-LEAK"


def test_source_integrity_report_to_dict_normalizes_malformed_direct_records():
    from hermes_wiki.source_integrity import SourceHashRecord, SourceIntegrityReport

    report = SourceIntegrityReport(
        records=[
            SourceHashRecord(
                relative_path=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
                stored_sha256=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
                actual_sha256=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
                status=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
            ),
            SourceIntegrityLeakyObject(),  # type: ignore[list-item]
        ],
        updated_sources=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
    )

    payload = source_integrity_report_to_dict(report)
    assert payload == {
        "total_sources": 1,
        "ok_sources": 0,
        "missing_hashes": 0,
        "drifted_sources": 0,
        "updated_sources": 0,
        "records": [
            {"relative_path": "", "stored_sha256": None, "actual_sha256": "", "status": "unknown"}
        ],
    }
    assert "SOURCE-INTEGRITY-LEAK" not in str(payload)


def test_render_source_integrity_report_normalizes_malformed_direct_records():
    from hermes_wiki.source_integrity import (
        SourceHashRecord,
        SourceIntegrityReport,
        render_source_integrity_report,
    )

    report = SourceIntegrityReport(
        records=[
            SourceHashRecord(
                relative_path=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
                stored_sha256=None,
                actual_sha256="abc123",
                status=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
            ),
            SourceIntegrityLeakyObject(),  # type: ignore[list-item]
        ],
        updated_sources=SourceIntegrityLeakyObject(),  # type: ignore[arg-type]
    )

    rendered = render_source_integrity_report(report)
    assert "SOURCE-INTEGRITY-LEAK" not in rendered
    assert "- Sources: 1" in rendered
    assert "- Updated sources: 0" in rendered
    assert "- **unknown** ``" in rendered
