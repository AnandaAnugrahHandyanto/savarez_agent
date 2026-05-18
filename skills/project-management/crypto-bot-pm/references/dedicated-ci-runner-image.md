# Dedicated CI runner image and network recovery

Use this reference when crypto_bot local Gitea Actions reaches jobs but JavaScript actions such as `actions/checkout` fail before project validation runs.

## Durable pattern

For local Gitea/act_runner CI, fix runner infrastructure in the Hermes control plane instead of editing product workflows just to bypass checkout.

A healthy S006-style local runner should provide both:

- A Node-capable job image label, e.g. `ubuntu-latest:docker://crypto-bot-ci-runner:python313-node20-go`.
- Job-container network access to the Gitea service, e.g. act_runner `container.network: crypto-bot-gitea-net` or an equivalent configuration that lets job containers resolve `crypto-bot-gitea`.

The dedicated image fixes `Cannot find: node in PATH`, but it does not by itself guarantee checkout can fetch the repo. If the runner launches job containers on an isolated/default Docker network, checkout can progress to Node execution and still fail with:

```text
fatal: unable to access 'http://crypto-bot-gitea:3000/preston/crypto_bot/': Could not resolve host: crypto-bot-gitea
```

That is a runner networking/config blocker, not a product workflow failure.

## Triage sequence

1. Inspect runner labels and logs first.
   - Bad old state: `ubuntu-latest:host` or missing dedicated image label.
   - Good image-label state: `ubuntu-latest:docker://crypto-bot-ci-runner:python313-node20-go`.
2. If logs still show `Cannot find: node in PATH`, repair or rebuild the dedicated CI job image / label mapping.
3. If logs show `node .../actions/checkout.../dist/index.js` and `git version ...` but checkout fails on `Could not resolve host: crypto-bot-gitea`, repair act_runner job-container networking.
4. Only rerun S006 CI after the relevant runner repair is applied and bounded approval covers the rerun.
5. Keep S007A/later product work blocked until S006 has CI and merge-readiness evidence.

## Evidence expectations

Collect concise, non-secret evidence:

- Runner inspect output: label mapping, no host-mode `ubuntu-latest`, registration success.
- Toolchain proof from the job image: Python, Node/npm, Go, git versions.
- Post-rerun job summary: run number, job statuses, whether `Cannot find: node` is absent, and whether DNS/network errors remain.
- Log excerpts with secrets redacted. Gitea/checkout masks auth headers as `***`; do not preserve tokens.

## Token hygiene for local Gitea API actions

When a temporary Gitea token is required to dispatch a workflow or read logs:

- Generate it for the narrow local action and keep it in process/env only.
- Do not write the token to files or reports.
- Delete or revoke it immediately after use.
- If API token deletion fails because auth has already become invalid, clean up the local token record through the local Gitea data plane and report only the token name/cleanup result, never the token value.

## Governance reminder

Runner repair and CI rerun are not product authorization. Do not mutate PR comments/statuses/checks, merge, push product branches, or start later product slices unless a separate approval explicitly covers that action.