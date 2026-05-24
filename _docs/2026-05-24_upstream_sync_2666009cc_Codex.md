# 2026-05-24 Upstream Sync 2666009cc

## Scope

- Target worktree: `C:\Users\downl\Desktop\hermes-agent-upstream-sync`
- Target branch: `main`
- Official upstream: `upstream/main` at `2666009ccc00f653a1db4ff249c9b1aabdb34f13`
- Fork base before merge: `24ad08bb5d7e6318aa31733b771566b1b3c6d228`
- Merge driver: `scripts/sync_all.py --merge --target main --allow-preflight-blockers --skip-fetch`

## Merge Policy

- Official upstream changes were taken first for latest features, security maintenance, and bug fixes.
- Fork-only behavior was preserved through the scripted overlay policy.
- Manual follow-up focused on Windows runtime correctness, local OpenCode fallback behavior, gateway media path safety, and development dependency completeness.

## Local Follow-Up

- Added missing dev extra libraries through uv metadata:
  - `aiohttp==3.13.3`
  - `pywinpty==2.0.15 ; sys_platform == 'win32'`
  - `ptyprocess==0.7.0 ; sys_platform != 'win32'`
- Kept `uv.lock` minimal by adding only the new dev extra references. The broad lockfile metadata rewrite from an older PATH uv binary was discarded.
- Fixed Windows PTY stdin handling:
  - pywinpty writes strings, while ptyprocess writes bytes.
  - Windows PTY submit uses carriage return.
  - Windows PTY EOF uses Ctrl+Z plus Enter.
- Preserved fork-specific OpenCode free fallback sentinel handling in fallback configuration.
- Preserved fallback provider chain compatibility for `fallback_providers` plus legacy `fallback_model`.
- Extended `MEDIA:` path filtering for Windows drive-letter paths.
- Repaired TUI Windows verification issues introduced by the upstream merge:
  - platform-specific terminal config path joining
  - slash voice TTS state wiring
  - editor fallback tests with explicit POSIX platform coverage
  - hermes-ink child-process typing under current Node types
  - slower Windows cursor regression timeout

## Verification

- `uv lock --check`
- `uv run --extra dev --no-editable python -c "import aiohttp, winpty"`
- `uv run --extra dev --no-editable ruff check ...`
- `uv run --extra dev --no-editable pytest ... tests/tools/test_send_message_tool.py tests/tools/test_process_registry.py tests/hermes_cli/test_fallback_cmd.py`
  - Result: 212 passed, 5 skipped
- Earlier focused Python suites during this sync:
  - OpenCode/fallback/security focus: 291 passed, 4 skipped
  - Discord gateway focus: 116 passed
  - Security/Bitwarden/process focus: 236 passed, 7 skipped
  - Gateway/runtime/provider focus: 404 passed, 7 skipped
- `npm ci` in `web`
- `npm ci` in `ui-tui`
- `npm run build` in `web`
- `npm run build` in `ui-tui/packages/hermes-ink`
- `npm run build` in `ui-tui`
- `npm test` in `ui-tui`
  - Result: 838 passed, 8 skipped
- `npm run type-check` in `ui-tui`
- `npm audit --omit=dev --json` in `web`
  - Result: 0 production vulnerabilities
- `npm audit --omit=dev --json` in `ui-tui`
  - Result: 0 production vulnerabilities
- `git diff --check`

## Known Residuals

- Full `npm run lint` still reports pre-existing or upstream-wide style/rule failures outside the narrow repair set. Targeted lint for the files touched in this follow-up has no errors.
- Web production build succeeds, with Vite's existing large chunk warning.
- `docs/CONTRACTS.md` and `CHANGELOG.md` were not present in this repository checkout despite the local agent instructions naming them.
