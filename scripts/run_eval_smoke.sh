#!/usr/bin/env bash
set -euo pipefail

# Lightweight, PR-friendly smoke run over a fixed gate set.
# Expected env overrides:
#   HERMES_EVAL_MODEL / HERMES_EVAL_PROVIDER
#   HERMES_EVAL_JUDGE_MODEL / HERMES_EVAL_JUDGE_PROVIDER
#   HERMES_EVAL_OUTPUT_DIR
#   HERMES_EVAL_FAIL_UNDER
#   HERMES_EVAL_FIXTURE_RESULTS   (optional offline YAML/JSON payload for CI-safe smoke)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_DIR="${HERMES_EVAL_OUTPUT_DIR:-evals/results/smoke}"
FAIL_UNDER="${HERMES_EVAL_FAIL_UNDER:-1.0}"

CMD=(
  python scripts/run_evals.py
  --case routing.local-repo-inspection
  --case routing.web-search-straightforward
  --case review.pr-code-quality
  --case briefing.change-summary-no-speculation
  --fail-under "$FAIL_UNDER"
  --output "$OUTPUT_DIR"
)

if [[ -n "${HERMES_EVAL_MODEL:-}" ]]; then
  CMD+=(--model "$HERMES_EVAL_MODEL")
fi
if [[ -n "${HERMES_EVAL_PROVIDER:-}" ]]; then
  CMD+=(--provider "$HERMES_EVAL_PROVIDER")
fi
if [[ -n "${HERMES_EVAL_JUDGE_MODEL:-}" ]]; then
  CMD+=(--judge-model "$HERMES_EVAL_JUDGE_MODEL")
fi
if [[ -n "${HERMES_EVAL_JUDGE_PROVIDER:-}" ]]; then
  CMD+=(--judge-provider "$HERMES_EVAL_JUDGE_PROVIDER")
fi
if [[ -n "${HERMES_EVAL_FIXTURE_RESULTS:-}" ]]; then
  CMD+=(--fixture-results "$HERMES_EVAL_FIXTURE_RESULTS")
fi

"${CMD[@]}"
