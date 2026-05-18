---
name: crypto-bot-pm
description: Use when Hermes autonomously manages safe branch-local crypto_bot development through the Hermes-owned managed-project descriptor, strategic plan, Kanban, policy gates, validators, and Codex sidecar audits while escalating blocked surfaces.
version: 3.0.0
author: Hermes PM
license: MIT
metadata:
  hermes:
    tags: [project-management, crypto-bot, autonomy, gitea, kanban]
    related_skills: [kanban-orchestrator, codex-sidecar]
---

# Crypto Bot PM Bridge

## Overview

Use this skill when Hermes manages, selects, executes, reviews, or reports
software-development work for the `crypto_bot` managed project.

Source of truth:

- Hermes source root: `/Users/preston/.hermes/hermes-agent`
- Managed-project descriptor: `/Users/preston/.hermes/hermes-agent/projects/crypto_bot/crypto_bot.project.yaml`
- Target loop: `/Users/preston/.hermes/hermes-agent/docs/autonomy/crypto_bot_target_loop_v2.md`
- Completion evidence contract: `/Users/preston/.hermes/hermes-agent/docs/autonomy/crypto_bot_completion_evidence_contract.md`
- Remote lifecycle contract: `/Users/preston/.hermes/hermes-agent/docs/autonomy/crypto_bot_remote_lifecycle_contract.md`
- Gitea CI PR target loop: `/Users/preston/.hermes/hermes-agent/docs/autonomy/crypto_bot_gitea_ci_pr_target_loop.md`
- Completion gate: `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_completion_gate.py`
- Remote readiness probe: `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_remote_readiness.py`
- PR evidence packet tool: `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_pr_evidence_contract.py`
- Controlled Gitea PR pilot adapter: `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_gitea_pr_pilot.py`
- Gated Gitea runner recovery helper: `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_gitea_runner_recovery.py`
- Merge readiness dry-run: `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_merge_readiness.py`
- Sidecar prompt generator: `/Users/preston/.hermes/hermes-agent/tools/render_crypto_bot_sidecar_audit_prompt.py`
- Unsupported-claim scanner: `/Users/preston/.hermes/hermes-agent/tools/scan_crypto_bot_completion_claims.py`
- Evidence issue registry: `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_evidence_issue_registry.py`
- Managed product repo: `/Users/preston/robinhood/crypto_bot`
- Strategic plan: `docs/planning/autoresearch_runpod_to_live_trade/plan.json`

Hermes is the autonomous PM, architect, supervisor, verifier, and reporter.
Codex is a bounded audit/coding sidecar, not the primary decision-maker.
The Operator is the strategic supervisor, policy/change-of-scope authority,
emergency stop authority, and live-risk owner. The Operator is not the normal
per-task approval gate for ordinary safe branch-local development.

## Native Tenacity Control Plane

Use native `/goal` for the standing crypto_bot objective. Use the native
Kanban `crypto_bot` board as lifecycle truth for cards, dependency links,
assignees, comments, and blocked/done status. The strategic plan remains the
backlog source, but native Kanban is the durable work queue once imported.
When planning files disagree, prefer live machine-verifiable control-plane state
in this order: managed-project descriptor/readiness gates, native Kanban audit,
PR/CI audit, completion-gate/PR evidence artifacts, then strategic-plan fields.
Do not select a `plan.json` top-level `next_recommended_session_id` when the
session list, remaining-screen notes, native Kanban state, or autonomy readiness
show a lifecycle blocker. Report the conflict and close the blocker first.
If the board has not been imported, generate/read the machine-verifiable import
preview and ask for exact Operator approval before any live board mutation.
Board import approval may authorize only creation/import of the previewed
board/cards and dependency links; it does not authorize worker dispatch,
product writes, Gitea mutation, PR creation, PR updates, CI/runner work, or
merge.

Custom Hermes tools do not replace Tenacity; they enforce crypto_bot-specific
policy and evidence. The completion gate remains completion authority, PR/CI
evidence remains remote-lifecycle authority, and Gitea mutation remains blocked
unless explicit future policy enables the exact action.

