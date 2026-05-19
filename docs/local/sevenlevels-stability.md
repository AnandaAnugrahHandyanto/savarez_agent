# Sevenlevels Stability Record

Last updated: 2026-05-20

This record is the local stability anchor for the Hermes `sevenlevels` runtime
on this machine. It documents the current patch surface, runtime assumptions,
validation commands, and rollback path before more UI or gateway work is added.

## Runtime Anchor

- Source checkout: `C:\Users\Administrator\Documents\Codex\2026-05-12\herms-upstream-20260517`
- WSL runtime tree: `/root/hermes-agent-wsl`
- Profile home: `/mnt/c/Users/Administrator/.hermes/profiles/sevenlevels`
- Dashboard URL: `http://127.0.0.1:9122/chat`
- Status endpoint: `http://127.0.0.1:9122/api/status`
- Expected version: `0.13.0` / `2026.5.7`
- Current gateway policy: preserve the running gateway unless the user explicitly
  asks to stop or restart it.
- Current dashboard policy: restart only after a confirmed plan, then verify the
  `sevenlevels` profile through `/api/status`.

## Current Patch Manifest

Snapshot commands:

```powershell
git status --short
git diff --stat
```

Current local patch surface at this snapshot: 19 modified files, approximately
2399 insertions and 367 deletions before adding this stability record.

### Backend API and dashboard server

- Files: `hermes_cli/web_server.py`, `web/src/lib/api.ts`
- Purpose: support dashboard-side session/project APIs, file/paste upload paths,
  and runtime status flows used by the sevenlevels dashboard.
- Main risks: API shape drift between backend and frontend; accidental profile
  leakage if paths are not resolved through the active Hermes home.
- Verification: `npm.cmd run build --prefix web`; targeted Python tests that
  cover `hermes_cli/web_server.py`.
- Runtime status: synced into the sevenlevels dashboard runtime in prior
  iterations.

### Gateway and TUI integration

- Files: `tui_gateway/server.py`, `ui-tui/src/components/appLayout.tsx`,
  `ui-tui/src/components/branding.tsx`, `ui-tui/src/components/textInput.tsx`,
  `ui-tui/src/components/thinking.tsx`, `ui-tui/src/lib/virtualHeights.ts`,
  `ui-tui/src/types.ts`
- Purpose: keep the embedded PTY/TUI as the primary chat surface while improving
  inline dashboard behavior, thinking/status display, sizing, and composer
  usability.
- Main risks: terminal focus regressions, copy/paste regressions, long-text
  submission stalls, and hidden duplicate input surfaces.
- Verification: `npm.cmd run build --prefix ui-tui`; manual check in
  `http://127.0.0.1:9122/chat`.
- Runtime status: synced into the sevenlevels dashboard runtime in prior
  iterations.

### Dashboard session navigation

- Files: `web/src/components/ChatSessionNavigator.tsx`,
  `web/src/components/ChatSidebar.tsx`, `web/src/main.tsx`, `web/index.html`
- Purpose: add Codex-like session/project navigation, project menu actions,
  selected-session affordances, and translation-resistant shell behavior.
- Main risks: stale/mirrored sessions causing startup scanning, sidebar API
  failures obscuring the active PTY, and browser translation changing visible
  labels.
- Verification: `npm.cmd run build --prefix web`; `/api/status` remains healthy
  after dashboard refresh.
- Runtime status: synced into the sevenlevels dashboard runtime in prior
  iterations.

### Chat controls, upload, and clipboard

- Files: `web/src/pages/ChatPage.tsx`, `web/src/components/ChatModelControl.tsx`
- Purpose: provide model control near the composer, file/paste upload prompts,
  selection-to-chat, drag/drop support, copy-last-response, and stop controls
  without replacing the embedded TUI transcript/composer.
- Main risks: creating a second chat surface, stealing focus from xterm, or
  breaking normal Ctrl+C/Ctrl+V behavior.
- Verification: `npm.cmd run build --prefix web`; manual check for one visible
  Hermes input surface, file upload prompt injection, and selection copy.
- Runtime status: synced into the sevenlevels dashboard runtime in prior
  iterations.

### CLI, banner, and tests

- Files: `cli.py`, `hermes_cli/banner.py`,
  `tests/hermes_cli/test_banner.py`, `tests/test_tui_gateway_server.py`,
  `ui-tui/src/__tests__/virtualHeights.test.ts`
- Purpose: support the sevenlevels presentation and lock critical behavior with
  targeted tests.
- Main risks: tests becoming change-detectors instead of behavioral invariants;
  CLI changes diverging from dashboard/TUI behavior.
- Verification:

```bash
scripts/run_tests.sh tests/test_tui_gateway_server.py tests/hermes_cli/test_banner.py -q
npm.cmd run build --prefix ui-tui
```

## Validation Checklist

Run these after any confirmed implementation that changes dashboard, TUI, or
runtime behavior:

```powershell
git status --short
git diff --stat
npm.cmd run build --prefix web
npm.cmd run build --prefix ui-tui
```

For backend behavior, run targeted tests from WSL using the project wrapper:

```bash
scripts/run_tests.sh tests/test_tui_gateway_server.py tests/hermes_cli/test_banner.py -q
```

For runtime behavior, verify:

```powershell
Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:9122/api/status -TimeoutSec 8
```

Expected runtime evidence:

- `hermes_home` is `/mnt/c/Users/Administrator/.hermes/profiles/sevenlevels`.
- `gateway_running` is `true`.
- Gateway PID is preserved unless the confirmed plan explicitly changed it.
- Dashboard serves `http://127.0.0.1:9122/chat`.

## Latest Validation Notes

2026-05-20 validation for this stability pass:

- `npm.cmd run build --prefix web`: passed.
- `npm.cmd run build --prefix ui-tui`: passed.
- `/api/status`: passed; runtime reported `hermes_home` as
  `/mnt/c/Users/Administrator/.hermes/profiles/sevenlevels`, gateway running,
  and gateway PID `17370`.
- Direct checkout test using the runtime venv passed:

```bash
cd /mnt/c/Users/Administrator/Documents/Codex/2026-05-12/herms-upstream-20260517
PYTHONPATH=. /root/hermes-agent-wsl/.venv/bin/python -m pytest \
  tests/test_tui_gateway_server.py tests/hermes_cli/test_banner.py -q
```

Result: `185 passed`.

Known validation caveat: executing the CRLF `scripts/run_tests.sh` directly
inside WSL fails before tests run. A temporary no-CRLF copy in
`/root/hermes-agent-wsl` runs the script but currently fails two
`model.options` tests because the runtime tree is missing
`/root/hermes-agent-wsl/hermes_cli/inventory.py`, while the source checkout does
contain `hermes_cli/inventory.py`. Treat that as a runtime sync/state mismatch,
not as evidence that this documentation-only stability pass broke tests.

2026-05-20 runtime sync consistency pass:

- Confirmed the WSL runtime tree `/root/hermes-agent-wsl` was not a Git checkout
  and had drifted from the Windows source checkout.
- Synced only allowlisted source/test files from the source checkout into the
  runtime tree. No `.env`, profile, session, venv, cache, or `node_modules`
  paths were touched.
- Filled three missing runtime files:
  `hermes_cli/inventory.py`,
  `web/src/components/ChatModelControl.tsx`, and
  `web/src/components/ChatSessionNavigator.tsx`.
- A follow-up failed test showed another runtime drift:
  `tools/process_registry.py` in the runtime tree lacked
  `format_process_notification`; that single file was backed up and synced from
  the source checkout.
- Runtime backup roots:
  `C:\Users\ADMINI~1\AppData\Local\Temp\hermes-runtime-sync-backup-20260520-030209`
  and
  `C:\Users\ADMINI~1\AppData\Local\Temp\hermes-runtime-sync-backup-process-registry-20260520-030714`.
- Allowlisted source/runtime hashes matched after sync, including
  `tools/process_registry.py`.
- `hermes_cli/web_dist/index.html` and `ui-tui/dist/entry.js` matched between
  the source checkout and runtime tree after the builds, so no built asset sync
  was needed.
- Runtime tree targeted tests now pass:

```bash
cd /root/hermes-agent-wsl
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_tui_gateway_server.py tests/hermes_cli/test_banner.py -q
```

Result: `185 passed`.

- `npm.cmd run build --prefix web`: passed with the existing Vite large chunk
  warning.
- `npm.cmd run build --prefix ui-tui`: passed.
- `/api/status`: passed; `hermes_home` remained
  `/mnt/c/Users/Administrator/.hermes/profiles/sevenlevels`, gateway remained
  running, and gateway PID remained `17370`.
- The gateway was not restarted.

## Rollback Path

Do not use destructive reset commands casually. If a confirmed change breaks the
runtime:

1. Stop and record the symptom, dashboard PID, gateway PID, status JSON, and
   latest dashboard log path.
2. Prefer reverting only the last confirmed patch with `git diff`/`git apply -R`
   or a targeted follow-up patch.
3. Rebuild only the affected frontend/TUI bundle.
4. Resync only the affected built assets into `/root/hermes-agent-wsl`.
5. Restart only the dashboard process unless the confirmed plan explicitly
   requires a gateway restart.
6. Re-check `/api/status` before making more changes.

## Future Change Gate

Every future Hermes implementation should follow this order:

1. Read-only grounding: current diff, relevant files, runtime status.
2. Proposed plan: exact scope, touched subsystems, tests, runtime actions.
3. User confirmation.
4. Implementation in the smallest safe slice.
5. Build/test/status verification.
6. Update this record if the patch surface, runtime status, or rollback path
   changed.

No new UI feature work should be added on top of the current patch stack until
this stability record and the change gate are acknowledged in the final summary
of the current implementation.
