# Hermes eval operations

This is the executable path for CI and scheduled eval runs introduced by the Hermes eval MVP.

For the end-to-end human/operator workflow — case creation, suite runs, baseline comparison, and failcase promotion — see `docs/evals/README.md`.

## CI smoke gate

GitHub workflow: `.github/workflows/evals-smoke.yml`

What always runs:
- `scripts/run_tests.sh tests/evals/`
- `python scripts/run_evals.py --help`
- `python scripts/mine_eval_cases.py --help`

What runs only when live eval credentials are configured in GitHub Actions:
- `bash scripts/run_eval_smoke.sh`

Required GitHub Actions configuration for live smoke runs:
- secret: `OPENROUTER_API_KEY`
- variable: `HERMES_EVAL_MODEL`
- optional variables:
  - `HERMES_EVAL_PROVIDER` (defaults to `openrouter`)
  - `HERMES_EVAL_JUDGE_MODEL`
  - `HERMES_EVAL_JUDGE_PROVIDER`

Smoke gate corpus (fixed MVP set):
- `routing.local-repo-inspection`
- `routing.web-search-straightforward`
- `review.pr-code-quality`
- `briefing.change-summary-no-speculation`

Why this split exists:
- the repo can always validate loader/check/judge/report plumbing in hermetic CI,
- live model evals require provider credentials and should fail visibly only in environments that intentionally enable them.

## Scheduled regression runs

GitHub workflow: `.github/workflows/evals-nightly.yml`

Schedules:
- nightly regression: `30 1 * * *`
- weekly comparison window: `0 7 * * 1`

Runner entrypoint:
- `bash scripts/run_eval_nightly.sh`

Default behavior:
- runs the full current eval corpus
- writes artifacts under `evals/results/nightly/`
- saves fresh baselines under `evals/results/baselines/`
- enforces `HERMES_EVAL_FAIL_UNDER` (default `0.85`)

Optional manual dispatch inputs:
- `baseline_path`
- `fail_under`

## Local commands

Run eval unit tests:

```bash
scripts/run_tests.sh tests/evals/
```

Smoke the CLI entrypoints:

```bash
python scripts/run_evals.py --help
python scripts/mine_eval_cases.py --help
```

Run the fixed smoke gate locally:

```bash
HERMES_EVAL_MODEL=<model> \
HERMES_EVAL_PROVIDER=<provider> \
OPENROUTER_API_KEY=[REDACTED] \
./scripts/run_eval_smoke.sh
```

Run the nightly wrapper locally:

```bash
HERMES_EVAL_MODEL=<model> \
HERMES_EVAL_PROVIDER=<provider> \
OPENROUTER_API_KEY=[REDACTED] \
./scripts/run_eval_nightly.sh
```

## MVP truthfulness notes

- The always-on CI gate is currently unit/integration coverage for the eval framework itself plus CLI smoke, not an always-live model run. That is deliberate because public CI cannot assume paid model credentials.
- The live smoke and nightly workflows become real execution gates only after the GitHub secret/variables above are configured.
- The fixed smoke set is the current stand-in for “critical case regression” until the corpus grows explicit critical labels and baseline policies.
