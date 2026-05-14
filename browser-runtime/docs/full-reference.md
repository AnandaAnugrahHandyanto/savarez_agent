# HBR full reference

Local, CDP-first browser runtime for agents.

The crate exposes two operator-facing entrypoints:

- `hermes-browser-runtime server` — HTTP API on a private local bind by default.
- `hermes-browser-runtime sessions|profiles|artifacts ...` — CLI client for daily use against a running server.

This component is intentionally local/private-first. Treat it as an explicit sidecar service, not as a public web app.

## Local/private defaults

Server defaults come from `browser-runtime/src/config.rs`:

- bind: `127.0.0.1:7788`
- client base URL: `http://127.0.0.1:7788`
- takeover TTL: `900` seconds
- default server launch mode: headed when `DISPLAY` or `WAYLAND_DISPLAY` is present, or when `xvfb-run` is available for an automatic headed Xvfb wrapper; otherwise headless. Use `--headless`/`HBR_HEADLESS=true` or `--headful`/`HBR_HEADFUL=true` to force a mode. Clap-backed boolean env values should use `true`/`false`; `HBR_HEADFUL=1` is not the benchmark-safe form. If `--headful` is forced on a host without a display or Xvfb wrapper, session launch fails early with a fallback hint instead of silently downgrading to headless.
- default WebRTC/IP policy: `default_public_interface_only`, which hides local/private host-candidate IP literals by default while still allowing the public/default-interface address to be visible by design.
- default GPU policy: `auto`, which does not force SwiftShader or disable 3D APIs on the headed default path; explicit compatibility modes are available when the host or target site requires them.
- default CAPTCHA policy per session: `human_only`; the runtime records CAPTCHA/checkpoint status and pauses for human handling by default. A provider-backed connector foundation exists only behind explicit `auto_solve` session policy, `HBR_CAPTCHA_SOLVER_ENABLED=true`, provider-key availability, and budget gates; otherwise it fails closed to human takeover.
- default data dir: `dirs::data_dir()/hermes-browser-runtime`
  - on a typical Linux desktop/server this is `~/.local/share/hermes-browser-runtime`

Runtime storage is created with `0700` permissions and split into:

- `profiles/` — persistent profile directories
- `sessions/` — per-session artifacts and downloads
- `tmp/` — ephemeral seeded profiles and scratch data

Relevant env vars:

- `HBR_BIND`
- `HBR_DATA_DIR`
- `HBR_CHROME_PATH`
- `HBR_BEARER_TOKEN` (agent/client bearer for non-operator API routes)
- `HBR_OPERATOR_TOKEN` (separate operator-only bearer for credential approve/deny/privacy-guard clear; must not equal `HBR_BEARER_TOKEN`)
- `HBR_HEADFUL` / `HBR_HEADLESS`
- `HBR_XVFB_RUN_PATH` (optional custom `xvfb-run` wrapper path used for headed default detection and launch when no local display env is present)
- `HBR_ARTIFACT_RETENTION_SECS`
- `HBR_TAKEOVER_TTL_SECS`
- `HBR_LAUNCH_TIMEOUT_SECS`
- `HBR_CAPTCHA_SOLVER_ENABLED` (default `false`; global kill switch for provider-backed solve attempts)
- `HBR_DEFAULT_CAPTCHA_POLICY` (`human_only`, `observe_only`, `auto_solve`, `disabled`; default `human_only`)
- `HBR_CAPTCHA_SOLVER_POLICY_PATH` (private local policy path; do not commit or paste contents)
- `HBR_CAPTCHA_SOLVER_PROVIDER_ORDER`, `HBR_CAPTCHA_SOLVER_TIMEOUT_SECS`, `HBR_CAPTCHA_SOLVER_POLL_MS`, `HBR_CAPTCHA_SOLVER_VERIFY_TIMEOUT_SECS`, `HBR_CAPTCHA_SOLVER_MAX_ATTEMPTS`, `HBR_CAPTCHA_SOLVER_MAX_COST_USD_PER_SESSION`
- provider key env vars such as `HBR_2CAPTCHA_API_KEY`, `HBR_ANTI_CAPTCHA_API_KEY`, `HBR_ANTICAPTCHA_API_KEY`, `HBR_CAPSOLVER_API_KEY`, and `HBR_CAPTCHA_SOLVER_API_KEY` are private credentials. Key presence participates in availability gates; the current HTTP connector dispatches only 2Captcha/Anti-Captcha keys and otherwise fails closed. Never commit, paste, or log their values.
- `HBR_WEBRTC_IP_POLICY` (`default_public_interface_only`, `default_public_and_private_interfaces`, `disable_non_proxied_udp`)
- `HBR_GPU_POLICY` (`auto`, `swiftshader_compat`, `disable_3d`)
- `HBR_DEFAULT_LOCALE`
- `HBR_DEFAULT_ACCEPT_LANGUAGE`
- `HBR_DEFAULT_TIMEZONE_ID`
- `HBR_DEFAULT_PLATFORM`
- `HBR_DEFAULT_HARDWARE_CONCURRENCY` (default `8`, normalized to common buckets)
- `HBR_DEFAULT_DEVICE_MEMORY_GB` (default `8`, normalized to common buckets)
- `HBR_DEFAULT_MAX_TOUCH_POINTS` (default `0`, values above `10` fall back to default)
- `HBR_CREDENTIAL_PROVIDER` (default `disabled`; allowed values include `disabled`, `fake_status_only`, `mock`, and `onepassword_cli`)
- `HBR_CREDENTIAL_POLICY_PATH` (private local policy file; do not commit or paste contents)
- `HBR_OP_PATH` (optional path to the local `op` CLI binary)
- `HBR_OP_TIMEOUT_SECS` (default `5`)
- `HBR_CREDENTIAL_APPROVAL_TTL_SECS` (default `300`)
- `HBR_CREDENTIAL_PRIVACY_GUARD` (default `true`)
- `HBR_SERVER`
- `HBR_CHROME_NO_SANDBOX=1` only when your host cannot provide a working Chrome sandbox

