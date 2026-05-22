#!/usr/bin/env python3
"""Rescore existing trusted-shadow outputs without rerunning model calls."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

SPIKE = Path(__file__).resolve().parent
ROOT = SPIKE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SPIKE))

import run_trusted_shadow as bench  # noqa: E402
from agent.context_compressor import ContextCompressor  # noqa: E402


def main() -> int:
    old = json.loads((bench.OUT / "scores.json").read_text(encoding="utf-8"))
    old_by_id = {r["fixture_id"]: r for r in old}
    results: list[bench.Result] = []
    for fixture in bench.make_fixtures():
        prior = old_by_id[fixture.fixture_id]
        body = Path(prior["output_path"]).read_text(encoding="utf-8")
        latest = ContextCompressor._extract_latest_user_request(fixture.messages)
        validation_issues = ContextCompressor._validate_summary_guardrails(body, latest)
        score, total, misses = bench.check_patterns(body, fixture.checks)
        pct = round(score / total * 100, 1) if total else 0.0
        if prior["returncode"] != 0:
            verdict = "CALL_FAILED"
        elif pct >= 90 and not validation_issues:
            verdict = "PASS"
        elif pct >= 80:
            verdict = "PARTIAL"
        else:
            verdict = "FAIL"
        results.append(bench.Result(
            fixture_id=fixture.fixture_id,
            title=fixture.title,
            returncode=prior["returncode"],
            elapsed_s=prior["elapsed_s"],
            score=score,
            total=total,
            pct=pct,
            verdict=verdict,
            validation_issues=validation_issues,
            repair_count=prior["repair_count"],
            validation_failure_count=prior["validation_failure_count"],
            fallback_count=prior["fallback_count"],
            output_path=prior["output_path"],
            prompt_path=prior["prompt_path"],
            misses=misses,
            stderr_tail=prior.get("stderr_tail", ""),
        ))
    live = bench.verify_live_config()
    report = bench.write_report(results, live)
    print(report)
    print(json.dumps({
        "aggregate": {
            "pass": sum(r.verdict == "PASS" for r in results),
            "partial": sum(r.verdict == "PARTIAL" for r in results),
            "fail": sum(r.verdict not in {"PASS", "PARTIAL"} for r in results),
            "count": len(results),
        },
        "live_config_after": live,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
