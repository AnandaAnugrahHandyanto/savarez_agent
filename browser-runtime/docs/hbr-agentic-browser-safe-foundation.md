# HBR v0B safe agentic-browser foundation

This is the operator/developer runbook for the current Hermes Browser Runtime safe browser foundation.

Short version: HBR v0B is a local/private browser sidecar with human takeover, checkpoint state, a disabled-by-default CAPTCHA provider connector foundation, a fill-only credential broker, and a local inspector. It is not a universal CAPTCHA solver, credential vault, stealth product, payment agent, or public browser farm.

## Current status

| Area | Now usable | Mock-only | Real 1Password smoke | Needs Юра action | Deferred / boundary |
|---|---|---|---|---|---|
| Credential broker modes | `disabled`, `fake_status_only`, `mock`, `onepassword_cli`; default is `disabled`; approve/deny/privacy-guard clear require distinct operator auth. | Mock proves request, approval, fill status, redaction, privacy guard, and the post-fix email-field fill path. | Fresh post-fix real-provider smoke is blocked/untested; only historical pre-fix failure evidence exists. | Provision/unlock a safe test 1Password item/vault, set private policy + `onepassword_cli` + distinct operator token, run real-smoke harness, sanitize evidence, then request review. | No broad vault browse/search/list feature. |
| Exact origin allowlist | Private policy maps safe alias -> exact normalized origins -> private provider refs. | Mock policy can test allow/deny behavior without reading a vault. | Approved metadata path exercised historically; no provider values are in docs or artifacts. | Review/approve private allowlist changes outside repo/chat. | No wildcard, suffix, substring, or model-supplied origin trust. |
| Fill request/status API + CLI | `credentials fill|status|approve|deny|privacy-guard clear`; HTTP under `/sessions/:id/credentials/...`; fill/status use the agent bearer, operator actions use `HBR_OPERATOR_TOKEN`. | Green in sanitized v0B smoke. | Request/approval path was exercised only in the historical pre-fix real run; no fresh real-provider pass exists. | Approve or deny every real request locally with the operator token. | No raw password/OTP/passkey/card/provider output return path. |
| Per-request human approval | Required before provider read and browser fill. | Green in mock. | Historical pre-fix real run reached approval; fresh post-fix real approval is untested. | One explicit local operator decision per request. | No silent approval, reusable approval token, or model-controlled approval. |
| Privacy guard | Blocks screenshots, artifact listing/replay, and release while sensitive fields may be visible; clear explicitly with the operator capability. | Green in mock. | Fresh real-provider guard behavior is untested after the backend fix. | Clear only after a human confirms sensitive fields are no longer visible. | No pixel-level redaction claim. |
| CAPTCHA/checkpoint state | `captcha report` / `captcha resolve`; HTTP under `/sessions/:id/captcha/...`; provider-backed solve is a disabled-by-default connector foundation gated by `auto_solve`, `HBR_CAPTCHA_SOLVER_ENABLED=true`, provider-key availability, and budget limits. | Green local smoke covers report/resolve and fail-closed/no-key/disabled paths; controlled provider-call smoke verified dispatch + fail-closed fallback, but solve success was not achieved. | Not a credential-provider concern. | Human handles challenge/checkpoint by default; any readiness claim needs fresh controlled provider evidence, sanitized artifacts, and review. | No provider marketplace, protected-flow automation, or automatic solve readiness claim. |
| Inspector/live UX | `/inspector`, `/inspector/api/...`, session list/detail, checkpoint state, credential status, release/cancel, read-only/interactive live links, revoke. | Green for auth and UI/API availability. | Shows status only; never reveals provider data. | Keep local/private; do not expose publicly. | Signed public browser links remain out of scope. |
| Payment/final order boundary | Explicit approval gate remains mandatory. | N/A | N/A | Юра must approve any final pay/order action separately. | Credential fill never authorizes checkout, payment, MFA, OAuth consent, passkeys, or 3DS/bank checks. |
| Artifact hygiene | Sanitized v0B smoke bundle and mock after-fix proof exist. | Green: no public artifact provider refs or secret values in reviewed bundles. | Fresh real-provider evidence is absent until a new sanitized run exists. | Stop and sanitize if any finding appears. | Secret-bearing artifacts are not accepted. |

## Evidence used