Browser persona defaults are applied before normal navigation: the runtime opens a blank CDP page, sets locale/timezone/device metrics, sends `Accept-Language`/UA client-hint overrides, and installs init scripts for navigator language/platform/capability fields plus screen, window, `visualViewport`, and media-query metrics. P4 uses one resolved browser identity for the launch-level `--user-agent`, CDP `Network.setUserAgentOverride`, UA-CH/high-entropy metadata, and JS-observable persona so Chrome major/full version and platform stay coherent. P4-S1 extends that persona with conservative `navigator.hardwareConcurrency`, `navigator.deviceMemory`, and `navigator.maxTouchPoints` defaults and applies target-type-aware plans: page-like targets get the full page plan, while worker-like targets get only worker-safe navigator overrides via `Runtime.evaluate` and are resumed only when CDP reports `waitingForDebugger=true`. Explicit `persona.user_agent` overrides are still supported, but `HeadlessChrome/` is sanitized to `Chrome/`; when no explicit UA is supplied, the runtime derives the UA OS token from the configured persona platform and the selected Chrome version. `--disable-blink-features=AutomationControlled` and the init-script cleanup remove high-signal webdriver/global markers where the runtime can safely touch them, but this remains fingerprint hygiene and detector benchmarking, not an undetectability guarantee.

Security defaults from `browser-runtime/src/security.rs` and `browser-runtime/src/store.rs`:

- sensitive keys/text matching `cookie`, `authorization`, `token`, `password`, `secret`, `credential`, `label_hint`, `onepassword`, `op_uri`, `vault`, `item_id`, `otp`, `totp`, `passcode`, `api_key`, `card`, `cvv`, `form`, `fingerprint`, `cdp_ws`, `devtools`, `websocket`, or request/body markers are redacted as `[REDACTED]`; event payloads are redacted recursively before `events.jsonl` is written
- pause reasons are redacted before persistence/logging
- takeover tokens are random, short-lived, rotated on pause, and invalidated on release/expiry; persisted `session.json` records store paused takeover URLs as `[REDACTED]` rather than retaining the token-bearing URL
- persisted `session.json` records also redact live `cdp_ws_url` values; live API responses still return the CDP websocket URL to the caller that just created or owns the running session
- profile IDs are sanitized to avoid path traversal

## Safe agentic-browser foundation (HBR-v0B)

Short version for operators: HBR is a local/private browser sidecar with human takeover, checkpoint state, a disabled-by-default CAPTCHA provider connector foundation, a fill-only credential broker, and a local inspector. It is not a universal CAPTCHA solver, credential vault, stealth product, payment agent, or public browser farm.

Current v0B truth:

- CAPTCHA/checkpoint handling is exposed through authenticated HTTP and CLI report/resolve commands, plus an authenticated HTTP solve-status surface. `captcha_policy` still defaults to `human_only`; `human_required` pauses the session for human takeover and writes redacted state. Provider-backed solving is a disabled-by-default connector foundation: it requires `auto_solve`, `HBR_CAPTCHA_SOLVER_ENABLED=true`, a configured provider key, and budget gates. Missing gates fail closed to redacted status plus human takeover. Controlled provider-call smoke verified dispatch and fail-closed fallback, but solve success was not achieved.
- Human-only flows still use pause/takeover/release: CAPTCHA-like challenges, login, OAuth consent, OTP/MFA, passkeys, card entry, 3DS/bank checks, payment approval, and final purchase/order submission.
- Credential/1Password work is fill-only. The broker supports `disabled`, `fake_status_only`, `mock`, and `onepassword_cli`; provider mode defaults to `disabled`. Requests use a safe alias, optional selectors, purpose, and optional expected origin. HBR derives the live browser origin itself, checks the exact private allowlist, returns status-only metadata, requires a separate operator-only approval capability, then fills through CDP. Agent-visible responses/logs/events never include raw passwords, OTPs, passkeys, card data, provider output, item IDs, provider tokens, label material, selectors, or provider references.
- Mock proof is green: the sanitized v0B smoke bundle passed request -> approval -> filled status, CAPTCHA report/resolve, auth checks, inspector HTML/API, screenshot privacy guard, guard clear, wait while paused, and release. A later no-secret mock Son of a Tailor after-fix proof passed the email-field fill path after the backend robustness fix.
- Fresh post-fix real 1Password smoke is blocked/untested. The last real-provider run was pre-fix: it reached `requires_user_approval`, detected login fields, and found local `op`, but username-only approved fill ended `failed` and no password provider ref was configured. The remaining real-smoke work is an operator evidence gap unless new sanitized evidence identifies a code bug.
- Local inspector is available at `/inspector` plus `/inspector/api/...`: session list/detail, checkpoint state, credential fill status, latest safe screenshot/artifacts/downloads, release/cancel controls, and read-only or interactive live links for paused sessions. Approve/deny for credential fills remains through the operator-only credential API/CLI capability.
- Artifact hygiene is part of the feature, not an afterthought. Raw runtime-data/profile state, capability-bearing raw session JSON, takeover/live URLs, CDP websocket URLs, cookies/auth headers, credential hints, OTP/passcode/card-like fields, provider refs, item IDs, and private browser profile files must not be published or copied into handoffs. Use only sanitized bundles for review and public-redacted bundles for external sharing.

v0B status snapshot:

| Area | Now usable | Mock-only | Real 1Password smoke | Needs Юра action | Deferred / boundary |
|---|---|---|---|---|---|
| Credential broker modes | `disabled`, `fake_status_only`, `mock`, `onepassword_cli`; default is `disabled`; approve/deny/privacy-guard clear require distinct operator auth. | Mock proves broker flow, redaction, and the post-fix email-field fill path. | Fresh post-fix real-provider smoke is blocked/untested; only historical pre-fix failure evidence exists. | Provision/unlock a safe test 1Password item/vault, set private policy + `onepassword_cli` + distinct operator token, run real-smoke harness, sanitize evidence, then request review. | No broad vault browse/search/list feature. |
| Exact origin allowlist | Private policy maps safe alias to exact normalized origins. | Mock policy can test exact-origin blocks. | Approved test domain metadata only; no item values in docs. | Approve private allowlist changes outside repo/chat. | No wildcard/suffix/substring origin matching in v0B. |
| Fill request/status API + CLI | `credentials fill|status|approve|deny|privacy-guard clear` and `/sessions/:id/credentials/...`; fill/status use the agent bearer, operator actions use `HBR_OPERATOR_TOKEN`. | Green in smoke. | Request/approval path was exercised only in the historical pre-fix real run; no fresh real-provider pass exists. | Approve/deny each real request locally with the operator token. | No raw value return path. |
| Per-request human approval | Required before provider read/fill. | Green in mock. | Historical pre-fix real run reached approval; fresh post-fix real approval is untested. | One explicit operator decision per request. | No silent, reusable, or model-controlled approval. |
| Privacy guard | Screenshots, artifact listing/replay, and release fail closed while credential values may be visible; clear explicitly with the operator capability. | Green in mock. | Fresh real-provider guard behavior is untested after the backend fix. | Clear only after human confirms fields are safe. | No pixel-level redaction claim. |
| CAPTCHA report/resolve + solve status | `captcha report` / `captcha resolve` and `/sessions/:id/captcha/...`; provider connector foundation is available only behind explicit `auto_solve` + solver-enabled + provider-key + budget gates. | Green local smoke covers report/resolve and fail-closed/no-key/disabled paths; controlled provider-call smoke verified dispatch + fail-closed fallback, but solve success was not achieved. | Not a credential-provider concern. | Human handles challenges by default; any readiness claim needs fresh controlled provider evidence, sanitized artifacts, and review. | No provider marketplace, protected-flow automation, or automatic solve readiness claim. |
| Inspector/live UX | `/inspector`, inspector JSON APIs, read-only/interactive live links, revoke, release/cancel. | Green in smoke for auth and UI/API availability. | Shows status only; does not reveal provider data. | Keep local/private; do not expose publicly. | Signed public browser links remain out of scope. |
| Payment/final order boundary | Explicit approval gate stays mandatory. | N/A | N/A | Юра must approve final pay/order action separately. | Credential fill never authorizes checkout, payment, MFA, OAuth, passkey, or 3DS actions. |
| Artifact hygiene | Sanitized v0B smoke bundle and mock after-fix proof exist. | Green: no public artifact provider refs or secret values in reviewed bundles. | Fresh real-provider evidence is absent until a new sanitized run exists. | Stop and sanitize if any finding appears. | Secret-bearing artifacts are not accepted. |

Hyperbrowser-inspired roadmap, stated against current HBR truth:

| Capability | HBR has now | Next safe step | Gate |
|---|---|---|---|
| Session dashboard / inspector | Local `/inspector` page/API, session table/detail, checkpoint state, credential status, latest safe screenshot/artifacts/downloads, release/cancel, live link create/revoke. | Polish pending approval UX; keep status-only surfaces. | Local/private only; bearer auth when configured; no token persistence in inspector page. |
| Live view links | Read-only and interactive live links for paused sessions; TTL uses takeover TTL; revoke and release clear access. | Optional signed tailnet broker later. | Read-only action denial server-side; no token/query/body logging. |
| CAPTCHA handling | Human-default state machine plus authenticated HTTP/CLI report/resolve and a disabled-by-default HTTP provider connector foundation. | Controlled real-provider smoke and review before any readiness claim; keep inspector affordances status-only. | `auto_solve` + solver-enabled + provider-key + budget gates only; otherwise fail closed to human takeover. No protected-flow automation. |
| Credential autofill / 1Password | Fill-only broker, exact private allowlists, operator-only approval, field-scoped provider reads, safe `op` process boundary, mock smoke green, mock after-fix proof green; fresh real-provider smoke blocked/untested. | Operator-provisioned real smoke: safe test item/vault, unlocked `op`, private policy/config, distinct operator token, documented harness, sanitized evidence, reviewer sign-off. | Юра approval, dedicated test item/service account, no raw secret return path, reviewer sign-off. |
| Files | Path-safe downloads and replay; upload workaround via local Playwright/CDP helper. | First-class upload API/inspector helper. | Keep paths local; do not log sensitive filenames or bearer/CDP secrets. |
| Recording / replay | Local replay from screenshots and redacted `events.jsonl`, blocked by privacy guard when needed. | Opt-in recording/replay upgrade with retention and artifact tiers. | No default recording; public sharing only through public-redacted artifacts or reviewed excerpts. |
| Remote/mobile broker | SSH local-port-forward or tailnet-only Tailscale Serve in front of localhost. | Future signed short-lived HTTPS/tailnet broker. | Ops/security review; no Funnel/public exposure unless explicitly approved. |

Full operator and developer runbook: `browser-runtime/docs/hbr-agentic-browser-safe-foundation.md`.

## Browser policy and detector evidence

The browser-runtime exposes fingerprint-hygiene controls as explicit, reviewable policy surfaces. These controls reduce obvious local-runtime inconsistencies; they do not try to spoof every surface or defeat a site's access controls.

Supported modes and policy values:

- Browser identity/persona coherence is on by default. The runtime keeps launch UA, CDP UA override, UA-CH/high-entropy metadata, `navigator.userAgentData`, locale, timezone, platform, viewport, screen metrics, `visualViewport`, DPR, media-query answers for common dimension/resolution checks, hardware concurrency, device memory, and max touch points aligned before normal navigation when Chrome exposes the needed information.
- Default persona config can be set with `HBR_DEFAULT_LOCALE`, `HBR_DEFAULT_ACCEPT_LANGUAGE`, `HBR_DEFAULT_TIMEZONE_ID`, `HBR_DEFAULT_PLATFORM`, `HBR_DEFAULT_HARDWARE_CONCURRENCY`, `HBR_DEFAULT_DEVICE_MEMORY_GB`, and `HBR_DEFAULT_MAX_TOUCH_POINTS`. The hardware/device fields are normalized to conservative buckets before being exposed to page or worker JavaScript.
- CDP target handling is target-type aware: page-like targets receive the full page persona plan; worker-like targets receive a worker-safe `Runtime.evaluate` plan for navigator fields and are not sent unsupported `Page.*` commands. Service-worker behavior can remain CDP-version-sensitive, so treat worker/service-worker evidence as measured coverage, not a universal guarantee.
- WebRTC/IP policy is set globally with `HBR_WEBRTC_IP_POLICY` / `--webrtc-ip-policy`, or per session with `sessions create --webrtc-ip-policy ...` / `CreateSessionRequest.webrtc_ip_policy`.
  - `default_public_interface_only` is the default. It minimizes local/private host-candidate IP literal exposure, but it is not anonymity: the public/default-interface IP can still appear.
  - `default_public_and_private_interfaces` is the compatibility opt-in for sites or device flows that need fuller WebRTC behavior.
  - `disable_non_proxied_udp` is the stricter WebRTC mode and can break legitimate audio/video/sign-in flows.
- GPU policy is set globally with `HBR_GPU_POLICY` / `--gpu-policy`, or per session with `sessions create --gpu-policy ...` / `CreateSessionRequest.gpu_policy`.
  - `auto` is the default. On the headed default path it avoids explicit SwiftShader and `--disable-3d-apis` flags.
  - `swiftshader_compat` explicitly asks Chrome for SwiftShader WebGL compatibility.
  - `disable_3d` explicitly disables 3D APIs.
