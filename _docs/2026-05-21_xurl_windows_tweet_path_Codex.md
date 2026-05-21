# Xurl Windows Tweet Path Closeout

Date: 2026-05-21
Agent: Codex
Repo: hermes-agent

## Overview

Restored the Hermes Agent path for X posting on native Windows. The failure was
layered: the bundled `xurl` skill was Linux/macOS-only, the local installed
skills had a duplicate `xurl` name from an older OpenClaw import, the npm xurl
install left broken wrappers, and the Go xurl binary blocked in the Windows
agent shell.

## Changes

- `skills/social-media/xurl/SKILL.md`
  - Added `windows` to supported platforms.
  - Documented native Windows installation and the Hermes shim fallback.
- `website/docs/user-guide/skills/bundled/social-media/social-media-xurl.md`
  - Mirrored the Windows platform and shim documentation.
- `scripts/xurl_windows.py`
  - Added a Windows-safe xurl subset for Hermes usage.
  - Supports `auth status`, app list/add/default, OAuth2, `whoami`, `post`,
    `reply`, and `quote`.
  - Never prints token values from `~/.xurl`.
- `scripts/install_xurl_windows_shim.ps1`
  - Installs `xurl.cmd` into `%USERPROFILE%\.local\bin`, pointing at the shim.
- `tests/skills/test_xurl_windows.py`
  - Covers Windows platform availability, no-store auth status, and posting
    without leaking token values.

## Local Machine Repair

- Installed the shim at `C:\Users\downl\.local\bin\xurl.cmd`.
- Removed broken wrappers created by the failed npm install:
  `C:\Users\downl\AppData\Roaming\npm\xurl*`.
- Kept the Go-installed binary available as a lower-priority fallback:
  `C:\Users\downl\go\bin\xurl.exe`.
- Updated the installed local Hermes skill:
  `C:\Users\downl\.hermes\skills\social-media\xurl\SKILL.md`.
- Preserved the older OpenClaw-imported xurl skill by renaming its local skill
  name and directory to `openclaw-xurl`.

## Verification

Command resolution:

```text
Get-Command xurl -All
-> C:\Users\downl\.local\bin\xurl.cmd
-> C:\Users\downl\go\bin\xurl.exe
```

Shim smoke tests:

```text
xurl --help
-> xurl Windows shim for Hermes Agent

xurl auth status
-> No apps registered. Use 'xurl auth apps add' to register one.
```

Hermes skill resolution:

```text
skills_list(category='social-media')
-> xurl

skill_view('xurl')
-> success true, path social-media\xurl\SKILL.md, readiness_status available
```

Focused tests passed using H: for pytest temporary files because C: was nearly
full:

```text
python -m pytest tests/skills/test_xurl_windows.py -q -o addopts='' -p no:cacheprovider --basetemp=H:\codex-tmp\hermes-agent-pytest\basetemp
3 passed in 2.66s
```

Final rerun:

```text
Get-Command xurl -All
-> C:\Users\downl\.local\bin\xurl.cmd
-> C:\Users\downl\go\bin\xurl.exe

xurl auth status
-> No apps registered. Use 'xurl auth apps add' to register one.

python -m pytest tests/skills/test_xurl_windows.py -q -o addopts='' -p no:cacheprovider --basetemp=H:\codex-tmp\hermes-agent-final-pytest\basetemp
3 passed in 2.36s
```

## OAuth Callback Follow-up

The in-app browser showing `ERR_CONNECTION_REFUSED` at
`http://localhost:8080/callback` was expected while no OAuth callback server was
running. Verification showed:

```text
Get-NetTCPConnection -LocalPort 8080 -State Listen
-> NO_LISTENER_8080

xurl auth status
-> No apps registered. Use 'xurl auth apps add' to register one.
```

Updated `scripts/xurl_windows.py` so `xurl auth apps add` can prompt for the
client secret when `--client-secret` is omitted. This avoids putting the secret
in chat text, process arguments, or shell history.

```text
xurl --help
-> xurl auth apps add APP --client-id ID [--client-secret SECRET] [--redirect-uri URI]

python -m pytest tests/skills/test_xurl_windows.py -q -o addopts='' -p no:cacheprovider --basetemp=H:\codex-tmp\hermes-agent-xurl-prompt-pytest\basetemp
4 passed in 5.79s
```

Follow-up recovery after placeholder commands were run:

```text
Get-CimInstance Win32_Process -Filter "ProcessId=..."
-> python ... scripts\xurl_windows.py auth oauth2 --app hermes YOUR_X_HANDLE

xurl auth status
-> > hermes [client_id: YOUR_CLI...], oauth2: (none)
```

