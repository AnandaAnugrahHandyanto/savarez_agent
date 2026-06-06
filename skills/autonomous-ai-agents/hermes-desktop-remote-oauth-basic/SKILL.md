---
name: hermes-desktop-remote-oauth-basic
description: "Point Hermes Desktop at a remote OAuth-gated dashboard."
version: 1.0.0
author: Hermes Agent community
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, desktop, dashboard, oauth, basic-auth, websocket, remote]
    related_skills: [hermes-agent]
---

# Hermes Desktop → Remote Dashboard via OAuth + BasicAuth

The Hermes Desktop app can talk to a `hermes dashboard` backend over the network via two distinct auth models. The symptoms of mixing them up are confusing: HTTP `/api/status` succeeds and the WebSocket `/api/ws` then fails with an opaque 403, and the Desktop's retry loop masks the root cause behind a "Restarting desktop connection" boot cycle.

## When to use

- Desktop is configured with `mode: 'remote'` pointing at a `hermes dashboard` running on another machine.
- HTTP `/api/status` from the remote returns 200 (good), but the WS upgrade to `/api/ws` fails.
- The user's `connection.json` is set to `authMode: 'token'` but the dashboard on the other side is running with `--insecure`, or vice versa.
- The user wants to migrate an existing `--insecure` standalone dashboard to the auth-gated OAuth mode (recommended for any non-loopback bind).

## The two auth models (truth table from `web_server.py::should_require_auth`)

```python
# auth_required = (host not in loopback) AND (not allow_public)
#
# loopback bind              -> auth_required = False  (loopback gate off)
# non-loopback + --insecure  -> auth_required = False  (--insecure escape hatch)
# non-loopback, no --insecure -> auth_required = True   (OAuth gate engages)
```

With `--insecure`:
- WS upgrade is accepted with `?token=<_SESSION_TOKEN>` (legacy header auth).
- The Desktop fills the `connection.json` `token` field with a value it generated, but a standalone dashboard running under a process supervisor (`launchd`, `systemd`, `supervisord`, etc.) with no `HERMES_DASHBOARD_SESSION_TOKEN` in its env falls back to `secrets.token_urlsafe(32)` at startup (`web_server.py:139`). The two never match. Result: 403 on the WS upgrade, the upgrade is rejected *before* the 101, the Node client reports `onerror`, and `probeGatewayWebSocket` returns "WebSocket connection failed".

With OAuth (no `--insecure`):
- HTTP `/api/status` is public; everything else is gated.
- Login is via `POST /auth/password-login` (BasicAuthProvider) or `GET /auth/login?provider=...` (OAuth providers like Nous).
- On success, the server sets `hermes_session_at` (access token, default 12h) and `hermes_session_rt` (refresh token, default 30d) cookies.
- The client mints a single-use, 30s-TTL `?ticket=` via `POST /api/auth/ws-ticket`.
- WS upgrade uses `?ticket=`. The `?token=` legacy path is REJECTED in OAuth mode (see `_ws_auth_reason` around line 7747).

## Diagnostic steps

1. Check the dashboard's `auth_required` state via the public status endpoint:

   ```bash
   curl -s http://HOST:9119/api/status | python3 -c "import sys,json; print(json.load(sys.stdin).get('auth_required'))"
   ```

   - `false` = `--insecure` mode, expects `?token=<_SESSION_TOKEN>` on WS
   - `true` = OAuth mode, expects `?ticket=<single-use>` on WS

2. Check the registered providers:

   ```bash
   curl -s http://HOST:9119/api/auth/providers
   ```

   Should list `basic` (Username & Password) and/or `nous` (OAuth).

