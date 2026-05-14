# browser-runtime SEC-V review report

## HBR v0B docs alignment note

Canonical operator docs now describe the current v0B truth:

- README and `docs/hbr-agentic-browser-safe-foundation.md` separate what is usable now, mock-only, real 1Password smoke status, Юра-required approvals, and deferred work.
- CAPTCHA/checkpoint handling is authenticated report/resolve plus human takeover state by default. A provider-backed connector foundation exists but is disabled by default and gated by `auto_solve`, `HBR_CAPTCHA_SOLVER_ENABLED=true`, provider-key availability, and budget limits; missing gates fail closed to redacted status plus human takeover. No real-provider smoke/readiness, provider marketplace, or protected-flow automation is claimed.
- Credential broker behavior is fill-only, operator-approval-gated, and field-scoped. Modes are `disabled`, `fake_status_only`, `mock`, and `onepassword_cli`; default is `disabled`; private policy uses exact normalized origins and safe aliases.
- Mock smoke is green for request -> approval -> filled status, CAPTCHA report/resolve, auth checks, inspector HTML/API, privacy guard, wait while paused, and release. Post-fix no-secret mock Son of a Tailor proof is green for the email-field fill path.
- Fresh post-fix real 1Password smoke is blocked/untested: only historical pre-fix real-provider evidence exists, and it is not production readiness. The next real-smoke action is operator provisioning/unlock of a safe test item/vault, private provider/operator config, documented harness run, sanitized evidence, and reviewer sign-off.
- Inspector is local/private: `/inspector` and `/inspector/api/...` show status, artifacts, checkpoint state, credential fill status, release/cancel, and read-only/interactive live links. Credential approve/deny remains through the operator-only credential CLI/API capability.
- Payment/final-action boundary remains explicit: credential fill never authorizes checkout, payment, OAuth consent, MFA/passkey, 3DS/bank checks, or final order submission.

Date: 2026-05-11T10:21:53+01:00
Task: t_0760d84c
Repo: $HOME/.hermes/hermes-agent
Branch reported by git: main
Scope reviewed: browser-runtime/

## Handoffs and evidence reviewed first

- `t_18033d09`: SEC-A remediation requiring explicit pause before takeover is usable, plus release invalidation coverage.
- `t_078a711a`: SEC-B remediation sanitizing request tracing so `/takeover/...?...token=...` query secrets are never logged.
- Current workspace code/tests in `browser-runtime/src/store.rs`, `browser-runtime/src/api.rs`, and `browser-runtime/src/cli.rs`.

## Live inspection before rerunning verification

1. `git status --short --branch -- browser-runtime`
   - repo-root git still reports `?? browser-runtime/` on branch `main`
2. `git -C browser-runtime status --short --branch`
   - crate git reports `## main...origin/main [behind 46]`
   - unrelated dirt exists outside SEC-V scope (`../hermes_cli/main.py`, `../.recovery-*`, `?? ./`)
3. `date --iso-8601=seconds`
   - `2026-05-11T10:14:50+01:00` during initial SEC-V inspection
4. Chrome availability check
   - `HBR_CHROME_PATH` was unset in this worker profile environment
   - `$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome` exists and was used for the live smoke
5. Source spot-checks confirmed the intended security state before reruns:
   - `browser-runtime/src/store.rs` creates sessions with `takeover_url: None`, mints takeover only on `pause_for_human`, requires `PausedForHuman` plus a non-empty matching token in `validate_takeover_token(...)`, and clears token + `takeover_url` on `release`
   - `browser-runtime/src/api.rs` takeover routes return the uniform generic `403` body for invalid/expired takeover tokens
   - `browser-runtime/src/cli.rs` request tracing logs `request.uri().path()` rather than full query strings

## Targeted SEC-V test evidence

1. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo test --manifest-path browser-runtime/Cargo.toml persistent_profiles_require_pause_before_takeover_tokens_work -- --nocapture`
   - PASS
   - proves running sessions expose no live takeover URL/token before pause, pause generates a usable takeover token, and `release` invalidates the earlier token and clears `takeover_url`
2. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo test --manifest-path browser-runtime/Cargo.toml takeover_routes_accept_valid_tokens_and_drive_cdp_fallbacks -- --nocapture`
   - PASS
   - proves pause-generated takeover routes work end to end, including live takeover page access and takeover-triggered release returning the session to `running`
3. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo test --manifest-path browser-runtime/Cargo.toml takeover_routes_reject_invalid_tokens_without_echoing_secrets -- --nocapture`
   - PASS
   - proves pre-pause/invalid-token takeover requests return generic `403` bodies without echoing the token or sensitive request text
4. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo test --manifest-path browser-runtime/Cargo.toml request_tracing_drops_takeover_query_tokens_from_logs -- --nocapture`
   - PASS
   - proves debug tracing output contains the sanitized `/takeover/<id>` path but neither `token=` nor the token value

## Fresh full-gate rerun

1. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo fmt --manifest-path browser-runtime/Cargo.toml --all -- --check`
   - PASS
2. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo clippy --manifest-path browser-runtime/Cargo.toml --all-targets --all-features -- -D warnings`
   - PASS
3. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo test --manifest-path browser-runtime/Cargo.toml --all-features -- --quiet`
   - PASS
   - `123` lib tests passed
   - `4` `cli_binary` tests passed
   - `2` `browser_integration` tests remain intentionally ignored manual placeholders (`requires Chrome and node package playwright-core; run manually`)
4. `PATH=$HOME/.cargo/bin:$PATH CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup cargo llvm-cov --manifest-path browser-runtime/Cargo.toml --all-features --summary-only --fail-under-lines 98`
   - PASS
   - Total coverage: `98.31%` regions, `99.86%` functions, `99.80%` lines
   - Covered regions/functions/lines: `8981` regions, `726` functions, `6076` lines
   - Missed regions/functions/lines: `154` regions, `1` function, `12` lines

## Live Chrome smoke rerun

Chrome was available, so I reran a fresh live-browser smoke instead of reusing old evidence.

Server command used:

```bash
HBR_BIND=127.0.0.1:35741 \
HBR_DATA_DIR=/tmp/hbr-sec-v-smoke.<tmp> \
HBR_CHROME_PATH=$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome \
HBR_CHROME_NO_SANDBOX=1 \
$HOME/.hermes/hermes-agent/browser-runtime/target/debug/hermes-browser-runtime server
```

Smoke workflow used a local Python harness plus the compiled CLI binary at `$HOME/.hermes/hermes-agent/browser-runtime/target/debug/hermes-browser-runtime` to drive:
- `profiles create/list/delete`
- `sessions create/get/list/screenshot/pause/wait/release/delete`
- `artifacts list`
- direct `GET /takeover/:id?...` and `POST /takeover/:id/release?...` checks without printing takeover tokens

Fresh smoke result:
- server health OK on `http://127.0.0.1:35741/health`
- profile flow PASS: create/list/delete
- session flow PASS: create/get/list/screenshot/pause/wait/release/delete
- screenshot file written successfully (`3880` bytes)
- artifacts list PASS (`2` artifacts returned)
- pre-pause takeover request with a synthetic token returned generic `403`
- paused session returned a live takeover URL; opening it returned `200 OK` and the page still included `Hermes Browser Runtime takeover`, `Keyboard helpers`, and `Release browser back to agent`
- pause reason `manual oauth approval` came back redacted as `[REDACTED]`
- `sessions wait --timeout-secs 1` timed out while paused, then returned immediately with `running` after release
- takeover-triggered release invalidated the prior paused token; the same paused URL returned generic `403` after release
- temporary server/data dir were removed after the smoke

## SEC-V verdict

### PASS — SEC-A reviewer blocker is closed

Evidence:
- pre-pause session create/get/list responses exposed `takeover_url: null`
- a pre-pause takeover request was rejected with generic `403`
- pause generated a live takeover page
- release cleared `takeover_url`, invalidated the paused token, and returned `wait` to `running`

### PASS — SEC-B reviewer blocker is closed

Evidence:
- `request_tracing_drops_takeover_query_tokens_from_logs` passed on the current workspace
- `browser-runtime/src/cli.rs` still builds the HTTP tracing span from request method + path-only URI
- no fresh verification step required or observed any `token=` or raw takeover-token logging

