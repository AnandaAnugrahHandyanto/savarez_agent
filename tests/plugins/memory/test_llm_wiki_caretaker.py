from __future__ import annotations

import json

import pytest
import yaml

from hermes_wiki.caretaker import (
    caretaker_report_to_dict,
    render_caretaker_report,
    run_caretaker,
)
from hermes_wiki.caretaker import (
    main as caretaker_main,
)
from hermes_wiki.config import WikiConfig
from hermes_wiki.frontmatter import write_page


class FakeSearchResult:
    def __init__(self, page_path: str):
        self.page_path = page_path


class FakeSearcher:
    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.calls = []

    def search(self, query, limit=5):
        self.calls.append((query, limit))
        return self.results_by_query.get(query, [])


def _write_page(config: WikiConfig, rel_path: str, fm: dict, body: str):
    path = config.wiki_path / rel_path
    write_page(path, fm, body)
    return path


def test_caretaker_ignores_legacy_proposal_directory(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    proposal_path = config.wiki_path / "proposals" / "pending-memory.md"
    proposal_path.parent.mkdir(parents=True)
    proposal_path.write_text("---\ntitle: Pending memory\nstatus: pending\n---\nBody.\n", encoding="utf-8")
    before = proposal_path.read_text(encoding="utf-8")

    report = run_caretaker(config)

    assert proposal_path.read_text(encoding="utf-8") == before
    assert not hasattr(report.maintenance, "pending_proposals")
    assert report.has_blockers is False
    assert all(action.kind != "review_pending_proposal" for action in report.actions)


def test_caretaker_runs_retrieval_eval_when_cases_are_supplied(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    cases_path = tmp_path / "retrieval.yaml"
    cases_path.write_text(
        yaml.safe_dump([
            {
                "query": "How should Hermes use memory?",
                "expected_pages": ["concepts/hermes-memory.md"],
                "top_k": 2,
            }
        ]),
        encoding="utf-8",
    )
    searcher = FakeSearcher({"How should Hermes use memory?": [FakeSearchResult("concepts/hermes-memory.md")]})

    report = run_caretaker(config, eval_cases_path=cases_path, searcher=searcher)

    assert report.retrieval_eval is not None
    assert report.retrieval_eval.passed is True
    assert searcher.calls == [("How should Hermes use memory?", 2)]
    assert report.has_blockers is False


def test_caretaker_marks_eval_failure_as_blocker(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    cases_path = tmp_path / "retrieval.yaml"
    cases_path.write_text(
        yaml.safe_dump([
            {
                "query": "What is the user's preferred name?",
                "expected_pages": ["entities/example-user.md"],
            }
        ]),
        encoding="utf-8",
    )
    searcher = FakeSearcher({"What is the user's preferred name?": [FakeSearchResult("entities/hermes.md")]})

    report = run_caretaker(config, eval_cases_path=cases_path, searcher=searcher)

    assert report.has_blockers is True
    assert any(action.kind == "fix_retrieval_regression" and action.severity == "error" for action in report.actions)


def test_caretaker_rejects_nonscalar_eval_path_and_compare_modes(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")

    for bad_path in ({"path": "retrieval.yaml"}, ""):
        with pytest.raises(ValueError, match="eval_cases_path"):
            run_caretaker(config, eval_cases_path=bad_path)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="compare_modes"):
        run_caretaker(config, compare_modes={"enabled": True})  # type: ignore[arg-type]


def test_caretaker_report_to_dict_is_json_serializable(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")

    payload = caretaker_report_to_dict(run_caretaker(config))

    assert json.loads(json.dumps(payload))["maintenance"]["total_pages"] == 0
    assert "actions" in payload


def test_render_caretaker_report_is_agent_native(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")

    text = render_caretaker_report(run_caretaker(config))

    assert "# LLM Wiki Caretaker Report" in text
    assert "## Agent actions" in text
    assert "Human UI" not in text


def test_caretaker_cli_is_quiet_when_healthy(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")

    code = caretaker_main(["--config", str(config_path), "--quiet"])

    assert code == 0
    assert capsys.readouterr().out == ""
    assert not wiki_path.exists()


def test_caretaker_cli_writes_report_only_to_reports_namespace(tmp_path, capsys):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")

    code = caretaker_main(["--config", str(config_path), "--write-report", "reports/caretaker.md"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload == {"path": str(wiki_path / "reports" / "caretaker.md"), "written": True}
    assert (wiki_path / "reports" / "caretaker.md").exists()


def test_caretaker_cli_rejects_write_report_outside_reports(tmp_path):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")
    canonical = _write_page(
        WikiConfig(wiki_path=wiki_path, wiki_name="test"),
        "concepts/existing.md",
        {"title": "Existing", "type": "concept", "sources": ["raw/articles/source.md"]},
        "Original.",
    )
    before = canonical.read_text(encoding="utf-8")

    with pytest.raises(SystemExit):
        caretaker_main(["--config", str(config_path), "--write-report", "concepts/existing.md"])

    assert canonical.read_text(encoding="utf-8") == before


def test_caretaker_can_include_nonblocking_retrieval_mode_comparison(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    cases_path = tmp_path / "retrieval.yaml"
    cases_path.write_text(
        yaml.safe_dump([{"query": "literal", "expected_pages": ["concepts/package.md"]}]),
        encoding="utf-8",
    )

    class ModeAwareSearcher:
        def search(self, query, limit=5, **kwargs):
            if kwargs.get("search_mode") == "sparse":
                return [FakeSearchResult("concepts/noise.md")]
            return [FakeSearchResult("concepts/package.md")]

    report = run_caretaker(config, eval_cases_path=cases_path, searcher=ModeAwareSearcher(), compare_modes=True)
    payload = caretaker_report_to_dict(report)

    assert report.has_blockers is False
    assert payload["retrieval_eval"]["passed"] is True
    assert payload["retrieval_mode_comparison"]["passed"] is False
    assert payload["retrieval_mode_comparison"]["failed_modes"] == ["sparse"]
    assert payload["retrieval_mode_comparison"]["summary"]["dense"] == {
        "passed": True,
        "failures": 0,
        "total": 1,
    }


def test_caretaker_cli_compare_modes_includes_summary(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.yaml"
    wiki_path = tmp_path / "wiki"
    evals_path = wiki_path / "evals" / "retrieval.yaml"
    evals_path.parent.mkdir(parents=True)
    config_path.write_text(f"wiki:\n  path: {wiki_path}\n  name: test\n", encoding="utf-8")
    evals_path.write_text(
        yaml.safe_dump([{"query": "literal", "expected_pages": ["concepts/package.md"]}]),
        encoding="utf-8",
    )

    class FakeWikiSearch:
        def __init__(self, config, ensure_collection=False):
            pass

        def search(self, query, limit=5, **kwargs):
            return [FakeSearchResult("concepts/package.md")]

    def fake_build_searcher(config_path=None):
        return FakeWikiSearch(None)

    monkeypatch.setattr("hermes_wiki.caretaker._build_searcher", fake_build_searcher)

    code = caretaker_main(["--config", str(config_path), "--compare-modes", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["retrieval_mode_comparison"]["summary"]["hybrid"] == {
        "passed": True,
        "failures": 0,
        "total": 1,
    }


def test_render_caretaker_report_includes_mode_comparison_summary(tmp_path):
    config = WikiConfig(wiki_path=tmp_path / "wiki", wiki_name="test")
    cases_path = tmp_path / "retrieval.yaml"
    cases_path.write_text(
        yaml.safe_dump([{"query": "literal", "expected_pages": ["concepts/package.md"]}]),
        encoding="utf-8",
    )

    class ModeAwareSearcher:
        def search(self, query, limit=5, **kwargs):
            if kwargs.get("search_mode") == "sparse":
                return [FakeSearchResult("concepts/noise.md")]
            return [FakeSearchResult("concepts/package.md")]

    text = render_caretaker_report(
        run_caretaker(config, eval_cases_path=cases_path, searcher=ModeAwareSearcher(), compare_modes=True)
    )

    assert "- Retrieval mode comparison: dense=passed, sparse=failed, hybrid=passed" in text
    assert "diagnostic" in text.lower()


class CaretakerLeakyObject:
    def __str__(self):
        return "CARETAKER-LEAK"


def test_caretaker_report_to_dict_normalizes_malformed_direct_actions():
    from hermes_wiki.caretaker import CaretakerAction, CaretakerReport
    from hermes_wiki.maintenance import MaintenanceReport

    report = CaretakerReport(
        maintenance=MaintenanceReport(),
        actions=[
            CaretakerAction(
                kind=CaretakerLeakyObject(),  # type: ignore[arg-type]
                severity=CaretakerLeakyObject(),  # type: ignore[arg-type]
                message=CaretakerLeakyObject(),  # type: ignore[arg-type]
                autonomous=CaretakerLeakyObject(),  # type: ignore[arg-type]
                file_path=CaretakerLeakyObject(),  # type: ignore[arg-type]
            )
        ],
    )

    payload = caretaker_report_to_dict(report)
    assert payload["has_blockers"] is False
    assert payload["actions"] == [
        {"kind": "inspect", "severity": "info", "message": "", "autonomous": False, "file_path": None}
    ]
    assert "CARETAKER-LEAK" not in str(payload)


def test_render_caretaker_report_normalizes_malformed_direct_actions():
    from hermes_wiki.caretaker import CaretakerAction, CaretakerReport
    from hermes_wiki.maintenance import MaintenanceReport

    report = CaretakerReport(
        maintenance=MaintenanceReport(),
        actions=[
            CaretakerAction(
                kind=CaretakerLeakyObject(),  # type: ignore[arg-type]
                severity=CaretakerLeakyObject(),  # type: ignore[arg-type]
                message=CaretakerLeakyObject(),  # type: ignore[arg-type]
                autonomous=CaretakerLeakyObject(),  # type: ignore[arg-type]
                file_path=CaretakerLeakyObject(),  # type: ignore[arg-type]
            )
        ],
    )

    text = render_caretaker_report(report)

    assert "CARETAKER-LEAK" not in text
    assert "- Blockers: no" in text
    assert "- **info / inspect / needs evidence**: " in text