3. Reproduce the WS handshake to see the exact rejection:

   ```python
   import socket, base64, secrets
   s = socket.create_connection((HOST, 9119), timeout=4)
   key = base64.b64encode(secrets.token_bytes(16)).decode()
   s.sendall((
       f"GET /api/ws?token=WHATEVER HTTP/1.1\r\n"
       f"Host: {HOST}:9119\r\nUpgrade: websocket\r\n"
       f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
       f"Sec-WebSocket-Version: 13\r\n\r\n"
   ).encode())
   # Read status line. Expect 403 on --insecure+token mismatch, or 101 if accepted.
   ```

## Migration path: `--insecure` standalone → OAuth standalone (BasicAuthProvider)

The `BasicAuthProvider` (bundled at `plugins/dashboard_auth/basic/`) is the right provider for a self-hosted "just put a password on my dashboard" scenario. It uses scrypt password hashing and HMAC-signed stateless session tokens. No external IDP required.

### Step 1: configure credentials in `~/.hermes/.env`

The provider reads these env vars (env wins over `config.yaml` when set non-empty):

```bash
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=<usern...>
# Optional: HERMES_DASHBOARD_BASIC_AUTH_TTL_SECONDS=***  # access token TTL, default 12h
```

Generate a strong password and secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"  # use one for each
```

The `secret` is the HMAC key that signs session tokens. If you don't set it, a random per-process key is generated and **all sessions die on restart** (and don't span multiple workers). Always set it explicitly for a multi-restart, multi-worker deployment.

For higher security, precompute the password hash and use `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH` instead of plaintext (see `hash_password()` in `plugins/dashboard_auth/basic/__init__.py`).

### Step 2: update the LaunchAgent / systemd / init script

The Hermes launcher does NOT source `~/.hermes/.env` into the child process environment on its own. If you run the dashboard under a process supervisor, you need to load `.env` yourself. **Do NOT use `set -a; . .env`** in a bash script under `set -e` — if any line in `.env` contains a path with spaces (very common, e.g. browser-executable paths), bash word-splits it and tries to execute the trailing tokens, which aborts the script.

Safe `.env` loader for bash (use this pattern):

```bash
if [ -f "$HERMES_HOME/.env" ]; then
    while IFS= read -r line; do
        case "$line" in
            ''|'#'*|'export '*|'    '#*|'   '#*) continue ;;
        esac
        case "$line" in
            *'='*)
                key=${line%%=*}
                val=${line#*=}
                case "$val" in
                    \"*\") val=${val#\"}; val=${val%\"} ;;
                    \'*\') val=${val#\'}; val=${val%\'} ;;
                esac
                case "$key" in
                    ''|*[!A-Za-z0-9_]*) continue ;;
                esac
                export "$key"="$val"
                ;;
        esac
    done < "$HERMES_HOME/.env"
fi
```

Also set `HERMES_WEB_DIST` to the prebuilt dist to skip the auto-build step that runs `tsc -b && vite build` (which fails with `tsc: command not found` when the npm PATH isn't on the search path the launcher expects):

```bash
export HERMES_WEB_DIST="/path/to/hermes-agent/hermes_cli/web_dist"
```

### Step 3: remove `--insecure` from the `hermes dashboard` invocation

The gate engages automatically when:
- `host` is non-loopback (`0.0.0.0`, `::`, or a specific LAN IP), AND
- `--insecure` is NOT passed.

If a provider is registered (BasicAuthProvider is), the dashboard starts successfully. If NO provider is registered, the dashboard **fails closed** with a clear error listing the skip reasons. Never bind non-loopback without either `--insecure` or a registered provider.

### Step 4: reload the supervisor

```bash
# macOS LaunchAgent
launchctl kickstart -k "gui/$(id -u)/ai.hermes.dashboard"

# Linux systemd
systemctl --user restart hermes-dashboard.service
```

### Step 5: validate end-to-end

```bash
# Public status reports auth_required=true
curl -s http://HOST:9119/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('auth_required=',d.get('auth_required'))"
# → auth_required= True

# Provider list includes 'basic'
curl -s http://HOST:9119/api/auth/providers
# → {"providers":[{"name":"basic","display_name":"Username & Password","supports_password":true}]}

