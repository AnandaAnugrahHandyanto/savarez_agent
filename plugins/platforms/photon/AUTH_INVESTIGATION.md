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

8. Checked the current published Photon CLI package and public OpenAPI docs.

   Findings:

   - `@photon-ai/cli@0.4.0` is still the latest npm release as of
     2026-05-28.
   - The bundled CLI login code polls `/api/auth/device/token`, reads only
     `data.access_token`, saves that value, and validates login with
     `getSession`.
   - The bundled CLI project commands use that same saved value as
     `Authorization: Bearer <token>` for dashboard `/api/projects` calls.
   - The dashboard OpenAPI says `/api/projects/` uses bearer auth from the
     device login flow, but its token endpoint description says
     `set-auth-token` carries the bearer token.
   - The current hosted response observed by Hermes returns body-level
     `access_token` and no `set-auth-token` header.

   Outcome: there is no additional client-side token exchange visible in the
   published CLI or OpenAPI. The public sources disagree on whether the usable
   token is the body `access_token` or the `set-auth-token` header, so Hermes
   now treats every token-like value as a candidate but saves only a candidate
   that validates against `/api/projects/`.

9. Tried all token candidates from the device-token response.

   Implementation:

   - collect body `access_token`
   - collect body `accessToken`
   - collect nested `data.access_token`
   - collect nested `data.accessToken`
   - collect `set-auth-token` response header, if present
   - strip a leading `Bearer ` prefix if Photon ever returns one
   - dedupe candidates without logging or printing token bytes
   - validate each candidate against `/api/auth/get-session` and
     `/api/projects/`
   - save only a candidate that passes the project API check

   Outcome: the hosted response exposed exactly one candidate:
   body-level `access_token`. That token validated the auth session but failed
   `/api/profile` and `/api/projects/`, so there was no project-valid dashboard
   token for Hermes to save.

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
  token candidates : access_token(len=32,dots=0,jwt=no)
Photon auth diagnostics
-----------------------
  env path        : /Users/raysmacbookair/.hermes-photon-install-test/.env
  dashboard host  : https://app.photon.codes
  token source    : access_token
  token           : present (len=32, dots=0, jwt=no)
  endpoint checks :
    - session /api/auth/get-session -> 200 ok; ok; user=yes
    - profile /api/profile -> 401 fail; invalid_token
    - projects /api/projects/ -> 401 fail; invalid_token
login failed: Photon dashboard token was rejected while trying to validate
Photon project API access. Photon returned: invalid_token
```

## What The Endpoint Checks Mean

Hermes is checking three dashboard endpoints with the same bearer token:

```text
Authorization: Bearer <candidate-token>
```

The endpoints are not equivalent.

### Session Validation

`GET /api/auth/get-session` checks whether the token maps to a logged-in
Photon session and user. This is likely handled directly by Better Auth or by a
thin Better Auth wrapper. A `200` with `user=yes` means:

- the device login browser approval worked
- Photon can identify the user for this token
- the token is syntactically and semantically valid for session lookup

It does **not** prove the token is accepted by every Photon API route.

### Dashboard Profile Validation

`GET /api/profile` is a Photon dashboard API route on
`https://app.photon.codes`. It is not a Spectrum API route. It checks whether
the same bearer token is accepted by Photon dashboard API authorization for the
developer/profile surface.

Current result:

```text
/api/profile -> 401 invalid_token
```

That means the dashboard API auth guard rejected the token before Hermes could
use it as a normal authenticated API caller.

### Dashboard Project Validation

`GET /api/projects/` is the dashboard project API Hermes needs for setup. It
lists dashboard projects and returns the Spectrum credentials
(`spectrumProjectId`, `projectSecret`) needed by the rest of the installer.

Current result:

```text
/api/projects/ -> 401 invalid_token
```

This is the blocking failure. If project auth were valid but the user had no
projects, Hermes would expect an empty list or a successful response. If the
user lacked permission for a specific project, Hermes would expect a permission
or not-found style response. Instead, Photon returns `401 invalid_token`, which
means the project API route does not accept the bearer token as valid
authentication at all.

