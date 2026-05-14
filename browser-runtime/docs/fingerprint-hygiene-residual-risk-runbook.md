# HBR fingerprint-hygiene residual-risk runbook

Status: P4-S1 docs update after implementation and public-detector benchmark.
Scope: legitimate fingerprint coherence for local/private HBR sessions and repeatable detector benchmarking.

This runbook is not an undetectability claim. It is not a CAPTCHA, OAuth, MFA, passkey, OTP, 3DS, payment, rate-limit, access-control, account-abuse, proxy, IP reputation, TLS, or site-risk bypass plan.

## Current behavior to preserve

### Persona and config

`BrowserPersona` now carries browser-capability fields in addition to locale, timezone, platform, viewport, screen, DPR, and optional UA:

- `hardware_concurrency`
- `device_memory_gb`
- `max_touch_points`

Runtime defaults are conservative and normalized before use:

- hardware concurrency default: `8`
- device memory default: `8`
- max touch points default: `0`
- hardware/device memory values are bucketed to common values; out-of-range values fall back to defaults
- max touch points above `10` falls back to default

Server-level persona defaults can be set with:

- `HBR_DEFAULT_LOCALE`
- `HBR_DEFAULT_ACCEPT_LANGUAGE`
- `HBR_DEFAULT_TIMEZONE_ID`
- `HBR_DEFAULT_PLATFORM`
- `HBR_DEFAULT_HARDWARE_CONCURRENCY`
- `HBR_DEFAULT_DEVICE_MEMORY_GB`
- `HBR_DEFAULT_MAX_TOUCH_POINTS`

For benchmark scripts, boolean env values should use `true`/`false` for Clap-backed flags such as `HBR_HEADFUL` and `HBR_HEADLESS`.

### Target coverage semantics

The CDP persona path is target-type aware:

- Page-like targets receive the full page persona plan: UA/UA-CH, locale, timezone, viewport, screen, `visualViewport`, `matchMedia`, navigator capability fields, and automation-marker cleanup.
- Worker-like targets receive a worker-safe `Runtime.evaluate` persona plan for navigator-visible fields such as `userAgent`, `language`, `languages`, `platform`, `hardwareConcurrency`, `deviceMemory`, and `maxTouchPoints`.
- Worker-like targets must not receive unsupported `Page.*` commands.
- `Runtime.runIfWaitingForDebugger` is sent only when the target is actually waiting.

Do not describe worker/service-worker coverage as universal. Service-worker behavior can remain CDP-version-sensitive and must be verified by tests/evidence, not assumed.

## Probe and benchmark workflow

### Local deterministic probe

Use the deterministic probe for local, repeatable evidence. Keep raw session JSON private because it can contain live capability URLs.

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

The probe output is local deterministic evidence. It is not a public-detector score and not proof of real-site success.

### Public detector harness

Use public detector pages only as proxy evidence. The current source-controlled harness supports the ops command shape:

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

Harness rules:

- `public_detector_capture.py` writes redacted manifest counts and canonical screenshot metadata.
- `--strict-nonblank` should preserve manifest evidence even when it exits non-zero for blank/missing screenshots.
- `public_detector_compare.py --redact` is an explicit compatibility flag; comparisons are intended to stay redacted.
- Public markdown/JSON must not derive public labels from sensitive input directory names.
- Do not quote raw detector page text, public IP literals, stable detector/fingerprint hashes, CDP websocket URLs, takeover URLs, cookies, auth headers, or private profile paths in handoffs.

## Artifact tiers

Raw runtime artifacts stay private-local by default.

Use `artifact_hygiene_scan.py` for every evidence bundle:

```bash
python3 browser-runtime/scripts/artifact_hygiene_scan.py \
  --source browser-runtime/artifacts/<raw-run> \
  --sanitize-to browser-runtime/artifacts/<run>-internal-sanitized \
  --tier internal-sanitized \
  --strict \
  --json-report browser-runtime/artifacts/<run>-internal-sanitized/hygiene-scan-report.json

python3 browser-runtime/scripts/artifact_hygiene_scan.py \
  --source browser-runtime/artifacts/<raw-run> \
  --sanitize-to browser-runtime/artifacts/<run>-public-redacted \
  --tier public-redacted \
  --strict \
  --json-report browser-runtime/artifacts/<run>-public-redacted/public-redaction-scan-report.json
```