- CAPTCHA/checkpoint policy is a per-session model field (`CreateSessionRequest.captcha_policy`, `SessionInfo.captcha_policy`) with safe wire values `human_only`, `observe_only`, `auto_solve`, and `disabled`. The default `human_only` state machine records `none -> suspected -> human_required -> resolved|failed|dismissed` style transitions and pauses the session for human handling when `human_required` is reported through the runtime store integration surface. `auto_solve` is explicit opt-in and still requires the global solver kill switch, provider-key availability, and budget gates before any provider call; otherwise it records a redacted failure/status and pauses for human takeover. There is no evasion feature, provider marketplace, or real-provider readiness claim before controlled smoke and review.
- Credential autofill is represented by a fill-only broker core in `browser-runtime/src/credentials.rs` plus session-scoped HTTP/CLI fill endpoints. Provider mode defaults to `disabled`; `onepassword_cli` is explicit-only and approval-gated. Policy uses safe aliases plus exact normalized origins; private provider references stay internal to the approved fill executor path. Agent-visible responses, logs, and audit events carry status/audit metadata only and must never contain selectors, raw passwords, OTPs, 1Password item contents, provider tokens, label material, or provider references. While a credential privacy guard is active, screenshots and artifact replay/listing fail closed until `credentials clear-guard` is called.
- The deterministic fingerprint probe supports `--mode local-deterministic` only. It attaches to an already-created runtime session, runs local top/iframe/worker/popup checks, classifies WebRTC candidates/rendering, and writes sanitized JSON. The P5 measurement contract requires explicit context availability and popup status: measured with coherent identity fields, or a structured unavailable reason that cannot be treated as a pass. This is local deterministic evidence, not a public-detector score.

Reviewed evidence:

- BOT-02/P3 evidence: `browser-runtime/artifacts/bot02-p3-evidence/run-20260511T212756Z`. BrowserLeaks WebRTC did not show local/private IP literals and did show the public default-interface IPv4 address. BrowserLeaks WebGL was unavailable in this worker's no-display/Xvfb environment.
- P4 implementation evidence: `browser-runtime/artifacts/p4-implementation-sanitized/run-20260511T231333Z`. The local deterministic probe reported identity coherence and no strict sanitizer findings; its remaining red flag was `webgl_blocked` in the local/headless-style environment.
- P4 public-detector benchmark: `browser-runtime/artifacts/hbr-p4-bench/run-20260511T235056Z-sanitized`. Public detector collection completed 7/7 pages. The measured improvement was UA/UA-CH version coherence: prior evidence mixed Chrome 125 UA with Chromium 147 UA-CH surfaces; after P4, BrowserLeaks/CreepJS and the direct probe reported Chrome/Chromium/Google Chrome major 147 consistently. Strict artifact hygiene scanned 21 text files with 0 findings and 0 private-path findings.
- P5 residual-closure evidence: direct probe `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/fingerprint-probe.json`, internal strict report `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized/hygiene-scan-report.json`, and public-share strict report `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted/public-redaction-scan-report.json`. The fresh direct probe reported `measurement_completeness.complete=true`, `contexts.popup.measured=true`, `identity.coherent=true`, WebRTC candidate classes redacted with `mdns_host` only and no private/local literal class, and `webgl_blocked` as an environment limitation. Internal strict hygiene and public-redacted strict scans both had findings `[]`; only the public-redacted tier is marked `public_share_safe=true`.
- P4-S1 public-detector benchmark: `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z`. Before and after runs both report attempted=12, captured=12, nonblank=12. CreepJS, Sannysoft, and Pixelscan are unchanged; BrowserLeaks is marked regressed because the detector list is not apples-to-apples (`browserleaks-javascript` existed in the baseline while `fpscanner` was added in the after harness). Treat that BrowserLeaks verdict as a harness comparability issue until the detector list is aligned and rerun. Internal sanitized and public-redacted bundles exist beside the raw run; raw screenshots/page text/runtime data remain private-local.

How to interpret the P4/P5/P4-S1 evidence:

- Improved by P4: launch/header/client-hint identity coherence for the measured Chrome 147 runtime; direct probe `identity.coherent=true`, `ua_major=ua_ch_major=147`, and no webdriver property in top/iframe/worker contexts.
- Closed by P5 fix-now evidence: the direct probe popup ambiguity and the artifact-publication boundary. The P5 direct probe reports popup measured with coherent identity fields; internal sanitized artifacts are separated from the public-redacted tier.
- Extended by P4-S1: persona coherence now includes conservative hardware concurrency, device memory, max touch points, `visualViewport`, common dimension/resolution `matchMedia`, and target-type-aware page/worker CDP handling. This is a coherence improvement, not proof that every detector surface is covered.
- Current P4-S1 benchmark caveat: the latest public-detector run captured 12/12 pages with 12/12 nonblank screenshots, but BrowserLeaks group comparison is affected by detector-list drift (`browserleaks-javascript` missing after; `fpscanner` new after). Cite it as a harness comparability issue, not as an apples-to-apples product regression or pass.
- Accepted by design: browser-runtime's `default_public_interface_only` policy is intended to prevent private/local IP exposure. It does not hide the public egress/default-interface IP. Public detectors may still show mDNS `.local` host candidates and public srflx candidates; this is accepted when fresh evidence shows no RFC1918, ULA, link-local, or other private/local IP addresses are exposed.
- Needs external capability: CreepJS headless/stealth percentages are public-detector proxy evidence, not a product pass/fail target. In the no-display/Xvfb/SwiftShader worker environment, headless-like or WebGL-blocked findings may remain. Proving consumer-GPU behavior requires a separate headed consumer-GPU benchmark host; the project must not fake GPU/WebGL claims or chase detector-specific stealth scores.
- Needs external capability: WebGL/GPU unavailable in the worker environment is a documented environment limitation, not a silent browser-runtime pass. Consumer GPU renderer coherence remains unproven until separately benchmarked on a real headed GPU-capable host.
- Out of scope: Network/IP reputation, account history, TLS/JA3/JA4, HTTP/2 fingerprinting, rate-limit systems, and site risk models are outside browser-runtime browser-flag scope and are not claimed as solved. P5 must not be used as evidence that CAPTCHA/OAuth/OTP/MFA/passkeys/3DS/payment/access-control/anti-abuse systems are handled automatically.