### Spectrum API Auth Is Separate

Do not confuse `/api/profile` with a Spectrum profile endpoint. The failed
profile check above is dashboard `/api/profile` on `app.photon.codes`.

Spectrum runtime/setup APIs live under `https://spectrum.photon.codes` and use
HTTP Basic auth with:

```text
username = spectrumProjectId / PHOTON_PROJECT_ID
password = projectSecret / PHOTON_PROJECT_SECRET
```

Once Hermes already has `PHOTON_PROJECT_ID` and `PHOTON_PROJECT_SECRET`, it can
create users and register webhooks through the Spectrum API without needing the
dashboard device-login token. The dashboard token is only needed to list/create
dashboard projects and fetch project credentials.

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

The current hosted Photon device flow is issuing exactly one token candidate:
a 32-character opaque `access_token`. That token is valid for Better Auth
session lookup but is not accepted as a bearer API token by dashboard
project/profile routes. This is no longer a Hermes credential storage problem,
an active profile `.env` path problem, or an `auth.json` migration problem.

Hermes cannot synthesize a different dashboard project token from the current
response when the only returned candidate is the failing body `access_token`.
If Photon expects a distinct dashboard API bearer, the server needs to return
it from the device-token exchange or document another exchange endpoint. If the
body `access_token` is intended to work, `/api/projects/` and `/api/profile`
need to accept that device-flow token server-side.

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

- `hermes photon login` validates `/api/projects/` before saving any token
  candidate.
- body `access_token`, `accessToken`, `data.access_token`,
  `data.accessToken`, and `set-auth-token` are treated as candidates, but only
  a candidate that works against `/api/projects/` is saved.
- invalid dashboard tokens are cleared during project list/create failures.
- `hermes photon login --debug-auth` provides sanitized debug output.
- `hermes photon diagnose-auth` checks a saved token, if one exists.
- if `PHOTON_PROJECT_ID` and `PHOTON_PROJECT_SECRET` are already present,
  `quick-setup` can continue without dashboard login because Spectrum project
  APIs use HTTP Basic auth with those project credentials.

This is the right behavior until Photon confirms the correct project API token
or fixes project/profile API acceptance for device-flow tokens.

## Follow-Up: Create Project Without Credentials

After the dashboard token began working against `/api/projects/`, setup reached
the next failure:

```text
[2/5] Looking for an existing Photon project...
  No matching Photon project found; creating one for Hermes.
[2/5] Creating Photon project 'Hermes Agent' (spectrum=true, imessage)...
create-project did not return spectrumProjectId + projectSecret.
```

This is a different issue from the original auth failure. It means:

- the saved dashboard token was accepted for project listing
- the saved dashboard token was accepted for project creation
- Photon created or attempted to create the dashboard project
- the create response did not include the Spectrum Basic-auth credentials
  Hermes needs for runtime setup

Hermes cannot create users or register webhooks from only the dashboard project
record. It needs:

```text
PHOTON_PROJECT_ID      = spectrumProjectId
PHOTON_PROJECT_SECRET  = projectSecret
```

The public dashboard OpenAPI says `POST /api/projects/` should return both
`spectrumProjectId` and `projectSecret` when `spectrum: true`. The published
Photon CLI does not rely on create-project returning a secret; it has a
separate `POST /api/projects/{id}/regenerate-secret` command for rotating and
printing the Spectrum API secret.

Hermes now handles the create-project response more defensively:

1. `POST /api/projects/` with `spectrum: true`.
2. If the response lacks credentials, `GET /api/projects/{id}`.
3. If the new project still lacks `projectSecret`, call
   `POST /api/projects/{id}/regenerate-secret`.
4. Merge those sanitized response shapes internally.
5. Save only `spectrumProjectId` / `projectSecret`; never print the secret.

This recovery path is limited to newly-created projects. For existing projects,
Hermes should not silently rotate a secret that may already be used by other
integrations.
`