Stopped the placeholder OAuth listener, added placeholder rejection guards for
client id, client secret, and username values, added `xurl auth apps remove APP`,
and removed the bad local `hermes` app registration.

```text
python -m pytest tests/skills/test_xurl_windows.py -q -o addopts='' -p no:cacheprovider --basetemp=H:\codex-tmp\hermes-agent-xurl-placeholder-pytest\basetemp
6 passed in 2.51s

xurl auth apps remove hermes
-> App "hermes" removed.

xurl auth status
-> No apps registered. Use 'xurl auth apps add' to register one.

Get-NetTCPConnection -LocalPort 8080 -State Listen
-> NO_LISTENER_8080
```

Follow-up for public OAuth2/PKCE clients:

The user reported that X OAuth did not provide a client secret. Confirmed from
the current X docs that PKCE supports public clients, and changed the Windows
shim so client secret is optional by default. Confidential clients can still
pass `--client-secret` or use `--prompt-client-secret`.

```text
xurl auth apps add hermes --client-id zapabob_ouj
-> App "hermes" registered successfully.

xurl auth status
-> > hermes [client_id: zapabob_...], oauth2: (none)

python -m pytest tests/skills/test_xurl_windows.py -q -o addopts='' -p no:cacheprovider --basetemp=H:\codex-tmp\hermes-agent-xurl-no-secret-final-pytest\basetemp
8 passed in 2.38s
```

Also added `xurl auth oauth2 --app APP [USER] --no-browser` and made the shim
always print the authorization URL, so the user can paste it into the in-app
browser while the local callback server is running.

Follow-up for X authorization denial:

The user reached X's consent screen but saw that app access could not be
granted. The active OAuth listener used the previous broad scope set, so it was
stopped and the default scopes were reduced to the minimum required for posting
plus refresh:

```text
tweet.read tweet.write users.read offline.access
```

This follows the X API v2 authentication mapping for `POST /2/tweets`, which
requires `tweet.read`, `tweet.write`, and `users.read`; `offline.access` is kept
only so refresh tokens can be issued.

```text
python -m pytest tests/skills/test_xurl_windows.py -q -o addopts='' -p no:cacheprovider --basetemp=H:\codex-tmp\hermes-agent-xurl-min-scope-pytest\basetemp
9 passed in 3.09s

Get-NetTCPConnection -LocalPort 8080 -State Listen
-> NO_LISTENER_8080
```

Follow-up after WSL2 recovery:

Installed the normal upstream Linux xurl CLI inside WSL2 using the official
installer. This path avoids the native-Windows Go binary hang.

```text
wsl --exec sh -lc 'curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash'
-> Installed /home/downl/.local/bin/xurl

wsl --exec bash -lc 'export PATH="$HOME/.local/bin:$PATH"; xurl auth status'
-> No apps registered. Use 'xurl auth apps add' to register one.
```

Important constraint: upstream xurl currently requires `--client-secret` for
`xurl auth apps add`. For an X public OAuth2/PKCE client with no secret, use the
Hermes Windows shim path; for the normal upstream xurl path, configure/copy a
client secret in the X Developer Portal and run the app registration inside
WSL2.

## Residual Risks

- `~/.xurl` does not currently exist, so there is no registered X app/token on
  this machine. Actual tweeting is ready after the user registers credentials
  and completes OAuth outside the agent session.
- Some stale exited `xurl.exe` process entries from earlier failed shell runs
  may remain visible briefly in CIM/task listings, but the active `xurl`
  command now resolves to the Python shim and returns promptly.

## Git Closeout

The implementation was split into separate commits to keep unrelated concerns
reviewable:

```text
python -m pytest tests/skills/test_xurl_windows.py tests/gateway/test_config.py::TestLinePluginEnvEnablement tests/hermes_cli/test_status.py::test_show_status_discovers_plugin_platforms -q -o addopts='' -p no:cacheprovider --basetemp=H:\codex-tmp\hermes-agent-commit-pytest\basetemp
-> 11 passed in 3.47s

git commit -m "fix: support xurl on Windows and WSL"
-> a9016d921

git commit -m "fix: surface plugin platform status"
-> f32fd8ae7

git push origin main
-> c4002c929..f32fd8ae7 main -> main

git status --short --branch
-> ## main...origin/main
```

The `_docs/` directory is ignored in this repository for local implementation
notes. This file is intentionally force-added as the durable implementation log
for the Windows/WSL xurl closeout requested by the user.
