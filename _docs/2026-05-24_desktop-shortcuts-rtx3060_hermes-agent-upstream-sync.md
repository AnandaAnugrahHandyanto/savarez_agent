# Desktop Shortcuts RTX3060 Refresh

## Overview

Desktop Hermes shortcuts were refreshed so the generated launchers target the current `hermes-agent-upstream-sync` checkout and the active RTX3060 llama.cpp fallback path.

## Background / requirements

- User request: rewrite the desktop shortcut.
- Existing generated shortcuts under `C:\Users\downl\Desktop\Hermes Agent` still exposed `Hermes Llama Fallback (RTX3080).lnk`.
- Gateway launch paths still called `hermes_cli gateway run` without `--replace`, which was less suitable for repairing stale gateway runtime state.
- The active local fallback now uses `start-hermes-llama-fallback-rtx3060.ps1` with a 64K context.

## Assumptions / decisions

- Keep the generated shortcut folder model: `C:\Users\downl\Desktop\Hermes Agent`.
- Keep the RTX3080 fallback script available for legacy/manual use, but stop making it the default desktop/autostart launcher.
- Regenerate shortcuts from `scripts/create-hermes-desktop-shortcuts.ps1` instead of editing `.lnk` files by hand.

## Changed files

- `scripts/create-hermes-desktop-shortcuts.ps1`
- `scripts/windows/start-hermes-gateway.ps1`
- `scripts/windows/register-hermes-autostart.ps1`
- `scripts/windows/start-hermes-stack.ps1`
- `AGENTS.md`

## Implementation details

- Added `Hermes Llama Fallback (RTX3060).lnk` as the generated fallback shortcut.
- Treated old owned shortcut names inside `Desktop\Hermes Agent` as stale so the RTX3080 shortcut is removed during regeneration.
- Updated Gateway and Stack launch commands to use `gateway run --replace`.
- Updated Gateway and autostart fallback selection to use `start-hermes-llama-fallback-rtx3060.ps1`.
- Updated the local workspace fact in `AGENTS.md`.

## Commands run

- `git status --short --branch`
- `Get-Content` / `Select-String` inspections for shortcut and autostart scripts.
- `git diff --check`
- PowerShell parser validation for changed scripts.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\create-hermes-desktop-shortcuts.ps1 -DesktopRoot`
- COM-based `.lnk` target verification using `WScript.Shell.CreateShortcut(...)`.
- `.venv\Scripts\hermes.exe gateway run --help`
- `Get-ScheduledTask -TaskName HermesLlamaFallbackRTX3060,HermesLlamaFallbackRTX3080,HermesGatewayAutoStart`

## Test / verification results

- PowerShell parser validation passed for:
  - `scripts/create-hermes-desktop-shortcuts.ps1`
  - `scripts/windows/start-hermes-gateway.ps1`
  - `scripts/windows/register-hermes-autostart.ps1`
  - `scripts/windows/start-hermes-stack.ps1`
  - `scripts/windows/start-hermes-llama-fallback-rtx3060.ps1`
- `git diff --check` passed with only existing Git line-ending warnings.
- Shortcut regeneration succeeded.
- `C:\Users\downl\Desktop\Hermes Agent\Hermes Llama Fallback (RTX3060).lnk` points to `scripts\windows\start-hermes-llama-fallback-rtx3060.ps1`.
- No `*RTX3080*.lnk` remained under `C:\Users\downl\Desktop\Hermes Agent`.
- `C:\Users\downl\Desktop\Hermes Agent\Hermes Gateway.lnk` points to `scripts\windows\start-hermes-gateway.ps1`.
- `hermes gateway run --help` confirms `--replace` is accepted.
- Read-only Task Scheduler inspection showed `HermesLlamaFallbackRTX3080` and `HermesGatewayAutoStart` are currently registered, while `HermesLlamaFallbackRTX3060` is not yet registered.

## Residual risks

- Existing scheduled tasks were not modified; the current registered llama autostart task is still `HermesLlamaFallbackRTX3080` until the autostart registration shortcut or script is run.
- The legacy RTX3080 script remains in the repository for manual use.

## Recommended next actions

- To update logon autostart, run the generated `Hermes Autostart (register).lnk` once so Task Scheduler receives the RTX3060 task definition and removes the old RTX3080 task.
