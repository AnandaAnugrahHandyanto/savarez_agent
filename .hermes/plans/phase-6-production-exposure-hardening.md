# Phase 6 Production Exposure Hardening Implementation Plan

> **For Hermes:** Implement directly in small verified steps; keep localhost defaults safe and preserve backward compatibility.

**Goal:** Make `hermes dashboard` safely accessible on a LAN/reverse proxy without exposing the injected admin session token to every network visitor.

**Architecture:** Keep the current localhost-only dashboard path unchanged. Add an explicit `--public` mode for network exposure that disables legacy HTML-injected token auth and uses first-admin/password login with an HttpOnly signed session cookie, CSRF protection for mutating API calls, strict Host allow-listing, proxy-aware secure cookies, and security headers. Keep legacy `--insecure` as the existing unsafe escape hatch.

**Tech Stack:** FastAPI/uvicorn backend in `hermes_cli/web_server.py`; argparse CLI in `hermes_cli/main.py`; React/Vite frontend in `web/src`; pytest + FastAPI TestClient for regression coverage.

---

## Task 1: Add backend public-mode auth/security tests

**Objective:** Capture desired public-mode behavior before implementation.

**Files:**
- Create: `tests/pallas_cli/test_production_exposure_hardening.py`
- Modify if directory differs: use `tests/hermes_cli/` if `tests/pallas_cli/` is absent.

**Checks:**
- `--public` does not inject `window.__HERMES_SESSION_TOKEN__`.
- public mode rejects legacy `X-Hermes-Session-Token` / bearer auth.
- default localhost mode still accepts legacy token for backward compatibility.
- `0.0.0.0` public mode rejects unlisted Host headers and accepts configured `--allowed-host` values.
- `start_server(... production=True/public=True ...)` records safe app state.
- CLI parser forwards `--public`, `--allowed-host`, `--secure-cookies`, and proxy trust flags.

**Verify:**
```bash
python -m pytest tests/hermes_cli/test_production_exposure_hardening.py -q -o 'addopts='
```
Expected initially: failures proving tests cover missing behavior.

## Task 2: Add dashboard runtime flags and Host allow-listing

**Objective:** Make network binding safe by default and explicit.

**Files:**
- Modify: `hermes_cli/main.py`
- Modify: `hermes_cli/web_server.py`

**Implementation:**
- Add CLI flags:
  - `--public`: safe network exposure mode.
  - `--allowed-host HOST`: repeatable Host allow-list for public/all-interface binds.
  - `--secure-cookies`: force Secure on auth cookies.
  - `--no-trust-proxy`: ignore `X-Forwarded-*` headers.
- Keep `--insecure`, but label it as dangerous legacy token exposure.
- In `start_server`, reject non-localhost unless `--public` or `--insecure` is set.
- Store on `app.state`: `public_mode`, `legacy_token_auth_enabled`, `allowed_hosts`, `secure_cookies`, `trust_proxy_headers`.
- Update `_is_accepted_host` to enforce explicit allow-list for `0.0.0.0`/`::` public mode.

**Verify:** targeted pytest.

## Task 3: Add cookie-session auth, first-admin setup, and CSRF

**Objective:** Provide real browser authentication in public mode without exposing a bearer token in HTML.

**Files:**
- Modify: `hermes_cli/web_server.py`

**Implementation:**
- Store dashboard users at `$HERMES_HOME/dashboard-users.yaml`.
- Password hashing: PBKDF2-HMAC-SHA256 with per-user salt.
- Public endpoints:
  - `GET /api/auth/status`
  - `POST /api/auth/setup` only when no users exist; creates first admin.
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `GET /api/auth/me`
- Session cookie: signed, HttpOnly, SameSite=Lax, expiry, restart invalidation acceptable.
- CSRF token: included in signed session and returned by login/status; required for cookie-authenticated unsafe methods.
- Auth middleware accepts either legacy token in localhost/default mode or cookie auth in public mode; legacy token disabled when public mode is active.

**Verify:** tests for first-admin setup, login, protected GET, mutating request CSRF rejection/acceptance.

## Task 4: Update SPA API client and login/setup gate

**Objective:** Make the React app usable in public mode with cookies and no injected session token.

**Files:**
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/App.tsx`
- Modify: `web/src/pages/ChatPage.tsx`
- Modify: `web/src/components/ChatSidebar.tsx` if it hard-requires the legacy token.

**Implementation:**
- Always send `credentials: 'same-origin'`.
- Keep injecting `X-Hermes-Session-Token` only when present.
- Store CSRF token returned by auth endpoints; add `X-Hermes-CSRF-Token` on mutating cookie-auth requests.
- On app boot, call `/api/auth/status`; if public auth is disabled, render existing dashboard.
- If setup needed, render first-admin setup form.
- If login needed, render login form.
- Logout clears cookie and returns to login.
- Chat WebSockets use cookie auth in public mode; token query remains only for legacy mode.

**Verify:** `npm run build` and browser smoke.

## Task 5: Add production exposure docs

**Objective:** Document safe LAN/reverse-proxy operation.

**Files:**
- Create: `docs/phase-6-production-exposure-runbook.md`

**Content:**
- Safe command examples:
  - LAN: `hermes dashboard --public --host 0.0.0.0 --allowed-host <ip-or-dns>`
  - Reverse proxy: `--allowed-host agents.example.com --secure-cookies`
- Explain why `--insecure` is unsafe.
- Caddy and nginx snippets.
- systemd user service snippet.
- Smoke checks for no injected session token, Host rejection, auth/login, and protected API behavior.

## Task 6: Verify, smoke, commit, push

**Objective:** Prove behavior and publish the changes.

**Commands:**
```bash
python -m pytest tests/hermes_cli/test_production_exposure_hardening.py tests/hermes_cli/test_web_server_host_header.py tests/hermes_cli/test_web_server_public_api_auth.py -q -o 'addopts='
cd web && npm run build
python -m compileall -q hermes_cli
python -m pytest tests/hermes_cli -q -o 'addopts='
git diff --check
git status --short
git add hermes_cli/main.py hermes_cli/web_server.py web/src tests/hermes_cli docs .hermes/plans/phase-6-production-exposure-hardening.md
git commit -m "feat: harden public dashboard exposure"
git push origin HEAD
```

**Browser smoke:**
- Start temporary dashboard with isolated `HERMES_HOME`.
- Confirm first-admin screen.
- Create admin.
- Confirm no `window.__HERMES_SESSION_TOKEN__` in public-mode HTML.
- Login/logout works.
- Bad Host gets 400.
- Legacy token gets 401.
- Protected page/API works after cookie login.