For code-changing tasks, use the review-required block/comment convention:
move the card to `review_required` or comment `review_required` with branch,
HEAD, changed files, validators, sidecar status, and completion-gate path
before marking it done. Do not move a card to done until the completion gate
returns `PASS`.
S006 currently has local completion-gate, sidecar, and PR evidence, but it is
not remotely done until PR existence, CI evidence, and merge readiness all close
the remote lifecycle. Missing
historical dev13 docs are warnings unless proven current global blockers. The
`validate-security-evidence-wrapper.py` validator is task-scoped; make it a
blocker only when the selected task requires that validator.
Native Kanban board existence is not sufficient permission to dispatch S007A or
any next product task while `crypto_bot_autonomy_readiness.py` reports
`s006_remote_lifecycle_blocks_next_task: true` or
`ready_to_request_s006_pr_pilot: true`. In that state, ask only for the
controlled S006 PR pilot decision and pause product-task dispatch until PR, CI,
and merge evidence close the S006 remote lifecycle.

## Timeboxed Sleep / Unattended Autonomy Loops

When the Operator gives an overnight, sleep, or otherwise unattended crypto_bot PM window, treat it as a bounded execution budget rather than a plan-only request. Create or update a self-contained cron job, attach `crypto-bot-pm` and any needed control-plane skill such as `hermes-agent`, restrict toolsets to the safe surfaces needed, use the canonical Hermes workdir, and trigger the first run immediately when coverage should begin now. The cron prompt must restate active authorities, evidence requirements, milestone-only reporting expectations, and all hard forbids because future runs do not inherit chat context. See `references/timeboxed-sleep-autonomy-loop.md` for the exact setup, prompt-contract, and reporting pattern. In cron-run sessions, let the scheduler deliver the final assistant response; do not call `send_message` for the same report, and return exactly `[SILENT]` only when the prompt permits silent no-op runs and there is genuinely nothing new. See `references/sleep-cron-delivery-discipline.md` for the no-duplicate-delivery pattern. When summarizing verbose JSON preflights unattended, avoid shell pipes into interpreters that can trigger approval gates; use the single-process subprocess parsing pattern in `references/unattended-preflight-json-summarization.md`. In cron/sleep runs this is not just style: never run `tool.py --format json | python -c ...` because the approval prompt can strand the run with no operator present. Instead launch the preflight from one Python process with `subprocess.run(..., capture_output=True)`, parse stdout, and print only the concise fields needed for the report. If a previous run or context compaction only preserved "one-line JSON output" or truncated verbose tool output, rerun the preflight through that summarizer before deciding or reporting so the final milestone cites exact readiness booleans, blocker lists, and artifact paths instead of inferred pass/fail state. Before commenting or reporting timestamped evidence paths, verify the exact artifact file exists; see `references/control-plane-artifact-path-verification.md` for the proof-before-comment pattern and minimal correction approach.

## True Target Loop

1. Load the managed-project descriptor from `/Users/preston/.hermes/hermes-agent`.
2. Read native `/goal`, native Kanban lifecycle truth, and the crypto_bot
   strategic plan. If native Kanban is not imported and no explicit
   transitional plan-driven mode is active, stop at board-import approval
   request instead of selecting S007A. If native Kanban is imported but S006
   remote lifecycle still blocks next-task readiness, stop at the S006 PR pilot
   decision instead of selecting S007A.
3. Select the next unblocked task that advances crypto_bot completion and record
   durable task-source proof: strategic-plan item/session id or Hermes Kanban
   card/export path.
4. Record the path allowlist source for the selected task, then classify the
   task by infrastructure policy.
5. If the task is auto-executable branch-local work, proceed without per-task
   Operator approval.
6. Delegate bounded implementation, review, validation, and Codex sidecar audit
   work as needed.
7. Commit locally only after validators and any pre-commit review pass.
8. Generate a final sidecar audit prompt with
   `/Users/preston/.hermes/hermes-agent/tools/render_crypto_bot_sidecar_audit_prompt.py`,
   then run the required final post-commit Codex sidecar audit on the clean
   committed HEAD.
