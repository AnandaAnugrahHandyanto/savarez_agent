#!/usr/bin/env bash
set -euo pipefail

# Nightly/weekly scheduled regression wrapper.
# The caller supplies model/provider env plus optional baseline location.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_DIR="${HERMES_EVAL_OUTPUT_DIR:-evals/results/nightly/${STAMP}}"
BASELINE_DIR="${HERMES_EVAL_BASELINE_DIR:-evals/results/baselines}"
FAIL_UNDER="${HERMES_EVAL_FAIL_UNDER:-0.85}"

CMD=(
  python scripts/run_evals.py
  --fail-under "$FAIL_UNDER"
  --output "$OUTPUT_DIR"
  --save-baseline "$BASELINE_DIR"
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
if [[ -n "${HERMES_EVAL_BASELINE_PATH:-}" ]]; then
  CMD+=(--baseline "$HERMES_EVAL_BASELINE_PATH")
fi

mkdir -p "$BASELINE_DIR"
"${CMD[@]}"
