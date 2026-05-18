# Controlled Gitea PM Evidence Comment

Use this pattern when the Operator explicitly approves narrow Gitea PM mutations to record evidence/status for an already-completed crypto_bot work block.

## Scope

Allowed under the narrow approval:

- A minimal issue/PR comment, label, card, or project update strictly needed to record the approved work block's evidence/status.
- Read-only verification before and after the mutation.

Still forbidden unless separately approved:

- Runner/workflow starts.
- Deploy/runtime actions.
- Secret inspection or exposure.
- Provider resource mutation.
- Broker/trading/financial actions.
- Protected-branch merge.
- Unrelated Gitea resources.

## Procedure

1. Re-read live Gitea PM state with GET-only tooling and identify the single minimal mutation needed.
2. Confirm write-auth readiness without printing token material:
   - Check only whether the configured token environment variable exists and is non-empty, plus optionally its length.
   - Do not echo, cat, log, copy, rotate, or inspect the token value.
3. If write auth is absent, stop before attempting the write when possible and report `blocked: token required` plus the intended endpoint/action.
4. If write auth is present, execute exactly the planned minimal Gitea mutation.
5. Immediately re-read the affected issue/PR/card state with GET-only tooling and report the durable handle: issue/PR number, comment ID if returned, endpoint class, and post-mutation count/state.
6. Report non-actions explicitly, especially runners/workflows/runtime/secrets/trading/merge.

## Evidence comment shape

A concise evidence/status comment should include:

- Task/session boundary.
- Branch and commit.
- Changed files.
- Validators and results.
- Codex sidecar audit path/result.
- Completion-gate path/result.
- Current local git state if relevant.
- Remaining gates.
- Non-actions.

## Pitfalls

- Do not treat broad Gitea PM mutation approval as authority to repair authentication, inspect secrets, or try credential workarounds.
- Do not mutate just because approval exists; if read-only state proves the evidence/status is already recorded, consume approval conservatively and report no mutation needed.
- A failed unauthenticated POST is not evidence of a completed mutation. Verify with GET-only lifecycle/comment reads before reporting outcome.
