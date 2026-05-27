import textwrap
from collections import Counter
from pathlib import Path

import pytest
import yaml

from evals.loader import load_eval_cases, resolve_case_files
from evals.schemas import EvalCase, EvalRunResult, EvalSchemaError, load_eval_case_file


class TestEvalCaseLoading:
    def test_load_eval_case_file_parses_valid_yaml(self, tmp_path):
        case_file = tmp_path / "case.yaml"
        case_file.write_text(
            textwrap.dedent(
                """
                case_id: briefing.hp.homepage.visible-campaigns
                suite: ci-briefings
                task_type: briefing
                title: Detect visible homepage campaigns and summarize changes
                prompt: >
                  Review the provided homepage capture and summarize the visible campaigns,
                  banners, and promotional hooks in at most 10 lines.
                context: >
                  Output must be concise, observation-led, and avoid invented commercial claims.
                tags: [igo, homepage, daily, concise]
                enabled_toolsets: [browser, vision]
                expected_tools: [browser_navigate, browser_vision]
                forbidden_tools: [terminal]
                assertions:
                  - kind: max_lines
                    params:
                      max_lines: 10
                  - kind: required_regex
                    params:
                      pattern: "(banner|campaign|promotion|discount)"
                    weight: 2
                    required: false
                judge_dimensions:
                  - name: factuality
                    description: Are claims grounded in visible evidence?
                    pass_threshold: 4
                gold_answer: Visible hero banner plus seasonal promotion summary.
                notes: Seed case for the briefing suite.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        case = load_eval_case_file(case_file)

        assert isinstance(case, EvalCase)
        assert case.case_id == "briefing.hp.homepage.visible-campaigns"
        assert case.task_type == "briefing"
        assert case.enabled_toolsets == ["browser", "vision"]
        assert case.assertions[0].kind == "max_lines"
        assert case.assertions[0].params == {"max_lines": 10}
        assert case.assertions[1].weight == 2.0
        assert case.assertions[1].required is False
        assert case.judge_dimensions[0].name == "factuality"
        assert case.judge_dimensions[0].pass_threshold == 4.0

    def test_load_eval_case_file_rejects_unknown_top_level_fields(self, tmp_path):
        case_file = tmp_path / "case.yaml"
        case_file.write_text(
            textwrap.dedent(
                """
                case_id: invalid.extra-field
                suite: ci-briefings
                task_type: briefing
                title: Invalid case
                prompt: Hello
                unexpected_field: nope
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(EvalSchemaError, match=r"unexpected_field"):
            load_eval_case_file(case_file)

    def test_load_eval_case_file_rejects_invalid_task_type(self, tmp_path):
        case_file = tmp_path / "case.yaml"
        case_file.write_text(
            textwrap.dedent(
                """
                case_id: invalid.task-type
                suite: ci-briefings
                task_type: summary
                title: Invalid task type
                prompt: Hello
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        with pytest.raises(EvalSchemaError, match=r"task_type"):
            load_eval_case_file(case_file)


class TestSuiteResolution:
    def test_resolve_case_files_orders_root_and_nested_cases_deterministically(self, tmp_path):
        (tmp_path / "z-last.yaml").write_text(
            "case_id: z-last\nsuite: alpha\ntask_type: briefing\ntitle: Z\nprompt: hi\n",
            encoding="utf-8",
        )
        suite_dir = tmp_path / "alpha"
        suite_dir.mkdir()
        (suite_dir / "b-second.yaml").write_text(
            "case_id: b-second\nsuite: alpha\ntask_type: briefing\ntitle: B\nprompt: hi\n",
            encoding="utf-8",
        )
        (suite_dir / "a-first.yaml").write_text(
            "case_id: a-first\nsuite: alpha\ntask_type: briefing\ntitle: A\nprompt: hi\n",
            encoding="utf-8",
        )

        paths = resolve_case_files(tmp_path)

        assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
            "alpha/a-first.yaml",
            "alpha/b-second.yaml",
            "z-last.yaml",
        ]

    def test_load_eval_cases_filters_by_suite_and_case_id(self, tmp_path):
        alpha_dir = tmp_path / "alpha"
        alpha_dir.mkdir()
        beta_dir = tmp_path / "beta"
        beta_dir.mkdir()
        (alpha_dir / "first.yaml").write_text(
            "case_id: alpha.first\nsuite: alpha\ntask_type: briefing\ntitle: First\nprompt: hi\n",
            encoding="utf-8",
        )
        (beta_dir / "second.yaml").write_text(
            "case_id: beta.second\nsuite: beta\ntask_type: briefing\ntitle: Second\nprompt: hi\n",
            encoding="utf-8",
        )

        cases = load_eval_cases(tmp_path, suites=["beta"], case_ids=["beta.second"])

        assert [case.case_id for case in cases] == ["beta.second"]

    def test_load_eval_cases_rejects_unknown_case_ids(self, tmp_path):
        (tmp_path / "case.yaml").write_text(
            "case_id: alpha.first\nsuite: alpha\ntask_type: briefing\ntitle: First\nprompt: hi\n",
            encoding="utf-8",
        )

        with pytest.raises(EvalSchemaError, match=r"missing case_id\(s\): beta.second"):
            load_eval_cases(tmp_path, case_ids=["beta.second"])

    def test_repo_seed_cases_load_and_cover_requested_suites(self):
        repo_root = Path(__file__).resolve().parents[2]
        cases_dir = repo_root / "evals" / "cases"

        cases = load_eval_cases(cases_dir)

        counts = Counter(case.suite for case in cases)

        required_suites = {"routing", "review", "briefing", "multimodal"}

        assert len(cases) >= 8
        assert required_suites.issubset(counts)
        assert all(counts[suite] >= 1 for suite in required_suites)
        assert all(case.assertions for case in cases)
        assert any(case.judge_dimensions for case in cases if case.suite in {"review", "briefing", "multimodal"})

    def test_seed_rubric_files_exist_and_have_dimensions(self):
        repo_root = Path(__file__).resolve().parents[2]
        rubrics_dir = repo_root / "evals" / "rubrics"
        expected = ["routing.yaml", "review.yaml", "briefing.yaml", "multimodal.yaml"]

        for name in expected:
            path = rubrics_dir / name
            assert path.exists(), f"missing rubric file: {name}"

            data = yaml.safe_load(path.read_text(encoding="utf-8"))

            assert data["version"] == 1
            assert data["suite"] == path.stem
            assert data["status"] == "informational-until-loader-support"
            assert isinstance(data["dimensions"], list)
            assert data["dimensions"]
            assert all(dimension.get("name") for dimension in data["dimensions"])
            assert all(dimension.get("description") for dimension in data["dimensions"])


class TestEvalRunResultSchema:
    def test_eval_run_result_from_dict_parses_nested_results(self):
        result = EvalRunResult.from_dict(
            {
                "run_id": "run-123",
                "case_id": "briefing.hp.homepage.visible-campaigns",
                "suite": "ci-briefings",
                "provider": "openai",
                "model": "gpt-5.4",
                "judge_provider": None,
                "judge_model": None,
                "started_at": "2026-05-26T12:00:00Z",
                "ended_at": "2026-05-26T12:00:01Z",
                "elapsed_ms": 1000,
                "completed": True,
                "failed": False,
                "error": None,
                "final_response": "Visible campaign summary.",
                "tool_calls": [{"name": "browser_navigate"}],
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "estimated_cost_usd": 0.01,
                "actual_cost_usd": 0.02,
                "assertions": [
                    {
                        "kind": "max_lines",
                        "passed": True,
                        "score": 1,
                        "details": {"max_lines": 10},
                    }
                ],
                "judge_results": [
                    {
                        "dimension": "factuality",
                        "score": 4,
                        "passed": True,
                        "rationale": "Grounded in the capture.",
                    }
                ],
                "aggregate_scores": {"deterministic": 1.0, "overall": 0.9},
                "labels": {"channel": "ci"},
            }
        )

        assert isinstance(result, EvalRunResult)
        assert result.elapsed_ms == 1000
        assert result.assertions[0].score == 1.0
        assert result.judge_results[0].dimension == "factuality"
        assert result.aggregate_scores["overall"] == 0.9

    def test_eval_run_result_from_dict_rejects_unknown_fields(self):
        with pytest.raises(EvalSchemaError, match=r"mystery"):
            EvalRunResult.from_dict(
                {
                    "run_id": "run-123",
                    "case_id": "briefing.hp.homepage.visible-campaigns",
                    "suite": "ci-briefings",
                    "provider": None,
                    "model": None,
                    "judge_provider": None,
                    "judge_model": None,
                    "started_at": "2026-05-26T12:00:00Z",
                    "ended_at": "2026-05-26T12:00:01Z",
                    "elapsed_ms": 1000,
                    "completed": True,
                    "failed": False,
                    "error": None,
                    "final_response": "Visible campaign summary.",
                    "tool_calls": [],
                    "input_tokens": None,
                    "output_tokens": None,
                    "cache_read_tokens": None,
                    "cache_write_tokens": None,
                    "estimated_cost_usd": None,
                    "actual_cost_usd": None,
                    "assertions": [],
                    "judge_results": [],
                    "aggregate_scores": {},
                    "labels": {},
                    "mystery": True,
                }
            )
