## What does this PR do?

Fixes #40296 — Model displayed in UI/footer differs from config.yaml when using Nous provider.

**Problem:** Nous Portal is a unified subscription gateway that dynamically routes requests across 300+ models. When users configure `model.default: stepfun/step-3.7-flash:free` with `provider: nous`, the API returns a different model (e.g., `nvidia/nemotron-3-ultra:free`) but the UI displayed the routed model instead of the configured one, creating confusion.

**Solution:** Track both the user's configured model (`configured_model`) and the actual routed model (`routed_model`) end-to-end, and display both transparently when they differ.

## Type of Change

- [x] 🐛 Bug fix (non-breaking change that fixes an issue)

## Changes Made

### CLI (`cli.py`)
- Added `configured_model` field to store original config.yaml model at startup
- Added `routed_model` field updated by Agent after API responses
- Status bar now shows `configured → routed` when they differ (e.g., `step-3.7-flash:free → nemotron-3-ultra:...`)
- `show_config()` displays `Routed: model (via Nous Portal)` 
- Session status shows `Model: configured → routed (provider)`
- Mid-session `/model` switch updates `configured_model` automatically

### Agent Core
- `agent/agent_init.py`: Initialize `configured_model = model`, `routed_model = None`
- `agent/conversation_loop.py`: Capture `response.model` for Nous provider, store in `agent.routed_model`, debug log routing decisions

### Gateway / Desktop
- `tui_gateway/server.py`: Emit `configured_model` + `routed_model` in `session.info` events
- `ui-tui/src/types.ts`: Extended `SessionInfo` with both fields
- `ui-tui/src/components/appLayout.tsx`: Pass both to `StatusRule`
- `ui-tui/src/components/appChrome.tsx`: Added `buildModelDisplay()` helper showing `configured → routed` when different

### Tests
- Updated `appChromeStatusRule.test.tsx` with new required props

## How to Test

1. **CLI**: Configure `model.default: stepfun/step-3.7-flash:free` + `provider: nous` in config.yaml, start Hermes, observe status bar shows `step-3.7-flash:free → nemotron-3-ultra:...`
2. **Desktop**: Same config, open TUI, status bar shows dual-model display
3. **Mid-session switch**: Run `/model anthropic/claude-opus-4.8`, verify `configured_model` updates and display tracks new intent
4. **`/config` command**: Shows `Routed: nvidia/nemotron-3-ultra:free (via Nous Portal)`
5. **Session status**: Shows `Model: stepfun/step-3.7-flash:free → nvidia/nemotron-3-ultra:free (nous)`

## Checklist

### Code
- [x] I've read the Contributing Guide
- [x] Commit messages follow Conventional Commits
- [x] Searched for existing PRs — addressed issue #40296
- [x] PR contains only changes related to this fix
- [x] Added tests for new props in StatusRule
- [x] Core test suites pass: `tests/cli/test_cli_provider_resolution.py`, `tests/cli/test_cli_status_bar.py`, `tests/agent/test_model_metadata.py`, `tests/hermes_cli/test_runtime_provider_resolution.py` (all 600+ tests pass)
- [x] TypeScript compiles clean for modified files

### Tests
Note: Pre-existing failure in `test_personality_none.py` (unrelated to this change — gateway personality feature). All relevant tests pass.