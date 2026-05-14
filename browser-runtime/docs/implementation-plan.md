# browser-runtime implementation plan

## Coverage exception register

### HBR-P1-COV-D1B4: backend.rs generic/async launch helper

- Source file: `browser-runtime/src/backend.rs`
- Helper: `launch_with_port_allocator_and_poll`
- Approved exception: llvm-cov still reports `backend.rs` at 99.40% lines (829/834) because generic/async instantiation rows are charged as misses even though the non-instantiation backend-only show view has zero zero-count source lines.
- Historical charged lines from the evidence artifact: `178`, `179`, `180`, `195`, `198`
  - create user data dir
  - create downloads dir
  - allocate port
  - spawn Chrome
  - first `poll_process` readiness check
- Existing deterministic tests already cover the source success/error flow for those operations:
  - `launch_with_retries_until_cdp_ready_and_returns_browser_info`
  - `launch_with_reports_user_data_dir_creation_error`
  - `launch_with_reports_downloads_dir_creation_error`
  - `launch_with_reports_port_allocation_error`
  - `launch_with_reports_spawn_error`
  - `launch_with_reports_poll_error`
  - `launch_reports_child_exit_before_cdp_ready`
  - `launch_with_times_out_and_kills_hanging_process`
  - `launch_with_returns_browser_even_when_open_blank_page_fails`
- Evidence artifacts:
  - `browser-runtime/target/d1b3_backend_evidence.txt`
  - `browser-runtime/target/d1b3_backend_only_show.txt`
  - `browser-runtime/target/d1b3_backend_only_show_inst.txt`
- Reviewer note: helper-only instantiation artifacts can also appear at historical `backend.rs` lines `265` and `288`; do not chase them with more tests unless the non-instantiation show view regresses.

## HBR-v0B agentic browser safety foundation

### Current status after v0B implementation and docs alignment

- The operator/developer runbook is `browser-runtime/docs/hbr-agentic-browser-safe-foundation.md`. Keep README concise and link there for the full status matrix and operator commands.
- HBR v0B now exposes authenticated CAPTCHA/checkpoint report/resolve through HTTP and CLI, an HTTP solve-status/provider-connector foundation that is disabled by default and gate-controlled, a local `/inspector` page/API, read-only or interactive live links for paused sessions, and the session-scoped credential fill API/CLI.
- Credential broker modes are explicit: `disabled`, `fake_status_only`, `mock`, and `onepassword_cli`; default is `disabled`. Policy stays private, alias-based, exact-origin checked, operator-approval-gated, field-scoped, and fill-only.
- Sanitized mock smoke is green for request -> approval -> filled status, CAPTCHA report/resolve, auth checks, inspector HTML/API, screenshot privacy guard, guard clear, wait while paused, and release. A post-fix no-secret mock Son of a Tailor proof is green for the email-field fill path.
- Fresh post-fix real 1Password smoke is blocked/untested. Historical real evidence reached username-only `requires_user_approval`, detected login fields, and found local `op`, but username-only approved fill ended `failed` before the backend fix and no password ref was configured. Treat this as historical status and an operator evidence gap, not production readiness.
- Deferred / gated: fresh operator-approved real 1Password smoke with sanitized evidence and reviewer sign-off, controlled real CAPTCHA-provider smoke with approved keys/sanitized evidence/reviewer sign-off, better inspector affordance for pending credential approval, signed public/tailnet broker, and recording retention.

### Runtime truth that docs/review must preserve

- CAPTCHA/checkpoint work is safe handling first. The default per-session `captcha_policy` is `human_only`; reported `human_required` checkpoints pause the session for takeover and audit state through authenticated HTTP/CLI and store surfaces. The `auto_solve` path is explicit opt-in and still requires the solver kill switch, provider-key availability, and budget gates; missing gates fail closed to redacted status plus human takeover. This is not evasion or protected-flow automation, and real-provider readiness is not claimed until downstream smoke/review passes.
- `CaptchaStatus` is an audit/state-machine surface for `none`, `suspected`, `human_required`, `in_progress`, `resolved`, `failed`, and `dismissed`. Resolution records a manual outcome; it does not imply the runtime solved a challenge.
- Credential/autofill has a fill-only broker with session-scoped HTTP/CLI commands and CDP fill execution: provider mode defaults to disabled, `onepassword_cli` is explicit-only, private policy uses safe aliases plus exact normalized origins, responses require operator approval, approval/denial notes are redacted, field safety/origin are revalidated before provider read and browser fill, provider reads are scoped to requested/approved fields, and audit events are redacted. No raw passwords, OTPs, 1Password item contents, provider tokens, label material, provider references, or field values are returned to the agent or persisted logs. Mock smoke and mock after-fix proof are green; fresh real-provider smoke is blocked/untested until an operator provisions/unlocks a safe test item/vault, sets private provider/operator config, runs the documented real-smoke harness, sanitizes evidence, and gets reviewer sign-off.
- Redaction covers credential labels/hints, 1Password/op URI markers, vault/item IDs, OTP/TOTP/passcode/API-key markers, takeover tokens, CDP websocket capabilities, auth headers, cookies, card/form/body payloads, and pause/checkpoint reasons.
- Hyperbrowser-style roadmap items remain source-backed design inputs only. Do not turn them into claims that this local runtime has production challenge solving, public remote browser infrastructure, or production-ready managed credential injection.