9. Run `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_completion_gate.py` for the exact
   task/base/branch/HEAD. A task is complete only when the completion gate
   returns `PASS` and writes a completion-gate JSON report.
10. Update native Kanban comments/state, report evidence, and continue while
   `/goal` budget permits only when the latest completion-gate JSON is `PASS`
   and readiness remains green.

Before any PR pilot, mirror acquisition, dispatch, or CI-related action, run the
control-plane preflight from `/Users/preston/.hermes/hermes-agent` using absolute paths:

- `python3 tools/crypto_bot_control_plane_self_check.py --format json`
- `python3 tools/crypto_bot_kanban_import_audit.py --expected-card-count 90 --expected-dependency-count 101 --preview /Users/preston/.local/state/hermes-operator/kanban-import-previews/crypto_bot-preview.json --format json`
- `python3 tools/crypto_bot_pr_ci_audit.py --repo-root /Users/preston/robinhood/crypto_bot --gitea-url http://127.0.0.1:3005 --owner preston --repo crypto_bot --source-branch hermes/dev13-006-daemon-trust-contract-mapping --source-head 8be208ba317972da03060eb0170a40d2a678aa99 --target-branch main --format json`
- `python3 tools/crypto_bot_autonomy_readiness.py --format json`

If any command fails or reports source/runtime parity drift, stop and repair the
Hermes control plane first. Do not continue to PR pilot, mirror, runner,
dispatch, or product-work steps while self-check reports `native_control_plane_ready: false`
or a runtime asset diverges from `/Users/preston/.hermes/hermes-agent`. When a
skill/reference is updated in the source checkout during control-plane work,
synchronize the installed skill copy as part of the same change before rerunning
preflight; otherwise the self-check will correctly block runner/CI actions on
source/runtime parity drift.

## Auto-Executable Branch-Local Work

Hermes may proceed without per-task Operator approval when the task:

- Uses a non-protected local branch.
- Modifies only allowlisted non-secret files in the managed repo.
- Allows docs-only contract Markdown to mention daemon/service concepts only
  when the exact safe docs path or pattern is allowlisted by the selected
  strategic-plan item or managed-project descriptor.
- Has durable selected-task evidence from the strategic plan or a Hermes Kanban
  card/export path. Commissioning or maintenance tasks outside the strategic
  plan require a Kanban card/export path before any write.
- Does not inspect secrets or touch broker/trading/financial/runtime/deploy
  surfaces.
- Does not edit `.gitea/workflows`, start runners/workflows, mutate Gitea, push,
  or promote protected branches unless a current Operator directive and the managed-project descriptor explicitly allow the exact code-related surface for documented plan advancement.
- Even under broad code-work approval, preserves hard forbids for secrets, broker/trading/financial APIs, live runtime/deploy, and protected-branch merge unless separately and exactly authorized.
- Runs required validators and `git diff --check`.
- Uses `ruff check` where appropriate and never uses `ruff format`.
- Runs Codex sidecar final post-commit audit on a clean worktree,
  and does not substitute Hermes self-audit for a failed or missing Codex audit.
- Runs the Hermes completion gate after the sidecar audit and records the
  completion-gate JSON path.
- Produces branch, commit, changed-file, validator, sidecar, and non-action
  evidence.

Safe branch-local autonomy remains allowed once the completion gate returns `PASS`.

## Staged Remote Lifecycle

Push, PR, and merge authorities are staged authorities, not general permissions.
Local branch-local autonomy remains available when readiness and the completion
gate pass, but remote lifecycle work must follow this staged policy:

- Read-only remote/CI discovery is allowed.
- PR evidence packet generation is allowed.
- Controlled branch pushes and draft PR creation are allowed for validated slice
  branches when the scope is CI validation only.
- Read-only CI/PR status monitoring is allowed after those draft PRs exist.
- PR updates beyond draft creation, PR comments, statuses, and check mutation are
  escalation-required.
- Merge-to-main and protected branch mutation are escalation-required and
  disabled by default.

