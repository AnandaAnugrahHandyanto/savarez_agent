# Hermes Browser Runtime

Local browser runtime for agents.

It runs Chrome as a private sidecar, exposes a local HTTP API, and gives operators safe control over sessions, screenshots, artifacts, human takeover, credential fill, and CAPTCHA/checkpoint state.

## Assumptions

- You run HBR on a trusted local or tailnet host.
- Integrations connect through the CLI or loopback HTTP API.
- Secrets stay outside the repo and outside chat/logs.
- Human approval remains required for login checkpoints, MFA, OAuth consent, payments, final order submission, and destructive actions.

## What it is not

- Not a public browser farm.
- Not an undetectable browser.
- Not a credential vault.
- Not an automatic payment agent.
- Not a proven universal CAPTCHA solver.

## Current status

Ready:

- Local server and CLI.
- Persistent browser profiles.
- Session create/list/get/wait/pause/release/delete.
- Screenshots, downloads, artifact listing, replay, cleanup.
- Local inspector at `/inspector`.
- Human takeover with short-lived tokens.
- Credential broker foundation: fill-only, approval-gated, origin-scoped.
- CAPTCHA/checkpoint report/resolve/status flow.
- CAPTCHA provider-call foundation with fail-closed behavior.
- Fingerprint hygiene controls for persona, UA/UA-CH, locale, timezone, viewport, WebRTC/IP policy, and GPU policy.

Not claimed as ready:

- Automatic CAPTCHA solving. Provider-call was verified, but solve success was not achieved.
- Fresh real 1Password smoke. Mock path is green; real provider path still needs a safe approved test item and sanitized evidence.
- Public exposure. Keep HBR local/private unless reviewed separately.

## Install

From the repo root:

```bash
cargo build --manifest-path browser-runtime/Cargo.toml --release
install -Dm755 browser-runtime/target/release/hermes-browser-runtime ~/.local/bin/hermes-browser-runtime
```

If Chrome is not auto-detected:

```bash
export HBR_CHROME_PATH=/absolute/path/to/chrome
```

If your Linux host cannot use Chrome sandbox:

```bash
export HBR_CHROME_NO_SANDBOX=1
```

## Start

```bash
export HBR_BIND=127.0.0.1:7788
export HBR_BEARER_TOKEN='local-agent-token'
export HBR_OPERATOR_TOKEN='different-local-operator-token'

hermes-browser-runtime server
```

Health check:

```bash
curl -s http://127.0.0.1:7788/health
```

Expected:

```json
{"ok":true}
```

## Connect from CLI

```bash
export HBR_SERVER=http://127.0.0.1:7788
export HBR_BEARER_TOKEN='local-agent-token'
export HBR_OPERATOR_TOKEN='different-local-operator-token'
```

Create a profile and session:

```bash
hermes-browser-runtime profiles create --id agent-main
hermes-browser-runtime sessions create --profile-id agent-main
```

Copy the returned session id into `SESSION_ID`.

Basic operations:

```bash
hermes-browser-runtime sessions get "$SESSION_ID"
hermes-browser-runtime sessions screenshot "$SESSION_ID" --output /tmp/hbr.png
hermes-browser-runtime sessions pause "$SESSION_ID" --reason "human approval needed"
hermes-browser-runtime sessions wait "$SESSION_ID" --timeout-secs 300
hermes-browser-runtime sessions release "$SESSION_ID"
hermes-browser-runtime sessions delete "$SESSION_ID"
```

## Main CLI areas

```bash
hermes-browser-runtime profiles   create|list|delete
hermes-browser-runtime sessions   create|get|list|pause|wait|release|screenshot|delete
hermes-browser-runtime artifacts  list|downloads|download|cleanup|replay
hermes-browser-runtime credentials fill|status|approve|deny|privacy-guard clear
hermes-browser-runtime captcha    report|resolve
```

## Configure credentials

Default is disabled:

```bash
export HBR_CREDENTIAL_PROVIDER=disabled
export HBR_CREDENTIAL_PRIVACY_GUARD=true
```

Mock mode for local testing:

```bash
export HBR_CREDENTIAL_PROVIDER=mock
export HBR_CREDENTIAL_POLICY_PATH=/absolute/private/path/hbr-credential-policy.json
```

Real 1Password mode is approval-gated:

```bash
export HBR_CREDENTIAL_PROVIDER=onepassword_cli
export HBR_OP_PATH=/absolute/path/to/op
export HBR_CREDENTIAL_POLICY_PATH=/absolute/private/path/hbr-credential-policy.json
```

Rules:

- Policy file stays private.
- Origins must match exactly.
- Agent sees status only, never raw secret values.
- `HBR_OPERATOR_TOKEN` must be different from `HBR_BEARER_TOKEN`.
- Approve/deny and privacy-guard clear are operator-only actions.

## Credential fill flow

```bash
hermes-browser-runtime credentials fill "$SESSION_ID" \
  --alias demo_login \
  --expected-origin https://example.com \
  --username-selector 'input[name=email]' \
  --password-selector 'input[type=password]' \
  --purpose "operator-approved login fill"
```

Copy the returned request id into `REQUEST_ID`.

```bash
hermes-browser-runtime credentials status "$SESSION_ID" "$REQUEST_ID"
hermes-browser-runtime credentials approve "$SESSION_ID" "$REQUEST_ID" --note "approved"
hermes-browser-runtime credentials privacy-guard clear "$SESSION_ID"
```

Do not clear privacy guard while secrets are visible in the browser.

## CAPTCHA and checkpoints

Default policy is human-first:

```bash
export HBR_DEFAULT_CAPTCHA_POLICY=human_only
export HBR_CAPTCHA_SOLVER_ENABLED=false
```

Manual flow:

```bash
hermes-browser-runtime captcha report "$SESSION_ID" \
  --state human_required \
  --challenge-type "visual-checkpoint" \
  --reason "manual checkpoint"

hermes-browser-runtime sessions wait "$SESSION_ID" --timeout-secs 300

hermes-browser-runtime captcha resolve "$SESSION_ID" \
  --outcome resolved \
  --note "human completed checkpoint"
```

Provider-backed solve attempts require all gates:

- session policy: `auto_solve`
- `HBR_CAPTCHA_SOLVER_ENABLED=true`
- provider API key
- budget limit
- sanitized evidence review

Missing gates fail closed to human takeover.

## Inspector

Open locally:

```text
http://127.0.0.1:7788/inspector
```

The inspector shows sessions, checkpoint state, credential fill status, screenshots/artifacts/downloads, release/cancel controls, and live links for paused sessions.

Keep it local/private. Do not expose it publicly.

## Important environment variables

- `HBR_BIND`
- `HBR_SERVER`
- `HBR_DATA_DIR`
- `HBR_CHROME_PATH`
- `HBR_BEARER_TOKEN`
- `HBR_OPERATOR_TOKEN`
- `HBR_HEADFUL` / `HBR_HEADLESS`
- `HBR_CREDENTIAL_PROVIDER`
- `HBR_CREDENTIAL_POLICY_PATH`
- `HBR_CREDENTIAL_PRIVACY_GUARD`
- `HBR_CAPTCHA_SOLVER_ENABLED`
- `HBR_DEFAULT_CAPTCHA_POLICY`
- `HBR_CAPTCHA_SOLVER_POLICY_PATH`
- `HBR_2CAPTCHA_API_KEY`
- `HBR_ANTI_CAPTCHA_API_KEY`
- `HBR_CAPSOLVER_API_KEY`
- `HBR_WEBRTC_IP_POLICY`
- `HBR_GPU_POLICY`

Full reference: `docs/full-reference.md`.

## Developer checks

From repo root:

```bash
cargo fmt --manifest-path browser-runtime/Cargo.toml --check
cargo clippy --manifest-path browser-runtime/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path browser-runtime/Cargo.toml --all-targets
browser-runtime/scripts/security-gates.sh
browser-runtime/scripts/coverage-gates.sh
```

Current verified gate:

- `cargo fmt --check`: pass
- `cargo clippy --all-targets -- -D warnings`: pass
- `cargo test --all-targets`: pass
- `git diff --check`: pass

## Deeper docs

- Safe foundation runbook: `docs/hbr-agentic-browser-safe-foundation.md`
- Fingerprint risk runbook: `docs/fingerprint-hygiene-residual-risk-runbook.md`
- Full reference: `docs/full-reference.md`

## Principle

Small surface. Explicit gates. No hidden approvals. No secret leakage. No claims beyond measured evidence.
