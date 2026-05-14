# HBR-P4 fingerprint-hygiene architecture handoff

Task: `t_e581356c`
Date: 2026-05-11
Scope: legitimate fingerprint hygiene and detector benchmarking for Юра's own `browser-runtime` sessions.

This is not an undetectability, challenge-bypass, payment-bypass, rate-limit-bypass, or account-abuse plan. Public detector results are evidence only; they do not prove real-site success.

## Decision

Implement P4A as a narrow identity-coherence and evidence-harness slice:

1. Make browser identity resolution explicit and version-coherent so the launch-level UA, CDP `Network.setUserAgentOverride`, UA-CH/high-entropy metadata, and JS-observable persona agree on Chrome major/full version and platform.
2. Add a source-controlled deterministic fingerprint probe that emits sanitized, comparable JSON across top page, iframe, worker, and popup contexts, plus WebRTC candidate classes and rendering availability classes.
3. Produce redacted before/after evidence and risk deltas before any further public-detector or real-site pilot claim.

Why this design:
- BOT-02-R1 was `needs_changes` / no-go; the measured blocker most suitable for a bounded code slice was UA vs UA-CH version incoherence, while CreepJS/WebGL/network reputation residuals need measurement and environment-specific evidence.
- The artifact-hygiene blocker is now independently approved by `t_c8b56233`, so P4 can build on the sanitized/private evidence boundary instead of redoing that remediation.
- Browser-level identity coherence and deterministic local probes are safer than detector-specific JS stealth patches or network/IP work.

## Post-implementation / benchmark status

Current status after implementation review and the P4 benchmark:

- P4A implementation was independently approved by `t_fb3543e1`: fmt, clippy, Rust tests, Python fingerprint-script tests, coverage gate, ignored Chrome smokes, and strict artifact hygiene passed; reviewed line coverage was 98.00% against the >=97% hard gate.
- `browser-runtime/scripts/fingerprint_probe.py` and `fingerprint_compare.py` are now source-controlled. The probe's supported mode is `local-deterministic`; it emits sanitized `hbr.p4.fingerprint_probe.v1` JSON, not raw fingerprint dumps or public-detector proof.
- P4 public-detector benchmark evidence is `browser-runtime/artifacts/hbr-p4-bench/run-20260511T235056Z-sanitized`. Public detector collection was 7/7 OK, strict hygiene scanned 21 text files with 0 findings and 0 private-path findings, and UA/UA-CH coherence improved from mixed Chrome 125/Chromium 147 evidence to consistent Chrome/Chromium/Google Chrome 147 evidence.
- Remaining detectable/residual surfaces are expected and must stay documented: public/default-interface IP by design, CreepJS mDNS `.local` plus public srflx candidates, CreepJS 44% like headless / 33% headless / 0% stealth, WebGL/GPU blocked in the no-display/Xvfb worker environment, and no consumer-GPU proof.
- The benchmark direct probe had `popup.measured=false`; popup coherence comes from the parent ignored headed Chrome smoke, not from that direct probe artifact.
- No CAPTCHA, OAuth/OTP/MFA/passkey/3DS/payment, rate-limit, account-abuse, network/IP reputation, TLS/JA4/JA3/HTTP2, or access-control bypass is implemented, measured, or claimed.