Hermes may read workflow files and check status. For validated slice branches,
Hermes may push those branches and create draft PRs for CI validation only.
Hermes must not edit workflows, start workflows, start runners, deploy, inspect
secrets, mutate PR metadata beyond draft creation, mutate Gitea broadly, or merge
unless a future policy explicitly enables that specific authority. No merge-to-main
is allowed without explicit future policy, current CI/check evidence, and a
separate merge readiness gate.

A successful remote branch push does not prove PR creation. A failed PR creation leaves the pilot in a partial paused state until read-only Gitea PR discovery proves that a PR exists or the Operator gives fresh exact approval for a retry. An adapter runtime failure before any API call is a Hermes tool/runtime bug, not a crypto_bot product failure; Hermes must not retry PR creation until the adapter `--self-check`, dry-run, and `--create-pr-only --preflight-only` pass with the same command shape and the same Python runtime Hermes used. If any adapter failure occurs, do not retry PR creation again until those three checks pass immediately before execution. If the remote branch already exists at the exact approved SHA, the retry must not push again; it may request at most one PR creation from that existing branch/head to `main` through the Hermes-owned adapter. If an open PR already exists but its remote source branch points to an older SHA than the locally validated completion-gate HEAD, do not request PR creation again and do not dispatch the next product task. Classify the state as stale PR branch / head mismatch, generate fresh local-head completion and PR-evidence packets if needed, run read-only `ls-remote` and PR/CI audit evidence, then request only a narrowly scoped controlled remote branch update for the existing PR branch; PR metadata/comments/statuses/checks, workflow/runner starts, merge, deploy, runtime, secrets, and broker/trading actions remain separately forbidden. During the pilot, PR updates, comments, status/check mutation, workflow/runner starts, and merge remain blocked.

Gitea assigns pull request numbers sequentially. Never assume a strategic-plan
item such as `S006` maps to PR `#42` or any other fixed number. Read the actual
PR number from the Gitea API response or from
`/Users/preston/.hermes/hermes-agent/tools/crypto_bot_pr_ci_audit.py`, then use that resolved
number for PR/CI evidence. The audit defaults to discovering the matching S006
PR by source branch, source HEAD, and target branch.

Before any approved PR creation attempt, authentication readiness means the
Hermes-owned adapter can see a non-empty token environment variable named by
`--token-env-var`, and read-only Gitea probes can verify PR state without
printing token material. Do not echo, cat, log, or otherwise reveal tokens. If a
token is missing or invalid, stop and report the blocker; do not fall back to
direct database insertion or token-printing workarounds.

When local Gitea write auth is missing and the Operator explicitly asks to
create/configure it, generate an access token inside the `crypto-bot-gitea`
container for user `preston` with only the scopes needed for Hermes PM work.
Redirect `gitea admin user generate-access-token --raw` to a `0600` temp file;
never let token material reach terminal output, tool output, logs, or chat.
For PM comments/status evidence, include `write:issue,read:repository,read:user`:
`read:user` is required for `/api/v1/user` verification, while `write:issue`
allows issue comments. Persist as `GITEA_TOKEN` and `GITEA_READ_TOKEN` in
`/Users/preston/.hermes/.env`, chmod the file `0600`, verify with authenticated
API calls that print only booleans/IDs/URLs, and note that long-lived Hermes
gateway processes may need restart/reload before the new env is visible to
agent-launched plugin subprocesses.

Runner recovery is not product work and remains gated. If the Operator
explicitly authorizes local `crypto_bot` runner recovery, use
`/Users/preston/.hermes/hermes-agent/tools/crypto_bot_gitea_runner_recovery.py --inspect`
first. If inspect already reports `PASS`, the approved container is up,
registered successfully, and token/instance empty loops are absent, consume the
approval conservatively: do not run `--execute`, recreate the container, or
otherwise mutate runtime state just because approval was granted. Report the
healthy runner state and continue only with read-only CI evidence checks.
Execution requires the helper's exact approval phrase and the explicit CLI execution flag (`--execute --approval-phrase "..."`); `--approval-phrase` without `--execute` is only inspect/default mode and must not be reported as runtime recovery. It may recreate only the
`crypto-bot-linux-runner` container with the correct act_runner image contract:
`GITEA_RUNNER_REGISTRATION_TOKEN`, `/data/.runner`, `crypto-bot-gitea-net`, and
labels `linux,crypto-bot-python-313,ubuntu-latest:docker://crypto-bot-ci-runner:python313-node20-go`, using the dedicated CI job image `crypto-bot-ci-runner:python313-node20-go`. See `references/dedicated-ci-runner-image.md` for the durable runner-image pattern and fail-closed inspection requirements. It must not dispatch workflows, update PR
metadata/comments/statuses/checks, merge, edit workflow files, touch product
files, print secrets, or insert tokens directly into the database.

