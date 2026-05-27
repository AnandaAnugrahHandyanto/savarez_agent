# Hermes eval operator workflow

This guide is the day-to-day operator path for the Hermes eval MVP. It covers the flywheel from creating a curated case, running a suite, comparing against a baseline, and promoting a mined failcase into the versioned dataset.

For CI and scheduled execution details, see `docs/evals-operations.md`.

## What is in git vs. generated

Versioned, reviewable inputs:

- `evals/cases/<suite>/<case>.yaml` — curated eval cases.
- `evals/rubrics/*.yaml` — rubric dimensions for judge-scored suites.
- `evals/fixtures/*.yaml` — offline fixture results for CI-safe smoke tests.
- `scripts/run_evals.py` — local/CI eval runner.
- `scripts/mine_eval_cases.py` — session/trajectory mining helper.

Generated outputs:

- `evals/results/**` — run outputs, reports, comparisons, and baselines. This is ignored by default except for `.gitignore` and deliberately committed fixtures.
- `evals/cases/drafts/**` — recommended temporary location for mined draft cases before human review. Do not treat drafts as accepted coverage until promoted into a suite directory.

## Workflow 1 — Create a curated eval case

1. Choose the suite and task type.

   Current suite directories:

   - `evals/cases/routing/`
   - `evals/cases/review/`
   - `evals/cases/briefing/`
   - `evals/cases/multimodal/`

2. Add a YAML file with a stable `case_id`.

   Naming convention:

   - file: `evals/cases/<suite>/<short-name>.yaml`
   - case id: `<suite>.<short-name>`
   - use lowercase kebab-case after the suite prefix

3. Include at least one deterministic assertion.

   Minimum useful fields:

   ```yaml
   case_id: review.decision-memo
   suite: review
   task_type: review
   title: Decision memo usefulness
   prompt: >
     Review the provided decision memo and identify the decision, evidence,
     missing proof, and recommended next move.
   context: >
     Output should separate facts from interpretation and avoid generic advice.
   tags: [review, decision-quality]
   enabled_toolsets: []
   assertions:
     - kind: non_empty_output
       params: {}
     - kind: required_regex
       params: {pattern: '(?i)(decision|evidence|next move)'}
   judge_dimensions:
     - name: decision_usefulness
       description: Does the output make the decision easier and safer to make?
       pass_threshold: 4
   ```

4. Validate the new case through the loader/tests.

   ```bash
   scripts/run_tests.sh tests/evals/test_loader.py tests/evals/test_checks.py
   ```

   Then either run the new case with a real model-backed route, or add a fixture entry when the case should become part of the CI-safe smoke set. Fixture-backed runs only work for cases explicitly listed in `evals/fixtures/smoke_ci.yaml`.

   ```bash
   # Existing fixture-backed smoke example.
   python scripts/run_evals.py \
     --case routing.web-search-straightforward \
     --fixture-results evals/fixtures/smoke_ci.yaml \
     --output evals/results/manual-smoke

   # New case example; requires a real model/provider route.
   python scripts/run_evals.py \
     --case review.decision-memo \
     --provider openai-codex \
     --model gpt-5.4 \
     --output evals/results/manual/review-decision-memo
   ```

## Workflow 2 — Run a suite

Use `scripts/run_evals.py` for both local runs and automation.

Common local commands:

```bash
# Run all cases in a suite with the configured/default Hermes route.
python scripts/run_evals.py --suite review --output evals/results/manual/review

# Run one case.
python scripts/run_evals.py --case routing.web-search-straightforward --output evals/results/manual/routing-web

# Run with explicit model/provider.
python scripts/run_evals.py --suite review --provider openai-codex --model gpt-5.4 --output evals/results/manual/review-gpt54

# Run with judge scoring.
python scripts/run_evals.py --suite review --provider openai-codex --model gpt-5.4 --judge-provider openai-codex --judge-model gpt-5.5 --output evals/results/manual/review-judged

# Enforce a pass-rate gate.
python scripts/run_evals.py --suite routing --fail-under 0.85 --output evals/results/manual/routing-gate
```

Each run writes:

- `results.json` — machine-readable `EvalRunResult` records.
- `report.md` — human-readable pass/fail and score summary, unless `--json` is used.
- `comparison.json` — only when `--baseline` is supplied.

Operator checks after every run:

1. Open `report.md` first for the human summary.
2. Inspect any failed case in `results.json` for assertion failures and tool calls.
3. Treat judge output as advisory unless deterministic gates and source evidence support it.
4. Do not promote a routing/model change on aggregate score alone; check regressions by case.

