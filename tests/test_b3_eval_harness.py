import json
from pathlib import Path

import pytest

from eval_harness.b3 import (
    EvalAttempt,
    EvalTask,
    VeraFinding,
    load_fixture,
    main,
    score_eval_suite,
)


def test_scores_pass_metrics_cost_latency_and_vera_precision_recall():
    tasks = [
        EvalTask(
            task_id="bob-fix-1",
            agent="bob",
            attempts=[
                EvalAttempt(passed=True, cost_usd=0.10, latency_ms=1200),
                EvalAttempt(passed=False, cost_usd=0.20, latency_ms=1800),
            ],
        ),
        EvalTask(
            task_id="steve-fix-1",
            agent="steve",
            attempts=[
                EvalAttempt(passed=False, cost_usd=0.05, latency_ms=900),
                EvalAttempt(passed=True, cost_usd=0.15, latency_ms=1100),
            ],
        ),
        EvalTask(
            task_id="vera-review-1",
            agent="vera",
            attempts=[EvalAttempt(passed=True, cost_usd=0.03, latency_ms=600)],
            expected_findings=[
                VeraFinding(id="missing-test", severity="high"),
                VeraFinding(id="secret-log", severity="critical"),
            ],
            reported_findings=[
                VeraFinding(id="missing-test", severity="high"),
                VeraFinding(id="style-nit", severity="low"),
            ],
        ),
    ]

    summary = score_eval_suite(tasks, k=2)

    assert summary["overall"]["task_count"] == 3
    assert summary["overall"]["pass@1"] == pytest.approx(2 / 3)
    assert summary["overall"]["pass^2"] == 1.0
    assert summary["overall"]["cost_usd"] == 0.53
    assert summary["overall"]["latency_ms"]["mean"] == 1120
    assert summary["agents"]["bob"]["pass@1"] == 1.0
    assert summary["agents"]["steve"]["pass@1"] == 0.0
    assert summary["agents"]["vera"]["vera"]["precision"] == 0.5
    assert summary["agents"]["vera"]["vera"]["recall"] == 0.5
    assert summary["agents"]["vera"]["vera"]["tp"] == 1
    assert summary["agents"]["vera"]["vera"]["fp"] == 1
    assert summary["agents"]["vera"]["vera"]["fn"] == 1


def test_load_fixture_accepts_mini_swe_runner_shape_and_usage_telemetry(tmp_path):
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "task_id": "mini-1",
                "agent": "steve",
                "k": 2,
                "runs": [
                    {
                        "completed": False,
                        "api_calls": 2,
                        "metadata": {"model": "anthropic/claude-sonnet-4-20250514"},
                        "usage": {
                            "cost_usd": 0.12,
                            "latency_ms": 1500,
                            "input_tokens": 1000,
                            "output_tokens": 200,
                        },
                    },
                    {
                        "completed": True,
                        "api_calls": 3,
                        "metadata": {"model": "anthropic/claude-sonnet-4-20250514"},
                        "usage": {"cost_usd": 0.34, "latency_ms": 2500},
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    tasks = load_fixture(fixture)
    summary = score_eval_suite(tasks, k=2)

    assert tasks[0].task_id == "mini-1"
    assert tasks[0].attempts[0].passed is False
    assert tasks[0].attempts[1].passed is True
    assert tasks[0].attempts[0].api_calls == 2
    assert summary["overall"]["pass@1"] == 0.0
    assert summary["overall"]["pass^2"] == 1.0
    assert summary["overall"]["cost_usd"] == 0.46
    assert summary["overall"]["latency_ms"]["mean"] == 2000


def test_repository_fixture_example_scores_without_network():
    fixture = Path(__file__).parent / "fixtures" / "b3_eval_fixture.json"

    summary = score_eval_suite(load_fixture(fixture), k=2)

    assert summary["overall"]["task_count"] == 3
    assert summary["overall"]["pass^2"] == 1.0
    assert summary["agents"]["vera"]["vera"]["precision"] == 0.5



def test_cli_writes_json_summary_for_fixture(tmp_path, capsys):
    fixture = tmp_path / "fixture.json"
    output = tmp_path / "summary.json"
    fixture.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "task_id": "vera-1",
                        "agent": "vera",
                        "attempts": [{"passed": True, "cost_usd": 0.01, "latency_ms": 100}],
                        "expected_findings": [{"id": "bug-a"}],
                        "reported_findings": [{"id": "bug-a"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["--fixture", str(fixture), "--k", "3", "--output", str(output)])

    assert exit_code == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["overall"]["pass^3"] == 1.0
    assert saved["overall"]["task_count"] == 1
    assert "pass^3" in capsys.readouterr().out
