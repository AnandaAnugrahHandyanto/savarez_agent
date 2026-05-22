#!/usr/bin/env python3
"""Rescore existing Spark compression benchmark outputs with semantic checks.

The first scorer used exact F/L identifier retention, which unfairly rewarded
copying synthetic IDs and punished good paraphrases. This scorer evaluates the
actual context-continuity properties we care about.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts"
MODELS = [
    {"label": "baseline-gpt-5.5", "model": "gpt-5.5"},
    {"label": "spark-gpt-5.3-codex-spark", "model": "gpt-5.3-codex-spark"},
]

CHECKS = {
    "active_task_user_request": {
        "weight": 12,
        "section": "## Active Task",
        "patterns": [r"gpt-5\.3-codex-spark", r"(testing|test|benchmark|vet|vetted)", r"context compression|compression"],
        "anti": [r"Create a structured checkpoint summary"],
    },
    "goal_subscription_without_quality_loss": {
        "weight": 6,
        "patterns": [r"subscription bucket|subscription", r"quality|context quality", r"without (sacrificing|degrading)|before.*switch"],
    },
    "baseline_live_config": {
        "weight": 8,
        "patterns": [r"openai-codex", r"gpt-5\.5", r"272000", r"(active|current|baseline|compression)"],
    },
    "spark_candidate_context": {
        "weight": 7,
        "patterns": [r"gpt-5\.3-codex-spark", r"128000", r"not 272000|below|smaller|context"],
    },
    "spark_smoke_ok": {
        "weight": 4,
        "patterns": [r"gpt-5\.3-codex-spark", r"Reply exactly: OK|returned `?OK`?|Result: `?OK`?"],
    },
    "threshold_auto_lower": {
        "weight": 5,
        "patterns": [r"auto-lower|auto-lowered", r"136000", r"128000"],
    },
    "opus_blocker_exact": {
        "weight": 7,
        "patterns": [r"claude-opus-4-7|Opus 4\.7", r"Third-party apps now draw from your extra usage", r"HTTP 400|400"],
    },
    "avoid_paid_api_routes": {
        "weight": 5,
        "patterns": [r"direct Anthropic|Anthropic/OpenRouter|OpenRouter", r"unless Joe|explicitly"],
    },
    "gateway_state_repair": {
        "weight": 5,
        "patterns": [r"gateway_state\.json", r"invalid UTF-8|trailing", r"truncate|truncated|terminator"],
    },
    "backup_path": {
        "weight": 4,
        "patterns": [r"/home/joe/\.hermes/gateway_state\.json\.bak-20260521213715"],
    },
    "gateway_active_after_restart": {
        "weight": 4,
        "patterns": [r"gateway", r"active|running", r"restart"],
    },
    "no_production_change": {
        "weight": 6,
        "patterns": [r"no production|do not switch|without .*config", r"benchmark", r"config"],
    },
    "stage_rollout_if_pass": {
        "weight": 4,
        "patterns": [r"staged rollout|staged", r"if Spark passes|if acceptable|quality"],
    },
    "low_risk_if_weaker": {
        "weight": 4,
        "patterns": [r"lower-risk|low-risk", r"short summaries|classification|non-critical"],
    },
    "secret_redaction": {
        "weight": 8,
        "patterns": [r"\[REDACTED\]"],
        "anti_global": [r"FAKE_OPENAI_VALUE_DO_NOT_KEEP", r"FAKE_ANTHROPIC_VALUE_DO_NOT_KEEP"],
    },
    "pending_user_ask_preserved": {
        "weight": 6,
        "section": "## Pending User Asks",
        "patterns": [r"benchmark|testing|test|vet", r"Spark|gpt-5\.3-codex-spark", r"quality|compression"],
    },
    "current_not_spark_default": {
        "weight": 5,
        "patterns": [r"Spark.*not (active|approved|default)|not.*Spark.*active|candidate under test", r"gpt-5\.5"],
        "anti_global": [r"active compression config\s*[:=]\s*`?gpt-5\.3-codex-spark"],
    },
}

SECTION_RE = re.compile(r"^## .*$", re.M)

def extract_section(text: str, heading: str) -> str:
    m = re.search(rf"^{re.escape(heading)}\s*$", text, re.M)
    if not m:
        return ""
    start = m.end()
    n = SECTION_RE.search(text, start)
    end = n.start() if n else len(text)
    return text[start:end]


def check_pass(text: str, check: dict) -> tuple[bool, list[str]]:
    hay = extract_section(text, check["section"]) if check.get("section") else text
    misses = []
    for pat in check.get("patterns", []):
        if not re.search(pat, hay, re.I | re.S):
            misses.append(f"missing:{pat}")
    for pat in check.get("anti", []):
        if re.search(pat, hay, re.I | re.S):
            misses.append(f"anti:{pat}")
    for pat in check.get("anti_global", []):
        if re.search(pat, text, re.I | re.S):
            misses.append(f"anti_global:{pat}")
    return (not misses), misses


def score_one(label: str, model: str) -> dict:
    path = OUT / f"{label}.md"
    text = path.read_text(encoding="utf-8")
    total = sum(c["weight"] for c in CHECKS.values())
    got = 0
    details = {}
    for name, chk in CHECKS.items():
        ok, misses = check_pass(text, chk)
        if ok:
            got += chk["weight"]
        details[name] = {"ok": ok, "weight": chk["weight"], "misses": misses}
    pct = round(got / total * 100, 1)
    if pct >= 92:
        verdict = "PASS"
    elif pct >= 82:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {"label": label, "model": model, "score_pct": pct, "points": got, "total_points": total, "verdict": verdict, "output_path": str(path), "details": details}


def main() -> int:
    scores = [score_one(m["label"], m["model"]) for m in MODELS]
    (OUT / "scores_v2_semantic.json").write_text(json.dumps(scores, indent=2), encoding="utf-8")

    lines = [
        "# Spark Compression Benchmark Spike", "",
        "Question: can `gpt-5.3-codex-spark` preserve Hermes context-compression quality well enough to use its subscription bucket?", "",
        "## Method", "",
        "- Generated a realistic Hermes/GSD context-compaction fixture with must-keep facts, current-vs-stale corrections, secret traps, and filler/noise.",
        "- Sent the same Hermes-style compaction prompt to `gpt-5.5` and `gpt-5.3-codex-spark` via `hermes chat -Q --provider openai-codex --toolsets safe`.",
        "- Initial exact-ID score was too brittle, so this report uses semantic continuity checks: active task fidelity, current config, candidate context, blockers, redaction, stale-state handling, and pending asks.",
        "- This spike did not modify `~/.hermes/config.yaml` and did not restart the gateway.", "",
        "## Results", "",
        "| Model | Semantic score | Verdict | Key misses | Output |",
        "|---|---:|---|---|---|",
    ]
    for s in scores:
        misses = [name for name, d in s["details"].items() if not d["ok"]]
        lines.append(f"| `{s['model']}` | {s['score_pct']:.1f}% | {s['verdict']} | {', '.join(misses[:5]) or 'none'} | `{s['output_path']}` |")

    base = next(s for s in scores if s["label"].startswith("baseline"))
    spark = next(s for s in scores if "spark" in s["label"])
    lines.extend(["", "## Findings", ""])
    lines.append(f"- Baseline `gpt-5.5`: {base['score_pct']:.1f}% ({base['verdict']}).")
    lines.append(f"- Spark `gpt-5.3-codex-spark`: {spark['score_pct']:.1f}% ({spark['verdict']}).")
    if not spark["details"]["active_task_user_request"]["ok"]:
        lines.append("- Spark's biggest miss: it put the harness instruction itself in `## Active Task` instead of Joe's latest unfulfilled request. That is a serious continuity failure for Hermes compaction.")
    if base["details"]["active_task_user_request"]["ok"]:
        lines.append("- Baseline preserved Joe's actual active ask in `## Active Task`.")
    if spark["details"]["secret_redaction"]["ok"]:
        lines.append("- Spark did redact secrets correctly in this run.")
    if spark["details"]["current_not_spark_default"]["ok"]:
        lines.append("- Spark kept the important correction that Spark is only a candidate and `gpt-5.5` remains the active/default compression state.")
    lines.extend(["", "## Verdict", ""])
    if spark["score_pct"] >= 92 and spark["score_pct"] >= base["score_pct"] - 3:
        lines.append("Spark passed this first synthetic benchmark. Next step: run a harder real-session transcript benchmark before any staged rollout.")
    elif spark["score_pct"] >= 82:
        lines.append("Spark is promising but not baseline-equivalent yet. Because it missed active-task fidelity, do not use it as default compression until it passes real transcript tests and an active-task-specific retest.")
    else:
        lines.append("Spark did not pass this first benchmark. Keep `gpt-5.5` for compression; use Spark only for lower-risk summaries/classification unless further prompt tuning or tests improve results.")
    lines.extend(["", "## Artifacts", "",
        f"- Prompt: `{OUT / 'prompt.txt'}`",
        f"- Turns fixture: `{OUT / 'turns.txt'}`",
        f"- Baseline output: `{OUT / 'baseline-gpt-5.5.md'}`",
        f"- Spark output: `{OUT / 'spark-gpt-5.3-codex-spark.md'}`",
        f"- Original exact-ID scores: `{OUT / 'scores.json'}`",
        f"- Semantic scores: `{OUT / 'scores_v2_semantic.json'}`",
    ])
    report = ROOT / "README.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report)
    print(json.dumps(scores, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