Keep readiness split into `local_evidence_ready`, `remote_readiness_ready`,
`pr_evidence_ready`, `ci_evidence_ready`, `merge_readiness_ready`,
`ready_for_local_autonomy`, `ready_for_remote_pr_pilot`, and
`ready_to_request_controlled_one_pr_pilot`, and `ready_for_merge_autonomy`. A
green local loop does not imply PR or merge authority. A request-ready one-PR
pilot state authorizes only asking the Operator for exact approval, not pushing
or creating a PR.

## Escalation Required

Stop and report the reason before any work involving:

- Secrets, `.env`, token files, Keychain material, private keys, cookies,
  credential stores, runtime databases, generated credential artifacts, or
  credential-bearing logs.
- Robinhood, broker, exchange, live-market, account, order, position, wallet,
  trading, or financial APIs.
- Runtime services, app servers, workers, schedulers, launchd, qmd, Docker
  builds, Kubernetes, Flux, Harbor, OpenBao, RabbitMQ, Redis, Temporal,
  production services, Gitea runners, or workflows.
- Deploys, GitOps promotion, protected-branch merge, release publishing, or
  package publication.
- Gitea writes, issue/PR/comment/label/project/check/status mutation, webhook
  mutation, repository mutation, tool-permission expansion, or policy changes.

## Procedure

1. Confirm `/Users/preston/robinhood/crypto_bot` exists and starts clean.
2. Load `/Users/preston/.hermes/hermes-agent/projects/crypto_bot/crypto_bot.project.yaml`.
3. Inspect the strategic plan and Hermes Kanban, then pick the next unblocked
   task.
4. Record the selected strategic-plan item/session id or durable Hermes Kanban
   card/export path. If no durable task source exists, stop and escalate instead
   of writing product files.
5. Record the allowlisted path source for the selected task and classify it as
   auto-executable or escalation-required.
6. For auto-executable work, create a branch and implement only within
   allowlisted paths.
7. Run targeted tests/validators, `git diff --check`, and secret/governance
   validators when relevant.
8. Commit locally only when pre-commit evidence passes.
9. Render the final sidecar prompt with
   `/Users/preston/.hermes/hermes-agent/tools/render_crypto_bot_sidecar_audit_prompt.py`.
   Do not hand-write a final prompt that pre-fills a clean/pass conclusion.
10. Run the final post-commit Codex sidecar audit through
   `/Users/preston/.local/bin/hermes-codex-audit --mode audit-readonly` after
   the commit. The result must be outside the product repo, non-empty, current,
   and name the same branch and commit hash as the local HEAD being reported.
   A dirty-worktree, pre-commit, smoke-test, stale, or different-HEAD audit is a
   blocker and must not be reported as completion.
11. Run `/Users/preston/.hermes/hermes-agent/tools/crypto_bot_completion_gate.py` against the
   exact base ref, branch, and final HEAD. The gate must run or verify
   `git status --short --branch`, `git rev-parse --abbrev-ref HEAD`,
   `git rev-parse HEAD`, `git diff --name-only <base>..<head>`, and
   `git diff --check <base>..<head>`.
12. If the completion gate returns `FAIL` or `BLOCKED`, mark the task
   `BLOCKED`, `NEEDS_REPAIR`, or `repair_attempted`, record the gate JSON path
   and blockers, pause next-task selection, and do not report `Completed`.