Detector pages such as Sannysoft, CreepJS, and BrowserLeaks are proxy evidence only. Passing or improving them is not a guarantee of success on real merchants, login systems, or anti-abuse stacks. This runtime does not claim automated handling of CAPTCHA, OAuth, OTP/MFA, passkeys, 3DS, bank challenges, payment/checkout flows, rate limits, or access controls. Human-only checkpoints remain pause/takeover/approval.

Residual-risk operating checklist: `browser-runtime/docs/fingerprint-hygiene-residual-risk-runbook.md`.

### Deterministic fingerprint probe and compare helpers

Run these only against local/private sessions and keep raw session JSON private because it can contain live capability URLs:

```bash
python3 browser-runtime/scripts/fingerprint_probe.py \
  --session-json browser-runtime/artifacts/<run>/session-create.json \
  --out browser-runtime/artifacts/<run>/fingerprint-probe.json \
  --mode local-deterministic \
  --strict

python3 browser-runtime/scripts/fingerprint_compare.py \
  --before browser-runtime/artifacts/<before>/fingerprint-probe.json \
  --after browser-runtime/artifacts/<after>/fingerprint-probe.json \
  --out browser-runtime/artifacts/<after>/p4-risk-delta.md \
  --json-out browser-runtime/artifacts/<after>/p4-risk-delta.json
```

### Public detector capture and comparison helpers

Use these only for public diagnostic pages and treat results as proxy evidence:

```bash
python3 browser-runtime/scripts/public_detector_capture.py \
  --session-json browser-runtime/artifacts/<run>/session-create.json \
  --out-dir browser-runtime/artifacts/public-detector-screens/<run> \
  --viewport-width 1280 \
  --viewport-height 800 \
  --max-height 20000 \
  --strict-nonblank

python3 browser-runtime/scripts/public_detector_compare.py \
  --before browser-runtime/artifacts/public-detector-screens/<baseline> \
  --after browser-runtime/artifacts/public-detector-screens/<run> \
  --out browser-runtime/artifacts/public-detector-screens/<run>/comparison.md \
  --json-out browser-runtime/artifacts/public-detector-screens/<run>/comparison.json \
  --redact
```

The capture helper writes redacted manifest counts and canonical screenshot metadata. The compare helper accepts `--redact` as an explicit compatibility flag; public comparison output must not expose raw input directory names, public IP literals, CDP/takeover capability URLs, cookies/tokens/auth markers, private paths, or stable detector/fingerprint hashes.

Share only artifacts appropriate to their tier. Strict artifact hygiene means no secrets, capability URLs, or private paths were found; it does not automatically mean a bundle is safe for public sharing because detector page text/screenshots/JSON can still contain public IPs and stable fingerprint evidence. Internal sanitized bundles stay private. Only bundles produced by the public-share redaction tier, or explicitly reviewed/approved excerpts, may be shared externally.

## Build and run

Build a binary:

```bash
PATH=$HOME/.cargo/bin:$PATH \
CARGO_HOME=$HOME/.cargo \
RUSTUP_HOME=$HOME/.rustup \
cargo build --manifest-path browser-runtime/Cargo.toml --release
```

Optional user-local install:

```bash
install -Dm755 browser-runtime/target/release/hermes-browser-runtime \
  ~/.local/bin/hermes-browser-runtime
```

Start the server with an explicit Chrome path:

```bash
export HBR_CHROME_PATH="$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"
# Optional if your host sandbox is incompatible:
# export HBR_CHROME_NO_SANDBOX=1
# Optional shared-secret auth for the HTTP API / CLI client:
# export HBR_BEARER_TOKEN='choose-a-long-random-token'
# Required for credential approve/deny/privacy-guard clear when using the credential broker:
# export HBR_OPERATOR_TOKEN='choose-a-different-long-random-operator-token'

hermes-browser-runtime server
```

Health check:

```bash
curl -s http://127.0.0.1:7788/health
```

Expected result:

```json
{"ok":true}
```

## Dependency security checks

`cargo test` stays the normal build/test loop. Dependency advisories are intentionally split into an opt-in gate so missing third-party audit tools never break ordinary local development.

Install once:

```bash
cargo install cargo-audit cargo-deny
```

Run the repository helper from anywhere:

```bash
browser-runtime/scripts/security-gates.sh
```

That helper runs `cargo-audit audit --file browser-runtime/Cargo.lock` and `cargo-deny check --manifest-path browser-runtime/Cargo.toml --config browser-runtime/deny.toml`, but prints install guidance instead of failing if either tool is absent.

## Coverage gate

Run the browser-runtime-only coverage gate from anywhere in the repo:

```bash
browser-runtime/scripts/coverage-gates.sh
```

The helper resolves the real home directory, exports `CARGO_HOME`, `RUSTUP_HOME`, and `PATH`, then runs:

```bash
cargo llvm-cov --manifest-path browser-runtime/Cargo.toml --all-features --summary-only --fail-under-lines 97
```

If `cargo llvm-cov` is missing, the helper prints the reproducible setup commands:

```bash
rustup component add llvm-tools-preview
cargo install cargo-llvm-cov --locked
```

Coverage questions around `browser-runtime/src/backend.rs` should use the approved evidence bundle in `browser-runtime/target/d1b3_backend_evidence.txt` plus the exception register in `browser-runtime/docs/implementation-plan.md` before adding more tests just to chase instantiation-accounting noise.

## Daily-use CLI workflow

The CLI covers the daily operator flow:

- `profiles create|list|delete`
- `sessions create|get|list|pause|wait|release|screenshot|delete`
- `credentials fill|status|approve|deny|privacy-guard clear` (`credential ...` is accepted as a top-level alias; `credentials clear-guard` remains a compatibility alias)
- `captcha report|resolve`
- `artifacts list|downloads|download|cleanup|replay`

Example flow:

```bash
export HBR_SERVER=http://127.0.0.1:7788
# export HBR_BEARER_TOKEN='<local agent/server token>'      # fill/status/session routes; never paste into logs/docs
# export HBR_OPERATOR_TOKEN='<local operator-only token>'   # approve/deny/privacy-guard clear; must be different

# Broker setup: keep real provider disabled unless this run is explicitly approved.
export HBR_CREDENTIAL_PROVIDER=mock
export HBR_CREDENTIAL_POLICY_PATH=/absolute/private/path/hbr-credential-policy.json
export HBR_CREDENTIAL_PRIVACY_GUARD=true
# Fresh real-provider smoke is blocked/untested until an operator provisions/unlocks a safe test 1Password item/vault,
# sets a private policy plus onepassword_cli/op/operator-token config, runs the documented real-smoke harness,
# sanitizes the evidence bundle, and gets reviewer sign-off.

hermes-browser-runtime profiles create --id yura-main
hermes-browser-runtime profiles list

hermes-browser-runtime sessions create --profile-id yura-main
# Copy the returned session id from JSON into SESSION_ID

hermes-browser-runtime sessions get "$SESSION_ID"
hermes-browser-runtime sessions screenshot "$SESSION_ID" --output /tmp/hbr-shot.png

# Fill-only credential broker flow: request/status use the agent bearer; approval/guard clear use the operator token.
hermes-browser-runtime credentials fill "$SESSION_ID" --alias demo-login --username-selector '#user' --password-selector '#pass' --expected-origin https://example.test
# Copy the returned request id from JSON into CREDENTIAL_REQUEST_ID.
hermes-browser-runtime credentials status "$SESSION_ID" "$CREDENTIAL_REQUEST_ID"
hermes-browser-runtime credentials approve "$SESSION_ID" "$CREDENTIAL_REQUEST_ID" --note "operator approved login fill"
hermes-browser-runtime credentials privacy-guard clear "$SESSION_ID"

# Manual challenge/checkpoint flow: report -> human takeover -> resolve.
hermes-browser-runtime captcha report "$SESSION_ID" --state human_required --challenge-type "visual-checkpoint" --reason "manual checkpoint"
hermes-browser-runtime sessions wait "$SESSION_ID" --timeout-secs 300
hermes-browser-runtime captcha resolve "$SESSION_ID" --outcome resolved --note "human completed checkpoint"

# Local inspector: open in a local browser. If bearer auth is enabled, the page prompts for the token and keeps it in memory for that tab only.
# http://127.0.0.1:7788/inspector

hermes-browser-runtime sessions pause "$SESSION_ID" --reason "manual oauth approval"
hermes-browser-runtime sessions wait "$SESSION_ID" --timeout-secs 300
hermes-browser-runtime sessions release "$SESSION_ID"
hermes-browser-runtime artifacts list "$SESSION_ID"
hermes-browser-runtime artifacts downloads "$SESSION_ID"
hermes-browser-runtime artifacts download "$SESSION_ID" report.csv --output /tmp/report.csv
hermes-browser-runtime artifacts replay "$SESSION_ID" --output /tmp/hbr-replay.html
hermes-browser-runtime artifacts cleanup --dry-run --older-than-secs 604800
hermes-browser-runtime sessions delete "$SESSION_ID"

hermes-browser-runtime profiles delete yura-main
```

Notes:

- `sessions create` defaults to `persist_profile=true` and lets the server choose headed/headless mode: headed when a local display or `xvfb-run` wrapper is available, otherwise headless. Pass `--headless` or `--headful` to override per session.
- `sessions create` also accepts `--webrtc-ip-policy` and `--gpu-policy`; if omitted, the server defaults from `HBR_WEBRTC_IP_POLICY` / `HBR_GPU_POLICY` are used.
- The HTTP API supports explicit `headless`, `persist_profile`, `webrtc_ip_policy`, and `gpu_policy` fields in `CreateSessionRequest` if an integration needs to override them.
- `sessions screenshot` writes a PNG when `--output` is provided.
- Credential fill HTTP endpoints are session-scoped under `/sessions/:id/credentials/...`. Fill/status use normal bearer-token auth when enabled; approve/deny/privacy-guard clear require the separate `HBR_OPERATOR_TOKEN` / `--operator-token` capability and are rejected if it is missing or reused as `HBR_BEARER_TOKEN`. They return redacted status records only; selectors and provider references are never returned. HBR observes the live origin itself, uses `expected_origin` only as an extra check, and scopes provider reads to the fields actually requested/approved (`allowed_fields` must permit username and/or password). The canonical privacy-guard clear endpoint is `POST /sessions/:id/credentials/privacy-guard/clear`; the old underscored route remains compatibility-only. Approve/deny accept an optional JSON body such as `{ "note": "..." }`; notes are redacted in persisted status/events.
  - Minimal auth-separation smoke: with the server started using different private values for `HBR_BEARER_TOKEN` and `HBR_OPERATOR_TOKEN`, `curl -o /dev/null -w '%{http_code}\n' -X POST -H "Authorization: Bearer $HBR_BEARER_TOKEN" "$HBR_SERVER/sessions/00000000-0000-0000-0000-000000000000/credentials/fill/00000000-0000-0000-0000-000000000000/approve"` must print `403`; repeat with `$HBR_OPERATOR_TOKEN` and it should pass auth (normally `404` for the dummy IDs).
- CAPTCHA HTTP endpoints are `POST /sessions/:id/captcha/report` with `suspected|human_required|in_progress`, `POST /sessions/:id/captcha/resolve` with `resolved|failed|dismissed`, `POST /sessions/:id/captcha/scan`, `GET /sessions/:id/captcha/status`, and `POST /sessions/:id/captcha/solve`. Report/resolve remain the manual fallback path. Solve is disabled by default and performs a provider call only when the session uses `auto_solve`, the solver kill switch is enabled, a provider key is configured, and budget gates pass; failures and missing gates record redacted status and require human takeover. Real-provider smoke is still downstream-gated.
- Inspector HTTP surfaces are `/inspector`, `/inspector/:id`, `/inspector/api/sessions`, `/inspector/api/sessions/:id`, `/inspector/api/sessions/:id/live-links`, `/inspector/api/sessions/:id/live-links/:link_id`, `/inspector/api/sessions/:id/release`, and `/inspector/api/sessions/:id/cancel`. Inspector requires loopback bind unless `HBR_ALLOW_NONLOCAL_INSPECTOR=true` is explicitly set; keep it local/private.
- `artifacts list` is the quickest way to inspect the event log + screenshots tied to one session.
- `artifacts downloads` lists sanitized download names; `artifacts download` streams raw bytes unless `--output` is provided.
- `artifacts replay` writes a standalone HTML timeline with embedded screenshots and the redacted event-log text for offline review.
- `artifacts cleanup` supports both dry-run inventory and destructive retention cleanup with the same `older_than_secs` cutoff as the HTTP API.

## Downloads, replay, retention cleanup, and upload helpers

Session downloads and artifacts stay inside the session's private runtime directory. The runtime only serves leaf download names, so requests like `../secrets.txt` are rejected before any path lookup.