- Sanitized smoke bundle: `browser-runtime/artifacts/hbr-v0b-smoke/20260513T182556Z-sanitized/`.
- Sanitized smoke summary says the mock path passed request -> approval -> filled status; CAPTCHA report/resolve; auth checks; inspector HTML/API; screenshot privacy guard; privacy guard clear; wait while paused; release.
- Mock after-fix proof: `browser-runtime/artifacts/hbr-v0b-smoke/20260513T185355Z-backend-eng-sot-mock-afterfix-sanitized/`. It reports the Son of a Tailor email-field fill path passed with the mock provider after the backend robustness fix; `real_accounts_touched=false`.
- Historical real-provider evidence: the earlier real 1Password path reached local approval metadata and found login fields, but username-only approved fill ended `failed` before the backend fix; password ref was not configured in that sanitized run. A direct CDP insert probe with non-secret text on the same field passed.
- Fresh post-fix real-provider smoke has not been rerun. Treat real 1Password status as blocked/untested until a new sanitized real-provider evidence bundle exists and is reviewed.

No secrets, item IDs, provider refs, tokens, cookies, takeover URLs, CDP websocket URLs, raw session JSON, or raw profile data belong in this runbook.

## Operating principles

1. Local/private by default.
   - Bind to loopback unless there is a reviewed tailnet-only reason.
   - If bearer auth is enabled, send it only in the HTTP Authorization header.
   - Do not put bearer tokens, takeover tokens, live-link tokens, or CDP websocket URLs in URLs, logs, comments, screenshots, or handoffs.

2. Human-only checkpoints.
   - CAPTCHA-like challenges, login, OAuth consent, OTP/MFA, passkeys, card entry, 3DS/bank checks, payment approval, and final purchase/order submission remain human takeover/approval flows.
   - HBR records and routes checkpoint state. The default is human handling. The provider connector foundation is disabled by default and only dispatches when `auto_solve`, the solver kill switch, provider key, and budget gates all pass; every missing gate fails closed to redacted status plus human takeover. It must not automate protected confirmations.

3. Fill-only credentials.
   - HBR can request a specific alias for a specific live origin.
   - HBR cannot browse a vault, list items, return raw values to the agent, approve its own request, or use one approval for future requests.
   - The browser origin is observed by HBR. `expected_origin` is an extra guard, not the source of truth.

4. Fail closed.
   - Unknown alias -> blocked.
   - Origin mismatch -> blocked.
   - Missing policy/provider -> blocked or disabled status.
   - Privacy guard active -> screenshots, artifact listing/replay, and release fail closed until explicitly cleared.
   - Missing fresh real-provider smoke -> mark the real 1Password path blocked/untested; do not describe it as usable.

5. Payment boundary is absolute.
   - A credential fill can put username/password text into login fields after approval.
   - It does not approve checkout, purchase, transfer, card entry, 3DS/bank step, subscription change, OAuth consent, passkey/MFA, or destructive account action.
   - Final pay/order action requires a separate explicit Юра approval.

## Credential broker setup

Default is safe:

```bash
export HBR_CREDENTIAL_PROVIDER=disabled
export HBR_CREDENTIAL_PRIVACY_GUARD=true
```

Use mock for local flow testing:

```bash
export HBR_CREDENTIAL_PROVIDER=mock
export HBR_CREDENTIAL_POLICY_PATH=/absolute/private/path/hbr-credential-policy.json
export HBR_CREDENTIAL_PRIVACY_GUARD=true
```

Use real 1Password only for an explicitly approved smoke:

```bash
export HBR_CREDENTIAL_PROVIDER=onepassword_cli
export HBR_CREDENTIAL_POLICY_PATH=/absolute/private/path/hbr-credential-policy.json
export HBR_OP_PATH=/absolute/path/to/op
export HBR_CREDENTIAL_PRIVACY_GUARD=true
```

Fresh real-provider smoke is blocked until the operator performs all of this outside repo/chat:

1. Provision or choose a safe dedicated test 1Password item/vault and unlock the local `op` session.
2. Set a private credential policy for that test item, `HBR_CREDENTIAL_PROVIDER=onepassword_cli`, `HBR_OP_PATH`, `HBR_BEARER_TOKEN`, and a distinct `HBR_OPERATOR_TOKEN`.
3. Run the documented HBR v0B real-smoke harness against the safe test item only.
4. Sanitize the evidence bundle with the approved artifact-hygiene scanner.
5. Send only sanitized status/hygiene evidence for reviewer sign-off.

