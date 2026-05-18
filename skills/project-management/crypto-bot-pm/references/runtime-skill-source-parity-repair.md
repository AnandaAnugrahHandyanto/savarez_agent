# Runtime Skill / Source Parity Repair

Use this reference when crypto_bot readiness or control-plane self-check reports that an installed Hermes runtime skill diverges from the canonical Hermes source checkout.

## Durable lesson

For crypto_bot PM work, installed runtime assets and canonical source assets must agree before product dispatch, CI/runner proposals, PR pilot work, or further autonomy. A divergence in `crypto-bot-pm` skill content is a control-plane blocker even if the product repo is clean and local evidence gates are otherwise green.

## Safe repair pattern

1. Stop product-task selection and classify the state as Hermes control-plane parity drift.
2. Inspect both repos' git state before edits:
   - `/Users/preston/.hermes/hermes-agent`
   - `/Users/preston/robinhood/crypto_bot`
3. Prefer the active installed runtime skill when it contains newly learned references or prompt-critical guidance from recent sessions, then sync that content back into the canonical Hermes source skill path.
4. Preserve the class-level skill shape:
   - keep `SKILL.md` concise but policy-complete;
   - put session-specific/detail-heavy lessons in `references/*.md`;
   - add a one-line pointer from `SKILL.md` to each new reference.
5. When the drift is a single installed `references/*.md` file that is newer than source, treat it as a likely missed skill-library sync from a previous unattended run: copy the installed reference back to the matching source path, then validate parity. Do not discard the installed version just because source is canonical; first inspect which side contains the durable lesson.
6. Validate from `/Users/preston/.hermes/hermes-agent`:
   - `scripts/run_tests.sh tests/test_crypto_bot_tenacity_control_plane.py tests/plugins/test_crypto_bot_pm_provider_isolation.py` when code/plugin behavior changed;
   - `git diff --check` for doc/reference-only changes;
   - `python3 tools/crypto_bot_control_plane_self_check.py --format json`;
   - `python3 tools/crypto_bot_autonomy_readiness.py --format json`.
7. For unattended cron/sleep runs, summarize verbose JSON preflights with the single-process subprocess pattern from `references/unattended-preflight-json-summarization.md` instead of shell-piping JSON or git output into interpreters.
8. Commit the Hermes control-plane repair locally on a non-protected branch before reporting readiness.
9. Re-run the preflight quartet before any PR pilot, mirror acquisition, dispatch, or CI-related action.

## Reporting requirements

Report:

- changed skill/reference paths;
- Hermes branch and commit;
- focused test results;
- self-check JSON path;
- readiness booleans and blockers;
- explicit non-actions: no product writes, Gitea mutation, runner/workflow action, runtime/service action, secrets, or trading/financial action unless separately authorized.

## Pitfalls

- Do not force readiness green by editing readiness constants or ignoring parity blockers.
- Do not proceed to S007A/S017G/product work while self-check still reports custom asset parity failure.
- Do not flatten every learned detail into `SKILL.md`; use references for session-derived recipes.