## Reviewer-ready conclusion

The P1 security remediations are green in the current workspace. Fresh targeted SEC-V tests passed, the full fmt/clippy/test/llvm-cov gate passed under the then-current `>=98%` standard; the active standard is now `>=97%` after Юра's threshold update. A new live-Chrome smoke against `$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome` confirmed the real takeover/release flow on an actual browser runtime.

ready_for_re_review: yes

## HBR-COV follow-up

Date: 2026-05-11T14:03:00+01:00
Task: t_b7b9293c

Fresh coverage/doc follow-up on the current workspace:
- Added `browser-runtime/scripts/coverage-gates.sh` as the browser-runtime-only helper for `cargo llvm-cov --manifest-path browser-runtime/Cargo.toml --all-features --summary-only --fail-under-lines 97`
- Added the matching coverage-gate and setup instructions to `browser-runtime/README.md`
- Re-ran `cargo fmt --manifest-path browser-runtime/Cargo.toml --all -- --check`
- Re-ran `cargo clippy --manifest-path browser-runtime/Cargo.toml --all-targets --all-features -- -D warnings`
- Re-ran `cargo test --manifest-path browser-runtime/Cargo.toml --all-features -- --quiet`
- Re-ran `bash -n browser-runtime/scripts/coverage-gates.sh && browser-runtime/scripts/coverage-gates.sh`
- Re-ran `HBR_CHROME_NO_SANDBOX=1 HBR_CHROME_PATH=$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome cargo test --manifest-path browser-runtime/Cargo.toml --test browser_integration -- --ignored --quiet`

Exact fresh llvm-cov TOTAL row:
- `TOTAL 11679 416 96.44% 862 25 97.10% 7723 138 98.21% 0 0 -`

Interpretation:
- The enforced browser-runtime gate is now the explicit line-coverage threshold (`--fail-under-lines 97`). The latest reviewed P2 measurement of `97.56%` passes this gate; `>=98%` is aspirational only.
- Do not rely on older stored `98.31%`/`99.80%` figures for this workspace state; use the fresh command above instead.
- `browser-runtime/src/backend.rs` still uses the previously approved instantiation-accounting exception documented in `browser-runtime/docs/implementation-plan.md` and evidenced by `browser-runtime/target/d1b3_backend_evidence.txt`.

## BOT-02/P3 docs alignment note

Documentation task: `t_7e13d63b`.

Canonical docs now need to preserve these reviewer assumptions:
- WebRTC default is `default_public_interface_only`: local/private host-candidate IP literals are hidden by default, while the public/default-interface IP remains visible by design.
- WebRTC compatibility is explicit: `default_public_and_private_interfaces` for fuller WebRTC behavior, `disable_non_proxied_udp` for stricter behavior that can break legitimate WebRTC flows.
- GPU default is `auto`: no forced SwiftShader or `--disable-3d-apis` on the headed default path; `swiftshader_compat` and `disable_3d` are explicit opt-ins.
- BrowserLeaks WebGL evidence from `browser-runtime/artifacts/bot02-p3-evidence/run-20260511T212756Z` is Xvfb/no-display limited and must not be described as proof of a real headed GPU renderer path.
- Remote/mobile takeover remains localhost/private by default: SSH local-port-forward, tailnet-only Tailscale Serve, or a future signed HTTPS handoff. The future signed broker is not implemented in `browser-runtime` today.
- Takeover URLs remain TTL-scoped bearer secrets, rotated on pause and invalidated on release/expiry. Do not paste them into chat, tickets, logs, screenshots, or shell history.
- Redaction protects local runtime logs; it does not mean destination websites never receive human-entered passwords, OTPs, card data, or approval actions.
- CAPTCHA, OAuth, OTP/MFA, passkey, 3DS, bank challenges, card entry, and final payment/order approval stay human-only. Final `pay` / `place order` submission still requires explicit Telegram approval with merchant, items, total/currency, shipping summary, and payment-method label.

Deferred by design: first-class signed HTTPS takeover broker, real headed GPU validation on a consumer-like display/GPU stack, network/IP reputation work, and claims that detector-page results guarantee real-site success.