13. Report selected task source, branch, commit, changed files, checks, Codex
   result, blocked-surface proof, completion-gate JSON path, and next
   autonomous action.

Use absolute file paths for writes and evidence. Never claim completion, clean
state, successful checks, a commit, or sidecar evidence unless the commands
actually ran in the current session, the results are available, and the final
sidecar result corresponds to the reported committed HEAD. Never infer
`git diff --check` success from a clean worktree. Never accept old sidecar
diagnostics, smoke audits, Telegram reports, PM summaries, or prefilled sidecar
results as completion evidence.

## Completion Gate Rules

The canonical completion evidence schema is
`hermes.autonomy.crypto_bot_completion_gate.v1`. The completion gate is the only
authority for final branch-local completion. It fails closed when validators are
missing, when `git diff --check` fails, when changed paths touch blocked
surfaces, when sidecar evidence is stale or semantically insufficient, or when a
sidecar result claims success without command evidence. Treat changed filenames
as part of the blocked-surface contract: even safe planning/evidence artifacts
can block if their path contains hard-surface tokens such as `trading`, `broker`,
`order`, `account`, `live`, or `runtime`. Prefer neutral evidence filenames
inside the allowlist, and if the gate blocks on path-token hygiene, rename the
file, update evidence metadata, amend/recommit, regenerate the sidecar prompt,
rerun the sidecar audit, and rerun the completion gate on the new HEAD. See
`references/completion-gate-path-token-hygiene.md` for the repair pattern.

Do not proceed to a new autonomous crypto_bot task while the readiness verifier
reports `evidence_loop_ready: false` or `ready_for_next_task: false`. Readiness
uses active and repair-attempted evidence issues under
`/Users/preston/.local/state/hermes-operator/evidence-issues/`; do not patch
source constants to force readiness green.
If readiness reports `ready_to_request_board_import: true` while
`ready_for_next_task: false`, ask only for native board-import approval. Do not
run S007A, dispatch workers, mutate Gitea, create PRs, or write product files
as part of that request.
Previously piloted remote/PR/Gitea expansion does not override an unhealthy
evidence loop; do not push, create PRs, mutate Gitea, start services, run
workflows/runners, or edit workflow files while the evidence loop is blocked.

**Control Plane Consistency Rule**

The native Kanban audit, PR/CI audit, and readiness verifier must always agree
on board state, resolved PR existence, evidence linkage, completion-gate status,
and S006/S007A lifecycle before any CI-runner proposal or runner-start approval
can be considered trustworthy. When the Kanban audit reports DB read failure or
0 cards, or when a PR/CI audit tool is missing, the control plane is in
regression and all CI safety hardening proposals are blocked until the
repaired tools are committed to the canonical Hermes source root and all three
tools pass on the live state. Do not accept readiness alone when audit tools
disagree. Do not propose runner start, registration, or local action mirrors
while the audit tools report `IMPORT_FAILED_OR_PARTIAL` or are missing.

