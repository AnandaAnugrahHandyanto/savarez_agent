# Dedicated CI runner image for local Gitea Actions

Use this reference when crypto_bot local Gitea CI reaches jobs but JavaScript actions such as `actions/checkout` fail because the runner job environment lacks Node.

## Durable pattern

Keep the act_runner daemon image separate from the per-job execution image:

- Runner daemon container: `gitea/act_runner:<pinned-version>`
- Job image: a dedicated, pinned local Docker image with Node, Python, Go, git, and governance tooling
- Runner labels: advertise normal workflow labels plus a docker-backed job label, for example:
  - `linux`
  - `crypto-bot-python-313`
  - `ubuntu-latest:docker://crypto-bot-ci-runner:python313-node20-go`

This preserves existing workflow `runs-on: ubuntu-latest` compatibility while routing jobs into an image where Node is on PATH for JavaScript actions.

## Recovery helper requirements

A bounded recovery helper should:

1. Require an exact Operator approval phrase before execution.
2. Build the dedicated job image before registering/re-registering the runner.
3. Recreate only the local runner container/volume needed to refresh labels.
4. Generate runner registration tokens through the supported Gitea command path; never print or persist token material.
5. Emit explicit flags showing it did not dispatch workflows, mutate PR/check/status state, merge, or touch product files.

## Fail-closed inspection

Inspection must fail closed when the live runner is still host-backed:

- Treat `ubuntu-latest:host` in runner logs as a blocker.
- Detect the exact docker-backed label token, not a substring. A label such as `ubuntu-latest:docker://crypto-bot-ci-runner:python313-node20-go-unexpected` must not pass.
- Add regression tests for both old host labels and prefix/suffix label spoofing.

## Validation checklist

- `py_compile` the recovery helper.
- Run the focused control-plane test file with baked-in pytest addopts cleared.
- Run `git diff --check`.
- Use an independent code review pass for fail-closed logic before committing.
- After commit, run read-only inspect; if it reports the old host label blocker, the code is ready but live runner recovery still awaits exact approval.