Post-P5 residual-closure update:
- P5 doc: `browser-runtime/docs/p5-residual-closure.md`.
- Fresh P5 direct probe: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/fingerprint-probe.json`.
- P5 closes the P4 popup evidence ambiguity for that fresh artifact: `measurement_completeness.complete=true`, `unavailable_contexts={}`, `identity.coherent=true`, and `contexts.popup.measured=true` with coherent identity fields.
- P5 also separates internal-sanitized evidence from the public-redacted sharing tier: `run-20260512T083850Z-internal-sanitized/` remains internal-only, while `run-20260512T083850Z-public-redacted/` is the reviewed public-share tier.
- The P5 closure does not change the accepted/external residuals above: public/default-interface IP and mDNS/public srflx visibility remain accepted-by-design when no private/local IPs are exposed; CreepJS headless/stealth score and consumer-GPU/WebGL behavior still need a separate headed consumer-GPU benchmark host; network/TLS/reputation and protected-workflow bypass claims remain out of scope.

Post-P4-S1 follow-up update:
- P4-S1 extends P4/P5 coherence with browser-capability persona fields (`hardware_concurrency`, `device_memory_gb`, `max_touch_points`), `visualViewport`, common dimension/resolution `matchMedia`, and target-type-aware page/worker CDP plans.
- Server defaults for persona fields are exposed through `HBR_DEFAULT_LOCALE`, `HBR_DEFAULT_ACCEPT_LANGUAGE`, `HBR_DEFAULT_TIMEZONE_ID`, `HBR_DEFAULT_PLATFORM`, `HBR_DEFAULT_HARDWARE_CONCURRENCY`, `HBR_DEFAULT_DEVICE_MEMORY_GB`, and `HBR_DEFAULT_MAX_TOUCH_POINTS`.
- Source-controlled public-detector harness scripts now exist: `browser-runtime/scripts/public_detector_capture.py` and `browser-runtime/scripts/public_detector_compare.py`.
- Current P4-S1 public-detector evidence is `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z/`; both baseline and after runs report attempted `12`, captured `12`, nonblank `12`.
- Current comparison: CreepJS unchanged, Sannysoft unchanged, Pixelscan unchanged, BrowserLeaks marked regressed because the after detector set is not apples-to-apples with the baseline (`browserleaks-javascript` was present before; `fpscanner` is new after). Treat this as a harness comparability caveat until a baseline-aligned rerun exists.
- Canonical runbook: `browser-runtime/docs/fingerprint-hygiene-residual-risk-runbook.md`.

## Assumptions and tradeoffs

Assumptions:
- Canonical repo/workspace is `$HOME/.hermes/hermes-agent`, crate path `browser-runtime/`.
- Existing P1/P2/P3 invariants remain active: private localhost bind, redaction, takeover token rotation/release/expiry, human-only OAuth/MFA/3DS/payment checkpoints, WebRTC local/private literal hiding by default, warmed profile persistence, and coverage hard gate >=97%.
- Current public-detector baseline is BOT-02-R1: `browser-runtime/artifacts/bot02-r1-benchmark/run-20260511T214630Z-sanitized/signoff-report.md`; raw sibling artifacts remain private-local only.
- Chrome version can normally be obtained from CDP `Browser.getVersion`; for launch-time UA generation the implementer may either derive from the Chrome binary version or delay UA override until CDP is ready, but must not silently rely on a stale hard-coded Chrome/125 identity when actual Chrome differs.

Tradeoffs:
- Keeping a launch-level `--user-agent` avoids early `HeadlessChrome` exposure before CDP is ready, but can become stale unless it is derived from the actual Chrome binary. Delaying UA override until CDP gives exact version but relies on no external navigation before persona guard is installed.
- A deterministic local probe is reproducible and safe to gate, but is weaker external evidence than public detectors. Public detectors stay a later evidence tier, not a product guarantee.
- Real headed GPU validation is more consumer-like but may not be available in the shared worker/Xvfb environment. CI/Xvfb evidence must be labeled as reproducible but environment-limited.
- Persistent profiles reduce first-run anomalies but increase correlation risk; isolate by trust domain and never fabricate aged identities/cookies/history.

## Scope boundaries

In scope for P4A:
- Browser identity/version coherence across UA, UA-CH, `navigator.userAgentData`, headers, platform, locale, timezone, screen/viewport/DPR.
- Cross-context consistency evidence for top page, same-origin iframe, popup, dedicated worker, and fresh CDP targets when supported safely.
- WebRTC evidence as candidate classes only: e.g. `mdns_host`, `public_srflx`, `private_literal`, `relay`, `none`, with raw IPs/hostnames redacted.
- Rendering evidence as availability/classes: WebGL/WebGPU present/blocked, software-vs-hardware-like class, SwiftShader mention count/class; no raw fingerprint dumps in shareable artifacts.
- Sanitized local benchmark/probe artifacts and risk-delta reporting.

Out of scope/deferred:
- CAPTCHA/Turnstile/hCaptcha/reCAPTCHA solving or bypass.
- OAuth, passkey, OTP/MFA, 3DS, bank challenge, payment, checkout, or final order approval automation/bypass.
- Rate-limit, ban, access-control, scraping-abuse, account-farming, proxy/IP rotation, or TLS/JA4 manipulation as evasion.
- Claims of being undetectable on every site.
- Fake aged identities, seeded/stolen cookies, synthetic browsing history, broad random fingerprint rotation, or site-specific evasion playbooks.
- Consumer-like WebGL claims until tested on a real headed GPU/display stack.

## Architecture

### Components affected

1. `browser-runtime/src/models.rs`
   - Owns `BrowserPersona`, `Viewport`, `WebRtcIpPolicy`, `GpuPolicy`, and UA construction helpers.
   - Add/clarify a single browser-identity resolver used by both launch and CDP paths. Suggested shape: an internal `ResolvedBrowserIdentity`/helper containing `user_agent`, `chrome_full_version`, `chrome_major_version`, `client_hint_platform`, `architecture`, `bitness`, `mobile=false`, and `formFactors=["Desktop"]`.
   - Preserve explicit `persona.user_agent` override support, but sanitize `HeadlessChrome/` to `Chrome/` and validate that user-supplied UA/platform combinations are not internally contradictory enough to create obvious mismatches.

2. `browser-runtime/src/backend.rs`
   - Owns Chrome launch args and display/GPU/WebRTC policy flags.
   - Replace the current stale fallback launch identity behavior with a version-coherent path:
     - Preferred: derive Chrome full version before launch from the selected Chrome binary (`chrome --version` style parsing) and pass that into `BrowserPersona::resolved_user_agent(...)` for `--user-agent`.
     - Acceptable fallback: if version derivation fails, omit the launch UA override until CDP persona guard applies, or keep existing fallback only while marking a probe warning; do not report it as coherent.
   - Keep `--disable-blink-features=AutomationControlled`, WebRTC policy, GPU policy, viewport, language, and download dir behavior stable.
   - Do not add proxy or network-reputation flags.

3. `browser-runtime/src/cdp.rs`
   - Owns persona application, UA-CH metadata, target guard, and init script.
   - Ensure `user_agent_metadata(...)` consumes the same resolved identity as launch UA; no independent Chrome/125 fallback when the actual browser version is known.
   - Preserve `Target.setAutoAttach` guard for fresh page targets.
   - Do not blindly send `Page.*` commands to workers/service workers; if expanding non-page coverage, split command plans by target type and only send domains supported by that target.
   - Keep `navigator.webdriver`/automation-global cleanup as a regression invariant, not a promise of invisibility.

4. Source-controlled benchmark/probe scripts under `browser-runtime/scripts/`
   - Implemented files:
     - `scripts/fingerprint_probe.py`: attaches to a created session CDP websocket from session JSON and writes sanitized JSON.
     - `scripts/fingerprint_compare.py`: compares two sanitized probe JSON files and emits a markdown/JSON risk-delta summary.
   - Reuse the existing raw/private vs sanitized/shareable boundary from `scripts/artifact_hygiene_scan.py`.
   - The previous artifact-local `runtime_cdp_benchmark.py` remains public-detector benchmark reference only; do not copy its raw-page-text dumping behavior into shareable outputs.

### Data/control flow

1. Operator/ops starts `hermes-browser-runtime server` privately on localhost and creates a session with existing `sessions create` / HTTP API flags.
2. Backend resolves display mode, GPU policy, WebRTC policy, and resolved browser identity before constructing Chrome args.
3. Chrome starts on a private CDP port; backend waits for CDP `Browser.getVersion`.
4. CDP persona guard applies identity/persona to the initial blank page and future page targets before detector/probe navigation.
5. Probe harness connects over the live `cdp_ws_url` but treats it as a capability secret; it never persists the usable URL in shareable outputs.
6. Probe executes deterministic local checks in top page, iframe, popup, and worker contexts; WebRTC and rendering values are classified/redacted.
7. Probe writes raw/private working artifacts under the run directory and a sanitized JSON/markdown report suitable for downstream docs/review.
8. Artifact hygiene scanner verifies no usable CDP websocket URLs, takeover tokens, cookies/auth/request/form bodies, raw IPs/hostnames, or private profile state are present in sanitized outputs.

## Interfaces

No new public HTTP API fields are required for P4A. Keep using:
- `CreateSessionRequest.persona`
- `CreateSessionRequest.webrtc_ip_policy`
- `CreateSessionRequest.gpu_policy`
- `CreateSessionRequest.headless`
- `CreateSessionRequest.persist_profile`
- CLI/env: `HBR_WEBRTC_IP_POLICY`, `HBR_GPU_POLICY`, `HBR_HEADFUL`/`HBR_HEADLESS`, `HBR_CHROME_PATH`, `HBR_CHROME_NO_SANDBOX`, `HBR_BIND`, `HBR_DATA_DIR`, `HBR_BEARER_TOKEN`, and default persona env vars `HBR_DEFAULT_LOCALE`, `HBR_DEFAULT_ACCEPT_LANGUAGE`, `HBR_DEFAULT_TIMEZONE_ID`, `HBR_DEFAULT_PLATFORM`, `HBR_DEFAULT_HARDWARE_CONCURRENCY`, `HBR_DEFAULT_DEVICE_MEMORY_GB`, `HBR_DEFAULT_MAX_TOUCH_POINTS`

Internal interfaces likely affected:
- `BrowserPersona::resolved_user_agent(...)` or a new resolver in `models.rs`.
- `backend::chrome_args(...)` and launch plan tests.
- `cdp::persona_command_plan(...)` / `user_agent_metadata(...)` tests.
- P4-S1 target-type persona planning tests must keep page-like and worker-like commands separate and avoid unsupported `Page.*` commands for worker-like targets.

New script CLI interface:

```bash
python3 browser-runtime/scripts/fingerprint_probe.py \
  --session-json browser-runtime/artifacts/<run>/session-create.json \
  --out browser-runtime/artifacts/<run>/fingerprint-probe.json \
  --mode local-deterministic \
  --strict