### Exit criteria for later slices

- Any public/real 1Password integration beyond the current safe broker core must stay approval-gated, fill-only/no-read from the agent perspective, use a dedicated test item/service account for smoke tests, and be independently reviewed before it is described as ready for real pages.
- Any external/mobile remote browser handoff must preserve the token/TTL/private-transport contract and keep takeover URLs out of shared logs.
- Any CAPTCHA/checkpoint documentation must lead with `pause`, `manual checkpoint`, `human handling`, `fail-closed`, and `fallback` language; describe provider-backed solving only as a disabled-by-default gated connector foundation until controlled real-provider smoke and review pass. Avoid evasion or protected-flow automation claims.

## Remote/mobile takeover + payment approval contract

### Current runtime truth that docs must preserve

- Default bind remains local/private: `127.0.0.1:7788` from `browser-runtime/src/config.rs`.
- `pause_for_human()` rotates a random takeover token, stores `takeover_expires_at = now + takeover_ttl`, and emits a localhost takeover URL with the path shape `/takeover/<id>?token=<redacted>`.
- `validate_takeover_token()` only accepts a paused session with a non-empty matching token whose TTL has not expired.
- `release()` clears the token and `takeover_url` immediately, so release/return-control invalidates the current human link.
- The runtime also supports optional API-wide bearer auth via `HBR_BEARER_TOKEN`, but that is separate from the per-pause takeover token. Docs must not imply that takeover URLs are safe to paste around just because API bearer auth exists.
- Current localhost takeover links are TTL-scoped and rotated on every pause. They are not first-class signed HTTPS links and they are not strict single-click one-time URLs today.

### Mobile/off-LAN access contract

- Preserve `127.0.0.1` as the documented default bind. Do not document a public bind as the normal operator path.
- Remote/mobile takeover is allowed only through a private transport layer:
  - tailnet-only Tailscale Serve (or equivalent tailnet-only HTTPS proxy) in front of the localhost runtime,
  - an SSH tunnel/local port-forward that preserves the localhost workflow on the operator device, or
  - a future signed one-time HTTPS takeover URL with bearer auth plus explicit TTL/expiry.
- The first-class signed one-time HTTPS takeover URL is deferred/not yet implemented in `browser-runtime` today. Reviewers should expect current runtime behavior to stay localhost-generated until a separate remote handoff layer exists.
- Any remote/mobile handoff must stay phone-usable: normal phone browser, screenshot/action controls, explicit release/return-control guidance, and no dependence on a desktop-only localhost/LAN assumption.
- When a transport layer rewrites the host/origin (for example Tailscale Serve), the sensitive part is still the `/takeover/<id>?token=...` path/query. That bearer secret must not be copied into shared logs, chat, tickets, or screenshots.

### Human-only checkpoints and payment/order approval gate

- The agent may browse, reuse already-authorized sessions, add to cart, fill checkout, and prepare a payment/order.
- Before the final `pay` / `place order` / `submit purchase` action, automation must pause and wait for explicit Telegram approval.
- The approval request must summarize at least: merchant/domain, items, total amount/currency, shipping summary, and payment-method label before the run is released.
- No explicit approval means no final submission.
- hCaptcha, OAuth consent, OTP/MFA, 3DS, card entry, bank challenges, and similar manual-only steps remain human-only. Docs must make no automated-solving claim for those flows.
- If full remote takeover is unavailable, the fallback is Telegram approval/control plus a local/headful/manual completion path; that fallback still does not permit automatic final payment submission.

### Logging/privacy contract

- Event and audit logs must stay redacted.
- Never log or paste takeover URLs, query tokens, bearer tokens, cookies, auth headers, passwords, OTPs, card data, raw form bodies, or request bodies.
- Pause reasons must remain generic and redacted (`manual oauth approval`, `payment approval required`, `3DS challenge`) instead of embedding secrets.
- Docs should state that redaction protects the local runtime logs; it is not a claim that destination websites never receive the human-entered secret.

### Docs/review acceptance criteria for this contract

- `browser-runtime/docs/implementation-plan.md` and `browser-runtime/README.md` must both mention the remote/mobile takeover and payment-approval contract, not just local pause/release basics.
- README must stay truthful to current runtime behavior: localhost-generated takeover URLs, TTL-scoped per-pause tokens, immediate invalidation on release/expiry, and no claim of secret-safe public sharing.
- README must document only the approved phone/off-LAN access patterns: tailnet-only Tailscale Serve, SSH tunnel/local forward, or a clearly marked deferred signed HTTPS handoff.
- README and review docs must keep the Telegram approval gate explicit and keep the manual-only CAPTCHA/OAuth/3DS language explicit.

## BOT-02: fingerprint hygiene rollout for local Browser Runtime

### Problem statement grounded in BOT-01