Artifact hygiene rule: the raw runtime data directory is private by default. Do not publish `runtime-data/profiles/`, `runtime-data/tmp/`, Chrome profile files, raw screenshots/page text, raw `session.json`, raw `events.jsonl`, or session-create JSON containing `cdp_ws_url` from local runs without the approved sanitizer/redaction path. Use the text-only scanner for internal review bundles, and use the public-redacted tier before anything is shared externally:

```bash
python3 browser-runtime/scripts/artifact_hygiene_scan.py \
  --source browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z \
  --sanitize-to browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized \
  --tier internal-sanitized \
  --strict \
  --json-report browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized/hygiene-scan-report.json

python3 browser-runtime/scripts/artifact_hygiene_scan.py \
  --source browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z \
  --sanitize-to browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted \
  --tier public-redacted \
  --strict \
  --json-report browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted/public-redaction-scan-report.json
```

For the reviewed P5 closure, the raw evidence directory and internal sanitized bundle remain local/private because detector/probe material can contain public IPs, stable fingerprint evidence, screenshots/page text, or runtime state even when secret/private-path hygiene passes. The reviewed public-share bundle is `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted/`; its strict scan report has findings `[]` and `public_share_safe=true`. The reviewed internal bundle is `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized/`; its strict scan report has findings `[]` but `public_share_safe=false` by design. The current P4-S1 public-detector benchmark context is `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z/`; use `run-20260512T173631Z-public-redacted/` for public-safe summaries and keep raw/runtime-data plus internal sanitized bundles private. The older P4 sanitized bundle `browser-runtime/artifacts/hbr-p4-bench/run-20260511T235056Z-sanitized` remains historical P4 evidence, not the latest P4-S1 run.

Useful commands:

```bash
hermes-browser-runtime artifacts downloads "$SESSION_ID"
hermes-browser-runtime artifacts download "$SESSION_ID" report.csv --output /tmp/report.csv
hermes-browser-runtime artifacts replay "$SESSION_ID" --output /tmp/hbr-replay.html
hermes-browser-runtime artifacts cleanup --dry-run --older-than-secs 604800
hermes-browser-runtime artifacts cleanup --older-than-secs 604800
```

Notes:

- `artifacts replay` is the current MVP replay path: it renders stored screenshots plus captured `events.jsonl` into one local HTML file.
- `artifacts cleanup --dry-run` reports what would be removed without deleting anything; omitting `--dry-run` performs the real deletion.
- `HBR_ARTIFACT_RETENTION_SECS` and `--artifact-retention-secs` control the default retention window for automated cleanup policies.

There is no first-class upload endpoint yet. The supported workaround is a short Playwright helper attached to the session's `cdp_ws_url`, then `setInputFiles(...)` on the target page while keeping the file path local to the operator machine:

```ts
import { chromium } from 'playwright';

const browser = await chromium.connectOverCDP(process.env.HBR_CDP_WS_URL!);
const context = browser.contexts()[0];
const page = context.pages()[0];
await page.locator('input[type="file"]').setInputFiles('/absolute/path/to/local-file.pdf');
await browser.close();
```

Treat that helper like takeover: keep paths local, do not paste sensitive filenames or bearer secrets into shared logs, and prefer short-lived one-off scripts over baking uploads into general runtime logs.

## Wait/release human takeover flow

The intended human-in-the-loop flow is:

1. Agent or operator creates a session.
2. Work proceeds until a human checkpoint is needed.
3. Agent or operator pauses the session:
   ```bash
   hermes-browser-runtime sessions pause "$SESSION_ID" --reason "manual oauth approval"
   ```
4. The pause response includes a refreshed `takeover_url`.
5. Human opens that URL locally, reviews the screenshot, and uses the takeover helpers (`click`, `type`, `key`, `scroll`) until the checkpoint is complete.
6. Agent waits in a bounded loop:
   ```bash
   hermes-browser-runtime sessions wait "$SESSION_ID" --timeout-secs 300
   ```
7. Human clicks `Release browser back to agent` in the takeover page, or an operator runs:
   ```bash
   hermes-browser-runtime sessions release "$SESSION_ID"
   ```
8. The next `wait` returns immediately with the session back in `Running` state.

The takeover page intentionally includes:

- a screenshot-first, mobile-friendly viewport helper
- Fit/zoom controls, a scrollable/pannable screenshot, and a `Top-left form/captcha` preset for phone-sized screens
- click-coordinate mapping based on the screenshot's natural dimensions, so taps remain correct while fitted, zoomed, or panned
- path-prefix-safe same-origin action URLs for private proxies such as tailnet-only Tailscale Serve
- `Keyboard helpers`
- `/takeover/:id/key` support for safe navigation keys
- a text area for typed input
- an explicit warning that typed text is never stored in runtime logs

Important nuance: runtime log redaction protects the local runtime logs, not the remote website. If a human types a password, OTP, or card number into the takeover page, the destination site still receives it as intended.

## Phone/off-LAN takeover contract

The mobile/off-LAN contract is intentionally stricter than a normal localhost demo:

- keep the runtime bound to `127.0.0.1` by default
- treat the returned `takeover_url` as a TTL-scoped bearer secret for one paused session
- make the handoff usable from a normal phone browser
- require an explicit `Release browser back to agent` handoff when the human step is complete

Approved remote/mobile access patterns are:

1. SSH local-port-forward using the same local port, so the localhost-generated `takeover_url` works unchanged on the operator device.
2. Tailnet-only Tailscale Serve (or equivalent tailnet-only HTTPS proxy) in front of `127.0.0.1:7788`.
3. A future signed one-time HTTPS takeover URL with bearer auth plus TTL.

Current implementation truth: `browser-runtime` still generates takeover links from `http://127.0.0.1:<bind-port>/...`. It does not yet mint a first-class signed HTTPS handoff URL itself. That HTTPS broker path is deferred; until it exists, remote/mobile access should transport the localhost path/query over SSH or tailnet-only Tailscale rather than changing the runtime's default bind or exposing it publicly.

If the human is on a phone, the goal is a short, bounded checkpoint: open the link, use the zoom/pan/top-left screenshot controls to complete the manual-only step, confirm the state, and release control back to the agent immediately so `sessions wait` can resume. The page may remove the token query from the visible address bar after it loads, but the original `takeover_url` is still a bearer secret and must not be shared.

## OAuth, login, payment, and 3DS guidance

Use takeover for any flow that should remain human-only:

- username/password entry
- MFA / OTP / magic-link approval
- OAuth consent screens
- payment approval
- credit-card / debit-card entry
- 3DS / bank challenge flows

Rules:

- keep the agent out of raw credentials, OTPs, cookies, auth headers, and payment data
- do not paste passwords, card numbers, CVVs, or takeover URLs into chat, tickets, shell history, or logs
- keep pause reasons generic (`manual oauth approval`, `payment approval required`, `3DS challenge`) rather than embedding sensitive text
- card entry and 3DS approval remain human-in-the-loop even if the rest of the browsing flow is automated
- if a site resists headless automation or requires more visual certainty, prefer a local headful browser window when available

Before any final `pay`, `place order`, or equivalent purchase-confirmation action, require explicit Telegram approval that includes:

- merchant/domain
- item summary
- total amount and currency
- shipping summary
- payment-method label (for example `Visa •••• 1234` or `PayPal`)

No Telegram approval means no final submission. The agent may prepare checkout, but it must not claim to solve or automatically handle hCaptcha, OAuth consent, OTP/MFA, 3DS, bank challenges, or similar human-only checkpoints.

## Takeover URL security expectations

Treat every `takeover_url` as a bearer secret.

- whoever has the URL + token can drive the paused browser session
- do not post takeover URLs in shared chats, CI logs, tickets, or screenshots
- every pause rotates the token; old paused URLs stop working
- current runtime behavior is TTL-scoped per pause, not a strict single-click one-time link
- release and expiry invalidate the current token
- invalid/expired tokens return a generic `403` instead of echoing secrets back

The runtime normalizes the generated base URL back to localhost. Even if the server binds `0.0.0.0`, the generated takeover URL is still emitted as `http://127.0.0.1:<port>/...`. This is deliberate: remote access should happen through an explicit tunnel, not through an accidentally public bind.

If a future remote broker emits a signed HTTPS takeover link, that broker-layer link should be one-time or extremely short-lived on top of the runtime TTL. `browser-runtime` itself does not emit that HTTPS link today.

## Hermes integration

Current repo state documents `browser-runtime` as an explicit CLI/HTTP sidecar.

Practical integration pattern today:

1. Start `hermes-browser-runtime server` separately.
2. Keep it private on localhost or behind an SSH tunnel.
3. Export `HBR_SERVER` and, if enabled, `HBR_BEARER_TOKEN` in the same shell/session used by your automation.
4. Have Hermes tasks or wrappers call the CLI (`hermes-browser-runtime sessions ...`) or the HTTP API directly.

Example same-host shell setup:

```bash
export HBR_SERVER=http://127.0.0.1:7788
export HBR_BEARER_TOKEN='choose-a-long-random-token'   # optional if the server uses auth
```

Then a Hermes task can safely drive browser-runtime through ordinary terminal calls without exposing the server beyond localhost.

## systemd --user sample

There is no auto-installer here. If you want a long-lived user service, build/install the binary first, then create a user unit manually.

Suggested unit file: `~/.config/systemd/user/hermes-browser-runtime.service`

```ini
[Unit]
Description=Hermes browser runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=HBR_BIND=127.0.0.1:7788
Environment=HBR_CHROME_PATH=%h/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome
# Optional only when sandboxing is unavailable on the host:
# Environment=HBR_CHROME_NO_SANDBOX=1
# Optional shared-secret auth:
# Environment=HBR_BEARER_TOKEN=replace-with-a-long-random-token
# Optional explicit browser policies:
# Environment=HBR_WEBRTC_IP_POLICY=default_public_interface_only
# Environment=HBR_GPU_POLICY=auto
ExecStart=%h/.local/bin/hermes-browser-runtime server
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
```

Enable and inspect:

```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-browser-runtime.service
systemctl --user status hermes-browser-runtime.service --no-pager
journalctl --user -u hermes-browser-runtime.service -n 100 --no-pager
```

If the service must survive logout on a headless Linux host, the operator may also need:

```bash
sudo loginctl enable-linger "$USER"
```

That step is intentionally not automated here.

## Phone/off-LAN transport patterns

### SSH tunnel: easiest way to keep the returned URL unchanged

```bash
ssh -N -L 7788:127.0.0.1:7788 user@remote-host
```

Why the same port matters:

- the runtime emits takeover URLs on `127.0.0.1:<bind-port>`
- if you forward the same port locally, the returned `takeover_url` works unchanged in your local browser

If local port `7788` is already in use, either free it or intentionally run the remote server on a different bind port and forward that same port locally.

### Tailnet-only Tailscale Serve: phone-friendly private HTTPS access

On the Hermes host:

```bash
tailscale serve --bg 7788
tailscale serve status
```

Use the HTTPS origin reported by `tailscale serve status`, then copy the sensitive `/takeover/<id>?token=...` path/query from the runtime response onto that origin.

Example shape:

```text
runtime returns: <redacted local takeover URL>
open on phone:  <redacted tailnet takeover URL>
```

Notes:

- keep this tailnet-only; do not use a public internet exposure for the local runtime
- because the runtime still emits localhost URLs today, the host/origin rewrite is manual when using Tailscale Serve
- after the human step completes, use the takeover page's `Release browser back to agent` button so the waiting agent resumes promptly

## Troubleshooting

`curl http://127.0.0.1:7788/health` fails
- confirm the server is running
- confirm `HBR_BIND` / `--bind` matches the port you are checking
- inspect `journalctl --user -u hermes-browser-runtime.service` if using systemd

Chrome fails to launch
- set `HBR_CHROME_PATH` explicitly
- if the host cannot provide a usable sandbox, try `HBR_CHROME_NO_SANDBOX=1`
- re-check that the Chrome binary exists and is executable

CLI gets `401 Unauthorized`
- `HBR_BEARER_TOKEN` on the client does not match the server token
- avoid printing the token while debugging

Takeover page gets `403`
- the token is stale, expired, or from an earlier pause
- pause the session again and use the newest `takeover_url`

`sessions wait` keeps timing out
- the session is still paused
- the human completed the web action but forgot to release the browser back to the agent

Service works in a shell but not after logout
- run it under `systemd --user`
- if needed, enable linger so the user manager survives logout

## Logging and privacy rules

Do not log or copy into notes/chat:

- takeover URLs or tokens
- cookies
- bearer tokens / auth headers
- passwords / OTPs
- card numbers / CVVs
- raw form bodies or request bodies

The runtime already redacts many of these markers, but operator hygiene should assume redaction can fail if you paste secrets into the wrong place.