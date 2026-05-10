# Hermes Browser Runtime MVP Review Report

Date: 2026-05-10

## Verdict

MVP is usable on the Hermes host as a private local CDP-first browser runtime for one user and trusted agents. It can replace paid browser-session SaaS for the core local use cases: launching Chrome, returning `cdp_ws_url`, Playwright/CDP control, persistent profiles, screenshot artifacts, and human-in-the-loop pause/release.

It is not yet a cloud fleet, stealth/antibot system, or full Browserbase/Hyperbrowser/Kernel equivalent. That is intentional for MVP.

## Verification performed

```bash
cargo fmt -- --check
cargo clippy -- -D warnings
cargo test
HBR_CHROME_NO_SANDBOX=1 \
HBR_CHROME_PATH="$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome" \
cargo test --test browser_integration -- --ignored --nocapture
npm audit --omit=optional
```

Results:

- `cargo fmt -- --check`: pass
- `cargo clippy -- -D warnings`: pass
- `cargo test`: pass, 10 unit tests
- real browser integration tests: pass, 2 ignored-by-default tests run manually
- `npm audit --omit=optional`: 0 vulnerabilities
- added-line secret/static scan: no hardcoded secret assignments or common injection/eval/deserialization patterns

Additional smoke test:

- bearer auth rejects unauthenticated `/sessions`
- authenticated session create works
- screenshot returns PNG
- `pause_for_human` changes status
- `release` returns status to running and invalidates takeover URL
- artifacts include screenshot + event log
- delete session closes browser

## Code review notes

### Strengths

- Clear backend seam: `BrowserBackend` + concrete `LocalChromeBackend`.
- CDP-first: Chrome launched with remote debugging and `/json/version` discovery.
- Persistent profile flow works with Playwright: cookie and localStorage survive close/reopen.
- Persistent profile write lock prevents two concurrent writers.
- Launch failure releases profile locks.
- Human takeover token refreshes on pause and invalidates on release.
- Sensitive `pause_for_human.reason` text is redacted when it contains secret/card/auth/password markers.
- Profiles/runtime data are outside the repo and chmod `0700`.
- API binds to loopback by default and supports bearer auth.
- Integration tests use `spawn_blocking` for Node/Playwright to avoid Tokio runtime starvation.

### Remaining limitations / not blockers for MVP

- Takeover UI is screenshot polling, not live video/noVNC.
- CDP Input fallback supports basic click/type/scroll only.
- Artifact replay is screenshot/event timeline, not video.
- No packaged systemd service yet.
- No native Hermes tool wrapper yet.
- No BiDi adapter beyond product placeholder intent.
- Downloads are exposed as a directory path, not a download/file API.
- Browser sessions are in-memory; a server restart loses session registry, though profiles persist.
- No automatic cleanup policy for old session artifact directories yet.
- No cargo-audit run because `cargo-audit` is not installed on the host.

## Readiness assessment

Ready for local Hermes usage if the expected model is:

1. Agent creates session through local API.
2. Agent connects via Playwright/CDP.
3. Agent uses persistent profile for logins/cookies/localStorage.
4. Agent pauses when a human-only step appears.
5. Юра opens takeover URL or local headful Chrome, completes the step, and releases.
6. Agent continues in the same browser session/profile.

Not ready as a drop-in replacement for paid browser SaaS when needing:

- hosted browser fleet,
- region/proxy management,
- cloud recording/replay,
- remote multi-user live view,
- production auth/multi-tenant control plane,
- managed file upload/download APIs,
- browser pool autoscaling.

## Recommended next improvements

Priority 1 — make it comfortable for daily Hermes use:

1. Add a native Hermes tool/helper command: create session, wait for release, return `cdp_ws_url`.
2. Install as a user systemd service with healthcheck and logs.
3. Add a small CLI client: `hbr sessions create/list/delete/pause/release/screenshot`.
4. Improve takeover page UX: larger screenshot, coordinate overlay, keyboard shortcuts, typed text warning.
5. Add endpoint to wait/poll release: `GET /sessions/{id}/wait?status=running` or SSE.

Priority 2 — harden data/artifacts:

6. Add cleanup/retention policy for old sessions/artifacts.
7. Add file download listing and fetch endpoint.
8. Add safe file upload endpoint via CDP/Playwright helper pattern.
9. Add configurable artifact capture cadence for replay timeline.
10. Add cargo-audit/cargo-deny to quality gates.

Priority 3 — robustness:

11. Persist session metadata in SQLite so runtime can recover after restart.
12. Add browser crash detection and session status transition to `closed`/`failed`.
13. Add more HTTP API integration tests for auth, takeover token TTL, profile delete while locked.
14. Add graceful shutdown handler to close Chrome children on SIGTERM.
15. Add configurable launch timeout per request or CLI config.

Priority 4 — future adapters:

16. Add `BrowserBackend` adapter stubs for remote providers without importing SaaS SDKs.
17. Add optional WebDriver BiDi placeholder/adapter when needed.
18. Add browser pool abstraction only after one-user local runtime is stable.

## Final recommendation

Use this MVP for local Hermes browser automation now, especially for OAuth/login/payment/3DS human-in-the-loop flows. Keep paid SaaS browser providers only as fallback for cloud-hosted, proxy/region, fleet, or hosted replay requirements until the Priority 1–2 items are implemented.