# Login works
curl -s -c /tmp/cj -X POST http://HOST:9119/auth/password-login \
  -H 'Content-Type: application/json' \
  -d '{"provider":"basic","username":"<username>","password": "***"}'
# → {"ok":true,"next":"/"}

# Mint a ws-ticket
curl -s -b /tmp/cj -X POST http://HOST:9119/api/auth/ws-ticket \
  -H 'Content-Type: application/json' -d '{}'
# → {"ticket":"<43-char single-use token>"}

# WS upgrade with the ticket
python3 -c "
import socket, base64, secrets
s = socket.create_connection(('HOST', 9119), timeout=4)
key = base64.b64encode(secrets.token_bytes(16)).decode()
s.sendall(f'GET /api/ws?ticket=THE_TICKET HTTP/1.1\r\nHost: HOST:9119\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://HOST:9119\r\n\r\n'.encode())
print(s.recv(4096).decode('latin-1', errors='replace').split('\r\n', 1)[0])
"
# → HTTP/1.1 101 Switching Protocols
```

## Pointing the Desktop at the new endpoint

In the Desktop's `connection.json` (`~/Library/Application Support/Hermes/connection.json` on macOS, `%APPDATA%/Hermes/connection.json` on Windows, `~/.config/Hermes/connection.json` on Linux), set:

```json
{
  "mode": "remote",
  "remote": {
    "url": "http://<gateway-host>:9119",
    "authMode": "oauth"
  }
}
```

On first apply / test, the Desktop opens the browser to `/login`, the user enters the username + password, and the session cookies are stored. The Desktop then mints ws-tickets transparently for every reconnect.

Do **not** set `authMode: 'token'` anymore — the `?token=` legacy path is rejected in OAuth mode. Set `authMode: 'oauth'` (or omit it; the Desktop probes `/api/status` and auto-detects).

## Pitfalls

- **`set -a; . .env` in bash** under `set -e` will abort on any `.env` line with unquoted spaces (very common with browser executable paths). Use the per-line parser above.
- **Forgetting `HERMES_WEB_DIST`** triggers an auto-build via `npm run build`, which needs `tsc` and `vite` on PATH. If `tsc: command not found` shows up in the dashboard log, that's why.
- **The standalone dashboard generates a fresh `_SESSION_TOKEN` on every restart** (when `HERMES_DASHBOARD_SESSION_TOKEN` is not in env). With OAuth, this doesn't matter (sessions are cookie-based, not token-based). With `--insecure`, every restart breaks existing clients unless they read the SPA-injected token from the `<script>window.__HERMES_SESSION_TOKEN__=*** block.
- **The `BasicAuthProvider` secret must be persistent across restarts**. If unset, a random per-process key is generated and all existing sessions are invalidated on every restart. The dashboard log will say "dashboard-auth-basic: no 'secret' configured; generating a random per-process signing key" if you forgot.
- **The Desktop's "Test remote" probe runs through the full HTTP+WS path** (`probeGatewayWebSocket` in `gateway-ws-probe.cjs`). It reports a generic "WebSocket connection failed" on any `onerror` (which fires when the server rejects the upgrade with 4xx before sending 101). The user can't distinguish "wrong token" from "firewall" from "missing provider" without checking the server log.
- **HTTP `Host` header check**: the dashboard rejects requests whose `Host` header doesn't match the bound interface (DNS-rebinding defence, GHSA-ppp5-vxwm-4cf7). With `0.0.0.0` bind, this is a no-op (any host accepted). With a specific LAN IP bind, the client MUST use that exact IP. The Desktop sends the `Host` header from the URL automatically, so this only bites manual `curl`/`wget` users.
- **Existing `connection.json` with `authMode: 'token'`** continues to send `?token=<value>`, which the server rejects in OAuth mode. The user sees the same "Reached the gateway over HTTP, but the live WebSocket failed" message. Fix: change `authMode` to `oauth` (or remove it; the Desktop will auto-detect).