python3 browser-runtime/scripts/fingerprint_compare.py \
  --before browser-runtime/artifacts/<before>/fingerprint-probe.json \
  --after browser-runtime/artifacts/<after>/fingerprint-probe.json \
  --out browser-runtime/artifacts/<after>/p4-risk-delta.md

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

Minimum sanitized `fingerprint-probe.json` shape:

```json
{
  "schema_version": "hbr.p4.fingerprint_probe.v1",
  "generated_at_utc": "...",
  "runtime": {"headless": false, "launch_mode": "local-display|xvfb|headless", "chrome_product_major": "..."},
  "policy": {"webrtc_ip_policy": "default_public_interface_only", "gpu_policy": "auto"},
  "persona": {"locale": "en-US", "timezone_id": "...", "platform": "...", "viewport": {"width": 1280, "height": 800}},
  "identity": {"ua_major": "...", "ua_ch_major": "...", "coherent": true, "mismatches": []},
  "contexts": {"top": {}, "iframe": {}, "worker": {}, "popup": {}},
  "webrtc": {"candidate_classes": ["mdns_host", "public_srflx"], "raw_values_redacted": true},
  "rendering": {"webgl": {"available": false, "renderer_class": "blocked|swiftshader|hardware_like|unknown"}},
  "red_flags": [],
  "residual_risks": []
}
```

