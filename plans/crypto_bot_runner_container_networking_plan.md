# Crypto Bot Runner Container Networking Implementation Plan

> **For Hermes:** Implement directly in the Hermes control-plane repo. Do not mutate product files, PR/check/status metadata, merge, push, or dispatch workflows during implementation/testing unless separately approved.

**Goal:** Configure the local Gitea `act_runner` job containers to join `crypto-bot-gitea-net` so `actions/checkout` can resolve `crypto-bot-gitea` during S006 CI.

**Architecture:** Keep the act_runner container and the dedicated CI job image distinct. Add a runner config file generated/managed by the control-plane recovery helper, mount it read-only into the runner container, and set `container.network: crypto-bot-gitea-net` so spawned job containers share DNS with the Gitea service. Preserve fail-closed inspection and evidence reporting.

**Tech Stack:** Python control-plane helper, Docker/act_runner config YAML, pytest regression tests, local Gitea Actions.

---

## Root cause and evidence

- Previous S006 rerun reached `actions/checkout` and executed Node from the dedicated CI image.
- The old blocker `Cannot find: node in PATH` is gone.
- New blocker in all three S006 jobs:
  - `fatal: unable to access 'http://crypto-bot-gitea:3000/preston/crypto_bot/': Could not resolve host: crypto-bot-gitea`
- Root cause hypothesis: `act_runner` is connected to `crypto-bot-gitea-net`, but job containers are created on act_runner's default per-job network instead of `crypto-bot-gitea-net`. Docker DNS name `crypto-bot-gitea` is only resolvable on the shared Gitea network.

## Safety boundaries

- Allowed now: Hermes control-plane file edits, tests, local Docker runner config helper updates, local commit.
- Not allowed now: rerun S006 CI again, push, merge, PR/check/status/comment mutation, product repo mutation, secrets persistence, direct token insertion.
- If a live runner reconfiguration is required after implementation, require a new exact approval phrase unless the user explicitly grants that operational action.

## Task 1: Inspect act_runner networking support

**Objective:** Confirm the config key and current helper behavior before editing.

**Files/commands:**
- Read: `tools/crypto_bot_gitea_runner_recovery.py`
- Read: `tests/test_crypto_bot_tenacity_control_plane.py`
- Command: `docker run --rm --entrypoint /bin/sh gitea/act_runner:0.2.12 -lc 'act_runner generate-config | sed -n "1,220p"'`

**Expected finding:** act_runner supports:

```yaml
container:
  network: "crypto-bot-gitea-net"
```

## Task 2: Add managed runner config rendering

**Objective:** Generate a minimal deterministic runner config in the helper.

**Modify:** `tools/crypto_bot_gitea_runner_recovery.py`

**Implementation details:**
- Add constants:
  - `RUNNER_CONFIG_FILE = "config.yaml"`
  - `RUNNER_CONFIG_PATH = f"/data/{RUNNER_CONFIG_FILE}"`
- Add `render_runner_config() -> str` returning YAML with:
  - `runner.file: /data/.runner`
  - `runner.capacity: 1`
  - `runner.timeout: 3h`
  - `runner.fetch_timeout: 5s`
  - `runner.fetch_interval: 2s`
  - `runner.labels` containing the three runner labels
  - `cache.enabled: true`
  - `container.network: crypto-bot-gitea-net`
  - `container.force_pull: false`
  - `container.force_rebuild: false`
- Do not include tokens, connection strings, or secrets.

## Task 3: Mount and use config in runner recovery

**Objective:** Ensure recreated runner daemon uses the managed config.

**Modify:** `tools/crypto_bot_gitea_runner_recovery.py`

**Implementation details:**
- Write config into the runner data volume before starting daemon, using a temporary helper container or `docker run --rm -v volume:/data --entrypoint /bin/sh ...`.
- Start runner with command:
  - `act_runner daemon --config /data/config.yaml`
- Preserve existing env registration flow and labels.
- Add report fields:
  - `runner_config_path`
  - `runner_job_container_network`
  - `runner_config_network_detected`
- Update inspection to check runner logs or mounted config for the network setting if possible.

## Task 4: Add tests

**Objective:** Lock the behavior and prevent regression.

**Modify:** `tests/test_crypto_bot_tenacity_control_plane.py`

**Tests:**
- `test_runner_recovery_config_sets_job_container_network` asserts rendered config includes `container.network: crypto-bot-gitea-net` and exact dedicated image label.
- Existing execute test asserts a config-writing step occurs before runner start.
- Existing execute test asserts runner command includes `--config /data/config.yaml`.
- Existing no-secret test includes rendered config.

## Task 5: Local verification

**Objective:** Verify code correctness without remote mutation.

**Commands:**

```bash
venv/bin/python -m py_compile tools/crypto_bot_gitea_runner_recovery.py
venv/bin/python -m pytest tests/test_crypto_bot_tenacity_control_plane.py -o 'addopts=' -q
git diff --check
```

Expected: all pass.

## Task 6: Independent review and commit

**Objective:** Verify implementation before landing.

**Steps:**
- Static scan added lines for secrets/shell risks.
- Delegate independent reviewer over diff.
- Fix any blocking findings.
- Commit control-plane changes only.

**Commit message:**

```bash
git commit -m "fix: connect crypto bot job containers to gitea network"
```

## Task 7: Report next operational gate

**Objective:** Provide concise milestone report.

**Report:**
- Plan artifact path.
- Commit hash/state.
- Tests run and results.
- Exact remaining approval phrase for live runner reconfiguration if required.
- State that S006 CI was not rerun under this task unless separately approved.