## HBR-P4 docs alignment note

Documentation task: `t_2561e6df`.

Canonical docs now need to preserve these P4 reviewer assumptions:
- P4A is a browser identity-coherence and evidence-harness slice for legitimate fingerprint hygiene, not an undetectability, challenge-automation, payment-automation, rate-limit-automation, or access-control automation feature.
- Supported policy modes remain explicit: WebRTC `default_public_interface_only` / `default_public_and_private_interfaces` / `disable_non_proxied_udp`; GPU `auto` / `swiftshader_compat` / `disable_3d`; P4 probe mode `local-deterministic` only.
- Current P4 benchmark evidence is `browser-runtime/artifacts/hbr-p4-bench/run-20260511T235056Z-sanitized`: 7/7 public detector pages collected; strict hygiene scanned 21 text files with 0 findings and 0 private-path findings.
- The measured P4 improvement is UA/UA-CH identity coherence: prior evidence mixed Chrome 125 UA with Chromium 147 UA-CH surfaces; after P4, BrowserLeaks/CreepJS and the direct probe report Chrome/Chromium/Google Chrome major 147 consistently.
- Unchanged residuals must stay visible: public/default-interface IP remains visible by design; CreepJS still reports mDNS `.local` and public srflx candidates plus 44% like headless / 33% headless / 0% stealth; WebGL/GPU remains blocked/unavailable in the no-display/Xvfb worker environment; consumer-like GPU behavior is not proven.
- The P4 direct probe had `popup.measured=false` in the benchmark run; popup coherence should be cited from the parent ignored Chrome smoke, not from that artifact.
- Raw P4 benchmark artifacts contain screenshots, page text, and runtime profile state. Keep raw directories private-local and cite/share only sanitized bundles after strict hygiene scan.
- Human-only checkpoints remain human-only: CAPTCHA-like challenges, OAuth consent, OTP/MFA, passkeys, 3DS/bank challenges, card entry, payment approval, and final purchase/order submission still require pause/takeover/approval.

## HBR-P5 residual closure docs alignment note

Documentation task: `t_26ddadf8`.
Fresh verification task: `t_a9deff55`.
PM classification task: `t_c1c66943`.

Reviewer assumptions to preserve for final P5 sign-off:

