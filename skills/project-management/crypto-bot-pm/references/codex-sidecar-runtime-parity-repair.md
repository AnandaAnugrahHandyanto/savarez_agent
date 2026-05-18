# Codex-sidecar runtime/source parity repair

Use when crypto_bot control-plane self-check or autonomy readiness reports installed runtime divergence specifically for the `codex-sidecar` skill while the installed runtime copy contains legitimate newer guidance.

## Pattern

1. Treat this as a control-plane blocker before product work: do not dispatch product tasks while `native_control_plane_ready=false` or `ready_for_next_task=false` because of custom skill parity.
2. Compare source and runtime skill text without exposing credentials. For this class of drift, the relevant paths are:
   - Source: `/Users/preston/.hermes/hermes-agent/skills/development/codex-sidecar/SKILL.md`
   - Runtime: `/Users/preston/.hermes/skills/development/codex-sidecar/SKILL.md`
3. If the runtime copy contains legitimate updated guidance, port the minimal semantic delta back into the source checkout rather than overwriting runtime or suppressing the checker.
4. Validate the control plane after the sync:
   - `git diff --check`
   - `scripts/run_tests.sh tests/test_crypto_bot_tenacity_control_plane.py tests/plugins/test_crypto_bot_pm_provider_isolation.py`
   - `python3 tools/crypto_bot_control_plane_self_check.py --format json`
   - `python3 tools/crypto_bot_autonomy_readiness.py --format json`
5. Commit the source change on the Hermes control-plane branch, then rerun self-check/readiness and record the exact self-check artifact path.
6. If reporting or commenting on a Kanban card, include: Hermes branch, commit, changed file, validators, self-check path, readiness booleans, product repo unchanged/clean state if applicable, and explicit non-actions.

## Pitfalls

- Do not patch source constants or readiness checks to force green; parity must be restored by syncing legitimate content.
- Do not use shell pipelines into interpreters in unattended cron verification, for example `hermes ... --json | python3 -c ...`; the approval prompt can strand the run. Use one Python process with `subprocess.run(..., capture_output=True)` and parse stdout in-process.
- Do not claim product completion from a control-plane parity repair. Product branch-local completion still depends on its own sidecar/completion-gate evidence.

## Session-derived example

A cron run found `custom_skill_parity["codex-sidecar skill"] = false` and `native_control_plane_ready=false` because the installed runtime `codex-sidecar` skill accepted `Blocked-surface scan: PASS, basis: ...`, while source still recommended only `PASS with basis: ...`/standalone `PASS`. The repair ported that exact parser-compatible guidance into source, ran the focused tests and self-check/readiness, committed the Hermes change, then commented on S017F with the control-plane evidence while leaving the product branch unchanged.