When the Kanban import audit reports S006 remote state as `pr_absent` while the
PR/CI audit discovers the matching Gitea PR, repair Hermes control-plane tooling
before any product task or runner/CI proposal. The durable repair pattern is to
hydrate Kanban remote lifecycle status from the same live read-only PR/CI audit
payload used by readiness when no explicit remote-readiness JSON is supplied,
then classify the result as a valid remote lifecycle block such as
`IMPORT_VALID_REMOTE_LIFECYCLE_BLOCKED` when PR exists but CI evidence remains
pending. See `references/control-plane-lifecycle-consistency.md` for the
session-derived repair recipe, validator quartet, and reporting pattern. See
`references/merged-remote-lifecycle-readiness.md` when a live PR/CI audit reports
S006 or another blocking PR as `merged` but Kanban/readiness still classifies the
remote lifecycle as pending; a verified merged PR is terminal lifecycle evidence
and should be repaired in Hermes control-plane arbitration rather than by product
or Gitea mutation. See `references/stale-pr-branch-head-mismatch.md` when local
completion evidence is newer than the existing Gitea PR source branch; it records
the read-only probes, classification, and controlled remote-branch-update request
pattern. See
`references/post-push-pr-ci-evidence.md` after an approved stale-branch push:
it records the evidence-only follow-up, stale PR-body/evidence-link nuance,
merge-readiness CI evidence normalization, and why PR metadata/status/check
updates remain separate approvals. See
See `references/controlled-pr-metadata-evidence-refresh.md` when a scoped approval
allows updating an existing PR body to refresh evidence links only; it records
body-only PATCH scope, auth hygiene, explicit audit arguments, and reporting
requirements. See `references/controlled-gitea-pm-evidence-comment.md` when a
scoped approval allows only Gitea PM evidence/status mutation for a completed
work block; it records the minimal-comment pattern, write-auth preflight,
post-mutation verification, and conservative no-workaround behavior when a token
is absent. See `references/controlled-protected-branch-merge.md` when a
scoped approval allows exactly one protected-branch PR merge; it records final
preflight, Gitea merge endpoint usage, post-merge lifecycle verification, and
merged-state control-plane pitfalls.
See `references/planning-readiness-arbitration.md` for the planning-review rule:
when `plan.json`, strategic summaries, native Kanban, and readiness disagree,
close live control-plane/readiness blockers before selecting S007A, S017A, or
any other next product task. See `references/plan-track-readiness-reconciliation.md`
when an already-advanced strategic-plan track needs a small branch-local
reconciliation artifact to document the completed local boundary, avoid repeat
work, and stop before provider/cloud/runtime approval gates.

`references/dedicated-ci-runner-image.md` for the dedicated job image,
act_runner job-container network requirement, rerun evidence sequence, and
temporary-token hygiene. See `references/runner-networking-ci-recovery.md` for
fail-closed repair/inspection of `actions/checkout` DNS failures caused by job
containers not joining `crypto-bot-gitea-net`. See
`references/local-gitea-actions-toolcache-hardening.md` when CI gets past Node
and checkout but fails because local act_runner job images/toolcache lack
GitHub-hosted-runner assumptions such as Python 3.13 arm64 toolcache metadata or
`ripgrep`. See `references/pr-ci-deterministic-validator-iteration.md` when PR
sync CI reaches deterministic validators, when Gitea append-only statuses must
be collapsed to latest-per-context state, or when live PR HEAD differs from stale
completion/PR-evidence packets; it records the evidence-first repair, validator
rerun, commit/push, branch-target fallback PR discovery, `ls-remote` before stale
tracking refs, explicit stale-head lifecycle classification, current-head
mismatch triage, and final status-reporting loop. See
`references/s006-approved-code-scope-evidence-repair.md` when the Operator gives
broad code-related approval and S006 still has stale completion/PR evidence for
a live PR head; it captures the allowlist/policy-scanner repair pattern, ruff
fix loop, fresh sidecar/gate/PR-evidence sequence, and hard safety boundaries
that remain in force.

Evidence issue statuses are `active`, `repair_attempted`, `repaired`,
`invalidated`, and `superseded`. A dev13-005-style completion failure stays
`active` or `repair_attempted` until a later HEAD passes the completion gate and
the issue is marked `repaired` with the passing gate JSON path. A dev13-006-style
unsupported completion claim stays `active` until proven by local
branch/commit/sidecar/passing-gate evidence or explicitly marked `invalidated`
with a machine-readable artifact.

Use strategic-plan IDs such as `S006` as durable task IDs. Keep `task_id`,
`session_id`, `branch_alias`, and `claim_id` distinct: a branch alias such as
`dev13-006` must not revive an old invalidated Telegram-only claim unless the
new passing gate explicitly names that claim ID. Do not proceed to a new
autonomous crypto_bot task while the current completion gate is `FAIL` or
`BLOCKED`.

## Safe PM Plugin Tools

The `crypto-bot-pm` plugin remains read/proposal oriented. Prefer it for PM
status, read-only Gitea snapshots, development workstream packets, and Kanban
evidence when available. Plugin tool output is evidence for planning and
classification; it does not replace validators, local git evidence, Codex
sidecar final audit, or the completion-gate JSON report.

