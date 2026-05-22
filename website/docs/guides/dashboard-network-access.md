# Expose the Hermes dashboard on your network

The dashboard defaults to localhost because it can read and edit Hermes config, environment keys, sessions, cron jobs, profiles, and plugin state.

Use public mode when you need LAN or reverse-proxy access:

```bash
hermes dashboard \
  --host 0.0.0.0 \
  --public \
  --allowed-host agents.example.lan \
  --no-open
```

Then browse to `http://agents.example.lan:9119`.

## What public mode changes

`--public` enables network-safe defaults:

- does **not** inject the legacy ephemeral session token into the SPA HTML
- requires a dashboard login backed by `$HERMES_HOME/dashboard-users.yaml`
- creates the first local admin account on first launch
- stores sessions in an HttpOnly, SameSite=Lax cookie
- requires `X-Hermes-CSRF-Token` on cookie-authenticated mutating API calls
- enforces an explicit Host allow-list for all-interface binds
- adds baseline security headers: CSP, `X-Frame-Options`, `Referrer-Policy`, `X-Content-Type-Options`, and `Permissions-Policy`

## Host allow-list

When binding to `0.0.0.0` or `::`, public mode requires at least one host users will actually browse to:

```bash
hermes dashboard --host 0.0.0.0 --public \
  --allowed-host agents.example.lan \
  --allowed-host 192.168.1.50
```

Requests with any other `Host` header are rejected. This keeps DNS rebinding protections active even when the server listens on all interfaces.

## HTTPS reverse proxy

Recommended production shape:

1. Keep Hermes bound to localhost or a private interface.
2. Put Caddy, nginx, or another TLS reverse proxy in front.
3. Pass the original `Host` header through.
4. Use `--secure-cookies` when external access is HTTPS.

Example:

```bash
hermes dashboard \
  --host 127.0.0.1 \
  --port 9119 \
  --public \
  --allowed-host agents.example.com \
  --secure-cookies \
  --no-open
```

Caddy example:

```caddy
agents.example.com {
  reverse_proxy 127.0.0.1:9119
}
```

If your proxy sends `X-Forwarded-Proto: https`, Hermes can also infer secure cookies. Use `--no-trust-proxy` to ignore proxy headers.

## Legacy insecure mode

`--insecure` still exists for backwards-compatible trusted-network debugging:

```bash
hermes dashboard --host 0.0.0.0 --insecure --no-open
```

Do not use it on untrusted networks. It keeps the legacy token-in-HTML behavior so older bundles continue to work, but anyone who can fetch the served page can obtain the token for that server process.

## Resetting dashboard users

Dashboard users are local to the active Hermes home/profile:

```bash
rm "$HERMES_HOME/dashboard-users.yaml"
```

Restart `hermes dashboard --public`; the first browser visit will show the setup form again.