- Grounding artifact: `$HOME/.hermes/browser-bot-benchmark/latest-report.md` (2026-05-11 local rerun used as the surviving BOT-01 handoff snapshot).
- BOT-01 showed that plain headless local Chrome is immediately visible (`HeadlessChrome` UA/client hints, worst CreepJS scores) and should not be treated as the normal path for sensitive browsing.
- Headed Chrome via Xvfb removes the obvious headless UA signal, but still fails Sannysoft `WebDriver present`, still looks partially headless to CreepJS, still exposes SwiftShader, and still leaks WebRTC host/public-IP signals.
- Our current stealth-lite experiments only improved top-level local evals; detector pages still see webdriver/native getter evidence, which means the remaining gap is mostly in runtime launch/profile behavior and cross-realm patch coverage, not only in IP reputation.
- Therefore BOT-02 is a runtime-hardening plan for legitimate browsing, approvals, and human takeover reliability. It is not a claim that CAPTCHA, OAuth consent, OTP/MFA, 3DS, or other manual challenge flows are handled automatically.

### Safe framing

- Goal: reduce false-positive bot flags for legitimate browsing sessions, especially when an agent prepares work and a human takes over to approve or finish it.
- Goal: make local Chrome defaults less synthetic and more region-coherent before we spend effort on external proxy/network changes.
- Goal: keep logging and operator ergonomics safe while we add more benchmark and detector coverage.
- Non-goal: illicit challenge automation, stealth scraping claims, or guarantees that a detector-page pass equals real-site success.

### Non-goals and guardrails

- Do not claim automated handling of CAPTCHA, OAuth, OTP/MFA, passkey, 3DS, or payment challenges from this work.
- Do not widen the default trust boundary: keep localhost/private-bind behavior and current human-takeover auth model unless a separate task changes it.
- Do not mix browser-layer hardening with network reputation work in the same slice; residential/mobile egress remains a later validation step after browser/runtime fixes.
- Do not add broad public logging of headers, tokens, profile internals, benchmark dumps, or detector output that could contain secrets or session identifiers.
- Do not add a full Xvfb/window-manager supervisor inside `browser-runtime`; lightweight `xvfb-run` wrapping is acceptable when already installed, and otherwise the host wrapper/service should provide a usable headed display when this plan chooses headed mode.
- Do not attempt a "spoof everything" surface area explosion. Prioritize coherent defaults and the highest-signal leaks first.

### Rollout order

#### Slice 1: headed defaults, warmed profiles, coherence, and redaction

Scope:
- Prefer headed local Chrome for sensitive/local browsing when a local display or managed Xvfb is available; keep explicit headless opt-in instead of treating headless as the normal production path.
- Reuse persistent warmed profiles by default where the runtime already supports them, and seed non-persistent sessions from a warmed profile instead of from a sterile browser state when a profile exists.
- Make locale/timezone/client-hints/window metrics coherent before first navigation.
- Keep trace/event output redacted while new persona/coherence instrumentation is added.

Required exits for Slice 1:
- Local/internal echo checks prove coherence across the top-level page, at least one iframe probe, and a dedicated worker for `Accept-Language`, `navigator.language`, `navigator.languages`, worker locale, `Intl.DateTimeFormat().resolvedOptions().timeZone`, `Sec-CH-UA*`, and viewport/window/screen metrics.
- Headed benchmark rerun removes `HeadlessChrome` from UA/client hints everywhere we measure.
- Manual human-takeover smoke still works in headed mode and logs remain redacted.
- README stays untouched until behavior actually changes; once a default flips, README must document it in the same implementation task.

Current Slice 1-B status:
- Deterministic unit coverage now asserts that persona application keeps `Accept-Language`, locale, timezone, UA/client hints, viewport, screen metrics, and DPR coherent before navigation, and that no `HeadlessChrome` brand leaks into generated UA metadata.
- Runtime persona UA generation sanitizes explicit or browser-reported headless UA values and derives the default UA OS token from the configured persona platform when no explicit UA is supplied.
- Artifact hygiene now recursively redacts event payloads and persists paused takeover URLs and live CDP websocket URLs as `[REDACTED]`; takeover tokens, CDP websocket capabilities, cookies/auth headers, request bodies, card-like payloads, and raw fingerprint dumps should not be retained in `events.jsonl` or `session.json`. `scripts/artifact_hygiene_scan.py` creates text-only sanitized evidence bundles and fails strict scans when private profile paths, takeover tokens, or CDP websocket URLs remain.
- External detector gaps are not hidden by this slice: webdriver/cross-realm cleanup remains Slice 2, and WebRTC/IP/GPU/display signals remain Slice 3 residuals. Detector pages are evidence, not an undetectability guarantee.

#### Slice 2: webdriver / automation leakage cleanup across realms

Scope:
- Clean up automation markers before page JS runs, not only in top-level `page.evaluate` style probes.
- Add early-init and target-attach coverage for main frame, same-origin iframe, about:blank popup, and worker contexts.
- Verify raw descriptor/getter output, not just truthy/falsey checks, so detector pages do not still see native webdriver getters after local eval appears clean.

Required exits for Slice 2:
- Local realm harness passes for main frame, same-origin iframe, about:blank popup, and dedicated worker at minimum.
- Sannysoft no longer reports `WebDriver present` on the headed path.
- CreepJS improves materially versus the current BOT-01 headed baseline, even if it does not become perfect.
- Manual smoke confirms pause/release/takeover controls still work after cross-realm patching.