When PM status reports `Gitea snapshot module is unavailable` or recommends
regenerating PM/Kanban context, cross-check the direct snapshot module and the
Kanban packet before treating it as real Gitea unavailability. If Kanban or the
direct snapshot sees live Gitea state while PM status reports a `<local-import>`
blocker, classify it as Hermes control-plane/plugin import isolation and fix the
PM status path before relying on its recommendation. See
`references/pm-plugin-import-isolation.md` for the diagnostic sequence, durable
fix pattern, semantic parity regression gates, and focused provider-isolation tests. If PM status specifically fails on `scripts.hermes_pm.*` while plugin files exist, also see `references/pm-status-script-package-shadowing.md`; a third-party `scripts` package can shadow the plugin-local package unless `plugins/crypto-bot-pm/scripts/__init__.py` anchors the package and `project_status.py` clears unrelated preloaded `scripts` modules before provider imports.

When unattended PM/readiness preflight reports installed runtime skill divergence, repair it before product work: compare source/runtime hashes and diff, port legitimate runtime-only guidance back into the canonical source checkout, verify hashes match, rerun self-check/readiness, and commit the source repair. If the runtime copy has a legitimate extra reference file or small guidance delta, copy/sync the exact runtime bytes into source (or make the minimal source patch), then verify source/runtime hashes match before validators; do not hand-recreate semantically similar text and assume parity. If the only drift is installed `SKILL.md` prose that already contains more complete guidance than source, preserve that runtime guidance by patching the source copy to the same bytes rather than overwriting runtime from stale source; then verify matching SHA256 for both copies before claiming the blocker is fixed. When the divergence is a runtime-only `references/*.md` plus a SKILL.md pointer, copy the reference file byte-for-byte into source, patch the source pointer, verify both the main SKILL.md and the reference hashes against runtime, run the focused Tenacity/control-plane tests, then rerun self-check/readiness before selecting product work. See `references/unattended-runtime-skill-parity-repair.md` for the cron-safe pattern and report shape. For `codex-sidecar` skill parity drift specifically, see `references/codex-sidecar-runtime-parity-repair.md` for the minimal source-sync, validation, self-check artifact, and Kanban-comment pattern.

When the fix is in the Hermes Agent control-plane checkout rather than the
managed product repo, also follow the `hermes-agent` skill's control-plane branch
hygiene and divergence reconciliation references before committing, pushing, or
reporting branch readiness. See `references/runtime-skill-source-parity-repair.md`
when readiness/self-check reports installed runtime skill divergence from the
canonical Hermes source checkout; it records the safe sync-back, validation,
commit, and reporting pattern. In unattended cron runs, treat runtime/source
skill parity drift as a first-class control-plane blocker: repair the source
skill/reference, synchronize the installed skill copy through the skill manager
or approved runtime sync path, rerun self-check/readiness, and only then resume
product-branch evidence work.

When readiness is green but the strategic plan still points at a supposedly
planned session, check live product branches, completion-gate artifacts, and
sidecar evidence before writing product docs. If existing committed evidence
already covers the candidate session, preserve it and perform branch/evidence
arbitration or review-gate closure instead of regenerating files. See
`references/existing-product-evidence-branch-arbitration.md` for the safe
inspection/restore/report pattern. When the remaining safe work is closing a
`requires_review_before_next_session` boundary, add a narrow allowlisted review
closure artifact, commit it, regenerate the final sidecar audit, and rerun the
completion gate for the new HEAD; see
`references/review-gate-closure-after-reconciliation.md`. Do not advance into a
later provider/cloud/runtime approval gate just because local readiness is green.

## Forbidden Actions

Do not place trades, call broker/trading/financial APIs, inspect secrets, start
services, run workflows, start runners, deploy, edit `.gitea/workflows`, invoke
`apply_approved_write_plan.py`, invoke `branch_local_writer.py`, invoke
`execute_forge_issue_create.py`, use `ruff format`, push, create PRs, merge, or
mutate Gitea unless a future policy explicitly enables that exact authority.