Do not put usable `cdp_ws_url`, takeover URL/token, cookies, auth headers, request bodies, form bodies, card data, raw IPs/hostnames, private profile paths, or raw fingerprint dumps in this JSON.

## Safety invariants

- Runtime remains private/local by default; remote/mobile takeover remains SSH local-port-forward, tailnet-only Tailscale Serve, or future signed HTTPS broker only.
- Takeover URLs are TTL-scoped bearer secrets; rotate on pause and invalidate on release/expiry.
- Human-only checkpoints remain human-only: login/password, OAuth, passkey, OTP/MFA, magic links, CAPTCHA-like challenges, 3DS/bank challenges, card entry, and final `pay/place order` approval.
- Before final payment/order submission, explicit Telegram approval is still required with merchant/domain, items, total/currency, shipping summary, and payment-method label.
- Redaction protects local artifacts/logs only; it does not mean destination websites never receive human-entered secrets.
- Public detector pages must be described as evidence, not guarantees.
- No proxy/IP rotation, rate-limit bypass, account-abuse evasion, or site access-control bypass should be introduced or documented.

## Test strategy

Required code gates for `t_51a84dfc`:

```bash
PATH=$HOME/.cargo/bin:$PATH \
CARGO_HOME=$HOME/.cargo \
RUSTUP_HOME=$HOME/.rustup \
cargo fmt --manifest-path browser-runtime/Cargo.toml --all -- --check

PATH=$HOME/.cargo/bin:$PATH \
CARGO_HOME=$HOME/.cargo \
RUSTUP_HOME=$HOME/.rustup \
cargo clippy --manifest-path browser-runtime/Cargo.toml --all-targets --all-features -- -D warnings

PATH=$HOME/.cargo/bin:$PATH \
CARGO_HOME=$HOME/.cargo \
RUSTUP_HOME=$HOME/.rustup \
cargo test --manifest-path browser-runtime/Cargo.toml --all-features -- --quiet

browser-runtime/scripts/coverage-gates.sh
```