Interpretation:

- Internal sanitized: for local/internal review only, even with zero strict findings.
- Public redacted: whitelist-only public-share tier, still not a guarantee of real-site success.
- Raw screenshots, raw page text, runtime profile state, raw session JSON, and raw events are private unless a reviewer explicitly approves an excerpt.

## Current P4-S1 evidence snapshot

Baseline:

- `browser-runtime/artifacts/public-detector-screens/run-20260512T113556Z`

After implementation:

- `browser-runtime/artifacts/public-detector-screens/run-20260512T173631Z`
- `comparison.md` / `comparison.json`
- `ops-comparison-summary.md` / `ops-comparison-summary.json`
- `hygiene-scan-report.json`
- `detector-screenshots.zip` plus `detector-screenshots.zip.sha256`
- internal sanitized bundle: `run-20260512T173631Z-internal-sanitized/`
- public-redacted bundle: `run-20260512T173631Z-public-redacted/`

Benchmark counts:

- before: attempted `12`, captured `12`, nonblank `12`
- after: attempted `12`, captured `12`, nonblank `12`

Detector verdict summary:

- CreepJS: unchanged
- Sannysoft: unchanged
- Pixelscan: unchanged
- BrowserLeaks: marked regressed because of a harness coverage delta, not because the other BrowserLeaks rows proved a product fingerprint regression
- Other: `fpscanner` is new in the after harness

Important coverage note:

- Baseline included `browserleaks-javascript`; the current after harness added `fpscanner` and omitted `browserleaks-javascript`.
- Treat the BrowserLeaks group verdict as a detector-list comparability issue until a baseline-aligned harness selection is implemented and reviewed.

## Residual risk register

1. Public detector pages are proxy evidence.
   - They help spot obvious regressions.
   - They do not prove success on real merchants, login systems, or anti-abuse stacks.

2. Harness comparability is currently limited.
   - The latest before/after run has a detector-list delta: baseline `browserleaks-javascript` vs after `fpscanner`.
   - Do not present the BrowserLeaks group as apples-to-apples until the harness is aligned and rerun.

3. WebRTC/IP default is not anonymity.
   - `default_public_interface_only` is intended to suppress private/local host-candidate IP literals.
   - It does not hide public egress/default-interface IPs.
   - mDNS `.local` and public srflx evidence can remain acceptable only when no private/local literal class is exposed.

4. WebGL/GPU remains environment-dependent.
   - No-display/Xvfb/SwiftShader-like environments can still look synthetic.
   - Do not claim consumer-like GPU/WebGL behavior without a separate headed consumer-GPU benchmark host.

5. Worker/service-worker coverage is bounded.
   - Worker-like targets get a worker-safe persona plan.
   - Cross-origin iframes, service workers, extensions, GPU surfaces, and future CDP behavior may still create gaps.

6. Artifact hygiene is a release gate.
   - Strict internal hygiene with zero findings does not make raw detector artifacts public-share safe.
   - Public sharing requires public-redacted tier or explicit reviewer approval.

7. Network and account signals are out of browser-runtime scope.
   - ASN/IP reputation, TLS/JA3/JA4, HTTP/2 behavior, account history, rate limits, and site risk models are not solved here.

8. Human-only checkpoints remain human-only.
   - CAPTCHA-like challenges, OAuth consent, OTP/MFA, passkeys, 3DS/bank challenges, card entry, payment approval, and final purchase/order submission still require pause/takeover/approval.

## Review checklist before sign-off

Before claiming a P4-S1 doc/evidence state is ready, check:

- Runtime behavior described in docs matches the current code and reviewer handoffs.
- Persona config docs include hardware concurrency, device memory, max touch points, and default env vars.
- Target coverage docs distinguish page-like and worker-like CDP plans.
- Public detector docs state counts and limits without claiming universal undetectability.
- Harness comparability limitations are visible if detector lists differ.
- Raw artifacts stay private-local; public-redacted outputs pass strict hygiene.
- Human-only checkpoint language is still explicit.
