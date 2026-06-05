# UA Tier 1 — T1-005 Run/Report/Context Integration Complete

- Timestamp: 2026-06-05T03:42:11Z
- Branch: `feat/ua-tier1-static-signals`
- Base before bead: `42914c1d6` (`feat(code-scan): refine entrypoint recommendations`)
- Bead: `ua-tier1-005-run-ua-report-integration`

## Scope

Integrated Tier 1 `static-signals.json` into the public UA run bundle, manifest, summary/report data, rendered report, and subagent context bundle while preserving Tier 0/Tier 1 claim boundaries.

Changed in-scope files:

- `scripts/code-scan/run_ua.py`
- `scripts/code-scan/report_data.py`
- `scripts/code-scan/render_report.py`
- `scripts/code-scan/build_context_bundle.py`
- `tests/code_scan/test_run_ua.py`
- `tests/code_scan/test_report_data.py`
- `tests/code_scan/test_render_report.py`
- `tests/code_scan/test_build_context_bundle.py`
- `tests/code_scan/fixtures/static_signals_supabase/.github/workflows/ci.yml`
- `tests/code_scan/fixtures/static_signals_supabase/package.json`
- `tests/code_scan/fixtures/static_signals_supabase/supabase/functions/invite/index.ts`
- `tests/code_scan/fixtures/static_signals_supabase/supabase/migrations/20260601000000_rls.sql`
- `tests/code_scan/fixtures/static_signals_supabase/vite.config.ts`

## Implementation Notes

- `static-signals.json` is produced before manifest finalization in the public `run_ua.py` flow.
- `manifest.json` includes `static-signals.json` in `artifact_paths` and `artifact_integrity`.
- Summary, report data, rendered report, critic/context projections, and subagent context all retain Tier 1 labels: `heuristic_signal` and `not_validated`.
- Static-signal summaries are bounded and explicitly non-validating; no Tier 1 claim is represented as an executed external gate.
- Prior Must-Read Map behavior and Phase 7 manifest/context ordering boundaries were preserved.

## Verification Evidence

RED / regression reconstruction:

- Temporary reconstruction against current tests without the integration produced expected failures for missing static-signal run/report/context behavior.
- After restoring implementation, the focused integration tests passed.

GREEN / focused verification:

```text
python -m pytest tests/code_scan/test_run_ua.py tests/code_scan/test_report_data.py tests/code_scan/test_render_report.py tests/code_scan/test_build_context_bundle.py -q
221 passed in 34.20s
```

FULL verification:

```text
python -m pytest tests/code_scan -q
1074 passed in 168.29s (0:02:48)
```

Compile and hygiene:

```text
python -m py_compile scripts/code-scan/run_ua.py scripts/code-scan/report_data.py scripts/code-scan/render_report.py scripts/code-scan/build_context_bundle.py
PASS

git diff --check
PASS
```

Public entrypoint smoke:

```text
python scripts/code-scan/run_ua.py --target tests/code_scan/fixtures/static_signals_supabase --out /tmp/ua-tier1-artifacts/t1-005-smoke-bundle-1780630464-166020 --mode review
T1_005_SMOKE_STATIC_SIGNALS_OK
total_signals=15
top_context_signals=8
manifest_static_sha=bf21ef24b557fd0e4938c9c712bb2d47d18ce735c1f83b409cb5fa945f10b8fe
```

Static/scope scan:

- Diff artifact: `/tmp/ua-tier1-artifacts/ua-tier1-005-run-ua-report-integration-final.diff` — 894 lines / 39047 bytes.
- Added-line scan counts: hardcoded secrets 0, shell injection 0, eval/exec 0, unsafe deserialization 0, SQL format injection 0, unfinished-marker hits 0.
- `executed_external_gate` hits are only negative/boundary assertions, not Tier 1 claims.

Reviewer:

- Independent reviewer PASS.
- Security concerns: none.
- Logic errors: none.
- Spec concerns: none.
- Reviewer summary: Tier 1 static signals fully integrated with strict heuristic labels, pre-manifest write and integrity inclusion, bounded non-overclaim summaries in report/context/summary, Tier 0 separation preserved, Must-Read/render ordering intact, and all smoke/tests/evidence compliant.

## Boundary

No merge to main, deploy, production mutation, dependency change, dashboard/UI, auto-injection, SQLite/vector store, tree-sitter/WASM, or scanner-embedded LLM/provider calls were performed.
