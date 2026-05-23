import json

import pytest

from hermes_wiki.config import WikiConfig
from hermes_wiki.frontmatter import write_page
from hermes_wiki.maintenance import (
    generate_maintenance_report,
    maintenance_report_to_dict,
    render_maintenance_report,
)
from hermes_wiki.maintenance import main as maintenance_main


def _write_page(config, rel_path, fm, body):
    path = config.wiki_path / rel_path
    write_page(path, fm, body)
    return path


def test_generate_maintenance_report_detects_broken_links_and_orphans(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    _write_page(
        config,
        "concepts/a.md",
        {"title": "A", "type": "concept", "created": "2026-01-01", "updated": "2026-01-01"},
        "Links to [[Missing Page]].",
    )
    _write_page(
        config,
        "concepts/orphan.md",
        {"title": "Orphan", "type": "concept", "created": "2026-01-01", "updated": "2026-01-01"},
        "No inbound links.",
    )

    report = generate_maintenance_report(config)

    categories = {issue.category for issue in report.issues}
    assert "broken_link" in categories
    assert "orphan_page" in categories
    assert report.total_pages == 2
    assert report.broken_links == 1
    assert report.orphan_pages >= 1


def test_generate_maintenance_report_ignores_legacy_proposal_directory(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    legacy = config.wiki_path / "proposals" / "old.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("---\ntitle: Old proposal\nstatus: pending\n---\nBody.\n", encoding="utf-8")

    report = generate_maintenance_report(config)
    payload = maintenance_report_to_dict(report)

    assert not hasattr(report, "pending_proposals")
    assert "pending_proposals" not in payload
    assert all(issue.category != "pending_proposal" for issue in report.issues)


def test_generate_maintenance_report_detects_source_coverage_gap(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    _write_page(
        config,
        "concepts/no-source.md",
        {"title": "No Source", "type": "concept", "created": "2026-01-01", "updated": "2026-01-01"},
        "This page has no provenance marker.",
    )

    report = generate_maintenance_report(config)
    assert report.pages_without_sources == 1
    assert any(issue.category == "missing_source_coverage" for issue in report.issues)


def test_generate_maintenance_report_tolerates_non_mapping_frontmatter(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    page = config.wiki_path / "concepts" / "bad.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\n- not\n- mapping\n---\n[[missing]]\n", encoding="utf-8")

    report = generate_maintenance_report(config)

    assert report.total_pages == 1
    assert report.broken_links == 1


def test_maintenance_helpers_reject_nonscalar_config_and_report_paths(tmp_path):
    from hermes_wiki.maintenance import _load_explicit_wiki_config, _validate_report_path

    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    with pytest.raises(ValueError, match="config_path"):
        _load_explicit_wiki_config({"path": "config.yaml"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="report_path"):
        _validate_report_path(config, {"path": "reports/out.md"})  # type: ignore[arg-type]


def test_generate_maintenance_report_rejects_malformed_source_coverage_paths(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    page = config.wiki_path / "concepts" / "bad-source-paths.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "---\n"
        "title: Bad Source Paths\n"
        "type: concept\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "sources:\n"
        "  - /etc/hosts\n"
        "  - raw/articles/../../outside.md\n"
        "---\n\n"
        "Body cites ^[raw/articles/../../outside.md].\n",
        encoding="utf-8",
    )

    report = generate_maintenance_report(config)

    assert report.pages_without_sources == 1
    categories = {issue.category for issue in report.issues if issue.file_path == "concepts/bad-source-paths.md"}
    assert "invalid_source_path" in categories
    assert "missing_source_coverage" in categories


def test_generate_maintenance_report_rejects_nonscalar_source_entries(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    page = config.wiki_path / "concepts/object-source.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "---\n"
        "title: Object Source\n"
        "type: concept\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "sources:\n  - path: raw/articles/source.md\n"
        "---\n\n"
        "This page has object-shaped provenance only.\n",
        encoding="utf-8",
    )

    report = generate_maintenance_report(config)

    assert report.pages_without_sources == 1
    assert any(
        issue.category == "missing_source_coverage" and issue.file_path == "concepts/object-source.md"
        for issue in report.issues
    )


def test_maintenance_report_to_dict_is_json_serializable(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    _write_page(
        config,
        "concepts/a.md",
        {"title": "A", "type": "concept", "created": "2026-01-01", "updated": "2026-01-01"},
        "Body.",
    )

    payload = maintenance_report_to_dict(generate_maintenance_report(config))

    assert json.loads(json.dumps(payload))["total_pages"] == 1
    assert "issues" in payload


def test_render_maintenance_report_contains_summary(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    _write_page(
        config,
        "concepts/a.md",
        {"title": "A", "type": "concept", "created": "2026-01-01", "updated": "2026-01-01"},
        "Body.",
    )

    text = render_maintenance_report(generate_maintenance_report(config))

    assert "# LLM Wiki Maintenance Report" in text
    assert "Pages:" in text
    assert "Issues:" in text


def test_maintenance_cli_is_read_only_by_default(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")

    code = maintenance_main(["--config", str(config_path)])

    assert code == 0
    assert "# LLM Wiki Maintenance Report" in capsys.readouterr().out
    assert not wiki_path.exists()


def test_maintenance_cli_write_report_requires_explicit_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "ambient-home"))

    try:
        maintenance_main(["--write-report", "reports/maintenance.md"])
    except SystemExit:
        pass

    assert not (tmp_path / "ambient-home").exists()


def test_maintenance_cli_write_report_allows_reports_namespace_only(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")

    code = maintenance_main(["--config", str(config_path), "--write-report", "reports/maintenance.md"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload == {"path": str(wiki_path / "reports" / "maintenance.md"), "written": True}
    assert (wiki_path / "reports" / "maintenance.md").exists()


def test_maintenance_cli_write_report_rejects_canonical_paths(tmp_path):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")
    canonical = _write_page(
        WikiConfig(wiki_path=wiki_path, wiki_name="test"),
        "concepts/existing.md",
        {"title": "Existing", "type": "concept", "created": "2026-01-01", "updated": "2026-01-01"},
        "Original canonical content.",
    )
    before = canonical.read_text(encoding="utf-8")

    try:
        maintenance_main(["--config", str(config_path), "--write-report", "concepts/existing.md"])
    except SystemExit:
        pass

    assert canonical.read_text(encoding="utf-8") == before


def test_maintenance_cli_write_report_rejects_traversal(tmp_path):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")

    try:
        maintenance_main(["--config", str(config_path), "--write-report", "../outside.md"])
    except SystemExit:
        pass

    assert not (tmp_path / "outside.md").exists()


class MaintenanceLeakyObject:
    def __str__(self):
        return "MAINTENANCE-LEAK"


def test_maintenance_report_to_dict_normalizes_malformed_direct_fields():
    from hermes_wiki.maintenance import MaintenanceReport, maintenance_report_to_dict
    from hermes_wiki.models import LintIssue

    report = MaintenanceReport(
        issues=[
            LintIssue(
                severity=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                category=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                message=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                file_path=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                suggestion=MaintenanceLeakyObject(),  # type: ignore[arg-type]
            )
        ],
        total_pages=MaintenanceLeakyObject(),  # type: ignore[arg-type]
        total_sources=-1,
        total_links=2.5,  # type: ignore[arg-type]
        broken_links=True,  # type: ignore[arg-type]
        orphan_pages=MaintenanceLeakyObject(),  # type: ignore[arg-type]
        pages_without_sources=MaintenanceLeakyObject(),  # type: ignore[arg-type]
    )

    payload = maintenance_report_to_dict(report)
    assert payload == {
        "total_pages": 0,
        "total_sources": 0,
        "total_links": 0,
        "broken_links": 0,
        "orphan_pages": 0,
        "pages_without_sources": 0,
        "errors": 0,
        "warnings": 0,
        "infos": 0,
        "issues": [
            {
                "severity": "info",
                "category": "unknown",
                "message": "",
                "file_path": None,
                "suggestion": None,
            }
        ],
    }
    assert "MAINTENANCE-LEAK" not in str(payload)


def test_render_maintenance_report_normalizes_malformed_direct_fields():
    from hermes_wiki.maintenance import MaintenanceReport, render_maintenance_report
    from hermes_wiki.models import LintIssue

    report = MaintenanceReport(
        issues=[
            LintIssue(
                severity=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                category=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                message=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                file_path=MaintenanceLeakyObject(),  # type: ignore[arg-type]
                suggestion=MaintenanceLeakyObject(),  # type: ignore[arg-type]
            )
        ],
        total_pages=MaintenanceLeakyObject(),  # type: ignore[arg-type]
        total_sources=MaintenanceLeakyObject(),  # type: ignore[arg-type]
        total_links=MaintenanceLeakyObject(),  # type: ignore[arg-type]
        broken_links=MaintenanceLeakyObject(),  # type: ignore[arg-type]
        orphan_pages=MaintenanceLeakyObject(),  # type: ignore[arg-type]
        pages_without_sources=MaintenanceLeakyObject(),  # type: ignore[arg-type]
    )

    text = render_maintenance_report(report)

    assert "MAINTENANCE-LEAK" not in text
    assert "- Pages: 0" in text
    assert "- Issues: 1 (0 errors, 0 warnings, 0 info)" in text
    assert "**info / unknown**" in text
