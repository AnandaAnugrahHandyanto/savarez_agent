# Hermes Migration Plan

Last updated: May 14, 2026, 2:23 PM EDT

## Goal

Make Hermes the active owner for migrated commands, runtime outputs, logs,
generated artifacts, cron outputs, Telegram delivery paths, profiles, local
model assets, and local state. Treat `/Users/admin/.hermes` as the Hermes
runtime home and `/Users/admin/.hermes/hermes-agent` as the git project.

## Execution Plan

1. Capture live state from `/Users/admin/.hermes/hermes-agent`.
   - `pwd`
   - `git status --short`
   - `hermes status`
   - `hermes profile list`
   - `launchctl print gui/$(id -u)/ai.hermes.gateway`
   - `launchctl print gui/$(id -u)/local.qwen-mlx-11435`
   - `find /Users/admin/.hermes -maxdepth 3 -type d -name profiles -print`
   - model endpoint probes

2. Inventory active Claw/OpenClaw dependencies.
   - LaunchAgents
   - Active processes
   - Hermes cron jobs
   - Hermes Telegram/plugin bridge paths
   - Runtime env, output roots, and model roots

3. Redirect high-confidence migrated surfaces to Hermes-owned state.
   - Hermes Telegram command bridge
   - Voice memo bridge
   - Stock/video generated artifacts
   - Stock/video transcription model roots
   - Qwen MLX launchd wrapper, cwd, logs, model path, and served model id
   - Bonsai/OpenClaw residual LaunchAgent state

4. Preserve runtime profiles.
   - Do not move, delete, recreate, or overwrite `/Users/admin/.hermes/profiles`.
   - Document profile gateway state and profile-owned logs/state.

5. Verify after each meaningful change.
   - Syntax/compile checks for wrappers and plugin code
   - Focused stock/video tests
   - Hermes gateway restart and status checks
   - Dry-run bridge dispatch checks
   - Output-path help/state checks
   - LaunchAgent and port checks
   - Direct MLX endpoint and Hermes provider/alias smokes
   - Minimal transcription smoke

6. Document final classification.
   - Migrated to Hermes
   - Legacy Claw source/config responsibility
   - Stale or disabled OpenClaw/Bonsai state
   - Optional future cleanup needing approval

## In Scope

- Hermes default gateway `ai.hermes.gateway`
- Hermes profiles under `/Users/admin/.hermes/profiles`
- Hermes cron jobs and cron output
- Migrated Telegram command paths for `/activitymonitor`, `/birdclaw`,
  `/videosummary`, `/videosummarize`, `/stockupdates`, and `/voicememo`
- Local Qwen MLX service runtime ownership and Hermes-owned model asset
- Hermes-owned `distil-large-v3` transcription model root
- OpenClaw gateway/watchdog/Bonsai residual service audit

## Out of Scope

- Discord migration or Discord config inspection
- Deleting OpenClaw/Claw source trees
- Migrating unrelated legacy apps such as AutoResearch without explicit approval
- Moving or rewriting Hermes profiles
- Migrating the active Ollama blob store without a separate service window

## Completion State

The in-scope migration is complete. The remaining work is optional cleanup:
archive/delete preserved source model copies after explicit approval, decide
whether to migrate the active Ollama blob store, and decide whether the active
AutoResearch dashboard should remain in Claw or move under Hermes.