Current Slice 2-A status:
- `cdp.rs` now installs an early persona init script that removes known Selenium/WebDriver/CDP automation globals by exact name and prefix (`cdc_`, `wdc_`, `__webdriver*`, `__selenium*`, `__driver*`, `__fxdriver*`) from each window realm it touches.
- Cleanup runs immediately, again via microtask/timer/load/DOMContentLoaded scheduling, and when `window.open` returns an accessible about:blank popup, so late page-created marker globals are removed before normal detector readout without changing the private/local runtime boundary.
- Deterministic unit coverage asserts that the init script still preserves persona language/platform/screen overrides while carrying the automation-global cleanup denylist and scheduling logic.
- Local headed smoke after Slice 2-A confirmed injected marker globals are absent after page load; Sannysoft still passes webdriver checks on the headed path, while CreepJS remains partially headless-looking, so CreepJS/WebGL/WebRTC/display residuals remain open for later Slice 2/3 work.

#### Slice 3: explicit WebRTC / IP / GPU policy

Scope:
- Convert WebRTC, IP exposure, and GPU behavior from accidental side effects into an explicit operator policy.
- Default policy should minimize local host-candidate leakage for sensitive browsing, with an explicit compatibility opt-in for sites that genuinely require WebRTC/camera/mic flows.
- GPU/display behavior must be documented honestly: prefer real display/GPU when available; if the stack falls back to Xvfb/SwiftShader, keep that as a declared residual risk rather than pretending it is consumer-realistic.

Required exits for Slice 3:
- BrowserLeaks WebRTC default path no longer exposes local host candidates unless an explicit compatibility mode is enabled.
- BrowserLeaks WebGL / graphics checks reflect the chosen policy and are documented with any remaining SwiftShader/virtual-display caveats.
- A compatibility smoke exists for sites/features that require WebRTC after the explicit opt-in path is enabled.

Current Slice 3/P3 status:
- `models.rs` defines explicit policy enums with snake_case wire values: `WebRtcIpPolicy::{default_public_interface_only, default_public_and_private_interfaces, disable_non_proxied_udp}` and `GpuPolicy::{auto, swiftshader_compat, disable_3d}`.
- `config.rs` exposes global server/client defaults through `HBR_WEBRTC_IP_POLICY`, `HBR_GPU_POLICY`, `--webrtc-ip-policy`, and `--gpu-policy`. `store.rs` applies per-session request overrides first, then server defaults, and records the chosen policies in `SessionInfo` and the redacted `session_created` event payload.
- `backend.rs` always passes `--force-webrtc-ip-handling-policy=<policy>` to Chrome. The default is `default_public_interface_only`, which hides local/private host-candidate IP literals but still allows the public/default-interface address to appear by design.
- GPU default is `auto`: the headed default path does not request SwiftShader and does not add `--disable-3d-apis`. `swiftshader_compat` explicitly adds ANGLE/SwiftShader flags; `disable_3d` explicitly adds `--disable-3d-apis`. Headless mode remains a compatibility fallback and may still carry headless-specific GPU flags.
- Reviewed BrowserLeaks evidence: `browser-runtime/artifacts/bot02-p3-evidence/run-20260511T212756Z`. Default WebRTC evidence showed no local/private IP literals and did show the public default-interface IPv4 address. Default WebGL evidence was environment-limited: on this no-display worker, runtime used Xvfb and BrowserLeaks reported WebGL unavailable, with no evidence of a forced SwiftShader renderer leak.
- Compatibility note: sites that genuinely require fuller WebRTC/camera/mic behavior must opt into `default_public_and_private_interfaces` intentionally and should be smoke-tested separately. `disable_non_proxied_udp` is stricter and can break legitimate WebRTC flows.
- Safety note: detector pages remain proxy evidence only. This slice does not claim automated handling of CAPTCHA, OAuth, OTP/MFA, passkey, 3DS, bank-challenge, or payment flows.

#### Slice 4: P4A browser identity coherence and deterministic probe

Scope:
- Make browser identity resolution explicit and version-coherent so launch-level UA, CDP `Network.setUserAgentOverride`, UA-CH/high-entropy metadata, and JS-observable persona agree on Chrome major/full version and platform.
- Add source-controlled sanitized probe/compare helpers so future detector work can distinguish local deterministic evidence from public-detector evidence.
- Keep the work bounded to legitimate fingerprint hygiene and detector benchmarking; do not add proxy/IP rotation, challenge automation, or site-specific evasion playbooks.

Current P4A status:
- `models.rs` now exposes a shared resolved browser identity path used by UA and client-hint surfaces, including `HeadlessChrome` sanitization and platform/Chrome-version alignment.
- `backend.rs` derives the selected Chrome version for the launch UA when available and avoids silently reusing the stale Chrome/125 fallback for the measured Chrome/147 runtime.
- `cdp.rs` consumes the same resolved identity for UA-CH metadata while preserving locale/timezone/device metrics and the existing webdriver/global-marker cleanup invariants.
- `browser-runtime/scripts/fingerprint_probe.py` writes sanitized `hbr.p4.fingerprint_probe.v1` JSON in `--mode local-deterministic`; `fingerprint_compare.py` writes markdown/JSON risk deltas from sanitized probe JSON.
- Independent P4A implementation review approved the slice: fmt, clippy, Rust tests, Python fingerprint-script tests, coverage gate, ignored Chrome smokes, and strict artifact hygiene all passed; reviewed line coverage was 98.00% against the >=97% hard gate.
- Post-P4 public-detector benchmark evidence is `browser-runtime/artifacts/hbr-p4-bench/run-20260511T235056Z-sanitized`: 7/7 detector pages collected, strict sanitizer scanned 21 text files with 0 findings and 0 private-path findings, and UA/UA-CH major version coherence improved from mixed Chrome 125/Chromium 147 evidence to consistent Chrome/Chromium/Google Chrome 147 evidence.
- Residuals after P4 were explicit: public/default-interface IP visible by design, CreepJS mDNS `.local` plus public srflx candidates and 44% like headless / 33% headless / 0% stealth, WebGL/GPU blocked/unavailable in the no-display/Xvfb worker environment, and direct-probe `popup.measured=false` in the public benchmark run.

