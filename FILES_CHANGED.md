# Files Changed — Issue #40296 Fix

## Python Backend (5 files)

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `cli.py` | ~80 | Track `configured_model`/`routed_model`, update on `/model` switch, display in status bar, `/config`, session status |
| `agent/agent_init.py` | ~8 | Initialize `configured_model` + `routed_model` |
| `agent/conversation_loop.py` | ~15 | Capture `response.model` for Nous, store in `agent.routed_model`, debug log |
| `tui_gateway/server.py` | ~5 | Emit both fields in `session.info` |

## TypeScript Frontend (4 files)

| File | Lines Changed | Purpose |
|------|--------------|---------|
| `ui-tui/src/types.ts` | ~8 | Extend `SessionInfo` with `configured_model` + `routed_model` |
| `ui-tui/src/components/appLayout.tsx` | ~4 | Pass both to `StatusRule` |
| `ui-tui/src/components/appChrome.tsx` | ~20 | `buildModelDisplay()` helper, dual-model rendering |
| `ui-tui/src/__tests__/appChromeStatusRule.test.tsx` | ~6 | Add new required props |

## Test Coverage

| Test File | Status |
|-----------|--------|
| `tests/cli/test_cli_provider_resolution.py` | ✅ 20 passed |
| `tests/cli/test_cli_status_bar.py` | ✅ 37 passed |
| `tests/cli/test_cli_background_status_indicator.py` | ✅ passed |
| `tests/agent/test_model_metadata.py` | ✅ 97 passed |
| `tests/hermes_cli/test_config.py` | ✅ 94 passed |
| `tests/hermes_cli/test_auth_commands.py` | ✅ passed |
| `tests/hermes_cli/test_auth_nous_provider.py` | ✅ passed |
| `tests/hermes_cli/test_runtime_provider_resolution.py` | ✅ 110 passed |

**Total: 600+ tests pass**

## Pre-existing Test Failure (Unrelated)

- `tests/cli/test_personality_none.py` — gateway personality feature, 5 failures

## Conventional Commits Applied

```
fix(cli): track configured vs routed model for Nous provider transparency
fix(agent): capture routed model from Nous API response
fix(gateway): emit configured/routed model in session.info
feat(ui-tui): display dual-model in status bar for Nous routing
test(ui-tui): update StatusRule tests for new props
```