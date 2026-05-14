# HBR-P5 residual closure: classifications and evidence

Task: `t_26ddadf8`
PM classification source: `t_c1c66943`
Fresh verification source: `t_a9deff55`
Date: 2026-05-12
Scope: legitimate browser-runtime fingerprint hygiene and evidence-based benchmarking only.

This document closes the post-P4 residual register by classification. It does not claim universal stealth, undetectability, detector bypass, or protected-workflow bypass.

## Evidence artifacts cited

Fresh P5 verification artifacts from `t_a9deff55`:

- Raw/internal source: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/`
- Direct probe JSON: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/fingerprint-probe.json`
- Internal sanitized bundle: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized/`
- Internal strict scan report: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-internal-sanitized/hygiene-scan-report.json`
- Public-redacted bundle: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted/`
- Public strict scan report: `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z-public-redacted/public-redaction-scan-report.json`
- Public-redacted files: `PUBLIC-REDACTED-MANIFEST.json`, `public-summary.json`, `public-summary.md`, `public-redaction-scan-report.json`

Public-detector context that remains relevant from P4/P4-S1:

- Historical P4 public-detector benchmark summary: `browser-runtime/artifacts/hbr-p4-bench/run-20260511T235056Z-sanitized/benchmark-report.md`
- Current P4-S1 public-detector benchmark summary: `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z/ops-comparison-summary.md`
- The P4 benchmark remains the cited source for public detector observations such as BrowserLeaks public/default-interface IP visibility and CreepJS mDNS `.local` plus public srflx candidates. The P5 direct probe is local deterministic evidence, not a new public-detector run.
- The P4-S1 public-detector comparison captured 12/12 pages before and after, but the BrowserLeaks group verdict has a detector-list comparability caveat: `browserleaks-javascript` was present in the baseline while `fpscanner` is new after. Do not treat that group verdict as apples-to-apples until the harness is aligned and rerun.
- Current residual-risk runbook: `browser-runtime/docs/fingerprint-hygiene-residual-risk-runbook.md`

## Verification gate summary

`t_a9deff55` reran the following gates before this doc was updated:

- `python3 -m pytest -q browser-runtime/scripts/test_fingerprint_scripts.py`: 10 passed.
- `cargo fmt --manifest-path browser-runtime/Cargo.toml --all -- --check`: passed.
- `cargo clippy --manifest-path browser-runtime/Cargo.toml --all-targets --all-features -- -D warnings`: passed.
- `cargo test --manifest-path browser-runtime/Cargo.toml --all-features -- --quiet`: passed.
- Ignored live Chrome smoke `headed_persona_coherence_echo_page_covers_top_iframe_popup_worker_and_headers`: passed.
- `browser-runtime/scripts/coverage-gates.sh`: passed with TOTAL line coverage 98.00%; active gate is `--fail-under-lines 97`.
- Direct probe strict mode: passed with `measurement_completeness.complete=true`, `identity.coherent=true`, `unavailable_contexts={}`, and strict findings `[]`.
- Internal sanitized strict scan: findings `[]`, `scan_tier=internal-sanitized`, `public_share_safe=false`.
- Public-redacted strict scan: findings `[]`, `scan_tier=public-redacted`, `public_share_safe=true`.

## Residual classifications

| Residual | Classification | Closure / evidence | Product boundary |
| --- | --- | --- | --- |
| Direct P4 probe `popup.measured=false` | fix-now, closed by evidence | P5 direct probe at `browser-runtime/artifacts/hbr-p5-residual-closure/run-20260512T083850Z/fingerprint-probe.json` reports `measurement_contract_version=hbr.p5.direct_probe.v1`, `measurement_completeness.complete=true`, `unavailable_contexts={}`, and `contexts.popup.measured=true`. Popup availability is `status=measured`, `open_method=window.open_about_blank`, `cdp_runtime_evaluate_user_gesture=true`, with coherent language/platform/timezone/viewport/screen/DPR/UA-major fields. | Future direct-probe sign-off must explicitly report popup context status. If popup is unavailable, block/defer with the structured reason; do not treat ambiguous `popup.measured=false` as a pass. |
| Sanitized bundles can still contain public IP/fingerprint evidence | fix-now, closed by evidence and policy | P5 separates internal and public tiers. Internal sanitized bundle passed strict scan with no findings but remains `public_share_safe=false`. Public-redacted bundle passed strict scan with no findings and `public_share_safe=true`; it contains only whitelisted public summary files. Extra verification found no IP literals, ICE/srflx/candidate text, detector hashes, private paths, or capability/auth/cookie/form/request-body markers in the public-redacted text outputs. | Strict artifact hygiene means no secrets, capability URLs, or private paths were found. It does not automatically mean a bundle is safe for public sharing: detector page text/screenshots/JSON can still contain public IPs and stable fingerprint evidence. Internal sanitized bundles stay private; only bundles produced by the public-share redaction tier, or explicitly reviewed/approved excerpts, may be shared externally. |
| Public/default-interface IP visibility under `default_public_interface_only` | accepted-by-design | P5 direct probe used `policy.webrtc_ip_policy=default_public_interface_only`; WebRTC `candidate_classes` were redacted and contained `mdns_host` only, with no private/local literal class reported. P4 public-detector evidence remains the cited source that BrowserLeaks can still show the public/default-interface IP and CreepJS can still show mDNS `.local` plus public srflx candidates while private IPv4 literal count stays zero. | browser-runtime's `default_public_interface_only` policy is intended to prevent private/local IP exposure. It does not hide the public egress/default-interface IP. Public detectors may still show mDNS `.local` host candidates and public srflx candidates; this is accepted when fresh evidence shows no RFC1918, ULA, link-local, or other private/local IP addresses are exposed. |
| CreepJS mDNS/public-srflx/headless/stealth score | mixed: accepted-by-design for mDNS/public srflx when no private/local IP leaks; needs external capability for headed consumer-GPU behavior; unsafe if treated as detector-specific evasion | P4 public detector evidence still reported CreepJS mDNS `.local` plus public srflx candidates and 44% like headless / 33% headless / 0% stealth. P5 does not claim to close those public-detector scores; it closes popup evidence and public-share redaction only. | CreepJS headless/stealth percentages are public-detector proxy evidence, not a product pass/fail target. In the no-display/Xvfb/SwiftShader worker environment, headless-like or WebGL-blocked findings may remain. Proving consumer-GPU behavior requires a separate headed consumer-GPU benchmark host; the project must not fake GPU/WebGL claims or chase detector-specific stealth scores. |
| WebGL/GPU unavailable in the no-display/Xvfb worker environment | needs external capability | P5 direct probe records `rendering.webgl.available=false`, `renderer_class=blocked`, and red flag `webgl_blocked`. The public-redacted summary repeats `webgl_renderer_class=blocked`. | WebGL/GPU unavailable in the worker environment is a documented environment limitation, not a silent browser-runtime pass. Consumer GPU renderer coherence remains unproven until separately benchmarked on a real headed GPU-capable host. |
| Network/IP reputation, account history, TLS/JA3/JA4, HTTP/2 fingerprinting, rate limits, and site risk models | unsafe/out-of-scope for browser-runtime browser flags | No P5 artifact measures or claims these surfaces. P5 artifacts and docs are limited to the direct probe measurement contract, artifact-publication tiers, and explicit browser-runtime policy interpretation. | Network/IP reputation, account history, TLS/JA3/JA4, HTTP/2 fingerprinting, rate-limit systems, and site risk models are outside browser-runtime browser-flag scope and are not claimed as solved. P5 must not be used as evidence of bypassing CAPTCHA/OAuth/OTP/MFA/passkeys/3DS/payment/access-control/anti-abuse systems. |

## Remaining open external-capability item

Future human decision: whether and when to provide a real headed consumer-GPU benchmark host. Until that exists, consumer-GPU/WebGL renderer coherence and any CreepJS headless-score improvement tied to real GPU/display behavior remain unproven.

This open item is not a blocker for the P5 fix-now closure because P5 only closes the popup evidence ambiguity and the internal-vs-public artifact-sharing gap.

## Reviewer checklist for final P5 sign-off

- Cite the P5 direct probe path and confirm `measurement_completeness.complete=true`, `contexts.popup.measured=true`, and `unavailable_contexts={}`.
- Confirm internal sanitized and public-redacted strict scan reports both have findings `[]`.
- Treat `run-20260512T083850Z-internal-sanitized/` as internal-review only even though strict hygiene passed.
- Treat `run-20260512T083850Z-public-redacted/` as the only public-share tier unless a reviewer explicitly approves a narrower excerpt.
- Reject any claim of universal undetectability, CAPTCHA/OAuth/OTP/MFA/passkey/3DS/payment/rate-limit/access-control bypass, anti-abuse bypass, network reputation solving, TLS/JA3/JA4 solving, or fake GPU/WebGL success.