#### Slice 5: P5 residual closure classification, popup evidence, and public-redacted artifacts

Scope:
- Close only the safe fix-now residuals from the PM classification: direct-probe popup evidence ambiguity and public-share artifact redaction.
- Document accepted-by-design and needs-external-capability residuals without turning them into detector-specific evasion work.
- Keep unsafe/out-of-scope surfaces prohibited: automated CAPTCHA/OAuth/OTP/MFA/passkey/3DS/payment/access-control/anti-abuse handling, network/IP reputation, TLS/JA3/JA4, HTTP/2 fingerprinting, rate-limit systems, and site risk models.

Current P5 status:
- PM classification source: `t_c1c66943`. Fix-now residuals were `Direct P4 probe popup.measured=false` and `Sanitized public-detector bundles may include public IP/fingerprint evidence`.
- Fresh verification source: `t_a9deff55`, which preserved the P5 implementation from `t_b2a38d56` and produced evidence under `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/`.
- P5 direct probe artifact: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/fingerprint-probe.json`. It reports `measurement_contract_version=hbr.p5.direct_probe.v1`, `measurement_completeness.complete=true`, `unavailable_contexts={}`, `identity.coherent=true`, and `contexts.popup.measured=true` with popup availability `status=measured`, `open_method=window.open_about_blank`, and `cdp_runtime_evaluate_user_gesture=true`.
- P5 direct probe used `policy.webrtc_ip_policy=default_public_interface_only`; WebRTC candidate classes were redacted and contained `mdns_host` only, with no private/local literal class reported. P4 public-detector evidence remains the source for the public/default-interface IP and public srflx observations.
- P5 rendering evidence still reports `rendering.webgl.available=false`, `renderer_class=blocked`, and red flag `webgl_blocked`; this is an environment limitation, not a pass or consumer-GPU claim.
- Internal sanitized bundle: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized/`, with strict scan report `hygiene-scan-report.json`; findings `[]`, `public_share_safe=false` by design.
- Public-redacted bundle: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted/`, with strict scan report `public-redaction-scan-report.json`; findings `[]`, `public_share_safe=true`, whitelist-only public files.
- Verification gates rerun by `t_a9deff55`: Python fingerprint-script tests 10 passed, cargo fmt passed, cargo clippy passed with `-D warnings`, cargo test passed, ignored live Chrome smoke passed, coverage gate passed with TOTAL line coverage 98.00% and active `--fail-under-lines 97`.

P5 classification outcome:
- Fix-now closed by evidence: popup context status is now unambiguous in the direct probe; internal-vs-public artifact tiers are separated and scanned.
- Accepted-by-design: browser-runtime's `default_public_interface_only` policy is intended to prevent private/local IP exposure. It does not hide the public egress/default-interface IP. Public detectors may still show mDNS `.local` host candidates and public srflx candidates; this is accepted when fresh evidence shows no RFC1918, ULA, link-local, or other private/local IP addresses are exposed.
- Needs external capability: CreepJS headless/stealth percentages are public-detector proxy evidence, not a product pass/fail target. In the no-display/Xvfb/SwiftShader worker environment, headless-like or WebGL-blocked findings may remain. Proving consumer-GPU behavior requires a separate headed consumer-GPU benchmark host; the project must not fake GPU/WebGL claims or chase detector-specific stealth scores.
- Needs external capability: WebGL/GPU unavailable in the worker environment is a documented environment limitation, not a silent browser-runtime pass. Consumer GPU renderer coherence remains unproven until separately benchmarked on a real headed GPU-capable host.
- Unsafe/out-of-scope: Network/IP reputation, account history, TLS/JA3/JA4, HTTP/2 fingerprinting, rate-limit systems, and site risk models are outside browser-runtime browser-flag scope and are not claimed as solved. P5 must not be used as evidence that CAPTCHA/OAuth/OTP/MFA/passkeys/3DS/payment/access-control/anti-abuse systems are handled automatically.

P5 evidence-use rules:
- Strict artifact hygiene means no secrets, capability URLs, or private paths were found. It does not automatically mean a bundle is safe for public sharing: detector page text/screenshots/JSON can still contain public IPs and stable fingerprint evidence. Internal sanitized bundles stay private; only bundles produced by the public-share redaction tier, or explicitly reviewed/approved excerpts, may be shared externally.
- P5 direct probe evidence must explicitly report popup context status. Final sign-off should cite a fresh artifact where popup is measured with coherent identity fields, or block/defer with a structured environmental reason instead of relying on an ambiguous popup.measured=false.

Intentionally deferred after P4/P5:
- first-class signed HTTPS takeover broker; current runtime still emits localhost takeover URLs and relies on SSH/tailnet transport for remote/mobile use;
- real headed display/GPU validation on a host with a consumer-like GPU path;
- network egress/IP reputation, TLS/JA4/JA3/HTTP2 fingerprint, proxy, or residential/mobile network work;
- proof that detector-page improvements transfer to every real merchant/login/anti-abuse stack;
- any automated CAPTCHA, OAuth/OTP/MFA/passkey/3DS/payment/rate-limit/account-abuse, or access-control handling.

#### P4-S1: persona coherence core and public-detector harness follow-up

Scope:
- Close the fingerprint-hygiene coherence gaps that remained after P4/P5 without expanding into detector-specific evasion: navigator hardware/device fields, `visualViewport`, common dimension/resolution `matchMedia`, and target-type-aware page/worker persona application.
- Source-control the public-detector capture/compare harness so ops can collect comparable screenshots, manifests, and redacted comparison summaries.
- Keep public detector evidence explicitly bounded as proxy evidence and keep raw artifacts private-local.

Current P4-S1 status:
- `BrowserPersona` now includes `hardware_concurrency`, `device_memory_gb`, and `max_touch_points`. Defaults are conservative (`8`, `8`, `0`) and normalized to common buckets before being exposed.
- `config.rs` exposes server defaults through `HBR_DEFAULT_LOCALE`, `HBR_DEFAULT_ACCEPT_LANGUAGE`, `HBR_DEFAULT_TIMEZONE_ID`, `HBR_DEFAULT_PLATFORM`, `HBR_DEFAULT_HARDWARE_CONCURRENCY`, `HBR_DEFAULT_DEVICE_MEMORY_GB`, and `HBR_DEFAULT_MAX_TOUCH_POINTS`.
- `cdp.rs` keeps page-like and worker-like target plans separate. Page-like targets get full persona coverage including screen/window/`visualViewport`/`matchMedia` and navigator capability fields. Worker-like targets get a worker-safe `Runtime.evaluate` plan and are not sent unsupported `Page.*` commands; `Runtime.runIfWaitingForDebugger` is guarded by the target's waiting state.
- Public detector helpers are source-controlled: `browser-runtime/scripts/public_detector_capture.py` and `browser-runtime/scripts/public_detector_compare.py`.
- Current P4-S1 public-detector evidence is `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z/`. Before and after runs both report attempted `12`, captured `12`, nonblank `12`.
- Detector comparison from the current run: CreepJS unchanged, Sannysoft unchanged, Pixelscan unchanged, BrowserLeaks marked regressed because the detector list changed (`browserleaks-javascript` present in the baseline, `fpscanner` new in the after run). Treat this as harness comparability work, not a product regression claim.
- P4-S1 residual-risk runbook: `browser-runtime/docs/fingerprint-hygiene-residual-risk-runbook.md`.

### File / seam map after P1/P2/P3/P4/P5/P4-S1

| File | Current seam(s) to keep aligned | Why this seam owns the work |
| --- | --- | --- |
| `browser-runtime/src/config.rs` | `ServerArgs.{headful,headless,webrtc_ip_policy,gpu_policy}`, default persona env vars, `ClientCreateSessionArgs.{persist_profile,headless,headful,webrtc_ip_policy,gpu_policy}`, `RuntimeConfig`, `RuntimeConfig::from_server_args()` | Owns the localhost bind, headed/headless default, takeover TTL, launch timeout, global WebRTC/GPU policy env/flag defaults, and server-level persona defaults. |
| `browser-runtime/src/backend.rs` | `StartSessionOptions`, `launch_with_port_allocator_and_poll()`, `chrome_args()`, Chrome-version derivation | Owns Chrome launch flags: display/headless mode, version-coherent launch UA, `--force-webrtc-ip-handling-policy`, and explicit SwiftShader/disable-3D GPU modes. |
| `browser-runtime/src/store.rs` | `create_session()`, `copy_profile_read_only_seed()`, `pause_for_human()`, `release()`, `append_event()` | Owns persistent warmed-profile reuse, per-session policy override resolution, session info persistence, takeover token rotation/release invalidation, and redacted events. |
| `browser-runtime/src/cdp.rs` | persona init script, first-page/target helpers, UA-CH metadata, screenshot/input helpers, target-type persona plans | Owns locale/timezone/client-hint/screen coherence before navigation, shared resolved-identity application, `visualViewport`/`matchMedia`/navigator capability coherence, page-like vs worker-like CDP command separation, cross-realm automation-marker cleanup, and takeover action execution. |
| `browser-runtime/src/models.rs` | `WebRtcIpPolicy`, `GpuPolicy`, `CreateSessionRequest`, `SessionInfo`, `BrowserPersona`, `ResolvedBrowserIdentity` | Owns public JSON/CLI wire values for policies, browser identity resolution, normalized browser persona capability fields, and the session fields reviewers/users rely on. |
| `browser-runtime/src/api.rs` | `create_session()` pass-through, takeover routes, auth/error handling | Keeps HTTP API behavior minimal/private and preserves generic invalid-token responses without echoing secrets. |
| `browser-runtime/src/client.rs` | `create_session_request()`, `create_session()`, request/response tests | Keeps CLI/client requests in sync with the HTTP wire model, including per-session policy overrides. |
| `browser-runtime/src/cli.rs` | `runtime_app()` trace layer and CLI parse/default assertions | Keeps request tracing path-only and pins CLI defaults/flags so docs and runtime do not drift silently. |
| `browser-runtime/src/security.rs` | redaction markers/helpers/tests | Owns recursive redaction for tokens, auth, form/card/payment/fingerprint payloads, and pause reasons. |
| `browser-runtime/src/test_support.rs` | mock CDP helpers and local echo/detector-style fixtures | Hosts deterministic persona, realm, and policy fixtures without adding public diagnostic routes. |
| `browser-runtime/tests/browser_integration.rs` | headed/profile/manual takeover and ignored live-browser smokes | Owns the local Chrome integration coverage for warmed profiles, persona/policy coherence, popup coherence, and manual takeover behavior. |
| `browser-runtime/tests/cli_binary.rs` | server default assertions, paused takeover serialization, redaction-related output checks | Pins external CLI behavior and secret-safe output expectations. |
| `browser-runtime/scripts/fingerprint_probe.py` | `hbr.p4.fingerprint_probe.v1` schema with P5 `measurement_contract_version=hbr.p5.direct_probe.v1`, `--mode local-deterministic`, strict sanitizer marker checks, explicit context availability | Owns local deterministic direct-probe evidence and must keep capability URLs, raw IPs/hostnames, private paths, cookies/auth/form markers, and raw fingerprint dumps out of shareable JSON. Popup must be measured with coherent identity fields or reported with a structured unavailable reason. |
| `browser-runtime/scripts/fingerprint_compare.py` | sanitized probe before/after comparison, markdown/JSON risk deltas | Owns risk-delta wording and must not turn probe output into an undetectability or public-detector score. |
| `browser-runtime/scripts/public_detector_capture.py` | public detector screenshot/page metadata capture, redacted manifest counts, strict nonblank gate | Owns repeatable public-detector capture as proxy evidence and must keep raw page text/capability data out of public summaries. |
| `browser-runtime/scripts/public_detector_compare.py` | public detector before/after markdown/JSON comparison with redacted labels | Owns detector group verdict wording and must keep coverage deltas visible when detector lists are not apples-to-apples. |
| `browser-runtime/scripts/artifact_hygiene_scan.py` | raw-to-internal-sanitized text bundle creation, `--tier public-redacted`, strict scan reports | Owns the raw/private vs internal-review vs public-share boundary for screenshots, page text, runtime paths, CDP URLs, takeover tokens, profile state, public IPs, and stable fingerprint evidence. |
| `browser-runtime/README.md` | operator-facing runtime contract | Must stay truthful to shipped behavior: localhost/private defaults, explicit policy values, P4/P5/P4-S1 evidence interpretation, persona default env vars, target coverage semantics, TTL/release semantics, approved remote transports, redaction/public-share limits, and human-only payment/login checkpoints. |
| `browser-runtime/docs/fingerprint-hygiene-residual-risk-runbook.md` | residual-risk operating checklist | Must keep detector-evidence limits, artifact tiers, harness comparability caveats, target coverage bounds, and human-only checkpoints visible for reviewers/operators. |

Implementation note:
- Prefer test-only echo/detector helpers under `src/test_support.rs` and `tests/` before adding new production routes. If a temporary internal route becomes unavoidable, it must stay localhost/private and must not survive as a public diagnostic surface without a separate review.

### Test matrix and sign-off gates

| Gate | Owner slice | Automated/manual | Pass condition |
| --- | --- | --- | --- |
| Rust unit + existing CLI tests | all | automated | Existing `config.rs`, `backend.rs`, `store.rs`, `security.rs`, and `cli_binary.rs` coverage stays green after each slice. |
| Local/internal echo page for locale/timezone/client hints | Slice 1 | automated | Headed session reports coherent `Accept-Language`, `navigator.*language*`, worker locale, timezone, client hints, and viewport/window/screen metrics before normal navigation. |
| Warmed-profile persistence smoke | Slice 1 | automated or deterministic integration | A persistent profile retains cookie/local-storage state and a non-persistent session can seed from it without leaking secrets into logs. |
| Manual human-takeover smoke | Slice 1 + Slice 2 | manual | Pause URL still works, screenshot refresh works, click/type/key/scroll work, release invalidates the link, and logs remain redacted. |
| `bot.sannysoft.com` | Slice 2 | manual benchmark rerun | Headed default path no longer shows `WebDriver present`; headed path remains free of `HeadlessChrome` signals. |
| `creepjs` | Slice 2 | manual benchmark rerun | Headed path improves versus BOT-01 on headless/stealth scoring and no longer regresses locale/timezone coherence. |
| BrowserLeaks JS headers / UA client hints pages | Slice 1 | manual benchmark rerun | Headers and UA/client-hint surfaces match the intended locale/persona and no longer expose the obvious headless signature. |
| BrowserLeaks WebRTC page | Slice 3 | manual benchmark rerun | Default policy suppresses local host-candidate leakage; documented compatibility mode restores required functionality when explicitly enabled. |
| BrowserLeaks WebGL / graphics pages | Slice 3 | manual benchmark rerun | Report matches declared GPU/display policy; any SwiftShader or virtual-display residue is captured as a residual risk, not hidden. |
| Shared browser identity / UA-CH coherence | Slice 4 | automated + benchmark | Launch UA, CDP UA override, UA-CH/high-entropy metadata, and JS-observable persona use the same Chrome major/full version and platform; no stale Chrome/125 identity when Chrome 147 is measured. |
| `fingerprint_probe.py --mode local-deterministic --strict` | Slice 4 | automated/local live | Sanitized JSON reports identity coherence and classified WebRTC/rendering signals without usable CDP/takeover URLs, raw IPs/hostnames, private paths, cookies/auth/form/request bodies, or raw fingerprint dumps. |
| `fingerprint_compare.py` | Slice 4 | automated | Before/after sanitized probes produce risk deltas that list improvements, unchanged residuals, regressions, and limits without claiming automated protected-flow handling or undetectability. |
| P4 public detector benchmark | Slice 4 | manual benchmark rerun | Public detector results are collected as proxy evidence only; docs state what improved, what remained detectable, and which raw artifacts stay private. |
| P5 direct probe popup contract | Slice 5 | automated/local live | Fresh direct probe reports `measurement_completeness.complete=true`, every required context measured, `contexts.popup.measured=true`, coherent identity fields, and `unavailable_contexts={}`; otherwise final sign-off blocks with a structured unavailable reason. |
| P5 internal/public artifact tiers | Slice 5 | automated artifact scan | Internal sanitized strict scan has findings `[]` but remains `public_share_safe=false`; public-redacted strict scan has findings `[]`, whitelist-only outputs, and `public_share_safe=true`. |
| P4-S1 persona coherence core | P4-S1 | automated/local live | Page-like targets expose coherent language/platform/timezone/viewport/screen/DPR/`visualViewport`/`matchMedia` plus hardware concurrency, device memory, and max touch points; worker-like targets expose worker-safe navigator fields without unsupported `Page.*` calls. |
| P4-S1 public detector harness | P4-S1 | manual benchmark rerun | Public detector capture reports attempted/captured/nonblank counts, comparison output stays redacted, and any detector-list coverage delta is called out before interpreting group verdicts. |

### Residual risk register

- Detector pages are only proxies. Passing Sannysoft/CreepJS/BrowserLeaks does not guarantee success on real merchants, logins, or anti-abuse stacks.
- P4-S1 public-detector evidence currently has a detector-list delta: baseline includes `browserleaks-javascript`, while the after run adds `fpscanner`. Until a baseline-aligned harness run exists, treat the BrowserLeaks group verdict as a comparability caveat instead of an apples-to-apples product verdict.
- Local-only fixes cannot solve ASN reputation, IP reputation, geo-presence, TLS/JA4/JA3/HTTP2 fingerprints, account history, rate-limit systems, or site-specific risk models. Those remain out of browser-runtime browser-flag scope unless a later safe-review task defines them.
- `default_public_interface_only` is accepted-by-design as local/private host-candidate leak reduction, not an anonymity promise. It is intended to prevent RFC1918, ULA, link-local, and other private/local IP exposure; it does not hide the public egress/default-interface IP.
- Public detectors may still show mDNS `.local` host candidates and public srflx candidates. That remains acceptable only when fresh evidence shows no private/local IP addresses are exposed; P5 direct-probe evidence and P4 public-detector context must be cited honestly.
- CreepJS headless/stealth percentages are public-detector proxy evidence, not a product pass/fail target. They must not become detector-specific evasion goals or universal stealth claims.
- If the host only offers no-display/Xvfb/SwiftShader-like worker capability, some graphics/display signals will remain synthetic even after launch-flag cleanup.
- The current P5 WebGL/GPU evidence is still environment-limited and reports WebGL blocked/unavailable. Validate a real headed consumer-GPU path separately before claiming consumer-like graphics behavior.
- Tight WebRTC leak prevention can break legitimate audio/video/sign-in flows; the compatibility path must be explicit and documented.
- Cross-realm cleanup will likely remain imperfect on some combinations of cross-origin iframe, service-worker, extension, popup, or GPU surfaces. The plan should optimize the highest-signal leaks first rather than promise total invisibility.
- P4-S1 worker-like target handling is intentionally worker-safe, not universal. Service-worker behavior and future CDP target differences can still require fresh evidence or structured `not_measured` wording.
- P5 closes the old direct-probe popup ambiguity only for the cited fresh artifact. Future direct-probe evidence must explicitly report popup context status; if popup is not measured, block/defer with the structured environmental reason rather than treating `popup.measured=false` as a pass.
- Warmed profiles improve realism but also increase state-management risk. Redaction, profile locking, artifact hygiene, and trust-domain isolation must remain stricter than benchmark convenience.
- Raw benchmark screenshots/page text/runtime profile state remain private-local by default. Strict internal hygiene is not public-share approval; only public-redacted bundles or explicitly reviewed/approved excerpts may be shared externally.
- Manual-only checkpoints remain manual-only: this work must not weaken the existing human approval boundary for payment, OAuth, MFA, CAPTCHA-like challenges, passkeys, 3DS, bank challenges, or similar actions.