Rules:

- Keep the policy file outside the repo and outside chat/handoffs.
- Keep provider refs private. Treat them as secrets even when they are only item/field references.
- Do not paste `op` output, item IDs, vault names, labels, usernames, passwords, OTPs, passkeys, card data, or provider errors that include sensitive context.
- Real-provider smoke should use a dedicated test item/service account, not a personal/high-value account.

Private policy shape, redacted:

```json
{
  "aliases": {
    "demo_login": {
      "allowed_origins": ["https://example.com"],
      "provider_refs": {
        "username": "[REDACTED_PROVIDER_REF]",
        "password": "[REDACTED_PROVIDER_REF]"
      },
      "allowed_fields": ["username", "password"]
    }
  }
}
```

Policy constraints:

- Alias must be safe and non-sensitive.
- `allowed_origins` must be exact normalized origins.
- No wildcard/suffix matching.
- `allowed_fields` is fill-only safe: username/password. OTP/TOTP/card/CVV/passkey/MFA-style fields are blocked by policy validation. Provider reads are scoped to the fields requested/approved for that single fill, so username-only, password-only, and both-field fills do not over-read unused refs.
- If `expected_origin` is supplied in a request, it must equal the origin HBR observes from the live browser page.

## Credential fill operator flow

Prereqs:

```bash
export HBR_SERVER=http://127.0.0.1:7788
# export HBR_BEARER_TOKEN='<local agent/server token>'      # fill/status/session routes; never paste into docs/logs
# export HBR_OPERATOR_TOKEN='<local operator-only token>'   # approve/deny/privacy-guard clear; must be different
```

Request a fill:

```bash
hermes-browser-runtime credentials fill "$SESSION_ID" \
  --alias demo_login \
  --expected-origin https://example.com \
  --username-selector 'input[name=email]' \
  --password-selector 'input[type=password]' \
  --purpose "operator-approved login fill"
```

Expected safe response:

- status is usually `requires_user_approval` before approval.
- copy `request_id` from the JSON into `CREDENTIAL_REQUEST_ID`.
- response contains request/status/audit metadata only.
- response does not contain selectors, provider refs, raw provider output, usernames, passwords, OTPs, passkeys, card data, tokens, or labels.

Check status:

```bash
hermes-browser-runtime credentials status "$SESSION_ID" "$CREDENTIAL_REQUEST_ID"
```

Approve or deny:

```bash
hermes-browser-runtime credentials approve "$SESSION_ID" "$CREDENTIAL_REQUEST_ID" --note "operator approved login fill"
# or
hermes-browser-runtime credentials deny "$SESSION_ID" "$CREDENTIAL_REQUEST_ID" --note "operator denied login fill"
```

Approve/deny and privacy-guard clear are operator-only. They use `HBR_OPERATOR_TOKEN` / `--operator-token`, not the agent `HBR_BEARER_TOKEN`; the server rejects missing operator tokens and rejects configs that reuse the same value for both capabilities.

After a successful approved fill:

```bash
hermes-browser-runtime credentials status "$SESSION_ID" "$CREDENTIAL_REQUEST_ID"
# Human confirms sensitive fields are no longer visible, then:
hermes-browser-runtime credentials privacy-guard clear "$SESSION_ID"
```

Do not clear privacy guard while a secret is visible in the browser. Clearing the guard is a human assertion that screenshots, artifact listing/replay, and release can resume safely.

HTTP endpoint shapes:

- `POST /sessions/:id/credentials/fill`
- `GET /sessions/:id/credentials/fill/:request_id`
- `POST /sessions/:id/credentials/fill/:request_id/approve`
- `POST /sessions/:id/credentials/fill/:request_id/deny`
- `POST /sessions/:id/credentials/privacy-guard/clear`

Use bearer auth when configured:

```bash
# Set HBR_AUTH_HEADER privately in your shell when auth is enabled.
# Example value shape: Authorization header with a local bearer token.
curl -sS \
  -H "$HBR_AUTH_HEADER" \
  -H 'content-type: application/json' \
  -d '{"alias":"demo_login","expected_origin":"https://example.com","purpose":"operator-approved login fill"}' \
  "$HBR_SERVER/sessions/$SESSION_ID/credentials/fill"
```