Targeted unit/integration coverage:
- `models.rs`: Chrome full/major version extraction, `HeadlessChrome` sanitization, platform-to-UA token mapping, impossible/contradictory persona validation if added.
- `backend.rs`: launch args use actual/derived Chrome version when available, never emit `HeadlessChrome`, preserve WebRTC/GPU flags, no forced SwiftShader/`--disable-3d-apis` in `auto` headed default.
- `cdp.rs`: `userAgentMetadata.brands`, `fullVersionList`, `platform`, `architecture`, `bitness`, `mobile`, and `formFactors` match resolved UA/persona; command plan order still applies locale/timezone/device metrics before navigation.
- `tests/browser_integration.rs`: top/frame/worker/popup identity coherence remains green; webdriver hygiene and no `HeadlessChrome` remain green.
- Probe scripts: JSON schema/fixture tests and redaction tests for CDP websocket URLs, takeover token URLs, IP literals, hostnames, auth/cookie/form markers, and private runtime paths.
- P4-S1: persona defaults/env parsing tests for hardware concurrency, device memory, and max touch points; CDP target-plan tests for page-like vs worker-like commands; public detector harness fixture tests for strict nonblank counts, redacted comparison labels, and detector-list coverage deltas.

Relevant live smokes when Chrome is available:

```bash
HBR_CHROME_NO_SANDBOX=1 \
HBR_CHROME_PATH=$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome \
PATH=$HOME/.cargo/bin:$PATH \
CARGO_HOME=$HOME/.cargo \
RUSTUP_HOME=$HOME/.rustup \
cargo test --manifest-path browser-runtime/Cargo.toml --test browser_integration -- --ignored --quiet
```

Artifact checks:

```bash
python3 browser-runtime/scripts/artifact_hygiene_scan.py \
  browser-runtime/artifacts/<p4-run>-sanitized \
  --strict \
  --json-report browser-runtime/artifacts/<p4-run>-sanitized/hygiene-scan-report.json
```

Benchmark acceptance is not “all detectors pass”. Acceptance is:
- measurable before/after identity-coherence delta;
- no regression to P1/P2/P3 safety gates;
- sanitized evidence has zero secret/private-path findings;
- remaining CreepJS/WebRTC/WebGL/network risks are explicitly listed.

## Canonical docs and evidence after P4/P5/P4-S1

- `browser-runtime/README.md`
  - Documents P4 probe usage, public detector harness usage, supported modes, default persona env vars, benchmark interpretation, residual risks, artifact hygiene, and explicit no-bypass/no-undetectable language.
