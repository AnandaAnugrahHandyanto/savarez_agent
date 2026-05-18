# Unattended Runtime Skill Parity Repair

Use this when a crypto_bot sleep/cron PM run is blocked by Hermes control-plane self-check or autonomy readiness reporting installed runtime skill divergence, especially for `crypto-bot-pm`.

## Durable pattern

1. Treat parity drift as a first-class control-plane blocker. Do not proceed to product work, PR/CI work, runner work, or Gitea mutation while `native_control_plane_ready` / source-runtime self-check is false.
2. Compare canonical source and installed runtime skill files without printing secrets:
   - Source: `/Users/preston/.hermes/hermes-agent/skills/project-management/crypto-bot-pm/SKILL.md`
   - Runtime: `/Users/preston/.hermes/skills/project-management/crypto-bot-pm/SKILL.md`
   - Hash both files and inspect a concise unified diff.
3. If the runtime skill is ahead with legitimate guidance from a prior session, port that guidance back into the canonical Hermes source checkout rather than deleting it from runtime.
4. Verify source and runtime hashes match after the edit.
5. Rerun:
   - `python3 tools/crypto_bot_control_plane_self_check.py --format json`
   - `python3 tools/crypto_bot_autonomy_readiness.py --format json`
6. Commit the source-control repair in the Hermes Agent checkout before reporting readiness restored.

## Unattended-specific pitfall

In sleep/cron runs, avoid shell pipelines like `tool.py --format json | python -c ...` for preflight summarization. Approval prompts can strand the run with no operator present. Prefer a single Python process using `subprocess.run(..., capture_output=True)`, parse stdout, and print only concise readiness booleans, blockers, and artifact paths.

## Reporting shape

Report the repair as a control-plane readiness milestone, not as product completion:

- source repo/branch/commit
- exact asset synchronized
- before/after readiness booleans
- confirmation that no product, Gitea, PR/CI, runner, workflow, provider, runtime, or financial mutation occurred unless separately authorized