For approval/denial or privacy-guard clear, set a separate operator Authorization header from `HBR_OPERATOR_TOKEN` and never derive it from or store it alongside the model/agent bearer.

Keep command output private during real-provider smoke. It should be redacted/status-only, but operator terminals and scrollback are still durable artifacts.

## CAPTCHA/checkpoint operator flow

Report manual checkpoint state:

```bash
hermes-browser-runtime captcha report "$SESSION_ID" \
  --state human_required \
  --challenge-type "visual-checkpoint" \
  --reason "manual checkpoint"
```

Effect:

- session is marked paused for human handling when state is `human_required`;
- checkpoint state is redacted and visible in session/inspector surfaces;
- HBR does not send challenge data to an external service on the default human/manual path. The HTTP solve path is opt-in only (`auto_solve` + solver-enabled + provider key + budget); missing gates fail closed to human takeover, and real-provider smoke is still downstream-gated.

Wait while human handles it:

```bash
hermes-browser-runtime sessions wait "$SESSION_ID" --timeout-secs 300
```

Resolve outcome:

```bash
hermes-browser-runtime captcha resolve "$SESSION_ID" --outcome resolved --note "human completed checkpoint"
# or: --outcome failed
# or: --outcome dismissed
```

HTTP endpoint shapes:

- `POST /sessions/:id/captcha/report`
  - `state`: `suspected`, `human_required`, or `in_progress`
  - optional: `challenge_type`, `reason`
- `POST /sessions/:id/captcha/resolve`
  - `outcome`: `resolved`, `failed`, or `dismissed`
  - optional: `note`

## Inspector and live links

Open locally:

```text
http://127.0.0.1:7788/inspector
```

If bearer auth is enabled, the page prompts for the token and keeps it in memory for that tab only. The inspector page does not persist token-bearing links.

Inspector shows:

- session list/detail;
- pause reason and status;
- CAPTCHA/checkpoint state;
- credential fill status and privacy-guard state;
- latest safe screenshot, artifacts, and downloads;
- release/cancel controls;
- create/revoke read-only or interactive live links for paused sessions.

Inspector does not show:

- raw passwords, usernames from provider output, OTPs, passkeys, card data;
- provider refs, item IDs, vault names, `op` output;
- bearer tokens, takeover tokens, live-link tokens, CDP websocket URLs;
- credential approve/deny values. Approve/deny remains through the operator-only credential CLI/API capability.

Inspector HTTP surfaces:

- `GET /inspector`
- `GET /inspector/:id`
- `GET /inspector/api/sessions`
- `GET /inspector/api/sessions/:id`
- `POST /inspector/api/sessions/:id/live-links` with body `{"mode":"read_only"}` or `{"mode":"interactive"}`
- `DELETE /inspector/api/sessions/:id/live-links/:link_id`
- `POST /inspector/api/sessions/:id/release`
- `POST /inspector/api/sessions/:id/cancel`

Safety rules:

- Inspector requires loopback bind by default. Non-loopback inspector access requires explicit `HBR_ALLOW_NONLOCAL_INSPECTOR=true` approval and should stay tailnet/private.
- Live links are capability-bearing. Treat copied links as secrets.
- Live links are only for paused sessions, expire using takeover TTL, can be revoked, and are cleared on release.
- Read-only links must not allow browser actions server-side.
- Do not paste live links into chat, logs, task comments, screenshots, artifacts, or docs.

## Human approval rules

Approve only when all are true:

1. The alias is expected and non-sensitive.
2. The observed origin matches the intended exact origin.
3. The target page is the intended page.
4. The field selectors are expected for username/password only.
5. The action is login fill only, not checkout/payment/MFA/OAuth/passkey/3DS/final order.
6. The account/item is approved for this smoke.
7. You are ready to clear privacy guard only after sensitive fields are safe.

Deny when any of these are true:

- unknown alias;
- origin mismatch;
- unexpected page/frame;
- unexpected selectors;
- request asks for OTP/TOTP/card/CVV/passkey/MFA or final confirmation;
- provider or policy state is unclear;
- user did not explicitly approve this run.