- `browser-runtime/docs/implementation-plan.md`
  - Records P4A/P5/P4-S1 status, completed gates, seam map updates, benchmark result, and residual risk register.
- `browser-runtime/docs/fingerprint-hygiene-residual-risk-runbook.md`
  - Operational checklist for detector-evidence limits, artifact tiers, P4-S1 harness comparability, target coverage bounds, and human-only checkpoint preservation.
- `browser-runtime/docs/p4-fingerprint-hygiene-architecture.md`
  - Preserves the original architecture rationale and adds post-implementation/benchmark status sections for P4, P5, and P4-S1.
- `browser-runtime/artifacts/p4-implementation-sanitized/run-20260511T231333Z/signoff-report.md`
  - Implementation-gate sanitized evidence from the approved P4A review.
- `browser-runtime/artifacts/hbr-p4-bench/run-20260511T235056Z-sanitized/benchmark-report.md`
  - Historical P4 public-detector benchmark summary; raw sibling directory stays private-local.
- `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z/ops-comparison-summary.md`
  - Current P4-S1 public-detector benchmark summary. Treat BrowserLeaks group verdict as a harness comparability caveat because the detector list changed.
- `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z-public-redacted/public-summary.md`
  - Current P4-S1 public-share summary tier; raw and internal sanitized artifacts stay private-local unless a reviewer approves excerpts.

## Implementation slices and dependencies

P4 was intentionally serialized in the shared worktree:

1. `t_e581356c` — architect — produced this handoff.
2. `t_fb3543e1` — reviewer — independently approved the P4A implementation review that replaced the earlier blocked implementer lane.
3. `t_dfebb94c` — ops — collected the post-P4 public-detector benchmark artifacts and strict sanitized bundle.
4. `t_2561e6df` — writer — updates canonical docs after benchmark artifacts exist; do not document aspirational claims.
5. `t_3493b59b` — reviewer — final safety/fingerprint-hygiene sign-off after docs and benchmark complete.
6. `t_27ed75e9` — writer — updates P4-S1 docs and residual-risk runbook after implementation/remediation and public-detector benchmark evidence exist; do not document aspirational claims.

Do not split parallel code tasks into the same shared worktree. If a new blocker appears, block the current task with a precise reason instead of creating a second mutable lane.

## Risks and fallbacks

- Risk: Chrome binary version parsing differs by distribution.
  - Fallback: omit launch UA override until CDP persona guard applies, flag `launch_ua_version_unknown` in probe, and avoid claiming coherence before CDP.
- Risk: public detector pages change or rate-limit evidence runs.
  - Fallback: local deterministic probe remains the gate; public evidence is `not_measured` or `unstable`, not a failure to bypass.
- Risk: worker/Xvfb environment cannot validate real GPU/WebGL.
  - Fallback: report `webgl unavailable/blocked in this environment`; defer consumer-like GPU claims to a real headed GPU host.
- Risk: expanding target coverage breaks worker/service-worker CDP commands.
  - Fallback: keep page-target guard stable, send only worker-safe `Runtime.evaluate` plans to worker-like targets, and mark unsupported worker/service-worker checks as `not_measured`; do not send unsupported `Page.*` commands to non-page targets.
- Risk: public detector harness coverage changes between baseline and after runs.
  - Fallback: call the comparison a coverage/comparability caveat, align detector selection, rerun, and avoid presenting group verdicts as product regressions or passes until coverage matches.
- Risk: artifacts accidentally include capability URLs or private profile state.
  - Fallback: sanitizer strict gate fails; keep raw run private-local, regenerate sanitized bundle, and do not proceed to docs/review until zero findings.
- Rollback: code changes should be small enough to revert as one P4A patch; existing explicit `persona.user_agent`, `HBR_WEBRTC_IP_POLICY`, and `HBR_GPU_POLICY` behavior remain the operational fallback.

## Open questions

None blocking implementation. Real headed GPU validation is environment-dependent; if unavailable, record it as `not_measured`/residual risk rather than blocking P4A.