## Workflow 3 — Save and compare a baseline

A baseline is a snapshot of a known-good run used to judge a candidate run.

1. Save a baseline from the reference route.

   ```bash
   python scripts/run_evals.py \
     --suite review \
     --provider openai-codex \
     --model gpt-5.4 \
     --output evals/results/baseline-build/review-gpt54 \
     --save-baseline evals/results/baselines
   ```

2. Locate the written baseline JSON under `evals/results/baselines/`.

3. Run the candidate route against that baseline.

   ```bash
   python scripts/run_evals.py \
     --suite review \
     --provider openai-codex \
     --model gpt-5.5 \
     --baseline evals/results/baselines/<baseline-file>.json \
     --fail-under 0.85 \
     --output evals/results/compare/review-gpt55
   ```

4. Read `evals/results/compare/review-gpt55/comparison.json` and the stderr recommendation.

Decision rule:

- `ship` — no material case regressions and pass-rate gate met.
- `ship_with_scope_limit` — improvement exists but guardrails/regressions require narrower rollout.
- `no_ship` — pass-rate gate failed, critical cases regressed, or cases disappeared from the candidate run.

A comparison is decision-ready only if it names specific cases, not just the aggregate pass rate.

## Workflow 4 — Promote a production failcase into the dataset

Use mining to propose candidates, then human-review before promotion. Mining output is a draft, not an accepted eval.

1. Mine candidates from the session database, trajectories, or cron outputs.

   ```bash
   # Recent tool-using sessions from state.db.
   python scripts/mine_eval_cases.py \
     --source state-db \
     --days-back 7 \
     --min-tool-calls 1 \
     --limit 20 \
     --output evals/cases/drafts/session-mining

   # Failed trajectories.
   python scripts/mine_eval_cases.py \
     --source trajectories \
     --failed-only \
     --limit 20 \
     --output evals/cases/drafts/failed-trajectories

   # Cron outputs, useful for briefing failures.
   python scripts/mine_eval_cases.py \
     --source cron-outputs \
     --limit 20 \
     --output evals/cases/drafts/cron-briefings
   ```

2. Read the generated `MINED_REPORT.md`.

   Prioritize candidates where at least one of these is true:

   - a real user corrected the output,
   - the run failed or produced empty/unsupported output,
   - the tool route was surprising or expensive,
   - the task type is strategically important: routing, review, CI briefing, multimodal.

3. Convert the draft into a curated case.

   Required cleanup before promotion:

   - remove raw private or incidental context that is not needed for the eval,
   - rewrite the title/prompt so the case is stable and repeatable,
   - replace `needs-review` draft tags with intentional suite tags,
   - add deterministic assertions that catch the original failure,
   - add judge dimensions only when deterministic checks cannot capture quality,
   - move the file from `evals/cases/drafts/...` into the appropriate suite directory.

4. Run the promoted case.

   ```bash
   python scripts/run_evals.py --case <suite.case-id> --output evals/results/manual/promoted-case
   scripts/run_tests.sh tests/evals/test_loader.py tests/evals/test_checks.py
   ```

5. Commit only the curated case/rubric/test changes, not the generated result directory.

Promotion acceptance checklist:

- The case reproduces a real or plausible failure mode.
- The expected behavior is encoded in assertions or rubric dimensions.
- The case is not overfit to one exact phrasing unless exact phrasing is the product requirement.
- The case can run without live credentials unless explicitly classified as a live-only eval.
- The case has no secrets, tokens, raw PII, or unnecessary session transcript material.

## Rollout posture

Default posture for the MVP:

- Keep CI smoke hermetic by default: eval framework tests, script help checks, and fixture-backed smoke.
- Use live model-backed smoke only when provider secrets and `HERMES_EVAL_*` variables are intentionally configured.
- Use nightly/weekly runs for broader regression signal rather than blocking every PR on paid model calls.
- Use GPT-5.5/reviewer judging only for bounded approval-board checks, calibration, and high-stakes analysis/review cases; do not run the whole eval pipeline on the premium route by default.
- Treat the first corpus as calibration data. It is useful enough to catch regressions, not yet large enough to prove broad model superiority.

## Quick operator checklist

Before declaring an eval change ready:

- New or changed cases load successfully.
- Deterministic eval tests pass.
- `python scripts/run_evals.py --help` and `python scripts/mine_eval_cases.py --help` still work.
- A relevant suite/case was run and produced `results.json` plus `report.md`.
- If changing model/routing posture, compare against a saved baseline and inspect per-case regressions.
- If promoting a failcase, confirm it moved from draft to a curated suite and no generated result artifacts are being committed.
