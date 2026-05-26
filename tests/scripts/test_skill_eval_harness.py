from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CASES = REPO_ROOT / "tests" / "fixtures" / "skill_eval" / "basic_cases.jsonl"


def _load_skill_eval_module():
    spec = importlib.util.spec_from_file_location(
        "_skill_eval_harness_under_test",
        REPO_ROOT / "scripts" / "skill_eval_harness.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_skill(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_main_writes_accept_json_and_terse_receipt_for_single_skill(
    tmp_path, capsys
):
    module = _load_skill_eval_module()
    skill_path = _write_skill(
        tmp_path / "SKILL.md",
        "# Skill\n\n- Gstack pass: investigate\n- no mutation before root cause\n",
    )
    output_path = tmp_path / "result.json"

    exit_code = module.main(
        [
            "--skill",
            str(skill_path),
            "--cases",
            str(FIXTURE_CASES),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "accept"
    assert payload["passed"] == 1
    assert payload["failed"] == 0
    assert payload["score"] == 1.0
    assert payload["failures"] == []

    receipt = capsys.readouterr().out.strip()
    assert receipt == "ACCEPT 1/1 score=1.000 failures=0"


def test_load_cases_rejects_malformed_jsonl_with_line_number(tmp_path):
    module = _load_skill_eval_module()
    cases_path = tmp_path / "broken.jsonl"
    cases_path.write_text('{"id":"ok","expected":{"must_include":["x"]}}\nnot json\n', encoding="utf-8")

    try:
        module.load_cases(cases_path)
    except ValueError as exc:
        assert "broken.jsonl:2" in str(exc)
        assert "invalid JSONL case" in str(exc)
    else:
        raise AssertionError("load_cases should reject malformed JSONL")


def test_evaluate_text_supports_regex_matchers(tmp_path):
    module = _load_skill_eval_module()
    cases_path = tmp_path / "regex_cases.jsonl"
    cases_path.write_text(
        (
            '{"id":"regex-pass","expected":{"regex_include":["^Gstack pass: investigate$"],'
            '"regex_not_include":["plan-ceo-review"]}}\n'
        ),
        encoding="utf-8",
    )

    cases = module.load_cases(cases_path)
    evaluation = module.evaluate_text("Gstack pass: investigate\n", cases)

    assert evaluation["passed"] == 1
    assert evaluation["failed"] == 0
    assert evaluation["failures"] == []


def test_main_rejects_ties_when_candidate_matches_baseline(tmp_path, capsys):
    module = _load_skill_eval_module()
    baseline_path = _write_skill(
        tmp_path / "baseline.md",
        "# Skill\n\n- Gstack pass: investigate\n",
    )
    candidate_path = _write_skill(
        tmp_path / "candidate.md",
        "# Skill\n\n- Gstack pass: investigate\n",
    )
    output_path = tmp_path / "result.json"

    exit_code = module.main(
        [
            "--candidate-skill",
            str(candidate_path),
            "--baseline-skill",
            str(baseline_path),
            "--cases",
            str(FIXTURE_CASES),
            "--output",
            str(output_path),
            "--reject-ties",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "reject"
    assert payload["baseline_score"] == 1.0
    assert payload["token_delta"] == 0
    assert payload["line_delta"] == 0
    assert payload["reasons"] == ["candidate tied baseline and reject_ties is set"]

    receipt = capsys.readouterr().out.strip()
    assert receipt == "REJECT 1/1 score=1.000 failures=0 reason=candidate tied baseline and reject_ties is set"


def test_main_rejects_growth_budget_overages(tmp_path):
    module = _load_skill_eval_module()
    baseline_path = _write_skill(
        tmp_path / "baseline.md",
        "# Skill\n\n- Gstack pass: investigate\n",
    )
    candidate_path = _write_skill(
        tmp_path / "candidate.md",
        "# Skill\n\n- Gstack pass: investigate\n- extra line\n- extra tokens live here\n",
    )
    output_path = tmp_path / "result.json"

    exit_code = module.main(
        [
            "--candidate-skill",
            str(candidate_path),
            "--baseline-skill",
            str(baseline_path),
            "--cases",
            str(FIXTURE_CASES),
            "--output",
            str(output_path),
            "--max-token-growth",
            "0.0",
            "--max-line-growth",
            "0",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "reject"
    assert payload["token_delta"] > 0
    assert payload["line_delta"] > 0
    assert payload["reasons"] == [
        "candidate exceeded max token growth",
        "candidate exceeded max line growth",
    ]


def test_main_returns_nonzero_when_fail_on_reject_is_set(tmp_path):
    module = _load_skill_eval_module()
    baseline_path = _write_skill(
        tmp_path / "baseline.md",
        "# Skill\n\n- Gstack pass: investigate\n",
    )
    candidate_path = _write_skill(
        tmp_path / "candidate.md",
        "# Skill\n\n- Gstack pass: investigate\n",
    )
    output_path = tmp_path / "result.json"

    exit_code = module.main(
        [
            "--candidate-skill",
            str(candidate_path),
            "--baseline-skill",
            str(baseline_path),
            "--cases",
            str(FIXTURE_CASES),
            "--output",
            str(output_path),
            "--reject-ties",
            "--fail-on-reject",
        ]
    )

    assert exit_code == 1
