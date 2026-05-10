# Hermes Browser Runtime

Local, self-hosted, CDP-first browser runtime for one user and trusted agents. It is a private local analogue of the useful Browserbase/Hyperbrowser/Kernel primitives: session API, persistent profiles, takeover link, CDP connection, artifacts and screenshot replay.

This is **not** a captcha solver, antibot bypass, or stealth system. The intended use is legitimate human-in-the-loop login, OAuth, 3DS, checkout/payment confirmation, file upload/download and manual approvals.

## MVP architecture

- Rust server + CLI.
- HTTP API: `axum`/`tokio`/`serde`.
- Browser backend trait: `BrowserBackend`.
- MVP backend: `LocalChromeBackend`.
- Chrome/Chromium subprocess with:
  - `--remote-debugging-port=<free-local-port>`
  - `--user-data-dir=<profile-dir>`
  - configurable headless/headful and viewport
  - CDP discovery through `/json/version`
- Profiles stored outside the repo by default: `~/.local/share/hermes-browser-runtime/profiles`.
- Session artifacts: screenshots, `events.jsonl`, downloads dir.
- Human takeover: local web page with live screenshot polling, `release` button and CDP Input click/type/scroll fallbacks.

## Quick start

```bash
cd browser-runtime
cargo build

# If Chrome/Chromium is installed in a standard path, this is enough:
./target/debug/hermes-browser-runtime server

# Or point to a browser explicitly:
HBR_CHROME_PATH="$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome" \
HBR_CHROME_NO_SANDBOX=1 \
./target/debug/hermes-browser-runtime server
```

Defaults:

- Bind: `127.0.0.1:7788`
- Data dir: `~/.local/share/hermes-browser-runtime`
- Profiles chmod: `0700`
- No bearer token unless `HBR_BEARER_TOKEN` is set

## API

### Create a session

```bash
curl -s http://127.0.0.1:7788/sessions \
  -H 'content-type: application/json' \
  -d '{"profile_id":"yura-main","headless":true,"persist_profile":true,"viewport":{"width":1280,"height":800}}'
```

Response:

```json
{
  "id": "...",
  "status": "running",
  "cdp_ws_url": "ws://127.0.0.1:PORT/devtools/browser/...",
  "takeover_url": "http://127.0.0.1:7788/takeover/...?token=...",
  "profile_id": "yura-main"
}
```

### List/get/delete sessions

```bash
curl -s http://127.0.0.1:7788/sessions
curl -s http://127.0.0.1:7788/sessions/<id>
curl -X DELETE http://127.0.0.1:7788/sessions/<id>
```

### Pause for human and release

```bash
curl -s -X POST http://127.0.0.1:7788/sessions/<id>/pause_for_human \
  -H 'content-type: application/json' \
  -d '{"reason":"OAuth approval required"}'

# Open takeover_url manually, complete the step, press Release.
# Or release through API:
curl -s -X POST http://127.0.0.1:7788/sessions/<id>/release
```

### Screenshot and artifacts

```bash
curl -s http://127.0.0.1:7788/sessions/<id>/screenshot -o screenshot.png
curl -s http://127.0.0.1:7788/sessions/<id>/artifacts
```

### Profiles

```bash
curl -s -X POST http://127.0.0.1:7788/profiles \
  -H 'content-type: application/json' \
  -d '{"id":"yura-main"}'

curl -s http://127.0.0.1:7788/profiles
curl -X DELETE http://127.0.0.1:7788/profiles/yura-main
```

## Playwright/Hermes agent example

```js
const { chromium } = require('playwright-core');

const create = await fetch('http://127.0.0.1:7788/sessions', {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ profile_id: 'oauth-main', headless: true, persist_profile: true })
});
const session = await create.json();

const browser = await chromium.connectOverCDP(session.cdp_ws_url);
const context = browser.contexts()[0];
const page = context.pages()[0] || await context.newPage();

await page.goto('https://example.com/login');

// If OAuth/hCaptcha/3DS/payment confirmation blocks automation:
await fetch(`http://127.0.0.1:7788/sessions/${session.id}/pause_for_human`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ reason: 'manual OAuth/3DS step required' })
});
console.log('Open takeover:', session.takeover_url);

// Agent waits/polls GET /sessions/:id until status returns running.
```

Typical human-in-the-loop flow:

1. Agent creates session and connects by `cdp_ws_url`.
2. Agent works normally with Playwright/CDP.
3. Site requires a human-only step.
4. Agent calls `pause_for_human` and sends `takeover_url` to Юра.
5. Юра completes the step in takeover page or local headful Chrome window.
6. Юра presses `Release`.
7. Agent continues in the same browser/profile/session.

## Security defaults

- Binds to `127.0.0.1` by default.
- Optional bearer auth:

```bash
export HBR_BEARER_TOKEN=$(openssl rand -hex 32)
./target/debug/hermes-browser-runtime server
curl -H "authorization: Bearer $HBR_BEARER_TOKEN" http://127.0.0.1:7788/sessions
```

- Takeover tokens are random, one-session URLs with TTL (`HBR_TAKEOVER_TTL_SECS`, default 900s).
- Profiles and runtime data are stored outside the repo and chmod `0700`.
- Event logging is metadata-only. Do not log cookies, auth headers, passwords, card data, form fields or request bodies.
- No SaaS dependencies; Hyperbrowser/Kernel are product references only.

## Troubleshooting

### Chrome not found

Install Chrome/Chromium or set:

```bash
export HBR_CHROME_PATH=/path/to/chrome
```

For local Playwright Chromium:

```bash
npx playwright install chromium
export HBR_CHROME_PATH="$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"
```

### Chrome exits before CDP is ready

On some headless Linux hosts, sandboxing fails. For a private local runtime only, retry with:

```bash
export HBR_CHROME_NO_SANDBOX=1
```

### Profile lock

A persistent profile can have only one writer. Close the active session:

```bash
curl -X DELETE http://127.0.0.1:7788/sessions/<id>
```

Use `persist_profile:false` to seed from a profile into an ephemeral read-only copy without taking the persistent write lock.

### SSH tunnel

When server binds on the remote host:

```bash
ssh -L 7788:127.0.0.1:7788 user@host
```

Then use `http://127.0.0.1:7788` locally.

## Quality gates

See also `docs/review-report.md` for the latest local verification report, readiness assessment, and improvement backlog.

```bash
cargo fmt
cargo clippy -- -D warnings
cargo test

# Manual browser integration tests:
HBR_CHROME_NO_SANDBOX=1 \
HBR_CHROME_PATH="$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome" \
cargo test --test browser_integration -- --ignored --nocapture
```

The ignored integration tests cover:

- create session → connect Playwright over CDP → screenshot → close
- profile persistence: set cookie/localStorage → close → reopen same profile → verify state
