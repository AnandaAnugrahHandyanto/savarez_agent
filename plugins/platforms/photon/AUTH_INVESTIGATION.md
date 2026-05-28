# Photon Auth Investigation

Date: 2026-05-28

This note records the Photon dashboard/device auth investigation for the
Hermes Photon installer. It is intentionally sanitized: no dashboard token,
session token, project secret, or device user code is included.

## Goal

Make `hermes photon login` return and persist a Photon dashboard token that can
be used by the installer to:

- list dashboard projects with `GET /api/projects/`
- create a dashboard/Spectrum project with `POST /api/projects/`
- continue through `hermes photon quick-setup`

## Starting Failure

The installer could complete the device login browser approval, but setup later
failed when it tried to list or create projects:

```text
[2/5] Looking for an existing Photon project...
Photon dashboard token was rejected while trying to list Photon projects.
Photon returned: invalid_token
```

The same failure occurred with explicit project creation:

```text
[2/4] Creating new Photon project 'Hermes Agent' (spectrum=true, imessage)...
create-project failed: Client error '401 Unauthorized' for url
'https://app.photon.codes/api/projects/'
```

## Things Tried

1. Removed legacy `auth.json` as a credential source.

   Outcome: This worked as intended. Photon dashboard tokens now live only in
   the active Hermes profile `.env` as `PHOTON_DASHBOARD_TOKEN`.

2. Verified the active env path.

   Outcome: The path was not the root problem. With
   `HERMES_HOME=$HOME/.hermes-photon-install-test`, login writes to:

   ```text
   /Users/raysmacbookair/.hermes-photon-install-test/.env
   ```

3. Rejected `set-auth-token` as the saved token.

   Outcome: This removed a false positive. The short session header can pass
   some Better Auth session checks but is not accepted by dashboard project
   APIs.

4. Rejected generic `token` and `session.token` response fields.

   Outcome: This removed another false positive. Hermes now only accepts
   `access_token`, `accessToken`, `data.access_token`, or `data.accessToken`
   from the device-token response body.

5. Added token validation before saving.

   Outcome: Login no longer reports success unless the token also works against
   `/api/projects/`. This prevents saving a token that will immediately break
   setup.

6. Added sanitized diagnostics.

   Outcome: `hermes photon login --debug-auth` now prints response shape, token
   shape, token source, and endpoint status without printing token bytes.

7. Compared against the published Photon CLI.

   Findings from `@photon-ai/cli@0.4.0`:

   - client id: `photon-cli`
   - scope: `openid profile email`
   - device code endpoint: Better Auth device code flow
   - token polling accepts `data.access_token`
   - project API calls send `Authorization: Bearer <token>`
   - the official CLI validates login with `getSession`, not with
     `/api/projects/`

   Outcome: Hermes is now aligned with the official CLI token field and bearer
   header shape. The remaining failure is specifically that the token accepted
   by session lookup is rejected by project/profile APIs.

## Current Diagnostic Result

Running:

```bash
export HERMES_HOME="$HOME/.hermes-photon-install-test"
hermes photon login --debug-auth
```

Observed:

```text
Photon login debug
------------------
  device token POST : 200 json=yes
  body keys         : access_token, expires_in, scope, token_type
  data keys         : -
  session keys      : -
  user object       : no
  set-auth-token    : no
  selected token    : access_token (len=32, dots=0, jwt=no)
Photon auth diagnostics
-----------------------
  env path        : /Users/raysmacbookair/.hermes-photon-install-test/.env
  dashboard host  : https://app.photon.codes
  token           : present (len=32, dots=0, jwt=no)
  endpoint checks :
    - session /api/auth/get-session -> 200 ok; ok; user=yes
    - profile /api/profile -> 401 fail; invalid_token
    - projects /api/projects/ -> 401 fail; invalid_token
login failed: Photon dashboard token was rejected while trying to validate
Photon project API access. Photon returned: invalid_token
```

## What Worked

- Device authorization itself works.
- The token endpoint returns HTTP 200 after approval.
- The token endpoint returns a body-level `access_token`.
- That `access_token` authenticates `/api/auth/get-session`.
- Hermes correctly avoids storing the token after `/api/projects/` rejects it.
- Diagnostics show enough information to distinguish session-valid tokens from
  project-api-valid tokens without leaking secret material.

## What Failed

- The returned `access_token` is a 32-character opaque token, not a JWT.
- `/api/profile` rejects the token with `401 invalid_token`.
- `/api/projects/` rejects the token with `401 invalid_token`.
- Because `/api/projects/` fails, Hermes cannot safely list existing projects
  or create a new project during setup.

## What This Shows

The current hosted Photon device flow is issuing a token that is valid for
Better Auth session lookup but not valid for dashboard project/profile APIs.
This is no longer a Hermes credential storage problem and no longer an
`auth.json` migration problem.

Most likely interpretations:

- Photon is returning a Better Auth session-style opaque access token from
  `/api/auth/device/token`, while `/api/projects/` expects a different API
  bearer token.
- Or `/api/projects/` is not configured to accept device-flow access tokens,
  despite the API docs/CLI indicating that device-flow bearer auth should work.
- Or the official Photon CLI has the same latent issue, because it only checks
  `getSession` during login and may not discover the problem until the first
  project command.

## Open Question For Photon

Ask Photon which token should be used for dashboard project APIs after device
login.

Minimal repro to send:

```text
1. Request device code as client_id=photon-cli, scope="openid profile email".
2. Approve in browser.
3. Poll /api/auth/device/token.
4. Response has body keys:
   access_token, expires_in, scope, token_type
5. Use Authorization: Bearer <access_token>.
6. /api/auth/get-session returns 200 with user.
7. /api/profile returns 401 invalid_token.
8. /api/projects/ returns 401 invalid_token.
```

Do not send token bytes. Token shape is enough:

```text
len=32, dot_count=0, looks_jwt=false
```

## Current Hermes Behavior

Hermes now fails closed:

- `hermes photon login` validates `/api/projects/` before saving the token.
- invalid dashboard tokens are cleared during project list/create failures.
- `hermes photon login --debug-auth` provides sanitized debug output.
- `hermes photon diagnose-auth` checks a saved token, if one exists.

This is the right behavior until Photon confirms the correct project API token
or fixes project/profile API acceptance for device-flow tokens.