Approval notes should be short and non-sensitive. Do not write usernames, emails, item names, card fragments, one-time codes, or provider refs into notes.

## Payment and final-action boundary

Credential fill is not consent.

Allowed with explicit fill approval:

- Fill username/password into a login form.
- Let human inspect the page.
- Continue after the human releases the session.

Not allowed without a separate explicit Юра approval:

- Click Pay, Buy, Subscribe, Transfer, Submit Order, Confirm, Accept OAuth consent, Confirm 3DS, approve bank challenge, create passkey, enter OTP/MFA, change account/security settings, or perform destructive actions.

If a page turns a login fill into a high-risk confirmation, stop and pause for human takeover.

## Real 1Password smoke status

Current status: blocked/untested after the backend fix.

Implemented and usable behavior:

- agent-facing fill/status remains status-only and redacted;
- approve/deny/privacy-guard clear require the separate operator capability;
- provider reads are scoped to the fields requested/approved for the single fill;
- final payment, checkout, 3DS, OAuth, MFA/passkey, and destructive actions remain human/approval gated.

Mock proof:

- original sanitized mock smoke is green for the full local flow;
- post-fix mock Son of a Tailor proof is green for the email-field fill path;
- no real account was touched in the post-fix mock proof.

Historical real-provider evidence:

- the earlier real run reached local `op`, detected login fields, and reached `requires_user_approval`;
- username-only approved fill ended `failed` before the backend fix;
- password ref was not configured in that sanitized run.

Required operator action for a fresh real-provider smoke:

1. Provision/unlock a safe dedicated 1Password test item/vault.
2. Set private policy/config plus distinct `HBR_BEARER_TOKEN` and `HBR_OPERATOR_TOKEN` values.
3. Run the documented HBR v0B real-smoke harness without exposing raw secrets.
4. Sanitize evidence and run artifact hygiene checks.
5. Hand only sanitized evidence to reviewer.

Implication:

- Docs can say the architecture is fill-only, approval-gated, exact-origin checked, and redacted.
- Docs must not say real 1Password autofill is production-ready.
- Next step is an operator-approved real-provider rerun and review, unless new sanitized evidence shows a backend bug.

## Artifact hygiene

Allowed to share internally after review:

- sanitized smoke summary;
- redacted status records;
- public-redacted screenshots that do not show sensitive data;
- zero-finding hygiene scan outputs.

Never share:

- raw runtime-data/profile directories;
- raw `session.json` with capability URLs or CDP URLs;
- cookies, auth headers, bearer tokens, takeover/live URLs, CDP websocket URLs;
- 1Password item IDs, provider refs, vault names, labels, `op` output;
- usernames/passwords/OTPs/passkeys/card data;
- screenshots/replays while privacy guard is active;
- private browser profile files.

Before publishing a bundle:

1. Confirm it came from a sanitized/public-redacted artifact path.
2. Search for capability URLs, CDP websocket URLs, tokens, cookies, provider refs, item IDs, and credential-like values.
3. Confirm `raw_session_json_excluded`, `runtime_data_excluded`, and `profile_files_excluded` style checks are true when a smoke summary provides them.
4. If anything looks sensitive, stop and sanitize again.

## Deferred work

- Fresh approved real-provider smoke and reviewer sign-off before real 1Password autofill is described as passed/ready.
- Better inspector affordance for pending credential approval while keeping raw values out of the inspector.
- First-class upload helper.
- Optional signed tailnet broker for short-lived browser links.
- Opt-in recording/replay upgrade with retention tiers.
- The provider connector foundation still needs controlled real-provider smoke, sanitized evidence, and reviewer sign-off before it can be described as ready; keep user/provider/site-owner approvals outside repo/chat and keep human fallback as the default.

## Quick safe path

For daily operator testing:

1. Run local HBR with bearer auth if exposed beyond localhost.
2. Use `mock` provider and a private policy path.
3. Create a session.
4. Use `captcha report/resolve` for manual checkpoints.
5. Use `credentials fill/status/approve/deny` for fill-only login tests.
6. Clear privacy guard only after human confirmation.
7. Use `/inspector` locally for status, artifacts, release/cancel, and live links.
8. Keep all capability links and provider material private.
9. Stop before payment/final confirmation unless Юра explicitly approves that exact action.