- Fix-now closure evidence is limited to two safe items: direct-probe popup status ambiguity and public-share artifact redaction. It is not detector-specific evasion work.
- Fresh direct-probe artifact: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/fingerprint-probe.json`.
  - It reports `measurement_contract_version=hbr.p5.direct_probe.v1`, `measurement_completeness.complete=true`, `unavailable_contexts={}`, and `identity.coherent=true`.
  - Popup is explicitly measured: `contexts.popup.measured=true`, availability `status=measured`, `open_method=window.open_about_blank`, `cdp_runtime_evaluate_user_gesture=true`, with coherent language/platform/timezone/viewport/screen/DPR/UA-major fields.
  - WebRTC policy is `default_public_interface_only`; candidate classes are redacted and include `mdns_host` only, with no private/local literal class reported. P4 public-detector context remains the cited source for public/default-interface IP and public srflx visibility.
  - Rendering still reports `webgl_blocked`; this is an environment limitation, not a consumer-GPU pass.
- Fresh artifact hygiene evidence:
  - Internal sanitized bundle: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized/`; strict scan report `hygiene-scan-report.json`; findings `[]`; `public_share_safe=false` by design.
  - Public-redacted bundle: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted/`; strict scan report `public-redaction-scan-report.json`; findings `[]`; `public_share_safe=true`; whitelist-only files `PUBLIC-REDACTED-MANIFEST.json`, `public-summary.json`, `public-summary.md`, and `public-redaction-scan-report.json`.
- Gate summary from `t_a9deff55`: Python fingerprint-script tests 10 passed, cargo fmt passed, cargo clippy passed with `-D warnings`, cargo test passed, ignored live Chrome smoke passed, and coverage gate passed with TOTAL line coverage 98.00% under active `--fail-under-lines 97`.
- Accepted-by-design WebRTC/IP wording: browser-runtime's `default_public_interface_only` policy is intended to prevent private/local IP exposure. It does not hide the public egress/default-interface IP. Public detectors may still show mDNS `.local` host candidates and public srflx candidates; this is accepted when fresh evidence shows no RFC1918, ULA, link-local, or other private/local IP addresses are exposed.
- External capability limit: CreepJS headless/stealth percentages are public-detector proxy evidence, not a product pass/fail target. In the no-display/Xvfb/SwiftShader worker environment, headless-like or WebGL-blocked findings may remain. Proving consumer-GPU behavior requires a separate headed consumer-GPU benchmark host; the project must not fake GPU/WebGL claims or chase detector-specific stealth scores.
- WebGL/GPU limit: WebGL/GPU unavailable in the worker environment is a documented environment limitation, not a silent browser-runtime pass. Consumer GPU renderer coherence remains unproven until separately benchmarked on a real headed GPU-capable host.
- Artifact-sharing policy: strict artifact hygiene means no secrets, capability URLs, or private paths were found. It does not automatically mean a bundle is safe for public sharing because detector page text/screenshots/JSON can still contain public IPs and stable fingerprint evidence. Internal sanitized bundles stay private; only public-redacted bundles or explicitly reviewed/approved excerpts may be shared externally.
- Popup evidence policy: P5 direct probe evidence must explicitly report popup context status. Final sign-off should cite a fresh artifact where popup is measured with coherent identity fields, or block/defer with a structured environmental reason instead of relying on an ambiguous `popup.measured=false`.
- Prohibited claims remain prohibited: network/IP reputation, account history, TLS/JA3/JA4, HTTP/2 fingerprinting, rate-limit systems, and site risk models are outside browser-runtime browser-flag scope and are not claimed as solved. P5 must not be used as evidence that CAPTCHA/OAuth/OTP/MFA/passkeys/3DS/payment/access-control/anti-abuse systems are handled automatically.

## HBR-P4-S1 docs alignment note

Documentation task: `t_27ed75e9`.
Benchmark task: `t_4d947ff6`.

Canonical docs now need to preserve these P4-S1 reviewer assumptions:

- P4-S1 is a fingerprint-hygiene coherence follow-up, not an undetectability or protected-workflow automation feature.
- Persona coherence now includes normalized `hardware_concurrency`, `device_memory_gb`, `max_touch_points`, `visualViewport`, and common dimension/resolution `matchMedia` surfaces.
- Server-level persona defaults are documented through `HBR_DEFAULT_LOCALE`, `HBR_DEFAULT_ACCEPT_LANGUAGE`, `HBR_DEFAULT_TIMEZONE_ID`, `HBR_DEFAULT_PLATFORM`, `HBR_DEFAULT_HARDWARE_CONCURRENCY`, `HBR_DEFAULT_DEVICE_MEMORY_GB`, and `HBR_DEFAULT_MAX_TOUCH_POINTS`.
- CDP target handling must stay target-type aware: page-like targets can receive full page persona setup; worker-like targets receive worker-safe `Runtime.evaluate` navigator overrides and must not receive unsupported `Page.*` commands.
- Public-detector harnesses are source-controlled as `browser-runtime/scripts/public_detector_capture.py` and `browser-runtime/scripts/public_detector_compare.py`. Public detector output remains proxy evidence only.
- Current P4-S1 public-detector evidence is `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z/`; before and after both report attempted `12`, captured `12`, nonblank `12`.
- Current comparison: CreepJS unchanged, Sannysoft unchanged, Pixelscan unchanged, BrowserLeaks marked regressed due detector-list mismatch (`browserleaks-javascript` present in baseline, `fpscanner` new after). Do not describe the BrowserLeaks group as an apples-to-apples product regression or pass until the harness is aligned and rerun.
- Raw detector artifacts, runtime profile state, raw screenshots/page text, CDP/takeover URLs, public IP literals, cookies/auth markers, private paths, and stable fingerprint evidence must not be copied into public docs or handoffs. Use public-redacted bundles or reviewer-approved excerpts only.
- Residual-risk runbook: `browser-runtime/docs/fingerprint-hygiene-residual-risk-runbook.md`.
