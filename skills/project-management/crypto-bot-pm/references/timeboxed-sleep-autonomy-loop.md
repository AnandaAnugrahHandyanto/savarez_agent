# Timeboxed sleep autonomy loop

Use this reference when the Operator gives Hermes a sleep/overnight window for autonomous crypto_bot PM work.

## Durable pattern

- Treat the sleep window as a bounded autonomy budget, not a request for a plan-only response.
- Create or update a cron job with a self-contained prompt because future runs do not inherit the current chat context.
- Attach the `crypto-bot-pm` skill and any control-plane skill needed for Hermes runtime work, normally `hermes-agent` when the loop may inspect or repair Hermes-owned control-plane files.
- Use `deliver: origin` unless the Operator explicitly asks for another channel, so milestone/evidence updates return to the same thread/topic.
- Restrict toolsets to what the loop actually needs, usually `terminal`, `file`, `delegation`, `session_search`, `skills`, and `todo` for branch-local PM/code/evidence work. Avoid browser/social/runtime toolsets unless specifically in scope.
- Set `workdir` to the canonical Hermes source root `/Users/preston/.hermes/hermes-agent` so project context, control-plane scripts, and path policies load consistently.
- Trigger the first run immediately after creating the recurring job when the Operator says to continue now or sleep-loop coverage should begin immediately.

## Prompt contract for unattended runs

The cron prompt must restate all active authorities and hard forbids explicitly. Include:

- the exact timebox or end condition;
- approved work classes: safe branch-local docs/code/tests/evidence, local commits, validators, sidecar audits, completion gates, read-only discovery, and any specifically authorized minimal PM evidence/status mutation;
- continuation behavior: pick the next unblocked safe task, repair blockers when safely possible, and move to the next unblocked safe task rather than pausing for routine decisions;
- evidence requirements: branch, HEAD/commit, changed files, validators, sidecar path/status, completion-gate path/status, PR/CI/readiness evidence when relevant;
- milestone-only reporting so Telegram is useful rather than noisy;
- hard forbids: no secrets, broker/trading/financial actions, deploy/runtime/service/daemon starts, runner/workflow starts or reruns, workflow edits, provider/cloud spend, protected-branch merge, push/PR/remote branch update, status/check mutation, or unrelated Gitea mutation unless that exact surface is separately authorized.

## Reporting pattern

After scheduling or resuming a loop, report the operational facts only:

- job name and id;
- cadence, repeat count, delivery target, workdir;
- whether the first run was triggered;
- active authorities encoded;
- hard forbids preserved.

Do not pad the report with planning theater. Do not claim future work completed until a later run returns evidence.