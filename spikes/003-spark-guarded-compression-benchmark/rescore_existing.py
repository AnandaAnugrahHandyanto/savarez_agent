#!/usr/bin/env python3
"""Rescore already generated guarded Spark benchmark outputs without rerunning models."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import run_guarded_benchmark as bench

OUT = Path(__file__).resolve().parent / "artifacts"


def main() -> int:
    old = json.loads((OUT / "scores.json").read_text(encoding="utf-8"))
    rows_by_key = {(r["fixture_id"], r["lane"]): r for r in old}
    results: list[bench.Result] = []
    for fixture in bench.FIXTURES:
        for lane in bench.LANES:
            key = (fixture.fixture_id, lane.label)
            prev = rows_by_key[key]
            output_path = Path(prev["output_path"])
            body = output_path.read_text(encoding="utf-8")
            latest = bench.ContextCompressor._extract_latest_user_request(fixture.messages)
            validation_issues = bench.ContextCompressor._validate_summary_guardrails(body, latest)
            score, total, misses = bench.check_patterns(body, fixture.checks)
            pct = round(score / total * 100, 1) if total else 0.0
            if prev["returncode"] != 0:
                verdict = "CALL_FAILED"
            elif pct >= 92 and not validation_issues:
                verdict = "PASS"
            elif pct >= 82:
                verdict = "PARTIAL"
            else:
                verdict = "FAIL"
            results.append(bench.Result(
                fixture_id=fixture.fixture_id,
                lane=lane.label,
                model=lane.model,
                guarded=lane.guarded,
                returncode=prev["returncode"],
                elapsed_s=prev["elapsed_s"],
                score=score,
                total=total,
                pct=pct,
                verdict=verdict,
                validation_issues=validation_issues,
                repair_count=prev["repair_count"],
                validation_failure_count=prev["validation_failure_count"],
                fallback_count=prev["fallback_count"],
                output_path=prev["output_path"],
                prompt_path=prev["prompt_path"],
                misses=misses,
                stderr_tail=prev.get("stderr_tail", ""),
            ))
    report = bench.write_report(results)
    rescored = [asdict(r) for r in results]
    (OUT / "scores.rescored.json").write_text(json.dumps(rescored, indent=2), encoding="utf-8")
    print(report)
    print(json.dumps(rescored, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
